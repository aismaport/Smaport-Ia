import streamlit as st
import requests
import os
import pandas as pd
import textwrap

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Smaport IA SaaS", page_icon="📊", layout="wide")
st.title("📊 Smaport IA — Portal")

# --- Auth UI (simple) ---
if "token" not in st.session_state:
    st.session_state.token = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None

def api_post(path, json=None, auth=True):
    headers = {}
    if auth and st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        r = requests.post(f"{BACKEND_URL}{path}", json=json, headers=headers, timeout=60)
        return r
    except Exception as e:
        st.error(f"Error de conexión con backend: {e}")
        return None

# Login / Register
with st.sidebar:
    st.header("Cuenta")
    if not st.session_state.token:
        form = st.form("login_form")
        email = form.text_input("Email")
        password = form.text_input("Contraseña", type="password")
        col1, col2 = form.columns([1,1])
        with col1:
            login = form.form_submit_button("Iniciar sesión")
        with col2:
            register = form.form_submit_button("Registrarse")
        if login:
            data = {"username": email, "password": password}
            r = requests.post(f"{BACKEND_URL}/token", data=data)
            if r and r.status_code == 200:
                j = r.json()
                st.session_state.token = j["access_token"]
                st.session_state.user_email = email
                st.success("Sesión iniciada")
                st.experimental_rerun()
            else:
                st.error(f"Error login: {r.text if r is not None else 'no response'}")
        if register:
            payload = {"email": email, "password": password, "full_name": ""}
            r = requests.post(f"{BACKEND_URL}/register", json=payload)
            if r and r.status_code == 200:
                st.success("Cuenta creada. Inicia sesión.")
            else:
                st.error(f"Error registro: {r.text if r is not None else 'no response'}")
    else:
        st.markdown(f"**{st.session_state.user_email}**")
        if st.button("Cerrar sesión"):
            st.session_state.token = None
            st.session_state.user_email = None
            st.experimental_rerun()

st.markdown("---")

# If not logged, prompt
if not st.session_state.token:
    st.info("Inicia sesión o regístrate en la barra lateral para usar la app (demo local).")
    st.stop()

# ================= File upload and local analysis (same as before)
uploaded = st.file_uploader("Sube CSV o Excel", type=["csv","xlsx"])
if uploaded is None:
    st.info("Sube un fichero o usa la demo local en el backend.")
    st.stop()

try:
    if uploaded.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded, engine="openpyxl")
except Exception as e:
    st.error(f"Error leyendo archivo: {e}")
    st.stop()

st.sidebar.markdown("### Export & Informe")
# quick UI
if st.sidebar.button("Generar informe IA (backend)"):
    resumen = df.describe(include="all").to_string()
    muestra = df.head(50).to_string()
    prompt = textwrap.dedent(f"""
        Eres un analista de datos experto. Analiza la información y responde con:
        1) Resumen ejecutivo (3-5 frases)
        2) Tendencias
        3) Productos más/menos rentables
        4) Riesgos/anomalías
        5) 3 recomendaciones
        Resumen:
        {resumen}
        Muestra:
        {muestra}
    """)
    payload = {"prompt": prompt, "model": "gpt-5", "max_tokens": 800}
    r = api_post("/openai/proxy", json=payload, auth=True)
    if r is None:
        st.error("Fallo en la petición.")
    elif r.status_code != 200:
        st.error(f"Error backend: {r.status_code} {r.text}")
    else:
        data = r.json()
        # intento de extraer texto de la respuesta
        try:
            content = data["result"]["choices"][0]["message"]["content"]
        except Exception:
            content = str(data["result"])
        st.subheader("📄 Informe IA")
        st.write(content)
        st.download_button("Descargar informe (TXT)", data=content.encode("utf-8"), file_name="informe.txt")
