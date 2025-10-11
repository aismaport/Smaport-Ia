import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from openai import OpenAI
import io
# Configuración de la página
st.set_page_config(page_title="Smaport IA", page_icon="📊", layout="wide")
st.title("📊 Smaport IA — Analista de Negocio Inteligente")
# Sidebar
st.sidebar.header("Configuración")
api_key = st.sidebar.text_input("🔑 Ingresa tu API Key de OpenAI", type="password")

# Subida de archivo
st.write("Sube tu archivo CSV o Excel con datos de ventas, gastos o inventario.")
archivo = st.file_uploader("Selecciona un archivo", type=["csv", "xlsx"])

if archivo:
    try:
        # Cargar datos con soporte para Excel moderno
        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        # 🔧 Correcciones para evitar errores en Streamlit
        df = df.fillna("")       # Reemplaza valores vacíos o NaN
        df = df.astype(str)      # Convierte todo a texto compatible con JSON
        df = df.dropna(how="all")  # Elimina filas totalmente vacías

        st.subheader("📄 Vista previa de los datos")
        st.dataframe(df.head())

        # Análisis básico
        st.subheader("📈 Resumen estadístico")
        st.dataframe(df.describe(include='all'))

    except Exception as e:
        st.error(f"❌ Error al cargar el archivo: {e}")

    # Gráfico automático
    if "Fecha" in df.columns and "Ingresos" in df.columns:
        st.subheader("📊 Evolución de ingresos")
        df["Fecha"] = pd.to_datetime(df["Fecha"])
        df.sort_values("Fecha", inplace=True)
        fig, ax = plt.subplots()
        ax.plot(df["Fecha"], df["Ingresos"], marker="o")
        ax.set_title("Ingresos por fecha")
        ax.set_xlabel("Fecha")
        ax.set_ylabel("Ingresos (€)")
        st.pyplot(fig)

    # IA para resumen
    if api_key and st.button("🤖 Generar análisis con IA"):
        client = OpenAI(api_key=api_key)

        resumen_datos = df.describe().to_string()
        prompt = f"""
        Analiza los siguientes datos de negocio y genera un resumen ejecutivo profesional:
        - Describe las principales tendencias.
        - Identifica los productos o periodos más rentables.
        - Sugiere 3 recomendaciones para mejorar las ventas.

        Datos:
        {resumen_datos}
        """

        with st.spinner("Generando informe con IA..."):
            respuesta = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            analisis = respuesta.choices[0].message.content

        st.subheader("🧾 Informe de IA")
        st.write(analisis)

        # Descargar informe en texto
        buffer = io.BytesIO()
        buffer.write(analisis.encode("utf-8"))
        st.download_button(
            label="📥 Descargar informe (TXT)",
            data=buffer,
            file_name="informe_smaport.txt",
            mime="text/plain"
        )
