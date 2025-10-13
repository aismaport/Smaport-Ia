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

# Control de visualización (Mejora 3)
st.sidebar.markdown("---")
st.sidebar.subheader("Opciones de Visualización")
top_n_productos = st.sidebar.slider(
    "Mostrar Top N Productos/Items", 
    min_value=3, max_value=20, value=5, step=1
)
std_multiplier = st.sidebar.slider(
    "Umbral de Anomalías (Desviaciones Estándar)", 
    min_value=1.5, max_value=4.0, value=2.0, step=0.1,
    help="Define qué tan lejos de la media debe estar un punto para ser considerado una anomalía. (E.g., 2.0 es el 95% de los datos)."
)
MODEL_NAME = "gpt-4o" # Modelo de IA de última generación (Mejora 4)

# ==============================
#  HELPER FUNCTIONS
# ==============================
def find_column(df_columns, potential_names):
    """Busca una columna en el dataframe ignorando mayúsculas/minúsculas."""
    for name in potential_names:
        for col in df_columns:
            # Usamos strip().lower() para limpiar espacios y comparar
            if name.lower() == col.lower().strip():
                return col
    return None

def detect_header_row(file_stream, is_csv):
    """
    Intenta detectar la fila de encabezado real (índice 0-9) buscando la fila 
    con la mayor cantidad de celdas no vacías, probando distintas configuraciones.
    Devuelve el número de filas a saltar (skiprows).
    """
    import io
    file_stream.seek(0)
    
    # Configuraciones de lectura a probar para la detección. Priorizamos ';'
    if is_csv:
        configs = [
            {'sep': ';', 'encoding': 'latin1'},
            {'sep': ',', 'encoding': 'latin1'},
            {'sep': None, 'encoding': 'latin1'},
            {'sep': ';', 'encoding': 'utf-8'},
            {'sep': ',', 'encoding': 'utf-8'}
        ]
        read_func = lambda stream, **kwargs: pd.read_csv(stream, engine='python', on_bad_lines='skip', **kwargs)
    else:
        configs = [{'sep': None, 'encoding': None}] # Excel
        read_func = lambda stream, **kwargs: pd.read_excel(stream, engine='openpyxl', **kwargs)
        
    best_skiprows = 0
    max_valid_cols = 0
    
    for config in configs:
        try:
            file_stream.seek(0)
            temp_df = read_func(file_stream, header=None, nrows=20, encoding=config.get('encoding'), sep=config.get('sep'))

            for i in range(len(temp_df)):
                row_data = temp_df.iloc[i]
                # Criterio: Contamos cuántas celdas tienen contenido real
                valid_cols = row_data.apply(lambda x: pd.notna(x) and str(x).strip().lower() not in ('', 'nan', 'none', 'nan,')).sum()
                
                if valid_cols > max_valid_cols:
                    max_valid_cols = valid_cols
                    best_skiprows = i
        except Exception:
            continue

    file_stream.seek(0)
    return best_skiprows

def format_value(value, currency=False):
    """Formatea un valor a cadena con separadores de miles (espacio) y decimales (coma)."""
    if pd.isna(value) or value is None:
        return "N/A"

    val_rounded = round(value, 2)
    
    if currency:
        # Usamos :.2f para forzar 2 decimales y luego manejamos los separadores
        
        # 1. Obtenemos el formato americano con coma de miles y punto decimal
        # Usamos round(val_rounded) para evitar el error si el valor ya es float
        formatted = f"{val_rounded:,.2f}"
        
        # 2. Convertimos al formato europeo:
        # Reemplazamos el separador decimal (punto) por el temporal _TEMP_
        formatted = formatted.replace(".", "_TEMP_")
        # Reemplazamos el separador de miles (coma) por punto (o espacio, pero usaremos espacio)
        formatted = formatted.replace(",", " ")
        # Reemplazamos el separador decimal temporal por coma
        formatted = formatted.replace("_TEMP_", ",")
        
        return f"€ {formatted}"
    else:
        # Para valores no monetarios, solo formato de miles con espacio
        try:
            return f"{int(round(value)):,}".replace(",", " ")
        except (ValueError, TypeError):
            return f"{val_rounded:,.2f}".replace(",", "_TEMP_").replace(".", ",").replace("_TEMP_", " ")


