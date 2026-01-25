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
        # st.secrets lee tus credenciales de Streamlit Cloud
        url = st.secrets["supabase_url"]
        key = st.secrets["supabase_key"]
        return create_client(url, key)
       except Exception as e:
                    # Esto nos dirá el error real que envía Supabase
                    st.error(f"Error técnico: {e}")

# ESTA ES LA LÍNEA CLAVE: Creamos la conexión para que todo el código la vea
supabase = conectar_supabase()

def analizar_foda_profesional(df_foda):
    # ... resto de tus funciones ...
    pass

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
    
    if opcion == "Entrar":
        st.subheader("🔐 Iniciar Sesión")
        identificador = st.text_input("Correo o Usuario")
        password = st.text_input("Contraseña", type="password")
        
        if st.button("Acceder"):
            try:
                # Intentamos login con Supabase
                res = supabase.auth.sign_in_with_password({"email": identificador, "password": password})
                st.session_state.user = res.user
                st.session_state.logged_in = True
                st.success("¡Bienvenido!")
                st.rerun()
            except Exception as e:
                st.error("Credenciales incorrectas o usuario no encontrado.")

    else:
        st.subheader("📝 Registro de Nuevo Consultor")
        nombre = st.text_input("Nombre Completo")
        usuario = st.text_input("Nombre de Usuario (sin @)")
        correo = st.text_input("Correo Electrónico")
        clave = st.text_input("Contraseña", type="password")
        
        if st.button("Finalizar Registro"):
            if nombre and usuario and correo and clave:
                try:
                    # 1. Crear usuario en Auth
                    res = supabase.auth.sign_up({"email": correo, "password": clave})
                    if res.user:
                        # 2. Crear perfil en nuestra tabla 'perfiles'
                        supabase.table('perfiles').insert({
                            "id": res.user.id,
                            "username": usuario.lower().strip(),
                            "nombre_completo": nombre,
                            "email": correo
                        }).execute()
                        st.success("¡Cuenta creada! Revisa tu correo para confirmar (si está activo) o intenta entrar.")
                except Exception as e:
                    st.error(f"Error al registrar: {e}")
            else:
                st.warning("Por favor, llena todos los campos.")
                
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




