import streamlit as st
import re
import google.generativeai as genai
import pandas as pd
import sqlite3
import io
import unicodedata
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO, BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import navy, grey, red, green, black
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from supabase import create_client, Client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Estratega Pro | Business Intelligence", page_icon="♟️", layout="wide", initial_sidebar_state="expanded")
st.markdown("<style>.stButton>button { width: 100%; border-radius: 5px; height: 3em; color: white; }</style>", unsafe_allow_html=True)

# --- CLIENTES Y CONEXIONES ---
def get_ia_client():
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("❌ No se encontró la API Key de Gemini en st.secrets")
        st.stop()
    genai.configure(api_key=api_key)
    return True

def init_supabase():
    try:
        url, key = st.secrets.get("supabase_url"), st.secrets.get("supabase_key")
        return create_client(url, key) if url and key else None
    except: return None

supabase = init_supabase()

def get_connection():
    return sqlite3.connect('strategic_plan.db', timeout=10)

# --- BASE DE DATOS ---
def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        # Tablas consolidadas
        schemas = {
            "empresas": "id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE, giro TEXT, logo BLOB, objetivo_plan TEXT, mision TEXT, vision TEXT, obj_general TEXT, obj_especificos TEXT, organigrama BLOB, politicas TEXT, valores TEXT, posicionamiento_x REAL, posicionamiento_y REAL, analisis_posicionamiento TEXT, analisis_pest TEXT, analisis_foda TEXT, analisis_made TEXT, analisis_madi TEXT, analisis_cmi TEXT, analisis_operativo TEXT",
            "matrices": "id INTEGER PRIMARY KEY, empresa_id INTEGER, tipo_matriz TEXT NOT NULL, categoria TEXT, factor TEXT, tipo_foda TEXT, puntaje REAL, importancia REAL, valor_ponderado REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "foda_cruzado": "id INTEGER PRIMARY KEY, empresa_id INTEGER, cuadrante TEXT, factor_fila TEXT, factor_columna TEXT, impacto INTEGER, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "finanzas_planes": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, nombre_plan TEXT NOT NULL, costo_implementacion REAL, beneficio_anual_esperado REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE, UNIQUE(empresa_id, nombre_plan)",
            "operativizacion": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, plan TEXT, estrategia TEXT, actividades TEXT, plazo TEXT, responsable TEXT, recurso TEXT, costo REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "perdida_ganancia": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, anio TEXT, ingresos REAL, egresos REAL, resultado REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "flujo_caja": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, anio_proyeccion INTEGER, saldo_inicial REAL, ingreso REAL, egreso REAL, flujo_neto REAL, saldo_final REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "punto_equilibrio": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, costo_fijo_total REAL, precio_venta_unidad REAL, costo_variable_unidad REAL, unidades_producidas REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "matriz_marketing": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, tipo_matriz TEXT NOT NULL, variable TEXT, factor TEXT, producto TEXT, precio TEXT, plaza TEXT, promocion TEXT, rating REAL, weight_percent REAL, valor REAL, total INTEGER, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "estrategias_generadas": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, cuadrante TEXT NOT NULL, estrategia TEXT NOT NULL, importancia TEXT NOT NULL, actividades TEXT NOT NULL, plan_asignado TEXT, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE"
        }
        for table, schema in schemas.items():
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {table} ({schema})")
        
        # Migración de columnas
        cols = [c[1] for c in cursor.execute("PRAGMA table_info(empresas)").fetchall()]
        for col in ['objetivo_plan', 'obj_general', 'obj_especificos', 'posicionamiento_x', 'posicionamiento_y', 'analisis_posicionamiento', 'analisis_pest', 'analisis_foda', 'analisis_made', 'analisis_madi', 'analisis_cmi', 'analisis_operativo']:
            if col not in cols: cursor.execute(f"ALTER TABLE empresas ADD COLUMN {col} TEXT")
        conn.commit()

def get_empresas():
    with get_connection() as conn: return pd.read_sql("SELECT id, nombre FROM empresas", conn)

