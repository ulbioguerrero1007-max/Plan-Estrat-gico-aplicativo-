import streamlit as st
import pandas as pd
from supabase import create_client, Client
from openai import OpenAI
import re

# ==========================================
# 1. CONFIGURACIÓN Y ESTILO
# ==========================================
st.set_page_config(
    page_title="Estratega Pro | Business Intelligence",
    page_icon="♟️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #1e3a8a;
        color: white;
        border: none;
    }
    h1, h2, h3 { color: #1e3a8a; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MOTORES LÓGICOS
# ==========================================

def conectar_supabase():
    try:
        url = st.secrets["supabase_url"]
        key = st.secrets["supabase_key"]
        return create_client(url, key)
    except Exception as e:
        return None

supabase = conectar_supabase()

# ==========================================
# 3. COMPONENTES DE LA INTERFAZ
# ==========================================

def seccion_introduccion():
    st.header("🏢 Identidad Corporativa")
    col1, col2 = st.columns([1, 1])
    with col1:
        st.text_input("Nombre de la Organización", placeholder="Ej: Corporación Alpha")
        st.text_area("Misión", placeholder="Define el propósito de la empresa...")
    with col2:
        st.text_input("Giro del Negocio", placeholder="Ej: Consultoría Tecnológica")
        st.text_area("Visión", placeholder="¿Dónde ves la empresa en 5 años?")

def seccion_diagnostico():
    st.header("🔍 Diagnóstico Situacional")
    st.info("Analiza los factores externos e internos de tu negocio.")
    st.button("🤖 Generar Análisis con IA")

# ==========================================
# 4. SISTEMA DE ACCESO
# ==========================================

def pantalla_acceso():
    st.sidebar.title("Estratega Pro")
    opcion = st.sidebar.radio("Acceso al Sistema", ["Entrar", "Crear Cuenta"])
    
    if opcion == "Entrar":
        st.subheader("🔐 Iniciar Sesión")
        identificador = st.text_input("Correo o Usuario")
        password = st.text_input("Contraseña", type="password")
        if st.button("Acceder"):
            try:
                res = supabase.auth.sign_in_with_password({"email": identificador, "password": password})
                st.session_state.user = res.user
                st.session_state.logged_in = True
                st.rerun()
            except Exception as e:
                st.error(f"Error al entrar: {e}")
    else:
        st.subheader("📝 Registro de Nuevo Consultor")
        nombre = st.text_input("Nombre Completo")
        usuario = st.text_input("Nombre de Usuario (sin @)")
        correo = st.text_input("Correo Electrónico")
        clave = st.text_input("Contraseña", type="password")
        if st.button("Finalizar Registro"):
            if nombre and usuario and correo and clave:
                try:
                    res = supabase.auth.sign_up({"email": correo, "password": clave})
                    if res.user:
                        supabase.table('perfiles').insert({
                            "id": res.user.id,
                            "username": usuario.lower().strip(),
                            "nombre_completo": nombre,
                            "email": correo
                        }).execute()
                        st.success("¡Cuenta creada! Intenta entrar ahora.")
                except Exception as e:
                    st.error(f"Error técnico: {e}")
            else:
                st.warning("Por favor, llena todos los campos.")

# ==========================================
# 5. FLUJO PRINCIPAL
# ==========================================

def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        pantalla_acceso()
    else:
        with st.sidebar:
            st.title("♟️ Estratega Pro")
            if st.button("Cerrar Sesión"):
                st.session_state.logged_in = False
                st.rerun()

        tab_intro, tab_diag = st.tabs(["🏠 Introducción", "📊 Diagnóstico"])
        with tab_intro: seccion_introduccion()
        with tab_diag: seccion_diagnostico()

if __name__ == "__main__":
    main()
