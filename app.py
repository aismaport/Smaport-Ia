import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import os
import textwrap

# ==============================
# ⚙️ CONFIGURACIÓN DE LA PÁGINA
# ==============================
st.set_page_config(
    page_title="Smaport IA",
    page_icon="📊",
    layout="wide"
)

# ====== ESTILO CORPORATIVO ======
st.markdown("""
    <style>
        body {
            background-color: #f4f6f9;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        .stApp {
            background-color: #f4f6f9 !important;
        }
        .main-header {
            background-color: #1E3A8A;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }
        .metric-card {
            background-color: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            text-align: center;
        }
        .stTabs [role="tablist"] {
            justify-content: center;
        }
        .css-1v0mbdj, .stDataFrame {
            background-color: white !important;
            border-radius: 10px;
            padding: 15px;
        }
        hr {
            border: 0;
            border-top: 1px solid #ddd;
            margin: 40px 0;
        }
    </style>
""", unsafe_allow_html=True)

# ==============================
# 🔐 CARGA DE API KEY
# ==============================
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.warning("⚠️ No se encontró la clave API. Define `OPENAI_API_KEY` en tus secretos o entorno.")

MODEL_NAME = "gpt-5"

# ==============================
# 🧭 ENCABEZADO
# ==============================
st.markdown("""
    <div class="main-header">
        <h1>📊 Smaport IA</h1>
        <h3>Analítica inteligente impulsada por IA</h3>
    </div>
""", unsafe_allow_html=True)

# ==============================
# 🧩 SIDEBAR
# ==============================
st.sidebar.header("⚙️ Configuración de análisis")
top_n_productos = st.sidebar.slider("Top N productos", 3, 20, 5)
std_multiplier = st.sidebar.slider(
    "Umbral de anomalías (σ)", 1.5, 4.0, 2.0, 0.1,
    help="Desviaciones estándar para marcar anomalías"
)
st.sidebar.markdown("---")
st.sidebar.markdown("<p style='text-align:center; color:gray;'>Smaport IA © 2025</p>", unsafe_allow_html=True)

# ==============================
# 🔧 FUNCIONES AUXILIARES
# ==============================
def find_column(df, names):
    for col in df.columns:
        if any(name.lower() in col.lower() for name in names):
            return col
    return None

def clean_numeric(series):
    return (
        series.astype(str)
        .str.replace(r"[€$,%]", "", regex=True)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
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
        # --- CARGA ROBUSTA ---
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

        df.columns = df.columns.map(str).str.strip()
        df = df.loc[:, ~df.columns.str.contains("^Unnamed", na=False)]

        # --- DETECCIÓN AUTOMÁTICA ---
        date_col = find_column(df, ["fecha", "date"])
        revenue_col = find_column(df, ["ingresos", "ventas", "importe", "facturado", "revenue"])
        cost_col = find_column(df, ["coste", "gasto", "costo", "cost"])
        product_col = find_column(df, ["producto", "concepto", "item", "descripción", "product"])
        units_col = find_column(df, ["unidades", "cantidad", "qty", "units"])

        # --- CONVERSIÓN ---
        if revenue_col: df[revenue_col] = clean_numeric(df[revenue_col])
        if cost_col: df[cost_col] = clean_numeric(df[cost_col])
        if units_col: df[units_col] = clean_numeric(df[units_col])
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=[date_col])

        # ==============================
        # 🧩 PESTAÑAS
        # ==============================
        tab1, tab2, tab3 = st.tabs(["📈 Resumen", "📊 Gráficos", "🤖 Informe IA"])

        # --- TAB 1: RESUMEN ---
        with tab1:
            st.subheader("📄 Vista previa de los datos")
            st.dataframe(df.head(40))

            ingresos = df[revenue_col].sum() if revenue_col else 0
            coste = df[cost_col].sum() if cost_col else 0
            beneficio = ingresos - coste
            margen = (beneficio / ingresos * 100) if ingresos else 0
            unidades = int(df[units_col].sum()) if units_col else 0

            st.markdown("### 💼 Resumen Ejecutivo")
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Ingresos", format_value(ingresos, True))
            with c2: st.metric("Costes", format_value(coste, True))
            with c3: st.metric("Margen (%)", f"{margen:.2f}%")
            with c4: st.metric("Unidades", format_value(unidades))

            if date_col:
                st.info(f"**Periodo analizado:** {df[date_col].min().date()} → {df[date_col].max().date()}")

        # --- TAB 2: GRÁFICOS ---
        with tab2:
            st.subheader("📊 Visualizaciones interactivas")

            if product_col and revenue_col:
                st.markdown("#### 🏆 Top productos por ingresos")
                top_prod = (
                    df.groupby(product_col)[revenue_col]
                    .sum()
                    .sort_values(ascending=False)
                    .head(top_n_productos)
                )
                fig = px.bar(top_prod, x=top_prod.index, y=top_prod.values, text_auto=True,
                             color_discrete_sequence=["#1E3A8A"])
                fig.update_layout(xaxis_title="", yaxis_title="Ingresos (€)", template="simple_white")
                st.plotly_chart(fig, use_container_width=True)

            if date_col and revenue_col:
                st.markdown("#### 📅 Evolución de ingresos")
                df_temp = df[[date_col, revenue_col]].dropna().set_index(date_col).resample("M").sum()
                fig_line = px.line(df_temp, x=df_temp.index, y=revenue_col, markers=True,
                                   color_discrete_sequence=["#2563EB"])
                fig_line.update_layout(template="simple_white", yaxis_title="Ingresos (€)")
                st.plotly_chart(fig_line, use_container_width=True)

        # --- TAB 3: INFORME IA ---
        with tab3:
            st.subheader("🧠 Informe generado con GPT-5")

            if api_key and st.button("Generar informe con IA"):
                try:
                    client = OpenAI(api_key=api_key)
                    resumen = df.describe(include="all").to_string()
                    muestra = df.head(50).to_string()

                    prompt = textwrap.dedent(f"""
                    Eres un analista de datos senior. Analiza el siguiente conjunto de información:

                    - Resume tendencias y estacionalidades.
                    - Identifica productos o periodos más rentables.
                    - Detecta riesgos o anomalías en ventas o costes.
                    - Propón mejoras basadas en datos.

                    Resumen estadístico:
                    {resumen}

                    Muestra de datos:
                    {muestra}
                    """)

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
        # 🪶 FOOTER
        # ==============================
        st.markdown("""
            <hr>
            <p style='text-align:center; color:gray; font-size:13px;'>
            Desarrollado por <strong style='color:#1E3A8A;'>Smaport IA</strong> · 2025
            </p>
        """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
