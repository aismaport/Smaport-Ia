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
        # 📊 RESUMEN ESTADÍSTICO (MEJORADO Y ROBUSTO)
        # ==============================
        st.subheader("📊 Resumen estadístico")

        try:
            # Garantizar que df existe y es DataFrame
            if not isinstance(df, pd.DataFrame):
                df = pd.DataFrame(df)

            # Crear copia de trabajo
            df_clean = df.copy()

            # --- DEBUG: mostrar tipos detectados (útil si algo falla)
            st.write("🧩 Tipos detectados (antes de limpiar):")
            st.write(df_clean.dtypes)

            # Asegurar que todos los nombres de columnas sean strings (evita problemas con '~' y .str)
            df_clean.columns = df_clean.columns.map(lambda c: "" if pd.isna(c) else str(c))

            # Convertir todo a str para limpiar caracteres no numéricos
            df_str = df_clean.astype(str)

            # Reemplazar comas decimales por punto y eliminar símbolos no numéricos (excepto '-' y '.')
            # Hacemos esto por columna para evitar avisos de pandas
            for col in df_str.columns.tolist():
                # Reemplazo: coma -> punto, luego eliminar cualquier cosa que no sea dígito, punto o guion
                df_str[col] = (
                    df_str[col]
                    .str.replace(",", ".", regex=False)
                    .str.replace(r"[^0-9.\-]", "", regex=True)
                    .replace("", pd.NA)  # cadenas vacías vuelven a NA
                )

            # Intentar convertir a numérico (coerce convierte lo que no pueda a NaN)
            numeric_df = df_str.apply(pd.to_numeric, errors="coerce")

            # Seleccionar sólo columnas numéricas detectadas
            numeric_cols = numeric_df.select_dtypes(include="number").columns.tolist()

            if len(numeric_cols) == 0:
                st.warning("⚠️ No se encontraron columnas numéricas para analizar.")
            else:
                # Mostrar tipos después de la limpieza (útil para depuración)
                st.write("🧩 Tipos detectados (después de limpiar):")
                st.write(numeric_df[numeric_cols].dtypes)

                # Mostrar resumen estadístico transpuesto (más legible)
                st.dataframe(numeric_df[numeric_cols].describe().T)

        except Exception as e:
            st.error(f"⚠️ No se pudo generar el resumen estadístico: {e}")
            # Mostrar info adicional para depurar
            st.exception(e)

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
