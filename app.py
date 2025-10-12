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
        # 📊 RESUMEN EJECUTIVO DE NEGOCIO (INTELIGENTE)
        # ==============================
        st.subheader("📊 Resumen ejecutivo del negocio")

        try:
            resumen = {}

            # --- Información general ---
            resumen["Total de registros"] = len(df)

            if "Fecha" in df.columns:
                df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
                resumen["Periodo analizado"] = f"{df['Fecha'].min().date()} → {df['Fecha'].max().date()}"

            if "Producto" in df.columns:
                resumen["Productos únicos"] = df["Producto"].nunique()

            # --- Indicadores financieros ---
            # FIX: Comprobar si las columnas existen antes de intentar usarlas.
            if "Ingresos" in df.columns:
                ingresos = pd.to_numeric(df["Ingresos"], errors="coerce").sum()
            else:
                ingresos = 0

            if "Coste" in df.columns:
                coste = pd.to_numeric(df["Coste"], errors="coerce").sum()
            else:
                coste = 0

            beneficio = ingresos - coste
            margen = (beneficio / ingresos * 100) if ingresos > 0 else 0

            resumen["💰 Ingresos totales (€)"] = round(ingresos, 2)
            resumen["📉 Coste total (€)"] = round(coste, 2)
            resumen["🧮 Beneficio total (€)"] = round(beneficio, 2)
            resumen["📊 Margen medio (%)"] = round(margen, 2)

            if "Unidades vendidas" in df.columns:
                unidades = pd.to_numeric(df["Unidades vendidas"], errors="coerce").sum()
                resumen["📦 Total unidades vendidas"] = int(unidades)

            # Mostrar indicadores en formato tabla
            st.table(pd.DataFrame(resumen.items(), columns=["Indicador", "Valor"]))

            # ==============================
            # 🏆 TOP PRODUCTOS
            # ==============================
            if {"Producto", "Ingresos"} <= set(df.columns):
                st.subheader("🏆 Top productos más rentables")
                top_prod = (
                    df.groupby("Producto")["Ingresos"]
                    .sum()
                    .sort_values(ascending=False)
                    .head(5)
                )
                st.bar_chart(top_prod)

            # ==============================
            # 📅 ANÁLISIS TEMPORAL
            # ==============================
            if "Fecha" in df.columns and "Ingresos" in df.columns:
                st.subheader("⏳ Tendencia de ingresos")
                df_temp = df.copy()
                df_temp["Fecha"] = pd.to_datetime(df_temp["Fecha"], errors="coerce")
                df_temp = df_temp.dropna(subset=["Fecha"])
                # FIX: Asegurarse de que el índice es correcto para el gráfico de líneas
                df_temp_grouped = df_temp.groupby(df_temp['Fecha'].dt.to_period('D'))['Ingresos'].sum()
                st.line_chart(df_temp_grouped)


            # ==============================
            # ⚠️ DETECCIÓN DE ANOMALÍAS
            # ==============================
            if "Ingresos" in df.columns:
                ingresos_num = pd.to_numeric(df["Ingresos"], errors="coerce").dropna()
                if not ingresos_num.empty:
                    mean = ingresos_num.mean()
                    std = ingresos_num.std()
                    umbral_superior = mean + 2 * std
                    umbral_inferior = mean - 2 * std
                    outliers = df[(ingresos_num > umbral_superior) | (ingresos_num < umbral_inferior)]

                    if not outliers.empty:
                        st.subheader("⚠️ Posibles anomalías detectadas en ingresos")
                        columnas_a_mostrar = [col for col in ["Fecha", "Producto", "Ingresos"] if col in df.columns]
                        st.dataframe(outliers[columnas_a_mostrar])

        except Exception as e:
            st.error(f"⚠️ No se pudo generar el resumen ejecutivo: {e}")
            st.exception(e)
            
        # ==============================
        # 🤖 ANÁLISIS CON IA
        # ==============================
        if api_key and st.button("🤖 Generar análisis con IA"):
            try:
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
                    # NOTA: "gpt-5" no es un modelo válido actualmente. Se usará gpt-3.5-turbo.
                    respuesta = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    analisis = respuesta.choices[0].message.content

                st.subheader("🧾 Informe de IA")
                st.markdown(analisis)

                # Descargar informe
                buffer = io.BytesIO(analisis.encode("utf-8"))
                st.download_button(
                    label="📥 Descargar informe (TXT)",
                    data=buffer,
                    file_name="informe_smaport.txt",
                    mime="text/plain"
                )
            except Exception as e:
                st.error(f"❌ Error al conectar con la API de OpenAI: {e}")


    except Exception as e:
        st.error(f"❌ Error al cargar o procesar el archivo: {e}")
