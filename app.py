import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client, Client
from openai import OpenAI
import re

# ==========================================
# 1. CONFIGURACIÓN Y ESTILO (INTERFAZ SOBRIA)
# ==========================================
st.set_page_config(
    page_title="Estratega Pro | Business Intelligence",
    page_icon="♟️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS personalizado para una apariencia profesional
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
    .stButton>button:hover { background-color: #1e40af; color: white; }
    .stTextInput>div>div>input { border-radius: 5px; }
    .sidebar .sidebar-content { background-color: #1e3a8a; color: white; }
    h1, h2, h3 { color: #1e3a8a; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre;
        background-color: #ffffff;
        border-radius: 5px 5px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. MOTORES LÓGICOS (EL CEREBRO)
# ==========================================

def conectar_supabase():
    """Establece conexión con la base de datos eterna."""
    try:
        return create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
    except:
        return None

def analizar_foda_profesional(df_foda):
    """Procesa la matriz FODA y devuelve resultados estratégicos."""
    if df_foda.empty: return None
    # Lógica simplificada para el ejemplo
    puntajes = df_foda.groupby('cuadrante')['impacto'].sum()
    return puntajes

# ==========================================
# 3. COMPONENTES DE LA INTERFAZ (LA CARA)
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
    
    st.divider()
    st.subheader("🖼️ Activos Visuales")
    c1, c2 = st.columns(2)
    with c1: st.file_uploader("Cargar Logotipo", type=['png', 'jpg', 'jpeg'])
    with c2: st.file_uploader("Cargar Organigrama", type=['png', 'jpg', 'jpeg'])

def seccion_diagnostico():
    st.header("🔍 Diagnóstico Situacional")
    menu_diag = st.segmented_control(
        "Selecciona el Análisis", 
        ["Matriz PEST", "Matriz FODA", "MADI / MADE"],
        default="Matriz PEST"
    )
    
    if menu_diag == "Matriz PEST":
        st.info("Analiza los factores externos que impactan tu negocio.")
        # Aquí iría tu tabla de PEST mejorada
        df_pest = pd.DataFrame(columns=["Factor", "Descripción", "Impacto"])
        st.data_editor(df_pest, num_rows="dynamic", use_container_width=True)
        
    elif menu_diag == "Matriz FODA":
        st.info("Identifica el equilibrio entre tus capacidades internas y el entorno.")
        # Aquí iría tu tabla de FODA
        
    st.button("🤖 Generar Análisis con IA")

# ==========================================
# 4. SISTEMA DE ACCESO (LOGIN / REGISTRO)
# ==========================================

def pantalla_acceso():
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/1006/1006541.png", width=100 )
    st.sidebar.title("Estratega Pro")
    
    opcion = st.sidebar.radio("Acceso al Sistema", ["Entrar", "Crear Cuenta"])
    
    with st.container():
        if opcion == "Entrar":
            st.subheader("🔐 Iniciar Sesión")
            st.text_input("Correo o Usuario")
            st.text_input("Contraseña", type="password")
            if st.button("Acceder"):
                st.session_state.logged_in = True
                st.rerun()
        else:
            st.subheader("📝 Registro de Nuevo Consultor")
            st.text_input("Nombre Completo")
            st.text_input("Nombre de Usuario (@usuario)")
            st.text_input("Correo Electrónico")
            st.text_input("Contraseña", type="password")
            st.button("Finalizar Registro")

# ==========================================
# 5. FLUJO PRINCIPAL (MAIN)
# ==========================================

def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        pantalla_acceso()
    else:
        # Barra Lateral de Navegación
        with st.sidebar:
            st.title("♟️ Estratega Pro")
            st.write(f"Bienvenido, **@usuario**")
            st.divider()
            if st.button("Cerrar Sesión"):
                st.session_state.logged_in = False
                st.rerun()

        # Cuerpo Principal con Pestañas
        tab_intro, tab_diag, tab_plan, tab_colab = st.tabs([
            "🏠 Introducción", 
            "📊 Diagnóstico", 
            "📋 Plan Estratégico",
            "👥 Colaboración"
        ])

        with tab_intro: seccion_introduccion()
        with tab_diag: seccion_diagnostico()
        with tab_plan: st.header("📋 Planes de Acción")
        with tab_colab: st.header("👥 Gestión de Colaboradores")

if __name__ == "__main__":
    main()
