import os
import io
import textwrap

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI

# ==============================
# CONFIGURACIÓN BÁSICA
# ==============================
st.set_page_config(
    page_title="Smaport IA — Dashboard Premium",
    page_icon="📊",
    layout="wide",
)

# ==============================
# CSS PREMIUM
# ==============================
st.markdown("""
<style>
.stApp { background-color: #f4f6f9; font-family: 'Segoe UI', sans-serif; }
.block-container { padding: 2rem 2rem; }
h1 { color: #1a2b49; font-size:2.8rem; font-weight:700; }
h2 { color: #0078ff; font-weight:600; }
h3 { color: #6b6f76; font-weight:500; }
.card {
    background: #ffffff;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.08);
}
.metric-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 15px;
    text-align:center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.stButton>button {
    background-color: #0078ff;
    color: #ffffff;
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 20px;
    transition: 0.2s;
}
.stButton>button:hover { background-color: #005fcc; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ==============================
# PORTADA
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
# EXPANDER GUIA
# ==============================
with st.expander("🧭 Cómo funciona Smaport IA Premium"):
    st.markdown("""
    1️⃣ **Sube tus datos** (CSV o Excel con ventas, inventario o gastos).  
    2️⃣ **Filtra y explora** tus métricas clave y gráficos interactivos.  
    3️⃣ **Genera informes IA** con recomendaciones accionables.  
    4️⃣ **Descarga o comparte** tu análisis profesional.
    """)

# ==============================
# SIDEBAR
# ==============================
st.sidebar.header("⚙️ Configuración de análisis")
MODEL_NAME = "gpt-5"
top_n_productos = st.sidebar.slider("🔝 Top productos", 3, 20, 5)
std_multiplier = st.sidebar.slider("📉 Umbral de anomalías", 1.5, 4.0, 2.0, 0.1)
st.sidebar.markdown("---")
st.sidebar.markdown("<p style='text-align:center; color:gray;'>Smaport IA © 2025</p>", unsafe_allow_html=True)

# ==============================
# FUNCIONES
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
# SUBIDA DE DATOS
# ==============================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 📂 Subir tus datos")
archivo = st.file_uploader("CSV o Excel", type=["csv", "xlsx"])
st.markdown('</div>', unsafe_allow_html=True)

if not archivo:
    if st.button("🧪 Cargar datos de ejemplo"):
        df = pd.DataFrame({
            "Fecha": pd.date_range("2024-01-01", periods=90),
            "Producto": ["A", "B", "C"] * 30,
            "Ventas": (pd.Series(range(90)) * 1.5 + 500).sample(90).values,
            "Coste": (pd.Series(range(90)) * 1.2 + 300).sample(90).values
        })
        st.success("Datos de ejemplo cargados correctamente.")

# ==============================
# PROCESAMIENTO DE DATOS
# ==============================
if archivo or 'df' in locals():
    try:
        if archivo:
            if archivo.name.lower().endswith(".csv"):
                df = pd.read_csv(archivo, encoding="utf-8", engine="python")
            else:
                df = pd.read_excel(archivo, engine="openpyxl")
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
    except Exception as e:
        st.error(f"❌ Error procesando el archivo: {e}")
        st.stop()

    # ==============================
    # FILTROS
    # ==============================
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🔎 Filtros")
    filtro_prod = None
    if product_col:
        productos = df[product_col].astype(str).fillna("N/A").unique().tolist()
        productos = sorted(productos)
        filtro_prod = st.selectbox("Filtrar por producto (opcional)", options=["Todo"] + productos)
        if filtro_prod != "Todo":
            df = df[df[product_col].astype(str) == filtro_prod]
    if date_col:
        min_date = df[date_col].min().date()
        max_date = df[date_col].max().date()
        inicio, fin = st.date_input("Rango de fechas (opcional)", value=(min_date, max_date))
        df = df[(df[date_col].dt.date >= inicio) & (df[date_col].dt.date <= fin)]
    st.markdown('</div>', unsafe_allow_html=True)

    # ==============================
    # DASHBOARD DE MÉTRICAS PREMIUM
    # ==============================
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("💡 Métricas clave")
    ingresos = df[revenue_col].sum() if revenue_col else 0
    coste = df[cost_col].sum() if cost_col else 0
    beneficio = ingresos - coste
    margen = (beneficio / ingresos * 100) if ingresos else 0
    unidades = int(df[units_col].sum()) if units_col else 0
    df_sorted = df.sort_values(date_col) if date_col else df
    crecimiento = ((df_sorted[revenue_col].iloc[-1]-df_sorted[revenue_col].iloc[0])/df_sorted[revenue_col].iloc[0]*100) if revenue_col else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="metric-card">💰<br><b>{format_value(ingresos, True)}</b><br>Ingresos totales</div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card">📉<br><b>{format_value(coste, True)}</b><br>Costes totales</div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card">📈<br><b>{margen:.2f}%</b><br>Margen</div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card">📦<br><b>{format_value(unidades)}</b><br>Unidades</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ==============================
    # TABS DE GRAFICOS E INFORME
    # ==============================
    tab1, tab2, tab3 = st.tabs(["📊 Gráficos", "📈 Evolución", "🤖 Informe IA"])

    # --- TAB 1: GRAFICOS ---
    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Top productos por ingresos")
        if product_col and revenue_col:
            top_prod = df.groupby(product_col)[revenue_col].sum().sort_values(ascending=False).head(top_n_productos)
            fig = px.bar(top_prod.reset_index(), x=product_col, y=revenue_col,
                         labels={revenue_col: "Ingresos", product_col: "Producto"},
                         color=top_prod.values, color_continuous_scale="Blues")
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- TAB 2: EVOLUCIÓN ---
    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Evolución de ingresos y costes")
        if date_col and revenue_col and cost_col:
            temp = df.set_index(date_col)[[revenue_col, cost_col]].resample("W").sum()
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=temp.index, y=temp[revenue_col], mode='lines+markers', name='Ingresos', line=dict(color='#0078ff')))
            fig2.add_trace(go.Scatter(x=temp.index, y=temp[cost_col], mode='lines+markers', name='Costes', line=dict(color='#ff5a5f')))
            fig2.update_layout(legend=dict(y=0.99, x=0.01), hovermode="x unified")
            st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- TAB 3: INFORME IA ---
    with tab3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Generar informe con IA")
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            if st.button("🧾 Generar informe (GPT-5)"):
                try:
                    client = OpenAI(api_key=api_key)
                    resumen = df.describe(include="all").to_string()
                    muestra = df.head(50).to_string()
                    prompt = textwrap.dedent(f"""
                        Eres un analista de datos experto. Analiza la siguiente información de negocio y responde con apartados claros:

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
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================
# FOOTER PREMIUM
# ==============================
st.markdown("""
<hr style="margin-top:40px; opacity:0.2;">
<div style="text-align:center; color:#7a8088; font-size:13px;">
  Desarrollado por <strong>Smaport IA Premium</strong> — Dashboard y análisis inteligente
</div>
""", unsafe_allow_html=True)

