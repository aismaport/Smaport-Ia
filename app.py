import os
import io
import textwrap

import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI

# ==============================
# CONFIGURACIÓN BÁSICA
# ==============================
st.set_page_config(
    page_title="Smaport IA — Analítica Inteligente",
    page_icon="📊",
    layout="wide",
)

# ==============================
# CSS MODERNO
# ==============================
st.markdown("""
<style>
.stApp { background-color: #f8f9fb; font-family: 'Segoe UI', sans-serif; }
.block-container { padding: 2rem 2rem; }
h1 { color: #1a2b49; font-size:2.5rem; font-weight:700; }
h2 { color: #0078ff; font-weight:600; }
h3 { color: #6b6f76; font-weight:500; }
.card {
    background: #ffffff;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.08);
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
# PORTADA PRINCIPAL
# ==============================
st.markdown("""
<div style="text-align:center; padding:40px 0;">
  <h1>📊 Smaport IA</h1>
  <h3>Tu asistente inteligente de análisis de negocio</h3>
  <p style="color:#5b6470; font-size:16px; max-width:600px; margin:auto;">
    Convierte tus datos de ventas, inventario o gastos en <strong>informes automáticos</strong> con IA.
  </p>
  <div style="margin-top:20px;">
    <span style="font-size:18px;">⬇️ Comienza subiendo tus datos o prueba un ejemplo</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ==============================
# GUÍA RÁPIDA EXPANDER
# ==============================
with st.expander("🧭 Cómo funciona Smaport IA"):
    st.markdown("""
    1️⃣ **Sube tus datos** (CSV o Excel con ventas, inventario o gastos).  
    2️⃣ **Explora el resumen y gráficos automáticos**.  
    3️⃣ **Genera tu informe IA** con un clic.  
    4️⃣ **Descarga o comparte** tu análisis profesional.
    """)

# ==============================
# SIDEBAR CONFIG
# ==============================
st.sidebar.header("⚙️ Panel de configuración")
MODEL_NAME = "gpt-5"

st.sidebar.markdown("Ajusta tus preferencias de análisis:")
top_n_productos = st.sidebar.slider("🔝 Mostrar top productos", 3, 20, 5)
std_multiplier = st.sidebar.slider(
    "📉 Sensibilidad de detección de anomalías", 1.5, 4.0, 2.0, 0.1,
    help="Controla qué tan estricta es la detección de valores atípicos."
)
st.sidebar.markdown("---")
st.sidebar.markdown("<p style='text-align:center; color:gray;'>Smaport IA © 2025</p>", unsafe_allow_html=True)

# ==============================
# UPLOAD DE DATOS
# ==============================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 📂 Subir tus datos")
archivo = st.file_uploader("Selecciona un archivo CSV o Excel", type=["csv", "xlsx"])
st.markdown('</div>', unsafe_allow_html=True)

# Botón de ejemplo si no hay archivo
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
# TAB PRINCIPAL
# ==============================
if archivo or 'df' in locals():
    if archivo:
        # Aquí iría tu lógica de carga y limpieza de datos
        # df = pd.read_csv(...) o pd.read_excel(...)
        pass

    tab1, tab2, tab3 = st.tabs(["📈 Resumen", "📊 Gráficos", "🤖 Informe IA"])

    # --- TAB 1: RESUMEN ---
    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📄 Vista previa de los datos")
        st.dataframe(df.head(50), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- TAB 2: GRAFICOS ---
    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📊 Gráficos interactivos")
        # Ejemplo de gráfico
        if "Ventas" in df.columns and "Producto" in df.columns:
            top_prod = df.groupby("Producto")["Ventas"].sum().sort_values(ascending=False).head(top_n_productos)
            fig = px.bar(top_prod.reset_index(), x="Producto", y="Ventas", labels={"Ventas":"Ingresos"})
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- TAB 3: INFORME IA ---
    with tab3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🤖 Generar informe con IA")
        st.markdown("El informe se generará a partir de los datos cargados.")
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================
# FOOTER
# ==============================
st.markdown("""
<hr style="margin-top:40px; opacity:0.2;">
<div style="text-align:center; color:#7a8088; font-size:13px;">
  Desarrollado por <strong>Smaport IA</strong> — IA aplicada al análisis empresarial
</div>
""", unsafe_allow_html=True)


