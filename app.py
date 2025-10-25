import os
import io
import textwrap

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
from openai import OpenAI

# ==============================
# CONFIGURACIÓN BÁSICA
# ==============================
st.set_page_config(
    page_title="Smaport IA",
    page_icon="📊",
    layout="wide",
)

# ==============================
# CSS GLOBAL MEJORADO
# ==============================
st.markdown("""
<style>
/* Fondo y contenedores */
.stApp { background-color: #f8f9fb; font-family: 'Segoe UI', sans-serif; }
.block-container { padding: 2rem 2rem; }

/* Encabezados */
h1 { color: #1a2b49; font-size: 2.5rem; font-weight: 700; }
h2 { color: #0078ff; font-weight: 600; }
h3 { color: #6b6f76; font-weight: 500; }

/* Tarjetas */
.card {
    background: #ffffff;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.08);
}
.metric-card {
    background: #0078ff;
    color: white;
    border-radius: 12px;
    padding: 15px;
    text-align:center;
    font-weight:600;
    box-shadow: 0 3px 10px rgba(0,0,0,0.1);
    margin-bottom: 12px;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-radius: 0 12px 12px 0;
    padding: 20px;
}

/* Botones */
.stButton>button {
    background-color: #0078ff;
    color: #ffffff;
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 20px;
    transition: 0.2s;
}
.stButton>button:hover {
    background-color: #005fcc;
    color: #ffffff;
}

/* Footer */
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ==============================
# CABECERA
# ==============================
st.markdown("""
<div style="text-align:center; padding:40px 0;">
  <h1>📊 Smaport IA Premium</h1>
  <h3>Tu asistente de negocio inteligente con dashboard visual</h3>
  <p style="color:#5b6470; font-size:16px; max-width:600px; margin:auto;">
    Analiza tus datos de ventas, inventario y gastos, y genera informes automáticos con IA y visualizaciones interactivas.
  </p>
</div>
""", unsafe_allow_html=True)

# ==============================
# SIDEBAR - Configuración
# ==============================
st.sidebar.header("⚙️ Panel de configuración")
MODEL_NAME = "gpt-5"

st.sidebar.markdown("Ajusta tus preferencias de análisis:")

top_n_productos = st.sidebar.slider("🔝 Mostrar top productos", 3, 20, 5)
std_multiplier = st.sidebar.slider(
    "📉 Sensibilidad de detección de anomalías",
    1.5, 4.0, 2.0, 0.1,
    help="Controla qué tan estricta es la detección de valores atípicos."
)

st.sidebar.markdown("---")
st.sidebar.markdown("<p style='text-align:center; color:gray;'>Smaport IA © 2025</p>", unsafe_allow_html=True)

# ==============================
# UTILIDADES
# ==============================
def find_column(df, possible_names):
    for col in df.columns:
        for name in possible_names:
            if name.lower() in str(col).lower():
                return col
    return None

def clean_numeric(series):
    s = series.astype(str).fillna("").str.strip()
    s = s.str.replace(r"[€$%]", "", regex=True)
    s = s.str.replace(r"[ ]", "", regex=True)
    has_comma = s.str.contains(",").sum()
    has_dot = s.str.contains("\.").sum()
    if has_comma > 0 and has_dot == 0:
        s = s.str.replace(".", "", regex=False)
        s = s.str.replace(",", ".", regex=False)
    else:
        s = s.str.replace(",", "", regex=False)
    return pd.to_numeric(s, errors="coerce")

def format_value(val, currency=False):
    if pd.isna(val):
        return "N/A"
    if currency:
        return f"€ {val:,.2f}".replace(",", "_").replace(".", ",").replace("_", " ")
    return f"{val:,.0f}".replace(",", " ")

# ==============================
# CARGA DE API KEY
# ==============================
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.sidebar.warning("⚠️ No se encontró OPENAI_API_KEY en variables de entorno. Añádela en GitHub Secrets o en el entorno de despliegue.")

with st.expander("ℹ️ Acerca de Smaport IA"):
    st.markdown("""
    **Smaport IA** es un asistente de análisis empresarial que transforma tus datos
    en insights automáticos mediante IA.

    - 📊 Analiza ventas, inventario o gastos.
    - 🤖 Genera informes ejecutivos con GPT-5.
    - 🧠 Detecta tendencias, anomalías y oportunidades.

    **Cómo usarlo:**
    1. Sube tu archivo CSV o Excel.
    2. Revisa los gráficos interactivos.
    3. Genera un informe con IA para tus decisiones.
    """)

# ==============================
# UPLOAD
# ==============================
st.markdown("---")
st.markdown("### 📂 Subir datos")
archivo = st.file_uploader("Sube un CSV o Excel (ventas, inventario, etc.)", type=["csv", "xlsx"])
if not archivo:
    if st.button("🧪 Cargar datos de ejemplo"):
        df = pd.DataFrame({
            "Fecha": pd.date_range("2024-01-01", periods=90),
            "Producto": ["A", "B", "C"] * 30,
            "Ventas": (pd.Series(range(90)) * 1.5 + 500).sample(90).values,
            "Coste": (pd.Series(range(90)) * 1.2 + 300).sample(90).values
        })
        st.success("Datos de ejemplo cargados correctamente.")

if archivo:
    try:
        if archivo.name.lower().endswith(".csv"):
            try:
                df = pd.read_csv(archivo, encoding="utf-8", engine="python")
            except Exception:
                archivo.seek(0)
                df = pd.read_csv(archivo, encoding="latin1", engine="python")
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        if df is None or df.empty:
            st.error("El archivo está vacío o no se pudo leer.")
            st.stop()

        df = df.replace([float("inf"), float("-inf")], pd.NA).dropna(how="all")
        df.columns = df.columns.map(str).str.strip()
        df = df.loc[:, ~df.columns.str.contains("^Unnamed", na=False)]

        date_col = find_column(df, ["fecha", "date", "día"])
        revenue_col = find_column(df, ["ingresos", "ventas", "facturado", "importe", "revenue"])
        cost_col = find_column(df, ["coste", "gasto", "costo", "cost"])
        product_col = find_column(df, ["producto", "product", "item", "concepto", "descripcion", "descripción"])
        units_col = find_column(df, ["unidades", "cantidad", "qty", "units"])

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
        # FILTROS
        # ==============================
        st.markdown("---")
        st.markdown("### 🔎 Filtros")
        filtro_prod = None
        if product_col:
            productos = df[product_col].astype(str).fillna("N/A").unique().tolist()
            productos = sorted(productos)
            filtro_prod = st.selectbox("Filtrar por producto (opcional)", options=["Todo"] + productos)
            if filtro_prod and filtro_prod != "Todo":
                df = df[df[product_col].astype(str) == filtro_prod]

        if date_col:
            min_date = df[date_col].min().date()
            max_date = df[date_col].max().date()
            inicio, fin = st.date_input("Rango de fechas (opcional)", value=(min_date, max_date))
            if inicio and fin:
                df = df[(df[date_col].dt.date >= inicio) & (df[date_col].dt.date <= fin)]

        # ==============================
        # MÉTRICAS PRINCIPALES
        # ==============================
        ingresos = df[revenue_col].sum() if revenue_col else 0
        coste = df[cost_col].sum() if cost_col else 0
        beneficio = ingresos - coste
        margen = (beneficio / ingresos * 100) if ingresos else 0
        unidades = int(df[units_col].sum()) if units_col else 0

        # Crecimiento
        crecimiento = 0
        if date_col and revenue_col and len(df) > 1:
            df_sorted = df.sort_values(date_col)
            first = df_sorted[revenue_col].iloc[0]
            last = df_sorted[revenue_col].iloc[-1]
            if first != 0:
                crecimiento = ((last - first) / first * 100)

        producto_top = df.groupby(product_col)[revenue_col].sum().idxmax() if product_col else "N/A"

        # ==============================
        # TABS
        # ==============================
        tab1, tab2, tab3 = st.tabs(["📈 Resumen", "📊 Gráficos", "🤖 Informe IA"])

        # --- TAB 1: RESUMEN ---
        with tab1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📄 Vista previa de los datos (limpios)")
            st.dataframe(df.head(50), use_container_width=True)

            # Métricas en tarjetas
            col1, col2, col3, col4 = st.columns(4)
            col1.markdown(f'<div class="metric-card">💰<br><b>{format_value(ingresos, True)}</b><br>Ingresos</div>', unsafe_allow_html=True)
            col2.markdown(f'<div class="metric-card">📉<br><b>{format_value(coste, True)}</b><br>Costes</div>', unsafe_allow_html=True)

            # Tarjeta de margen con color
            if margen > 30:
                color_margen = "#28a745"
            elif margen > 10:
                color_margen = "#ffc107"
            else:
                color_margen = "#dc3545"
            col3.markdown(f'<div class="metric-card" style="background-color:{color_margen};">{margen:.2f}%<br>Margen</div>', unsafe_allow_html=True)

            col4.markdown(f'<div class="metric-card">📦<br><b>{format_value(unidades)}</b><br>Unidades</div>', unsafe_allow_html=True)

            # Crecimiento con alertas
            if crecimiento < 0:
                st.warning(f"⚠️ Crecimiento negativo: {crecimiento:.2f}%")
            elif crecimiento < 5:
                st.info(f"Crecimiento bajo: {crecimiento:.2f}%")
            else:
                st.success(f"Crecimiento saludable: {crecimiento:.2f}%")

            st.markdown("</div>", unsafe_allow_html=True)

        # --- TAB 2: GRAFICOS ---
        with tab2:
            st.subheader("📊 Gráficos interactivos")
            if date_col and revenue_col and cost_col:
                comp = df[[date_col, revenue_col, cost_col]].dropna()
                comp = comp.set_index(date_col).resample("M").sum().reset_index()
                fig = px.line(comp, x=date_col, y=[revenue_col, cost_col],
                              labels={date_col: "Fecha", "value": "€", "variable": "Concepto"})
                st.plotly_chart(fig, use_container_width=True)

            if product_col and revenue_col:
                top_prod = df.groupby(product_col)[revenue_col].sum().sort_values(ascending=False).head(top_n_productos)
                fig2 = px.bar(top_prod.reset_index(), x=product_col, y=revenue_col,
                              labels={revenue_col: "Ingresos", product_col: "Producto"})
                st.plotly_chart(fig2, use_container_width=True)

            # Evolución resample dinámico
            if revenue_col and date_col:
                time_range = df[date_col].max() - df[date_col].min()
                rule = "D" if time_range.days < 90 else "M" if time_range.days < 730 else "Q"
                temp = df.set_index(date_col)[revenue_col].resample(rule).sum().fillna(0)
                st.line_chart(temp)

            # Posibles anomalías
            if revenue_col:
                datos = df[revenue_col].dropna()
                if len(datos) > 2:
                    mean, std = datos.mean(), datos.std()
                    up = mean + std_multiplier * std
                    down = mean - std_multiplier * std
                    outliers = df[(df[revenue_col] > up) | (df[revenue_col] < down)]
                    if not outliers.empty:
                        st.markdown("### 📛 Anomalías detectadas")
                        st.dataframe(outliers[[date_col, product_col, revenue_col]].head(20), use_container_width=True)

        # --- TAB 3: INFORME IA ---
        with tab3:
            st.subheader("🤖 Generar informe con IA")
            st.markdown("El informe se generará a partir del resumen estadístico y una muestra de datos.")
            if api_key:
                if st.button("🧾 Generar informe (GPT-5)"):
                    try:
                        client = OpenAI(api_key=api_key)
                        resumen = df.describe(include="all").to_string()
                        muestra = df.head(50).to_string()
                        prompt = textwrap.dedent(f"""
                        Eres un analista de datos experto. Analiza la siguiente información y responde con apartados claros:
                        1) Resumen ejecutivo (3-5 frases)
                        2) Tendencias y estacionalidades
                        3) Productos/periodos más y menos rentables
                        4) Riesgos o anomalías detectadas
                        5) 3 recomendaciones accionables y priorizadas
                        Resumen estadístico:
                        {resumen}
                        Muestra:
                        {muestra}
                        """)
                        with st.spinner("Analizando con GPT-5..."):
                            response = client.chat.completions.create(
                                model=MODEL_NAME,
                                messages=[{"role": "user", "content": prompt}],
                            )
                            analysis = response.choices[0].message.content
                        st.success("✅ Informe generado")
                        st.markdown(analysis)
                        st.download_button("📥 Descargar informe (TXT)", data=analysis.encode("utf-8"),
                                           file_name="informe_smaport_ia.txt", mime="text/plain")
                    except Exception as e:
                        st.error(f"Error al conectar con OpenAI: {e}")
            else:
                st.info("No hay clave de OpenAI configurada. Añádela en las Secrets (OPENAI_API_KEY).")

        # ==============================
        # FOOTER PREMIUM
        # ==============================
        st.markdown("""
        <hr style="margin-top:40px; opacity:0.2;">
        <div style="text-align:center; color:#7a8088; font-size:13px;">
        Desarrollado por <strong>Smaport IA Premium</strong> — Dashboard y análisis inteligente
        </div>
        """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")

