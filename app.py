import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from openai import OpenAI
import os
import io

# ==============================
# 📘 CONFIGURACIÓN DE LA APP
# ==============================
st.set_page_config(page_title="Smaport IA", page_icon="📊", layout="wide")
st.title("📊 Smaport IA — Analista de Negocio Inteligente")

# ==============================
# 🧭 SIDEBAR
# ==============================
st.sidebar.header("Configuración")
api_key = st.sidebar.text_input("🔑 Ingresa tu API Key de OpenAI", type="password")

# ==============================
# 📤 SUBIDA DE ARCHIVO
# ==============================
st.write("Sube tu archivo CSV o Excel con datos de ventas, gastos o inventario.")
archivo = st.file_uploader("Selecciona un archivo", type=["csv", "xlsx"])

if archivo:
    try:
        # Cargar datos según el tipo de archivo
        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo, engine="openpyxl")

        # ==============================
        # 🔧 LIMPIEZA DE DATOS
        # ==============================
        df = df.replace([float("inf"), float("-inf")], pd.NA)
        df = df.dropna(how="all", axis=1)  # elimina columnas completamente vacías
        df = df.dropna(how="all", axis=0)  # elimina filas vacías
        df.columns = df.columns.map(str)  # Convierte todos los nombres de columnas a texto
        df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]

        # ==============================
        # 👀 VISTA PREVIA
        # ==============================
        st.subheader("📄 Vista previa de los datos")
        st.dataframe(df.head(50))  # Solo muestra las primeras filas

        # ==============================
        # 📈 ANÁLISIS ESTADÍSTICO
        # ==============================
        st.subheader("📊 Resumen estadístico")
        try:
            numeric_df = df.apply(pd.to_numeric, errors='coerce')
            st.dataframe(numeric_df.describe())
        except Exception:
            st.info("⚠️ No se pudieron calcular estadísticas numéricas. Verifica que haya columnas numéricas.")

        # ==============================
        # 📉 GRÁFICO AUTOMÁTICO
        # ==============================
        if "Fecha" in df.columns and "Ingresos" in df.columns:
            try:
                st.subheader("📊 Evolución de ingresos")
                df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
                df = df.dropna(subset=["Fecha"])
                df.sort_values("Fecha", inplace=True)
                fig, ax = plt.subplots()
                ax.plot(df["Fecha"], pd.to_numeric(df["Ingresos"], errors="coerce"), marker="o")
                ax.set_title("Ingresos por fecha")
                ax.set_xlabel("Fecha")
                ax.set_ylabel("Ingresos (€)")
                st.pyplot(fig)
            except Exception as e:
                st.warning(f"No se pudo generar el gráfico: {e}")

        # ==============================
        # 🤖 ANÁLISIS CON IA
        # ==============================
        if api_key and st.button("🤖 Generar análisis con IA"):
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            client = OpenAI(api_key=api_key)

            resumen_datos = df.head(50).to_string()
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
                    model="gpt-5",
                    messages=[{"role": "user", "content": prompt}]
                )
                analisis = respuesta.choices[0].message.content

            st.subheader("🧾 Informe de IA")
            st.write(analisis)

            # Descargar informe
            buffer = io.BytesIO()
            buffer.write(analisis.encode("utf-8"))
            st.download_button(
                label="📥 Descargar informe (TXT)",
                data=buffer,
                file_name="informe_smaport.txt",
                mime="text/plain"
            )

    except Exception as e:
        st.error(f"❌ Error al cargar o procesar el archivo: {e}")