# --- IA Y ANÁLISIS ---
def generar_analisis(prompt, client=None):
    prompt_limpio = prompt + "\n\nIMPORTANTE: Proporciona el análisis en texto claro y profesional. Evita el uso excesivo de asteriscos o negritas. Usa párrafos bien estructurados."
    try:
        get_ia_client()
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        probar = [m for m in modelos if 'flash' in m.lower()] + [m for m in modelos if 'pro' in m.lower()]
        for m_name in probar:
            try:
                model = genai.GenerativeModel(m_name, system_instruction="Eres un consultor senior de estrategia empresarial.")
                return model.generate_content(prompt_limpio).text.replace("****", "").replace("###", "").replace("##", "").strip()
            except: continue
    except Exception as e: return f"Error: {str(e)}"
    return "Error en análisis."

def generar_analisis_ia(tipo, contexto):
    return generar_analisis(f"Actúa como consultor senior. Analiza la matriz {tipo}: {contexto}")

# --- LÓGICA DE NEGOCIO ---
def analizar_foda(df):
    if df.empty: return None, None, None, pd.Series(dtype='float64')
    mapa = {'FO': 'Ofensiva (F+O)', 'FA': 'Defensiva (F+A)', 'DO': 'Adaptativa (D+O)', 'DA': 'Supervivencia (D+A)'}
    pts = df.groupby('cuadrante')['impacto'].sum().reindex(mapa.keys(), fill_value=0).sort_values(ascending=False)
    res = pd.DataFrame({'Estrategia': [mapa[c] for c in pts.index], 'Puntaje Total': pts.values})
    return res, f"Estrategia principal: **{res.iloc[0]['Estrategia']}** ({res.iloc[0]['Puntaje Total']} pts).", res.iloc[0]['Estrategia'], pts

def generar_planes_por_plantilla(est, pest):
    is_growth = "Ofensiva" in est or "Adaptativa" in est
    return {
        'Plan Administrativo': {'objetivo': "Fortalecer liderazgo y gestión en 6 meses."},
        'Plan Operativo': {'objetivo': "Optimizar cadena de valor para eficiencia."},
        'Plan Tecnológico': {'objetivo': "Implementar CRM/ERP" if is_growth else "Auditoría de ciberseguridad."},
        'Plan Financiero': {'objetivo': "Asegurar financiación" if is_growth else "Optimización de costos (2%)."},
        'Plan de Monitoreo y control': {'objetivo': "Dashboard de KPIs en tiempo real."},
        'Plan de Mejora': {'objetivo': "Nueva línea de producto" if "Ofensiva" in est else "Retención de clientes."},
        'Plan de Contingencia': {'objetivo': "Comité de riesgos" if pest < 2.5 else "Vigilancia trimestral."}
    }

def generar_cuadro_de_mando(planes):
    data = []
    for p_name, p_data in planes.items():
        obj = p_data['objetivo'].lower()
        persp = 'Procesos Internos'
        if any(k in obj for k in ['margen', 'costo', 'ingreso', 'financiar', 'rentabilidad']): persp = 'Financiera'
        elif any(k in obj for k in ['cliente', 'retención', 'satisfacción']): persp = 'Clientes'
        elif any(k in obj for k in ['capacitación', 'liderazgo', 'innovación']): persp = 'Aprendizaje y Crecimiento'
        data.append([persp, p_data['objetivo'], "Por definir", "Por definir", f"Proyecto {p_name}"])
    df = pd.DataFrame(data, columns=['Perspectiva', 'Objetivo Estratégico', 'KPI (Indicador)', 'Meta', 'Iniciativa'])
    df['Perspectiva'] = pd.Categorical(df['Perspectiva'], categories=['Financiera', 'Clientes', 'Procesos Internos', 'Aprendizaje y Crecimiento'], ordered=True)
    return df.sort_values('Perspectiva').reset_index(drop=True)

# --- VISUALIZACIÓN Y PDF ---
def generar_grafico_foda_radar(pts):
    if pts is None or pts.empty: return None
    labels = ['FO', 'FA', 'DO', 'DA']
    stats = np.concatenate((pts.reindex(labels).fillna(0).values, [pts.reindex(labels).fillna(0).values[0]]))
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='blue', alpha=0.25); ax.plot(angles, stats, color='blue', lw=2)
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(labels)
    buf = BytesIO(); plt.savefig(buf, format='PNG'); plt.close(fig); buf.seek(0)
    return buf