def clean_numeric_column(series):
    """
    CORRECCIÓN: Limpia y convierte una Serie de Pandas a formato numérico (float), 
    manejando explícitamente el formato europeo (coma decimal y punto de miles).
    """
    if series.dtype != 'object':
        return pd.to_numeric(series, errors='coerce')

    series_str = series.astype(str).str.strip()
    
    # Paso 1: Eliminar símbolos de moneda y porcentaje (ej: €, $, %, £)
    cleaned_series = series_str.str.replace(r'[€$£%]', '', regex=True)
    
    # Paso 2: Detección y limpieza del formato numérico
    has_comma = cleaned_series.str.contains(',').sum()
    has_dot = cleaned_series.str.contains('\.').sum()
    
    # Heurística para formato Europeo: Si hay más comas que puntos, asumimos coma decimal.
    # O si solo hay comas (ej. 9800,00)
    is_european_format = (has_comma > 0) and (has_comma >= has_dot)
    
    if is_european_format:
        # 2a. Formato Europeo (ej: 1.000,50): 
        # 1. Eliminar puntos (separador de miles)
        # 2. Reemplazar la coma (separador decimal) por punto (estándar Python/Pandas)
        cleaned_series = cleaned_series.str.replace('.', '', regex=False)
        cleaned_series = cleaned_series.str.replace(',', '.', regex=False)
    else:
        # 2b. Formato Americano (ej: 1,000.50): 
        # 1. Eliminar comas (separador de miles).
        cleaned_series = cleaned_series.str.replace(',', '', regex=False)
        # El punto decimal ya está correcto.

    # Paso 3: Convertir a numérico
    return pd.to_numeric(cleaned_series, errors='coerce')


# ==============================
# 📤 SUBIDA DE ARCHIVO
# ==============================
st.write("Sube tu archivo CSV o Excel con datos de ventas, gastos o inventario.")
archivo = st.file_uploader("Selecciona un archivo", type=["csv", "xlsx"])

