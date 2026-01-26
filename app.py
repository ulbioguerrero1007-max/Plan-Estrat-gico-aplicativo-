import streamlit as st
import re
from openai import OpenAI
import pandas as pd
import sqlite3
import io
from io import StringIO, BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import navy, grey, red, green, black
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
import matplotlib.pyplot as plt
import numpy as np
import unicodedata
import time
from supabase import create_client, Client

# --- CONFIGURACIÓN Y CLIENTES ---
st.set_page_config(page_title="Estratega Pro | Business Intelligence", page_icon="♟️", layout="wide", initial_sidebar_state="expanded")

# Estilos CSS unificados
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; color: white; border: none;}
    </style>
    """, unsafe_allow_html=True)

def get_ia_client():
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    if not api_key:
        st.error("❌ No se encontró la API Key de OpenRouter en st.secrets")
        st.stop()
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

def init_supabase():
    try:
        if "supabase_url" in st.secrets and "supabase_key" in st.secrets:
            return create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
    except Exception:
        pass
    return None

supabase = init_supabase()

# --- BASE DE DATOS ---
def get_connection():
    return sqlite3.connect('strategic_plan.db', timeout=10)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        # Creación de tablas (unificado)
        tablas = {
            "empresas": """id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE, giro TEXT, logo BLOB, 
                           objetivo_plan TEXT, mision TEXT, vision TEXT, obj_general TEXT, obj_especificos TEXT,
                           organigrama BLOB, politicas TEXT, valores TEXT,
                           posicionamiento_x REAL, posicionamiento_y REAL, analisis_posicionamiento TEXT,
                           analisis_pest TEXT, analisis_foda TEXT, analisis_made TEXT, analisis_madi TEXT""",
            "matrices": "id INTEGER PRIMARY KEY, empresa_id INTEGER, tipo_matriz TEXT NOT NULL, categoria TEXT, factor TEXT, tipo_foda TEXT, puntaje REAL, importancia REAL, valor_ponderado REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "foda_cruzado": "id INTEGER PRIMARY KEY, empresa_id INTEGER, cuadrante TEXT, factor_fila TEXT, factor_columna TEXT, impacto INTEGER, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "finanzas_planes": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, nombre_plan TEXT NOT NULL, costo_implementacion REAL, beneficio_anual_esperado REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE, UNIQUE(empresa_id, nombre_plan)",
            "operativizacion": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, plan TEXT, estrategia TEXT, actividades TEXT, plazo TEXT, responsable TEXT, recurso TEXT, costo REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "perdida_ganancia": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, anio TEXT, ingresos REAL, egresos REAL, resultado REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "flujo_caja": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, anio_proyeccion INTEGER, saldo_inicial REAL, ingreso REAL, egreso REAL, flujo_neto REAL, saldo_final REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "punto_equilibrio": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, costo_fijo_total REAL, precio_venta_unidad REAL, costo_variable_unidad REAL, unidades_producidas REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "matriz_marketing": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, tipo_matriz TEXT NOT NULL, variable TEXT, factor TEXT, producto TEXT, precio TEXT, plaza TEXT, promocion TEXT, rating REAL, weight_percent REAL, valor REAL, total INTEGER, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE",
            "estrategias_generadas": "id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, cuadrante TEXT NOT NULL, estrategia TEXT NOT NULL, importancia TEXT NOT NULL, actividades TEXT NOT NULL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE"
        }
        for tabla, schema in tablas.items():
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {tabla} ({schema})")
        
        # Migración de columnas faltantes
        columnas_existentes = [c[1] for c in cursor.execute("PRAGMA table_info(empresas)").fetchall()]
        nuevas_columnas = ['objetivo_plan', 'obj_general', 'obj_especificos', 'posicionamiento_x', 'posicionamiento_y', 'analisis_posicionamiento', 'analisis_pest', 'analisis_foda', 'analisis_made', 'analisis_madi']
        for col in nuevas_columnas:
            if col not in columnas_existentes:
                cursor.execute(f"ALTER TABLE empresas ADD COLUMN {col} TEXT")
        conn.commit()

# --- LÓGICA DE NEGOCIO ---
def generar_analisis(prompt, client):
    modelos = ["meta-llama/llama-3.3-70b-instruct:free", "deepseek/deepseek-r1-0528:free", "mistralai/mistral-small-3.1-24b:free", "openrouter/auto"]
    for modelo in modelos:
        try:
            response = client.chat.completions.create(
                model=modelo,
                messages=[{"role": "system", "content": "Eres un analista estratégico empresarial."}, {"role": "user", "content": prompt}],
                timeout=10
            )
            return response.choices[0].message.content
        except Exception:
            continue
    return "No se pudo generar el análisis. Intente más tarde."

def generar_analisis_ia(tipo_matriz, datos_contexto):
    client = get_ia_client()
    prompt = f"Actúa como un consultor senior de estrategia. Analiza la siguiente matriz {tipo_matriz} y proporciona conclusiones estratégicas clave, riesgos y recomendaciones. Datos: {datos_contexto}"
    return generar_analisis(prompt, client)

def analizar_foda(df_foda):
    if df_foda.empty: return None, None, None, pd.Series(dtype='float64')
    estrategias = {'FO': 'Ofensiva (F+O)', 'FA': 'Defensiva (F+A)', 'DO': 'Adaptativa (D+O)', 'DA': 'Supervivencia (D+A)'}
    puntajes = df_foda.groupby('cuadrante')['impacto'].sum().reindex(estrategias.keys(), fill_value=0).sort_values(ascending=False)
    analisis_df = pd.DataFrame({'Estrategia': [estrategias[c] for c in puntajes.index], 'Puntaje Total': puntajes.values})
    resumen = f"La estrategia principal es **{analisis_df.iloc[0]['Estrategia']}** ({analisis_df.iloc[0]['Puntaje Total']} pts)."
    return analisis_df, resumen, analisis_df.iloc[0]['Estrategia'], puntajes

def generar_planes_por_plantilla(estrategia_foda, pest_total):
    planes = {'Administrativo': {'introduccion': "Enfoque en base organizacional.", 'objetivo': "Programa de liderazgo en 6 meses."}}
    plantillas = {
        "Ofensiva": ("Posición Ofensiva.", "Lanzar nueva línea en 12 meses."),
        "Adaptativa": ("Estrategia Adaptativa.", "Mejorar procesos en 9 meses."),
        "Defensiva": ("Estrategia Defensiva.", "Alianzas estratégicas en 1 año."),
        "Supervivencia": ("Estrategia de Supervivencia.", "Reducir gastos 15% en 4 meses.")
    }
    for key, (intro, obj) in plantillas.items():
        if key in estrategia_foda:
            planes[key] = {'introduccion': intro, 'objetivo': obj}
    return planes

def procesar_made_madi(data, tipo):
    if isinstance(data, str):
        df = pd.read_csv(StringIO(data), sep='\t', header=0)
    else:
        df = data.copy()
    df.columns = [c.lower() for c in df.columns]
    columnas = ['variable', 'factor', 'producto', 'precio', 'plaza', 'promocion', 'rating', 'weight_percent']
    df = df[columnas]
    df['valor'] = df['rating'] * (df['weight_percent'] / 100.0)
    df['total'] = df['valor'].round().astype(int)
    df['empresa_id'] = st.session_state.get('empresa_id')
    df['tipo_matriz'] = tipo
    return df

# --- INTERFAZ ---
def aplicacion_principal():
    with get_connection() as conn:
        empresas = pd.read_sql("SELECT id, nombre FROM empresas", conn)
    
    if empresas.empty:
        st.warning("Cree una empresa para comenzar.")
        with st.form("nueva_empresa"):
            nombre = st.text_input("Nombre")
            if st.form_submit_button("Crear"):
                with get_connection() as conn:
                    conn.execute("INSERT INTO empresas (nombre) VALUES (?)", (nombre,))
                st.rerun()
        return

    empresa_nombre = st.sidebar.selectbox("Empresa", empresas['nombre'])
    empresa_id = empresas[empresas['nombre'] == empresa_nombre]['id'].values[0]
    st.session_state['empresa_id'] = empresa_id

    tabs = st.tabs(["📋 Identidad", "🔍 Diagnóstico", "🎯 Estrategias", "📊 CMI", "💰 Finanzas", "📥 Exportar"])

    with tabs[0]:
        with get_connection() as conn:
            emp = pd.read_sql(f"SELECT * FROM empresas WHERE id={empresa_id}", conn).iloc[0]
        with st.form("identidad"):
            mision = st.text_area("Misión", emp['mision'] or "")
            vision = st.text_area("Visión", emp['vision'] or "")
            if st.form_submit_button("Guardar"):
                with get_connection() as conn:
                    conn.execute("UPDATE empresas SET mision=?, vision=? WHERE id=?", (mision, vision, empresa_id))
                st.success("Guardado.")

    with tabs[1]:
        d_tabs = st.tabs(["MADE", "MADI", "Posicionamiento", "PEST", "FODA"])
        # Lógica de matrices (simplificada pero funcional)
        for i, tipo in enumerate(['MADE', 'MADI']):
            with d_tabs[i]:
                st.subheader(f"Matriz {tipo}")
                paste = st.text_area(f"Pegar {tipo} (Excel)", key=f"p_{tipo}")
                if st.button(f"Importar {tipo}"):
                    df = procesar_made_madi(paste, tipo)
                    with get_connection() as conn:
                        conn.execute(f"DELETE FROM matriz_marketing WHERE empresa_id={empresa_id} AND tipo_matriz='{tipo}'")
                        df.to_sql('matriz_marketing', conn, if_exists='append', index=False)
                    st.rerun()

    with tabs[2]:
        st.header("Estrategias")
        if st.button("🤖 Generar con IA"):
            # Simulación de generación
            nuevas = [{'cuadrante': 'FO', 'estrategia': 'Expansión', 'importancia': 'Alta', 'actividades': 'Marketing Digital'}]
            df_n = pd.DataFrame(nuevas)
            df_n['empresa_id'] = empresa_id
            with get_connection() as conn:
                conn.execute(f"DELETE FROM estrategias_generadas WHERE empresa_id={empresa_id}")
                df_n.to_sql('estrategias_generadas', conn, if_exists='append', index=False)
            st.rerun()
        
        with get_connection() as conn:
            df_e = pd.read_sql(f"SELECT * FROM estrategias_generadas WHERE empresa_id={empresa_id}", conn)
        if not df_e.empty:
            edited = st.data_editor(df_e, num_rows="dynamic", key="ed_est", use_container_width=True, disabled=['id', 'empresa_id'])
            if st.button("💾 Guardar y Enviar"):
                with get_connection() as conn:
                    conn.execute(f"DELETE FROM estrategias_generadas WHERE empresa_id={empresa_id}")
                    edited.to_sql('estrategias_generadas', conn, if_exists='append', index=False)
                    # Enviar a operativización
                    for _, r in edited.iterrows():
                        conn.execute("INSERT INTO operativizacion (empresa_id, plan, estrategia, actividades, costo) VALUES (?,?,?,?,?)", 
                                     (empresa_id, "Estratégico", r['estrategia'], r['actividades'], 0.0))
                st.success("Procesado.")

    with tabs[4]:
        st.header("Finanzas")
        with get_connection() as conn:
            df_o = pd.read_sql(f"SELECT * FROM operativizacion WHERE empresa_id={empresa_id}", conn)
        st.dataframe(df_o)
        st.metric("Inversión Total", f"${df_o['costo'].sum():,.2f}")

def pantalla_acceso():
    st.sidebar.title("Estratega Pro")
    if st.sidebar.radio("Acceso", ["Entrar", "Registro"]) == "Entrar":
        if st.button("Acceder (Demo)"):
            st.session_state.logged_in = True
            st.rerun()
    else:
        st.info("Registro deshabilitado en demo.")

def main():
    init_db()
    if not st.session_state.get('logged_in'):
        pantalla_acceso()
    else:
        if st.sidebar.button("Salir"):
            st.session_state.logged_in = False
            st.rerun()
        aplicacion_principal()

if __name__ == "__main__":
    main()
