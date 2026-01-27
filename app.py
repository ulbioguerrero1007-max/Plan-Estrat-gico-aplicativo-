import streamlit as st
import re
import google.generativeai as genai
import pandas as pd
import sqlite3
import io
import unicodedata
import time
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

# --- CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Estratega Pro | Business Intelligence", page_icon="♟️", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; color: white; }
    </style>
    """, unsafe_allow_html=True)

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
        # Tablas consolidadas para evitar redundancia en la creación
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
        
        # Migración de columnas faltantes
        cols = [c[1] for c in cursor.execute("PRAGMA table_info(empresas)").fetchall()]
        for col in ['objetivo_plan', 'obj_general', 'obj_especificos', 'posicionamiento_x', 'posicionamiento_y', 'analisis_posicionamiento', 'analisis_pest', 'analisis_foda', 'analisis_made', 'analisis_madi', 'analisis_cmi', 'analisis_operativo']:
            if col not in cols: cursor.execute(f"ALTER TABLE empresas ADD COLUMN {col} TEXT")
        conn.commit()

def get_empresas():
    with get_connection() as conn: return pd.read_sql("SELECT id, nombre FROM empresas", conn)

# --- IA Y ANÁLISIS (CON LIMPIEZA DE TEXTO) ---
def generar_analisis(prompt, client=None):
    # Instrucción estricta para evitar Markdown
    prompt_limpio = prompt + "\n\nIMPORTANTE: Proporciona el análisis en TEXTO PLANO. NO uses asteriscos (*), almohadillas (#), negritas ni ningún formato Markdown. Usa solo párrafos y saltos de línea."
    try:
        get_ia_client()
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        probar = [m for m in modelos if 'flash' in m.lower()] + [m for m in modelos if 'pro' in m.lower()]
        for m_name in probar:
            try:
                model = genai.GenerativeModel(m_name, system_instruction="Eres un consultor senior de estrategia empresarial. Tu respuesta debe ser texto plano, profesional y sin decoraciones de Markdown.")
                response = model.generate_content(prompt_limpio)
                texto = response.text
                # Limpieza agresiva de Markdown
                texto = re.sub(r'\*+', '', texto) # Elimina asteriscos
                texto = re.sub(r'#+', '', texto)  # Elimina almohadillas
                texto = re.sub(r'_+', '', texto)  # Elimina guiones bajos de cursiva
                texto = re.sub(r'`+', '', texto)  # Elimina backticks
                return texto.strip()
            except: continue
    except Exception as e: return f"Error: {str(e)}"
    return "Error en análisis."

def generar_analisis_ia(tipo_matriz, datos_contexto):
    return generar_analisis(f"Actúa como un consultor senior de estrategia. Analiza la siguiente matriz {tipo_matriz} y proporciona conclusiones estratégicas clave, riesgos y recomendaciones. Datos: {datos_contexto}")

# --- LÓGICA DE NEGOCIO ---
def analizar_foda(df_foda):
    if df_foda.empty: return None, None, None, pd.Series(dtype='float64')
    estrategias = {'FO': 'Ofensiva (F+O)', 'FA': 'Defensiva (F+A)', 'DO': 'Adaptativa (D+O)', 'DA': 'Supervivencia (D+A)'}
    puntajes = df_foda.groupby('cuadrante')['impacto'].sum().reindex(estrategias.keys(), fill_value=0)
    pts_ord = puntajes.sort_values(ascending=False)
    analisis_df = pd.DataFrame({'Estrategia': [estrategias[c] for c in pts_ord.index], 'Puntaje Total': pts_ord.values}).reset_index(drop=True)
    resumen = f"La estrategia principal recomendada es **{analisis_df.iloc[0]['Estrategia']}** ({analisis_df.iloc[0]['Puntaje Total']} puntos)."
    return analisis_df, resumen, analisis_df.iloc[0]['Estrategia'], pts_ord

def generar_planes_por_plantilla(estrategia_foda, pest_total):
    is_growth = any(x in estrategia_foda for x in ["Ofensiva", "Adaptativa"])
    return {
        'Plan Administrativo': {'objetivo': "Implementar un programa de formación en liderazgo y gestión de proyectos en los próximos 6 meses."},
        'Plan Operativo': {'objetivo': "Optimizar la cadena de valor y escalar las operaciones de manera eficiente."},
        'Plan Tecnológico': {'objetivo': "Implementar CRM/ERP en 9 meses" if is_growth else "Auditoría de ciberseguridad completa en el próximo trimestre."},
        'Plan Financiero': {'objetivo': "Asegurar ronda de financiación en 6 meses" if is_growth else "Plan de reducción de costos no esenciales (2%) en 6 meses."},
        'Plan de Monitoreo y control': {'objetivo': "Implementar dashboard de KPIs en tiempo real y ciclo de revisión mensual."},
        'Plan de Mejora': {'objetivo': "Lanzar nueva línea de producto en 12 meses" if "Ofensiva" in estrategia_foda else "Plan de retención de clientes clave en 6 meses."},
        'Plan de Contingencia': {'objetivo': "Comité de gestión de riesgos en 2 meses" if pest_total < 2.5 else "Sistema de vigilancia trimestral y simulacro anual."}
    }

def generar_cuadro_de_mando(planes):
    cmi_data = []
    for nombre_plan, datos_plan in planes.items():
        obj = datos_plan['objetivo'].lower()
        persp = 'Procesos Internos'
        if any(k in obj for k in ['margen', 'costo', 'ingreso', 'financiar', 'rentabilidad']): persp = 'Financiera'
        elif any(k in obj for k in ['cliente', 'retención', 'satisfacción']): persp = 'Clientes'
        elif any(k in obj for k in ['capacitación', 'liderazgo', 'innovación', 'ciberseguridad']): persp = 'Aprendizaje y Crecimiento'
        cmi_data.append([persp, datos_plan['objetivo'], "Por definir", "Por definir", f"Proyecto Plan {nombre_plan}"])
    df = pd.DataFrame(cmi_data, columns=['Perspectiva', 'Objetivo Estratégico', 'KPI (Indicador)', 'Meta', 'Iniciativa'])
    df['Perspectiva'] = pd.Categorical(df['Perspectiva'], categories=['Financiera', 'Clientes', 'Procesos Internos', 'Aprendizaje y Crecimiento'], ordered=True)
    return df.sort_values('Perspectiva').reset_index(drop=True)

# --- GRÁFICOS ---
def generar_grafico_foda_radar(puntajes):
    if puntajes is None or puntajes.empty: return None
    labels = ['FO', 'FA', 'DO', 'DA']
    stats = puntajes.reindex(labels).fillna(0).values
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
    stats = np.concatenate((stats, [stats[0]]))
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='blue', alpha=0.25); ax.plot(angles, stats, color='blue', linewidth=2)
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(['Ofensiva\n(FO)', 'Defensiva\n(FA)', 'Adaptativa\n(DO)', 'Supervivencia\n(DA)'])
    buf = BytesIO(); plt.savefig(buf, format='PNG', bbox_inches='tight'); plt.close(fig); buf.seek(0)
    return buf

# --- PDF ---
def encabezado_pie_pagina(canvas, doc, logo_bytes, nombre_empresa, version, coordinador):
    canvas.saveState()
    if logo_bytes:
        img = Image(logo_bytes, width=0.7*inch, height=0.7*inch)
        img.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - 0.4*inch)
    canvas.setFont('Helvetica-Bold', 14); canvas.drawString(doc.leftMargin + 0.8*inch, doc.height + doc.topMargin - 0.35*inch, nombre_empresa)
    canvas.setFont('Helvetica', 8); canvas.drawCentredString(doc.width/2 + doc.leftMargin, 0.5*inch, f"Revisado por: {coordinador}")
    canvas.restoreState()

def generar_pdf_completo(empresa_id, version, coordinador):
    with get_connection() as conn:
        empresa = pd.read_sql(f"SELECT * FROM empresas WHERE id={empresa_id}", conn).iloc[0]
        df_pest = pd.read_sql(f"SELECT * FROM matrices WHERE empresa_id={empresa_id} AND tipo_matriz='PEST'", conn)
        df_foda = pd.read_sql(f"SELECT * FROM foda_cruzado WHERE empresa_id={empresa_id}", conn)
    buf = BytesIO(); doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet(); story = []
    story.append(Paragraph(f"Plan Estratégico: {empresa['nombre']}", styles['Title']))
    story.append(Spacer(1, 0.5*inch))
    analisis_df, resumen, est_princ, pts = analizar_foda(df_foda)
    story.append(Paragraph("Diagnóstico Estratégico", styles['Heading2']))
    story.append(Paragraph(resumen, styles['Normal']))
    graf = generar_grafico_foda_radar(pts)
    if graf: story.append(Image(graf, width=4*inch, height=4*inch))
    doc.build(story, onFirstPage=lambda c, d: encabezado_pie_pagina(c, d, BytesIO(empresa['logo']) if empresa['logo'] else None, empresa['nombre'], version, coordinador))
    buf.seek(0); return buf

# --- UI HELPERS ---
def procesar_made_madi(data_str, tipo, empresa_id):
    df = data_str if isinstance(data_str, pd.DataFrame) else pd.read_csv(StringIO(data_str), sep='\t', header=0)
    def norm(t): return unicodedata.normalize('NFKD', str(t)).encode('ascii', 'ignore').decode('utf-8').lower().replace(' ', '_')
    df.columns = [norm(c) for c in df.columns]
    p_cols = ['producto', 'precio', 'plaza', 'promocion']
    for c in p_cols: df[c] = df[c].astype(str).str.lower() if c in df.columns else "no"
    df['total'] = df[p_cols].apply(lambda r: r.str.contains('si', na=False)).sum(axis=1)
    df['rating'] = pd.to_numeric(df.get('rating', 0), errors='coerce').fillna(0)
    df['weight_percent'] = pd.to_numeric(df.get('weight_percent', 0), errors='coerce').fillna(0)
    df['valor'] = df['rating'] * (df['weight_percent'] / 100.0)
    df['empresa_id'], df['tipo_matriz'] = empresa_id, tipo
    return df[['empresa_id', 'tipo_matriz', 'variable', 'factor', 'producto', 'precio', 'plaza', 'promocion', 'rating', 'weight_percent', 'valor', 'total']]

# --- APLICACIÓN PRINCIPAL ---
def aplicacion_principal():
    with st.sidebar:
        st.header("Gestión de Empresas")
        empresas_df = get_empresas()
        sel = st.selectbox("Selecciona una Empresa", empresas_df['nombre'], index=None)
        empresa_id = int(empresas_df[empresas_df['nombre'] == sel]['id'].iloc[0]) if sel else None
        
        with st.expander("➕ Crear Nueva Empresa"):
            with st.form("new_empresa_form"):
                new_name = st.text_input("Nombre de la nueva empresa")
                if st.form_submit_button("Crear") and new_name:
                    with get_connection() as conn: conn.execute("INSERT INTO empresas (nombre) VALUES (?)", (new_name,))
                    st.success(f"Empresa '{new_name}' creada."); st.rerun()
        
        if empresa_id and st.button("❌ Eliminar Empresa Seleccionada", type="primary"):
            with get_connection() as conn: conn.execute("DELETE FROM empresas WHERE id=?", (empresa_id,))
            st.success("Empresa eliminada."); st.rerun()

    if not empresa_id:
        st.info("👈 Selecciona o crea una empresa en el menú lateral para comenzar.")
        st.stop()

    tabs = st.tabs(["1. Introducción", "2. Diagnóstico", "3. Estrategia", "4. Planes", "5. CMI", "6. Operativización", "7. Exportar"])
    
    with tabs[0]:
        st.header("Introducción y Cultura Organizacional")
        with get_connection() as conn: d = pd.read_sql(f"SELECT * FROM empresas WHERE id={empresa_id}", conn).iloc[0]
        with st.form("form_intro"):
            nombre = st.text_input("Nombre de la Empresa", d['nombre'])
            giro = st.text_input("Giro del Negocio", d['giro'])
            logo_file = st.file_uploader("Subir Logo", type=['png', 'jpg', 'jpeg'])
            if d['logo']: st.image(BytesIO(d['logo']), width=150)
            mision = st.text_area("Misión", d['mision'])
            vision = st.text_area("Visión", d['vision'])
            obj_gen = st.text_area("Objetivo General", d.get('obj_general', ''))
            politicas = st.text_area("Políticas", d['politicas'])
            valores = st.text_area("Valores", d['valores'])
            if st.form_submit_button("Guardar Introducción"):
                logo_bytes = save_image(logo_file) if logo_file else d['logo']
                with get_connection() as conn:
                    conn.execute("UPDATE empresas SET nombre=?, giro=?, logo=?, mision=?, vision=?, obj_general=?, politicas=?, valores=? WHERE id=?", (nombre, giro, logo_bytes, mision, vision, obj_gen, politicas, valores, empresa_id))
                st.success("Datos guardados."); st.rerun()

    with tabs[1]:
        st.header("Diagnóstico Situacional")
        with get_connection() as conn:
            analisis_data = pd.read_sql(f"SELECT * FROM empresas WHERE id={empresa_id}", conn).iloc[0]
        d_tabs = st.tabs(["MADE", "MADI", "Posicionamiento", "PEST", "FODA Numérico"])
        
        for i, tipo in enumerate(['MADE', 'MADI']):
            with d_tabs[i]:
                st.subheader(f"Matriz {tipo}")
                with st.expander(f"📋 Pegar datos de {tipo} desde Excel"):
                    paste_data = st.text_area(f"Pega tus datos de {tipo} aquí", key=f"paste_{tipo}")
                    if st.button(f"Procesar {tipo}"):
                        df = procesar_made_madi(paste_data, tipo, empresa_id)
                        with get_connection() as conn:
                            conn.execute(f"DELETE FROM matriz_marketing WHERE empresa_id=? AND tipo_matriz='{tipo}'", (empresa_id,))
                            df.to_sql('matriz_marketing', conn, if_exists='append', index=False)
                        st.success(f"¡{len(df)} filas importadas!"); st.rerun()
                with get_connection() as conn:
                    df_db = pd.read_sql(f"SELECT * FROM matriz_marketing WHERE empresa_id={empresa_id} AND tipo_matriz='{tipo}'", conn)
                if not df_db.empty:
                    st.data_editor(df_db, use_container_width=True, key=f"editor_{tipo}")
                    if st.button(f"🤖 Analizar {tipo} con IA"):
                        with st.spinner("Analizando..."):
                            st.write(generar_analisis_ia(tipo, df_db.to_string()))

        with d_tabs[2]:
            st.subheader("Matriz de Posicionamiento")
            with get_connection() as conn: pos = pd.read_sql(f"SELECT posicionamiento_x, posicionamiento_y FROM empresas WHERE id={empresa_id}", conn).iloc[0]
            cx = st.number_input("Coordenada X", value=float(pos['posicionamiento_x'] or 0))
            cy = st.number_input("Coordenada Y", value=float(pos['posicionamiento_y'] or 0))
            if st.button("Guardar y Graficar"):
                with get_connection() as conn: conn.execute("UPDATE empresas SET posicionamiento_x=?, posicionamiento_y=? WHERE id=?", (cx, cy, empresa_id))
                st.rerun()
            fig, ax = plt.subplots(); ax.axhline(0, color='gray'); ax.axvline(0, color='gray'); ax.plot(cx, cy, 'ro', markersize=10); ax.grid(True); st.pyplot(fig)

        with d_tabs[3]:
            st.subheader("Análisis PEST")
            with st.expander("📋 Pegar datos PEST"):
                pest_paste = st.text_area("Pega datos PEST aquí")
                if st.button("Procesar PEST"):
                    df_p = pd.read_csv(StringIO(pest_paste), sep='\t', header=0)
                    df_p.columns = ['categoria', 'factor', 'tipo_foda', 'puntaje', 'importancia']
                    df_p['valor_ponderado'] = df_p['puntaje'] * (df_p['importancia'] / 100.0)
                    df_p['empresa_id'], df_p['tipo_matriz'] = empresa_id, 'PEST'
                    with get_connection() as conn:
                        conn.execute("DELETE FROM matrices WHERE empresa_id=? AND tipo_matriz='PEST'", (empresa_id,))
                        df_p.to_sql('matrices', conn, if_exists='append', index=False)
                    st.success("PEST importado."); st.rerun()
            with get_connection() as conn:
                df_pest = pd.read_sql(f"SELECT * FROM matrices WHERE empresa_id={empresa_id} AND tipo_matriz='PEST'", conn)
            if not df_pest.empty: st.data_editor(df_pest, use_container_width=True)

        with d_tabs[4]:
            st.subheader("FODA Cruzado")
            with st.expander("📋 Pegar datos FODA"):
                foda_paste = st.text_area("Pega datos FODA aquí")
                if st.button("Procesar FODA"):
                    df_f = pd.read_csv(StringIO(foda_paste), sep='\t', header=0)
                    df_f.columns = ['cuadrante', 'factor_fila', 'factor_columna', 'impacto']
                    df_f['empresa_id'] = empresa_id
                    with get_connection() as conn:
                        conn.execute("DELETE FROM foda_cruzado WHERE empresa_id=?", (empresa_id,))
                        df_f.to_sql('foda_cruzado', conn, if_exists='append', index=False)
                    st.success("FODA importado."); st.rerun()
            with get_connection() as conn:
                df_foda = pd.read_sql(f"SELECT * FROM foda_cruzado WHERE empresa_id={empresa_id}", conn)
            if not df_foda.empty:
                analisis_df, resumen, est_princ, pts = analizar_foda(df_foda)
                st.info(resumen); st.dataframe(analisis_df, use_container_width=True)
                graf = generar_grafico_foda_radar(pts)
                if graf: st.image(graf)

    with tabs[2]:
        st.header("🎯 Formulación de Estrategias")
        if st.button("🤖 Generar 12 Estrategias Maestras con IA"):
            with get_connection() as conn: df_foda = pd.read_sql(f"SELECT * FROM foda_cruzado WHERE empresa_id={empresa_id}", conn)
            if not df_foda.empty:
                with st.spinner("Generando..."):
                    res = generar_analisis(f"Basado en este FODA: {df_foda.to_string()}, genera 12 estrategias (3 por cuadrante: FO, FA, DO, DA). Formato: CUADRANTE|ESTRATEGIA|IMPORTANCIA|ACT1;ACT2;ACT3;ACT4;ACT5|PLAN")
                    nuevas = []
                    for line in res.strip().split("\n"):
                        p = line.split("|")
                        if len(p) >= 5: nuevas.append({"cuadrante": p[0].strip(), "estrategia": p[1].strip(), "importancia": p[2].strip(), "actividades": p[3].strip(), "plan_asignado": p[4].strip(), "empresa_id": empresa_id})
                    if nuevas:
                        with get_connection() as conn:
                            conn.execute("DELETE FROM estrategias_generadas WHERE empresa_id=?", (empresa_id,))
                            pd.DataFrame(nuevas).to_sql("estrategias_generadas", conn, if_exists="append", index=False)
                        st.success("Estrategias generadas."); st.rerun()

    with tabs[6]:
        st.header("Exportación")
        with st.form("pdf_form"):
            v = st.text_input("Versión", "1.0")
            c = st.text_input("Coordinador", "Consultor Senior")
            if st.form_submit_button("🚀 Generar y Descargar PDF"):
                st.session_state.pdf = generar_pdf_completo(empresa_id, v, c)
        if 'pdf' in st.session_state:
            st.download_button("✅ Descargar PDF Ahora", st.session_state.pdf, f"Plan_Estrategico_{v}.pdf", "application/pdf")

def main():
    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    if not st.session_state.logged_in:
        st.subheader("🔐 Iniciar Sesión")
        u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
        if st.button("Acceder"):
            try:
                res = supabase.auth.sign_in_with_password({"email": u, "password": p})
                st.session_state.user, st.session_state.logged_in = res.user, True
                st.rerun()
            except: st.error("Error de acceso. Verifica tus credenciales.")
    else:
        if st.sidebar.button("Cerrar Sesión"): st.session_state.logged_in = False; st.rerun()
        aplicacion_principal()

if __name__ == "__main__":
    init_db()
    main()