if archivo:
    # 1. Detección automática de la cabecera (skiprows)
    is_csv = archivo.name.endswith(".csv")
    
    # Calculamos el número de filas a saltar
    skip_rows_count = detect_header_row(archivo, is_csv=is_csv)
    
    if skip_rows_count > 0:
        st.info(f"✅ Cabecera detectada en la fila **{skip_rows_count + 1}**. Se saltarán **{skip_rows_count}** filas de metadatos.")
    else:
        st.info("✅ Cabecera detectada en la primera fila (1). No se saltarán filas.")

    try:
        # 2. Cargar datos usando el parámetro skiprows detectado
        read_success = False
        df = None
        
        if is_csv:
            # Lógica de carga robusta para CSV: Priorizamos ';' para formato europeo
            csv_configs = [
                (';', 'latin1'), (',', 'latin1'), 
                (';', 'utf-8'), (',', 'utf-8')
            ]
            
            for sep, enc in csv_configs:
                try:
                    archivo.seek(0)
                    # El argumento 'header=0' es importante después de skiprows
                    df = pd.read_csv(archivo, skiprows=skip_rows_count, encoding=enc, sep=sep, engine='python', header=0)
                    if not df.empty: # Aseguramos que la carga fue exitosa y no es solo metadatos
                        read_success = True
                        break
                except Exception:
                    continue
            
            if not read_success:
                raise Exception("No se pudo cargar el archivo CSV con los delimitadores o codificaciones comunes.")

        else:
            # Para Excel, la detección de skiprows suele ser más sencilla
            archivo.seek(0)
            df = pd.read_excel(archivo, engine="openpyxl", skiprows=skip_rows_count, header=0)
            read_success = True

        if df is None or df.empty:
            raise Exception("El archivo fue cargado, pero no contiene datos después de saltar las filas de metadatos.")

        # ==============================
        # 🔧 LIMPIEZA DE DATOS
        # ==============================
        df = df.replace([float("inf"), float("-inf")], pd.NA)
        df = df.dropna(how="all", axis=1)
        df = df.dropna(how="all", axis=0)
        # Limpiamos nombres de columnas (eliminamos espacios, € y el símbolo de la moneda en la columna)
        df.columns = df.columns.map(str).str.strip().str.replace(r'[^\w\s]', '', regex=True).str.strip()
        df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]

        # ==============================
        # 🔎 DETECCIÓN DINÁMICA DE COLUMNAS
        # ==============================
        date_col = find_column(df.columns, ["Fecha", "Date", "Día"])
        # Buscamos columnas sin el símbolo €/() que fue limpiado en el paso anterior
        revenue_col = find_column(df.columns, ["Ingresos", "Ventas", "Revenue", "Ingreso", "Facturado", "Importe"])
        cost_col = find_column(df.columns, ["Coste", "Costes", "Gastos", "Costo", "Gasto"])
        product_col = find_column(df.columns, ["Producto", "Product", "Concepto", "Item", "Descripción", "Detalle"])
        units_col = find_column(df.columns, ["Unidades vendidas", "Unidades", "Cantidad", "Qty"])

        # ==============================
        # 🧹 CONVERSIÓN DE TIPOS (Usando la función mejorada)
        # ==============================
        if revenue_col:
            df[revenue_col] = clean_numeric_column(df[revenue_col])
        if cost_col:
            df[cost_col] = clean_numeric_column(df[cost_col])
        if units_col:
            df[units_col] = clean_numeric_column(df[units_col]).astype('Int64', errors='ignore')
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True) # Añadido dayfirst=True para formato europeo DD/MM/AAAA
            df = df.dropna(subset=[date_col])

        # ==============================
        # 👀 VISTA PREVIA
        # ==============================
        st.subheader("📄 Vista previa de los datos limpios")
        st.dataframe(df)

        # ==============================
        # 📊 RESUMEN EJECUTIVO DE NEGOCIO (Mejora 7: Usando st.metric)
        # ==============================
        st.subheader("📊 Resumen ejecutivo del negocio")

        col1, col2, col3, col4, col5 = st.columns(5)
        
        try:
            # --- Cálculo de Indicadores ---
            ingresos = df[revenue_col].sum() if revenue_col and revenue_col in df.columns else 0
            coste = df[cost_col].sum() if cost_col and cost_col in df.columns else 0
            
            beneficio = ingresos - coste
            margen = (beneficio / ingresos * 100) if ingresos > 0 else 0
            
            # Formato de valores
            ingresos_str = format_value(ingresos, currency=True)
            beneficio_str = format_value(beneficio, currency=True)
            margen_str = f"{round(margen, 2):.2f}%"
            
            total_registros = format_value(len(df), currency=False)
            unidades_vendidas = format_value(df[units_col].sum(), currency=False) if units_col and units_col in df.columns else "N/A"
            
            # --- Despliegue de st.metric ---
            col1.metric("💰 Ingresos totales", ingresos_str)
            col2.metric("🧮 Beneficio total", beneficio_str)
            col3.metric("📈 Margen (%)", margen_str)
            col4.metric("Total Registros", total_registros)
            col5.metric("📦 Unidades Vendidas", unidades_vendidas)
            
            # Información de Periodo
            if date_col and not df[date_col].empty:
                min_date = df[date_col].min().date()
                max_date = df[date_col].max().date()
                st.info(f"**Periodo analizado:** Del **{min_date}** al **{max_date}**.")
            
            
            # ==============================
            # 🏆 TOP PRODUCTOS (Usando Top N configurable - Mejora 3)
            # ==============================
            if product_col and revenue_col:
                st.subheader(f"🏆 Top {top_n_productos} Productos/Servicios más rentables")
                top_prod = (
                    df.groupby(product_col)[revenue_col]
                    .sum()
                    .sort_values(ascending=False)
                    .head(top_n_productos)
                )
                st.bar_chart(top_prod)

            # ==============================
            # 📅 ANÁLISIS TEMPORAL (Mejora 2: Resampling dinámico)
            # ==============================
            if date_col and revenue_col and not df[date_col].empty:
                st.subheader(f"⏳ Tendencia de {revenue_col.lower()}")
                
                # Calcular el rango de tiempo
                time_range = df[date_col].max() - df[date_col].min()
                
                # Definir la granularidad (Mejora 2)
                if time_range.days < 90:
                    resample_rule = 'D'
                    resample_label = 'Diaria'
                elif time_range.days < 365 * 2:
                    resample_rule = 'M'
                    resample_label = 'Mensual'
                else:
                    resample_rule = 'Q'
                    resample_label = 'Trimestral'
                
                st.caption(f"Visualización: {resample_label}")
                
                df_temp = df.copy()
                df_temp = df_temp.dropna(subset=[date_col, revenue_col])
                df_temp_grouped = df_temp.set_index(date_col)[revenue_col].resample(resample_rule).sum().fillna(0)
                st.line_chart(df_temp_grouped)

            # ==============================
            # ⚠️ DETECCIÓN DE ANOMALÍAS (Mejora 3 y 5)
            # ==============================
            col_anomalias = revenue_col if revenue_col else cost_col
            if col_anomalias:
                datos_num = df[col_anomalias].dropna()
                if not datos_num.empty and len(datos_num) > 1:
                    mean = datos_num.mean()
                    std = datos_num.std()
                    
                    # Usar el multiplicador configurable (Mejora 3)
                    umbral_superior = mean + std_multiplier * std
                    umbral_inferior = mean - std_multiplier * std
                    
                    outliers_mask = (datos_num > umbral_superior) | (datos_num < umbral_inferior)
                    outliers_index = datos_num[outliers_mask].index
                    outliers = df.loc[outliers_index].copy() # Usar .copy() para evitar SettingWithCopyWarning
                    
                    # Calcular la desviación para el informe (Mejora 5)
                    outliers['Desviación de la media'] = (outliers[col_anomalias] - mean).round(2)

                    if not outliers.empty:
                        st.subheader(f"⚠️ Posibles anomalías detectadas en {col_anomalias.lower()}")
                        st.markdown(f"*(Fuera de $\pm{std_multiplier}$ Desviaciones Estándar)*")
                        
                        columnas_a_mostrar = [c for c in [date_col, product_col, col_anomalias, 'Desviación de la media'] if c and c in outliers.columns]
                        st.dataframe(outliers[columnas_a_mostrar].sort_values(by='Desviación de la media', ascending=False))

        except Exception as e:
            st.error(f"⚠️ No se pudo generar el resumen ejecutivo o gráficos. Asegúrate de que las columnas financieras contienen datos numéricos válidos. Error: {e}")
            
        # ==============================
        # 🤖 ANÁLISIS CON IA
        # ==============================
        if api_key and st.button("🤖 Generar análisis con IA"):
            try:
                client = OpenAI(api_key=api_key)
                
                # Agregar el resumen estadístico al prompt (Mejora 4)
                resumen_estadistico = df.describe(include='all').to_string()
                resumen_datos = df.head(50).to_string()
                
                prompt = f"""
                Analiza los siguientes datos de negocio y genera un resumen ejecutivo profesional y profundo:
                
                1. Describe las **principales tendencias** temporales y de rendimiento.
                2. Identifica los **productos, conceptos o periodos más rentables** y los menos rentables.
                3. Sugiere **3 recomendaciones clave y accionables** para mejorar el negocio, basadas en los datos proporcionados.
                
                ---
                
                **Resumen Estadístico del DataFrame (Datos Clave):**
                {resumen_estadistico}
                
                **Primeras 50 Filas del DataFrame (Muestra):**
                {resumen_datos}
                """
                with st.spinner(f"Generando informe con IA usando {MODEL_NAME}..."):
                    respuesta = client.chat.completions.create(
                        model=MODEL_NAME, 
                        messages=[{"role": "user", "content": prompt}]
                    )
                    analisis = respuesta.choices[0].message.content
                st.subheader("🧾 Informe de IA")
                st.markdown(analisis)
                buffer = io.BytesIO(analisis.encode("utf-8"))
                st.download_button(
                    label="📥 Descargar informe (TXT)",
                    data=buffer,
                    file_name="informe_smaport_ia.txt",
                    mime="text/plain"
                )
            except Exception as e:
                st.error(f"❌ Error al conectar con la API de OpenAI. Por favor, verifica tu clave. Error: {e}")
    except Exception as e:
        st.error(f"❌ Error al cargar o procesar el archivo. Verifica si el archivo está dañado o tiene un formato inesperado después de la fila {skip_rows_count + 1}. Error: {e}")