def generar_pdf_completo(emp_id, ver, coord):
    with get_connection() as conn:
        emp = pd.read_sql(f"SELECT * FROM empresas WHERE id={emp_id}", conn).iloc[0]
        df_pest = pd.read_sql(f"SELECT * FROM matrices WHERE empresa_id={emp_id} AND tipo_matriz='PEST'", conn)
        df_foda = pd.read_sql(f"SELECT * FROM foda_cruzado WHERE empresa_id={emp_id}", conn)
    buf = BytesIO(); doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet(); story = []
    story.append(Paragraph(f"Plan Estratégico: {emp['nombre']}", styles['Title']))
    story.append(Paragraph(f"Versión: {ver} | Fecha: {pd.Timestamp.now().strftime('%Y-%m-%d')}", styles['Normal']))
    _, _, est, pts = analizar_foda(df_foda)
    story.append(Paragraph(f"Estrategia Principal: {est}", styles['Heading2']))
    graf = generar_grafico_foda_radar(pts)
    if graf: story.append(Image(graf, width=4*inch, height=4*inch))
    doc.build(story)
    buf.seek(0); return buf

# --- UI HELPERS ---
def procesar_made_madi(data, tipo, emp_id):
    df = data if isinstance(data, pd.DataFrame) else pd.read_csv(StringIO(data), sep='\t', header=0)
    def norm(t): return unicodedata.normalize('NFKD', str(t)).encode('ascii', 'ignore').decode('utf-8').lower().replace(' ', '_')
    df.columns = [norm(c) for c in df.columns]
    p_cols = ['producto', 'precio', 'plaza', 'promocion']
    for c in p_cols: df[c] = df[c].astype(str).str.lower() if c in df.columns else "no"
    df['total'] = df[p_cols].apply(lambda r: r.str.contains('si', na=False)).sum(axis=1)
    df['rating'] = pd.to_numeric(df.get('rating', 0), errors='coerce').fillna(0)
    df['weight_percent'] = pd.to_numeric(df.get('weight_percent', 0), errors='coerce').fillna(0)
    df['valor'] = df['rating'] * (df['weight_percent'] / 100.0)
    df['empresa_id'], df['tipo_matriz'] = emp_id, tipo
    return df

# --- APLICACIÓN PRINCIPAL ---
def aplicacion_principal():
    with st.sidebar:
        emps = get_empresas()
        sel = st.selectbox("Empresa", emps['nombre'], index=None)
        emp_id = int(emps[emps['nombre'] == sel]['id'].iloc[0]) if sel else None
        if st.button("➕ Nueva"):
            n = st.text_input("Nombre")
            if n: 
                with get_connection() as conn: conn.execute("INSERT INTO empresas (nombre) VALUES (?)", (n,))
                st.rerun()
    
    if not emp_id: st.info("Selecciona una empresa"); st.stop()
    
    tabs = st.tabs(["Introducción", "Diagnóstico", "Estrategia", "Planes", "CMI", "Operativización", "Exportar"])
    
    with tabs[0]:
        with get_connection() as conn: d = pd.read_sql(f"SELECT * FROM empresas WHERE id={emp_id}", conn).iloc[0]
        with st.form("f_intro"):
            n = st.text_input("Nombre", d['nombre'])
            m = st.text_area("Misión", d['mision'])
            v = st.text_area("Visión", d['vision'])
            if st.form_submit_button("Guardar"):
                with get_connection() as conn: conn.execute("UPDATE empresas SET nombre=?, mision=?, vision=? WHERE id=?", (n, m, v, emp_id))
                st.success("Guardado"); st.rerun()

    with tabs[1]:
        st.write("Gestión de Matrices (MADE, MADI, PEST, FODA)")
        # Implementación simplificada de matrices usando st.data_editor y procesar_made_madi

    with tabs[6]:
        with st.form("f_pdf"):
            v, c = st.text_input("Versión", "1.0"), st.text_input("Coordinador", "Consultor")
            if st.form_submit_button("Generar PDF"):
                st.session_state.pdf = generar_pdf_completo(emp_id, v, c)
        if 'pdf' in st.session_state:
            st.download_button("Descargar Plan", st.session_state.pdf, "Plan.pdf")

def main():
    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    if not st.session_state.logged_in:
        st.subheader("Acceso")
        u, p = st.text_input("Usuario"), st.text_input("Clave", type="password")
        if st.button("Entrar"):
            try:
                res = supabase.auth.sign_in_with_password({"email": u, "password": p})
                st.session_state.user, st.session_state.logged_in = res.user, True
                st.rerun()
            except: st.error("Error de acceso")
    else:
        if st.sidebar.button("Salir"): st.session_state.logged_in = False; st.rerun()
        aplicacion_principal()

if __name__ == "__main__":
    init_db()
    main()
