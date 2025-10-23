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

# Tema / CSS neutral y elegante
st.markdown(
    """
    <style>
    .stApp { background-color: #f5f6f8; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    h1 { color: #2b2f36; margin-bottom: 0; }
    h3 { color: #6b6f76; margin-top: 0.25rem; font-weight: 400; }
    .card {
        background: #ffffff;
        border: 1px solid #e6e9ee;
        border-radius: 10px;
        padding: 12px;
        box-shadow: 0 2px 6px rgba(20,24,31,0.04);
    }
    div[data-testid="metric-container"] {
        background-color: transparent;
        padding: 0;
    }
    .small-muted { color: #7a8088; font-size:13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Cabecera
st.markdown(
    """
    <div style="text-align:center;">
        <h1>📊 Smaport IA</h1>
        <h3>Analista de negocio inteligente — Informe automático y dashboards</h3>
        <p class="small-muted">Diseñado para equipos que necesitan insights rápidos y accionables</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ==============================
# SIDEBAR - Configuración
# ==============================
st.sidebar.header("Configuración")
MODEL_NAME = "gpt-5"

st.sidebar.markdown("### Opciones de visualización")
top_n_productos = st.sidebar.slider("Top N productos", 3, 20, 5)
std_multiplier = st.sidebar.slider(
    "Umbral de anomalías (σ)", 1.5, 4.0, 2.0, 0.1, help="Número de desviaciones estándar para marcar anomalías"
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
    # Detect possible thousands separator and decimal coma heuristics
    # Remove spaces and non-numeric except . and -
    s = s.str.replace(r"[ ]", "", regex=True)
    # If there are commas and no dots, treat comma as decimal separator
    has_comma = s.str.contains(",").sum()
    has_dot = s.str.contains("\.").sum()
    if has_comma > 0 and has_dot == 0:
        s = s.str.replace(".", "", regex=False)  # remove dots (thousands)
        s = s.str.replace(",", ".", regex=False)  # comma -> dot
    else:
        s = s.str.replace(",", "", regex=False)  # remove commas (thousands)
    return pd.to_numeric(s, errors="coerce")


def format_value(val, currency=False):
    if pd.isna(val):
        return "N/A"
    if currency:
        return f"€ {val:,.2f}".replace(",", "_").replace(".", ",").replace("_", " ")
    return f"{val:,.0f}".replace(",", " ")


# ==============================
# CARGA DE API KEY (desde ENV / GITHUB SECRETS)
# ==============================
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.sidebar.warning("⚠️ No se encontró OPENAI_API_KEY en variables de entorno. Añádela en GitHub Secrets o en el entorno de despliegue.")

# ==============================
# UPLOAD
# ==============================
st.markdown("---")
st.markdown("### 📂 Subir datos")
archivo = st.file_uploader("Sube un CSV o Excel (ventas, inventario, etc.)", type=["csv", "xlsx"])

if archivo:
    try:
        # intento lectura robusta
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

        # limpieza básica
        df = df.replace([float("inf"), float("-inf")], pd.NA).dropna(how="all")
        df.columns = df.columns.map(str).str.strip()
        df = df.loc[:, ~df.columns.str.contains("^Unnamed", na=False)]

        # detección de columnas
        date_col = find_column(df, ["fecha", "date", "día"])
        revenue_col = find_column(df, ["ingresos", "ventas", "facturado", "importe", "revenue"])
        cost_col = find_column(df, ["coste", "gasto", "costo", "cost"])
        product_col = find_column(df, ["producto", "product", "item", "concepto", "descripcion", "descripción"])
        units_col = find_column(df, ["unidades", "cantidad", "qty", "units"])

        # convertir tipos
        if revenue_col:
            df[revenue_col] = clean_numeric(df[revenue_col])
        if cost_col:
            df[cost_col] = clean_numeric(df[cost_col])
        if units_col:
            df[units_col] = clean_numeric(df[units_col]).astype("Int64", errors="ignore")
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=[date_col])

        # filtros interactivos
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
        # TABS: Resumen / Gráficos / Informe IA
        # ==============================
        tab1, tab2, tab3 = st.tabs(["📈 Resumen", "📊 Gráficos", "🤖 Informe IA"])

        # --- TAB 1: RESUMEN ---
        with tab1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📄 Vista previa de los datos (limpios)")
            st.dataframe(df.head(50), use_container_width=True)

            # KPI avanzados
            ingresos = df[revenue_col].sum() if revenue_col and revenue_col in df.columns else 0
            coste = df[cost_col].sum() if cost_col and cost_col in df.columns else 0
            beneficio = ingresos - coste
            margen = (beneficio / ingresos * 100) if ingresos else 0
            unidades = int(df[units_col].sum()) if units_col and units_col in df.columns else 0

            # indicadores adicionales
            media_ingresos = df[revenue_col].mean() if revenue_col else 0
            producto_top = None
            if product_col and revenue_col:
                s = df.groupby(product_col)[revenue_col].sum()
                if not s.empty:
                    producto_top = s.idxmax()
                else:
                    producto_top = "N/A"

            col1, col2, col3, col4 = st.columns([1.6, 1.6, 1, 1])
            col1.metric("💰 Ingresos totales", format_value(ingresos, True))
            col2.metric("📉 Costes totales", format_value(coste, True))
            col3.metric("📈 Margen (%)", f"{margen:.2f}%")
            col4.metric("📦 Unidades vendidas", format_value(unidades))

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Ingreso medio:** {format_value(media_ingresos, True)}")
            c2.markdown(f"**Producto más rentable:** {producto_top}")
            # Crecimiento periodo (si hay fechas)
            crecimiento = "N/A"
            if date_col and revenue_col and len(df) > 1:
                df_sorted = df.sort_values(date_col)
                first = df_sorted[revenue_col].iloc[0]
                last = df_sorted[revenue_col].iloc[-1]
                if first and first != 0:
                    crecimiento = f"{((last - first) / first * 100):.2f}%"
                else:
                    crecimiento = "N/A"
            c3.markdown(f"**Crecimiento (inicio→fin):** {crecimiento}")

            st.markdown("</div>", unsafe_allow_html=True)

        # --- TAB 2: GRAFICOS ---
        with tab2:
            st.subheader("📊 Gráficos interactivos")

            # Ingresos vs Costes (si existen ambas columnas)
            if date_col and revenue_col and cost_col and revenue_col in df.columns and cost_col in df.columns:
                st.markdown("**Evolución: Ingresos vs Costes**")
                comp = df[[date_col, revenue_col, cost_col]].dropna()
                comp = comp.set_index(date_col).resample("M").sum().reset_index()
                fig = px.line(comp, x=date_col, y=[revenue_col, cost_col],
                              labels={date_col: "Fecha", "value": "€", "variable": "Concepto"})
                st.plotly_chart(fig, use_container_width=True)

            # Top productos por ingresos
            if product_col and revenue_col:
                st.markdown(f"**Top {top_n_productos} productos por ingresos**")
                top_prod = df.groupby(product_col)[revenue_col].sum().sort_values(ascending=False).head(top_n_productos)
                fig2 = px.bar(top_prod.reset_index(), x=product_col, y=revenue_col,
                              labels={revenue_col: "Ingresos", product_col: "Producto"})
                st.plotly_chart(fig2, use_container_width=True)

            # Evolución de ingresos (resample dinámico)
            if date_col and revenue_col:
                st.markdown("**Evolución de ingresos (resample dinámico)**")
                time_range = df[date_col].max() - df[date_col].min()
                if time_range.days < 90:
                    rule = "D"
                elif time_range.days < 365 * 2:
                    rule = "M"
                else:
                    rule = "Q"
                temp = df.set_index(date_col)[revenue_col].resample(rule).sum().fillna(0)
                st.line_chart(temp)

            # Anomalías
            if revenue_col:
                datos = df[revenue_col].dropna()
                if len(datos) > 2:
                    mean, std = datos.mean(), datos.std()
                    up = mean + std_multiplier * std
                    down = mean - std_multiplier * std
                    outliers = df[(df[revenue_col] > up) | (df[revenue_col] < down)]
                    if not outliers.empty:
                        st.markdown("**📛 Posibles anomalías**")
                        st.dataframe(outliers[[date_col, product_col, revenue_col]].head(20))

        # --- TAB 3: INFORME IA ---
        with tab3:
            st.subheader("🤖 Generar informe con IA")
            st.markdown("El informe se generará a partir del resumen estadístico y una muestra de datos. (Se requiere clave de OpenAI)")

            if api_key:
                if st.button("🧾 Generar informe (GPT-5)"):
                    try:
                        client = OpenAI(api_key=api_key)
                        resumen = df.describe(include="all").to_string()
                        muestra = df.head(50).to_string()

                        prompt = textwrap.dedent(
                            f"""
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
                            """
                        )

                        with st.spinner("Analizando con GPT-5..."):
                            response = client.chat.completions.create(
                                model=MODEL_NAME,
                                messages=[{"role": "user", "content": prompt}],
                            )
                            analysis = response.choices[0].message.content

                        st.success("✅ Informe generado")
                        st.markdown(analysis)

                        # Botón descarga
                        st.download_button(
                            "📥 Descargar informe (TXT)",
                            data=analysis.encode("utf-8"),
                            file_name="informe_smaport_ia.txt",
                            mime="text/plain",
                        )

                    except Exception as e:
                        st.error(f"Error al conectar con OpenAI: {e}")
            else:
                st.info("No hay clave de OpenAI configurada. Añádela en las Secrets (OPENAI_API_KEY).")

        # FOOTER
        st.markdown(
            """
            <hr style="margin-top:30px; opacity:0.2;">
            <div style="text-align:center; color:#7a8088; font-size:13px;">
            Desarrollado por <strong>Smaport IA</strong> · 2025
            </div>
            """,
            unsafe_allow_html=True,
        )

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
