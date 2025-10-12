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
#  HELPER FUNCTION
# ==============================
def find_column(df_columns, potential_names):
    """Busca una columna en el dataframe ignorando mayúsculas/minúsculas."""
    for name in potential_names:
        for col in df_columns:
            if name.lower() == col.lower():
                return col
    return None

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
        df = df.dropna(how="all", axis=1)
        df = df.dropna(how="all", axis=0)
        df.columns = df.columns.map(str)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]

        # ==============================
        # 👀 VISTA PREVIA
        # ==============================
        st.subheader("📄 Vista previa de los datos")
        st.dataframe(df.head(50))

        # ==============================
        # 🔎 DETECCIÓN DINÁMICA DE COLUMNAS
        # ==============================
        date_col = find_column(df.columns, ["Fecha", "Date", "Día"])
        revenue_col = find_column(df.columns, ["Ingresos", "Ventas", "Revenue", "Ingreso", "Facturado"])
        cost_col = find_column(df.columns, ["Coste", "Costes", "Gastos", "Costo"])
        product_col = find_column(df.columns, ["Producto", "Product", "Concepto", "Item", "Descripción"])
        units_col = find_column(df.columns, ["Unidades vendidas", "Unidades", "Cantidad", "Qty"])

        # ==============================
        # 📊 RESUMEN EJECUTIVO DE NEGOCIO (INTELIGENTE)
        # ==============================
        st.subheader("📊 Resumen ejecutivo del negocio")

        try:
            resumen = {"Total de registros": len(df)}

            if date_col:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
                resumen["Periodo analizado"] = f"{df[date_col].min().date()} → {df[date_col].max().date()}"

            if product_col:
                resumen[f"{product_col.capitalize()}s únicos"] = df[product_col].nunique()

            # --- Indicadores financieros ---
            ingresos = pd.to_numeric(df[revenue_col], errors="coerce").sum() if revenue_col else 0
            coste = pd.to_numeric(df[cost_col], errors="coerce").sum() if cost_col else 0
            
            beneficio = ingresos - coste
            margen = (beneficio / ingresos * 100) if ingresos > 0 else 0

            resumen["💰 Ingresos totales (€)"] = round(ingresos, 2)
            resumen["📉 Coste/Gasto total (€)"] = round(coste, 2)
            resumen["🧮 Beneficio total (€)"] = round(beneficio, 2)
            resumen["📊 Margen medio (%)"] = round(margen, 2)

            if units_col:
                unidades = pd.to_numeric(df[units_col], errors="coerce").sum()
                resumen["📦 Total unidades vendidas"] = int(unidades)

            st.table(pd.DataFrame(resumen.items(), columns=["Indicador", "Valor"]))

            # ==============================
            # 🏆 TOP PRODUCTOS
            # ==============================
            if product_col and revenue_col:
                st.subheader(f"🏆 Top {product_col.capitalize()}s más rentables")
                top_prod = (
                    df.groupby(product_col)[revenue_col]
                    .sum()
                    .sort_values(ascending=False)
                    .head(5)
                )
                st.bar_chart(top_prod)

            # ==============================
            # 📅 ANÁLISIS TEMPORAL
            # ==============================
            if date_col and revenue_col:
                st.subheader(f"⏳ Tendencia de {revenue_col.lower()}")
                df_temp = df.copy()
                df_temp[date_col] = pd.to_datetime(df_temp[date_col], errors="coerce")
                df_temp = df_temp.dropna(subset=[date_col, revenue_col])
                df_temp_grouped = df_temp.set_index(date_col).resample('D')[revenue_col].sum()
                st.line_chart(df_temp_grouped)

            # ==============================
            # ⚠️ DETECCIÓN DE ANOMALÍAS
            # ==============================
            col_anomalias = revenue_col if revenue_col else cost_col
            if col_anomalias:
                datos_num = pd.to_numeric(df[col_anomalias], errors="coerce").dropna()
                if not datos_num.empty and len(datos_num) > 1:
                    mean = datos_num.mean()
                    std = datos_num.std()
                    umbral_superior = mean + 2 * std
                    umbral_inferior = mean - 2 * std
                    outliers = df[(datos_num > umbral_superior) | (datos_num < umbral_inferior)]

                    if not outliers.empty:
                        st.subheader(f"⚠️ Posibles anomalías detectadas en {col_anomalias.lower()}")
                        columnas_a_mostrar = [c for c in [date_col, product_col, col_anomalias] if c]
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
                - Identifica los productos, conceptos o periodos más rentables.
                - Sugiere 3 recomendaciones clave para mejorar el negocio.

                Datos:
                {resumen_datos}
                """
                with st.spinner("Generando informe con IA..."):
                    respuesta = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    analisis = respuesta.choices[0].message.content
                st.subheader("🧾 Informe de IA")
                st.markdown(analisis)
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
