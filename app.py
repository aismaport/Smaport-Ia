import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
from openai import OpenAI
import io
import os

# ==============================
# 🔐 CARGA DE API KEY DESDE GITHUB SECRETS (variables de entorno)
# ==============================
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    st.warning("⚠️ No se encontró la clave API. Asegúrate de definir OPENAI_API_KEY como Secret en GitHub o en Streamlit Cloud.")

# ==============================
# 📘 CONFIGURACIÓN DE LA APP
# ==============================
st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color:#4A90E2;">📊 Smaport IA</h1>
        <h3 style="color:gray;">Analista de negocio inteligente impulsado por IA</h3>
    </div>
""", unsafe_allow_html=True)

# ==============================
# 🧭 SIDEBAR
# ==============================
st.sidebar.header("Configuración de análisis")

MODEL_NAME = "gpt-5"  

st.sidebar.write("Ajusta los parámetros antes de procesar los datos:")
st.sidebar.subheader("Opciones de visualización")
top_n_productos = st.sidebar.slider("Top N productos", 3, 20, 5)
std_multiplier = st.sidebar.slider(
    "Umbral de anomalías (σ)", 1.5, 4.0, 2.0, 0.1,
    help="Cuántas desviaciones estándar -> marcar anomalía"
)
st.sidebar.markdown("---")
st.sidebar.markdown("<p style='text-align:center; color:gray;'>Smaport IA © 2025</p>", unsafe_allow_html=True)
# ==============================
# 🔧 FUNCIONES AUXILIARES
# ==============================
def find_column(df, possible_names):
    for col in df.columns:
        if any(name.lower() in col.lower() for name in possible_names):
            return col
    return None

def clean_numeric(series):
    """Convierte texto con €, %, o comas a número."""
    return (
        series.astype(str)
        .str.replace(r"[€$,%]", "", regex=True)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
        .replace("", pd.NA)
        .pipe(pd.to_numeric, errors="coerce")
    )

def format_value(val, currency=False):
    if pd.isna(val):
        return "N/A"
    if currency:
        return f"€ {val:,.2f}".replace(",", "_").replace(".", ",").replace("_", " ")
    return f"{val:,.0f}".replace(",", " ")

# ==============================
# 📤 SUBIDA DE ARCHIVO
# ==============================
archivo = st.file_uploader("📂 Sube tu archivo CSV o Excel (ventas, inventario, etc.)", type=["csv", "xlsx"])

if archivo:
    try:
        # === CARGA ROBUSTA ===
        if archivo.name.endswith(".csv"):
            try:
                df = pd.read_csv(archivo, encoding="utf-8", sep=None, engine="python")
            except Exception:
                archivo.seek(0)
                df = pd.read_csv(archivo, encoding="latin1", sep=None, engine="python")
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        if df.empty:
            st.error("❌ El archivo está vacío o no contiene datos válidos.")
            st.stop()

        # === LIMPIEZA BÁSICA ===
        df = df.replace([float("inf"), float("-inf")], pd.NA).dropna(how="all")
        df.columns = df.columns.map(str).str.strip()
        df = df.loc[:, ~df.columns.str.contains("^Unnamed", na=False)]

        # === DETECCIÓN AUTOMÁTICA DE COLUMNAS ===
        date_col = find_column(df, ["fecha", "date"])
        revenue_col = find_column(df, ["ingresos", "ventas", "facturado", "importe", "revenue"])
        cost_col = find_column(df, ["coste", "gasto", "costo", "cost"])
        product_col = find_column(df, ["producto", "concepto", "item", "descripción", "product"])
        units_col = find_column(df, ["unidades", "cantidad", "qty", "units"])

        # === CONVERSIÓN DE TIPOS ===
        if revenue_col:
            df[revenue_col] = clean_numeric(df[revenue_col])
        if cost_col:
            df[cost_col] = clean_numeric(df[cost_col])
        if units_col:
            df[units_col] = clean_numeric(df[units_col]).astype("Int64", errors="ignore")
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=[date_col])

        # ==============================
        # 📊 INTERFAZ CON PESTAÑAS
        # ==============================
        tab1, tab2, tab3 = st.tabs(["📈 Resumen", "📊 Gráficos", "🤖 Informe IA"])

        # --- TAB 1: RESUMEN ---
        with tab1:
            st.subheader("📄 Vista previa de los datos (limpios)")
            st.dataframe(df.head(40))

            st.subheader("📊 Resumen ejecutivo")
            ingresos = df[revenue_col].sum() if revenue_col else 0
            coste = df[cost_col].sum() if cost_col else 0
            beneficio = ingresos - coste
            margen = (beneficio / ingresos * 100) if ingresos else 0
            unidades = int(df[units_col].sum()) if units_col else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💰 Ingresos", format_value(ingresos, True))
            col2.metric("📉 Costes", format_value(coste, True))
            col3.metric("📈 Margen (%)", f"{margen:.2f}%")
            col4.metric("📦 Unidades", format_value(unidades))

            if date_col:
                st.info(f"**Periodo analizado:** {df[date_col].min().date()} → {df[date_col].max().date()}")

        # --- TAB 2: GRÁFICOS ---
        with tab2:
            st.subheader("🏆 Top productos por ingresos")
            if product_col and revenue_col:
                top_prod = (
                    df.groupby(product_col)[revenue_col]
                    .sum()
                    .sort_values(ascending=False)
                    .head(top_n_productos)
                )
                st.bar_chart(top_prod)

            st.subheader("📈 Participación de ingresos")
            try:
                pie_df = (
                    df.groupby(product_col)[revenue_col]
                    .sum()
                    .sort_values(ascending=False)
                    .head(top_n_productos)
                ).reset_index()
                pie_df['porcentaje'] = pie_df[revenue_col] / pie_df[revenue_col].sum() * 100
                fig_pie = px.pie(pie_df, names=product_col, values=revenue_col,
                                 title=f"Top {top_n_productos} productos", hover_data={'porcentaje':':.2f'})
                st.plotly_chart(fig_pie, use_container_width=True)
            except Exception as e:
                st.warning(f"No se pudo generar el gráfico: {e}")

            if date_col and revenue_col:
                st.subheader("📅 Evolución de ingresos")
                df_temp = (
                df[[date_col, revenue_col]]
                    .dropna()
                    .set_index(date_col)
                    .resample("M")
                    .sum()
                )
                st.line_chart(df_temp)

        # ==============================
        # ⚠️ DETECCIÓN DE ANOMALÍAS
        # ==============================
        if revenue_col:
            data = df[revenue_col].dropna()
            if len(data) > 2:
                mean, std = data.mean(), data.std()
                outliers = df[(data > mean + std_multiplier * std) | (data < mean - std_multiplier * std)]
                if not outliers.empty:
                    st.subheader("⚠️ Anomalías detectadas")
                    cols_show = [c for c in [date_col, product_col, revenue_col] if c and c in outliers.columns]
                    st.dataframe(outliers[cols_show].head(50))

        # --- TAB 3: INFORME IA ---
        with tab3:
            st.subheader("🧾 Informe generado por IA (GPT-5)")
            if api_key and st.button("🤖 Generar informe con IA"):
                try:
                    client = OpenAI(api_key=api_key)
                    resumen = df.describe(include="all").to_string()
                    muestra = df.head(50).to_string()
                    prompt = f"""
                    Eres un analista de datos experto. Analiza la siguiente información de negocio:

                    - Detecta tendencias y estacionalidades.
                    - Identifica productos o periodos más rentables.
                    - Señala posibles riesgos o anomalías.
                    - Propón 3 recomendaciones concretas para mejorar ventas o eficiencia.

                    Resumen estadístico:
                    {resumen}

                    Muestra:
                    {muestra}
                    """
                    with st.spinner("Analizando con GPT-5..."):
                        response = client.chat.completions.create(
                            model=MODEL_NAME,
                            messages=[{"role": "user", "content": prompt}],
                        )
                        analysis = response.choices[0].message.content

                    st.success("✅ Informe generado con éxito")
                    st.markdown(analysis)
                except Exception as e:
                    st.error(f"❌ Error al conectar con OpenAI: {e}")

        # ==============================
        # 🪶 FOOTER — CRÉDITO DISCRETO
        # ==============================
        st.markdown(
            """
            <hr style="margin-top:40px; opacity:0.3;">
            <p style="text-align:center; color:gray; font-size:13px;">
            Desarrollado por <strong style="color:#4A90E2;">Smaport IA</strong> · 2025
            </p>
            """,
            unsafe_allow_html=True
