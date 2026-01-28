import streamlit as st
import re
import google.generativeai as genai
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
from typing import Optional, Dict, Any, List

# Configuración de página debe ser lo primero
st.set_page_config(
    page_title="Estratega Pro | Business Intelligence", 
    page_icon="♟️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

def init_session_state():
    """Inicializa las variables de sesión necesarias."""
    defaults = {
        'logged_in': False,
        'user': None,
        'pdf_file': None,
        'ia_analisis_MADE': '',
        'ia_analisis_MADI': '',
        'ia_analisis_posicionamiento': '',
        'ia_analisis_pest': '',
        'ia_analisis_foda': '',
        'ia_analisis_operativo': '',
        'ia_analisis_cmi': '',
        'df_estrategias_temp': None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def get_ia_client() -> bool:
    """Configura y verifica la conexión con Gemini."""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("❌ No se encontró la API Key de Gemini en st.secrets")
        return False
    
    genai.configure(api_key=api_key)
    return True

def generar_analisis(prompt: str) -> str:
    """Genera análisis usando Gemini con fallback de modelos."""
    if not get_ia_client():
        return "Error: No se pudo configurar el cliente de IA."
    
    # Limpieza de prompt para evitar formato no deseado
    prompt_limpio = prompt + "\n\nIMPORTANTE: Proporciona el análisis en texto claro y profesional. NO uses asteriscos (*), almohadillas (#), negritas ni ningún formato Markdown. Usa solo párrafos bien estructurados."
    
    try:
        modelos_disponibles = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        modelos_a_probar = [m for m in modelos_disponibles if 'flash' in m.lower()]
        modelos_a_probar.extend([m for m in modelos_disponibles if 'pro' in m.lower() and m not in modelos_a_probar])
        
        if not modelos_a_probar:
            return "No se encontraron modelos de Gemini disponibles."

        for nombre_modelo in modelos_a_probar:
            try:
                model = genai.GenerativeModel(
                    model_name=nombre_modelo,
                    system_instruction="Eres un consultor senior de estrategia empresarial. Tu lenguaje es formal, directo y limpio. No usas decoraciones innecesarias en el texto como asteriscos o almohadillas."
                )
                response = model.generate_content(prompt_limpio)
                texto = response.text
                # Limpieza agresiva de markdown
                texto = re.sub(r'[\*#_`]', '', texto)
                return texto.strip()
            except Exception:
                continue
                
        return "Error: No se pudo generar el análisis con ningún modelo disponible."
    except Exception as e:
        return f"Error de conexión: {str(e)}"

def generar_analisis_ia(tipo_matriz: str, datos_contexto: str) -> str:
    """Wrapper específico para análisis de matrices."""
    prompt = f"Actúa como un consultor senior de estrategia. Analiza la siguiente matriz {tipo_matriz} y proporciona conclusiones estratégicas clave, riesgos y recomendaciones. Datos: {datos_contexto}"
    return generar_analisis(prompt)

# Estilos CSS corregidos
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stButton>button { 
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #0066cc;
        color: white;
        border: none;
    }
    h1, h2, h3 { color: #1f1f1f; }
    </style>
    """, unsafe_allow_html=True)

def init_supabase() -> Optional[Client]:
    """Inicializa conexión con Supabase."""
    try:
        if "supabase_url" in st.secrets and "supabase_key" in st.secrets:
            url = st.secrets["supabase_url"]
            key = st.secrets["supabase_key"]
            return create_client(url, key)
        return None
    except Exception:
        return None

supabase = init_supabase()

def get_connection():
    """Factory para conexiones SQLite con timeout."""
    return sqlite3.connect('strategic_plan.db', timeout=10, check_same_thread=False)

def init_db():
    """Inicializa todas las tablas necesarias."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Tabla principal de empresas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS empresas (
                id INTEGER PRIMARY KEY, 
                nombre TEXT NOT NULL UNIQUE, 
                giro TEXT, 
                logo BLOB, 
                objetivo_plan TEXT, 
                mision TEXT, 
                vision TEXT, 
                obj_general TEXT, 
                obj_especificos TEXT,
                organigrama BLOB, 
                politicas TEXT, 
                valores TEXT,
                posicionamiento_x REAL, 
                posicionamiento_y REAL, 
                analisis_posicionamiento TEXT,
                analisis_pest TEXT, 
                analisis_foda TEXT, 
                analisis_made TEXT, 
                analisis_madi TEXT,
                analisis_cmi TEXT, 
                analisis_operativo TEXT
            )
        ''')
        
        # Tablas auxiliares
        tablas = [
            ('matrices', '''
                CREATE TABLE IF NOT EXISTS matrices (
                    id INTEGER PRIMARY KEY, 
                    empresa_id INTEGER, 
                    tipo_matriz TEXT NOT NULL, 
                    categoria TEXT, 
                    factor TEXT, 
                    tipo_foda TEXT, 
                    puntaje REAL, 
                    importancia REAL, 
                    valor_ponderado REAL,
                    FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                )
            '''),
            ('foda_cruzado', '''
                CREATE TABLE IF NOT EXISTS foda_cruzado (
                    id INTEGER PRIMARY KEY, 
                    empresa_id INTEGER, 
                    cuadrante TEXT, 
                    factor_fila TEXT, 
                    factor_columna TEXT, 
                    impacto INTEGER,
                    FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                )
            '''),
            ('operativizacion', '''
                CREATE TABLE IF NOT EXISTS operativizacion (
                    id INTEGER PRIMARY KEY,
                    empresa_id INTEGER NOT NULL, 
                    plan TEXT, 
                    estrategia TEXT, 
                    actividades TEXT, 
                    plazo TEXT,
                    responsable TEXT, 
                    recurso TEXT, 
                    costo REAL,
                    FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                )
            '''),
            ('perdida_ganancia', '''
                CREATE TABLE IF NOT EXISTS perdida_ganancia (
                    id INTEGER PRIMARY KEY,
                    empresa_id INTEGER NOT NULL, 
                    anio TEXT, 
                    ingresos REAL, 
                    egresos REAL, 
                    resultado REAL,
                    FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                )
            '''),
            ('flujo_caja', '''
                CREATE TABLE IF NOT EXISTS flujo_caja (
                    id INTEGER PRIMARY KEY, 
                    empresa_id INTEGER NOT NULL,
                    anio_proyeccion INTEGER, 
                    saldo_inicial REAL, 
                    ingreso REAL, 
                    egreso REAL, 
                    flujo_neto REAL,
                    saldo_final REAL,
                    FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                )
            '''),
            ('punto_equilibrio', '''
                CREATE TABLE IF NOT EXISTS punto_equilibrio (
                    id INTEGER PRIMARY KEY,
                    empresa_id INTEGER NOT NULL, 
                    costo_fijo_total REAL, 
                    precio_venta_unidad REAL,
                    costo_variable_unidad REAL, 
                    unidades_producidas REAL,
                    FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                )
            '''),
            ('matriz_marketing', '''
                CREATE TABLE IF NOT EXISTS matriz_marketing (
                    id INTEGER PRIMARY KEY,
                    empresa_id INTEGER NOT NULL, 
                    tipo_matriz TEXT NOT NULL, 
                    variable TEXT, 
                    factor TEXT,
                    producto TEXT, 
                    precio TEXT, 
                    plaza TEXT, 
                    promocion TEXT, 
                    rating REAL, 
                    weight_percent REAL,
                    valor REAL, 
                    total INTEGER,
                    FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                )
            '''),
            ('estrategias_generadas', '''
                CREATE TABLE IF NOT EXISTS estrategias_generadas (
                    id INTEGER PRIMARY KEY,
                    empresa_id INTEGER NOT NULL,
                    cuadrante TEXT NOT NULL,
                    estrategia TEXT NOT NULL,
                    importancia TEXT NOT NULL,
                    actividades TEXT NOT NULL,
                    plan_asignado TEXT,
                    FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                )
            ''')
        ]
        
        for nombre, sql in tablas:
            cursor.execute(sql)
        
        # Migraciones para columnas nuevas
        cursor.execute("PRAGMA table_info(empresas)")
        columnas_existentes = [c[1] for c in cursor.fetchall()]
        nuevas_columnas = [
            'objetivo_plan', 'obj_general', 'obj_especificos', 
            'posicionamiento_x', 'posicionamiento_y', 'analisis_posicionamiento',
            'analisis_pest', 'analisis_foda', 'analisis_made', 'analisis_madi',
            'analisis_cmi', 'analisis_operativo'
        ]
        for col in nuevas_columnas:
            if col not in columnas_existentes:
                cursor.execute(f"ALTER TABLE empresas ADD COLUMN {col} TEXT")
        
        # Verificar columna plan_asignado
        cursor.execute("PRAGMA table_info(estrategias_generadas)")
        cols_estrategias = [c[1] for c in cursor.fetchall()]
        if 'plan_asignado' not in cols_estrategias:
            cursor.execute("ALTER TABLE estrategias_generadas ADD COLUMN plan_asignado TEXT")
        
        conn.commit()

def get_empresas() -> pd.DataFrame:
    """Retorna DataFrame con empresas disponibles."""
    with get_connection() as conn:
        return pd.read_sql("SELECT id, nombre FROM empresas", conn)

def save_image(uploaded_file) -> Optional[bytes]:
    """Extrae bytes de archivo subido."""
    if uploaded_file:
        return uploaded_file.getvalue()
    return None

def analizar_foda(df_foda: pd.DataFrame):
    """Analiza matriz FODA cruzada."""
    if df_foda.empty:
        return None, None, None, pd.Series(dtype='float64')
    
    estrategias = {'FO': 'Ofensiva (F+O)', 'FA': 'Defensiva (F+A)', 'DO': 'Adaptativa (D+O)', 'DA': 'Supervivencia (D+A)'}
    puntajes = df_foda.groupby('cuadrante')['impacto'].sum().reindex(estrategias.keys(), fill_value=0)
    puntajes_ordenados = puntajes.sort_values(ascending=False)
    
    analisis_df = pd.DataFrame({
        'Estrategia': [estrategias[c] for c in puntajes_ordenados.index],
        'Puntaje Total': puntajes_ordenados.values
    }).reset_index(drop=True)
    
    estrategia_principal = analisis_df.iloc[0]['Estrategia']
    resumen = f"La estrategia principal recomendada es **{analisis_df.iloc[0]['Estrategia']}** ({analisis_df.iloc[0]['Puntaje Total']} puntos)."
    
    return analisis_df, resumen, estrategia_principal, puntajes_ordenados

def generar_planes_por_plantilla(estrategia_foda: str, pest_total: float) -> Dict[str, Dict[str, str]]:
    """Genera planes estratégicos basados en perfiles."""
    planes = {}
    
    # Planes base
    planes['Plan Administrativo'] = {
        'introduccion': "Fortalecer la base organizacional y fomentar innovación continua.",
        'objetivo': "Implementar programa de formación en liderazgo para mandos medios en 6 meses."
    }
    
    planes['Plan Operativo'] = {
        'introduccion': "Optimizar cadena de valor y escalar operaciones eficientemente.",
        'objetivo': "Reducir tiempos de entrega en 15% durante el próximo año."
    }
    
    # Plan Tecnológico adaptativo
    if "Ofensiva" in estrategia_foda or "Adaptativa" in estrategia_foda:
        intro_tec = "Invertir en innovación tecnológica para ganar ventaja competitiva."
        obj_tec = "Implementar CRM/ERP en 9 meses para mejorar eficiencia."
    else:
        intro_tec = "Robustecer operación actual, priorizando seguridad y estabilidad."
        obj_tec = "Auditoría de ciberseguridad completa y actualización de sistemas críticos."
    planes['Plan Tecnológico'] = {'introduccion': intro_tec, 'objetivo': obj_tec}
    
    # Plan Financiero adaptativo
    if "Ofensiva" in estrategia_foda or "Adaptativa" in estrategia_foda:
        intro_fin = "Asegurar fondos para expansión."
        obj_fin = "Preparar ronda de financiación o línea de crédito en 6 meses."
    else:
        intro_fin = "Gestión prudente con enfoque en optimización de costos y liquidez."
        obj_fin = "Reducir costos no esenciales para mejorar margen neto en 2% en 6 meses."
    planes['Plan Financiero'] = {'introduccion': intro_fin, 'objetivo': obj_fin}
    
    # Planes estándar
    planes['Plan de Monitoreo y control'] = {
        'introduccion': "Sistema de monitoreo ágil para asegurar cumplimiento de objetivos.",
        'objetivo': "Dashboard de KPIs en tiempo real y revisión estratégica mensual."
    }
    
    # Plan de Mejora según estrategia
    if "Ofensiva" in estrategia_foda:
        intro_mej = "Usar fortalezas para capitalizar oportunidades de mercado."
        obj_mej = "Lanzar nueva línea de producto en 12 meses para capturar 5% más de mercado."
    elif "Adaptativa" in estrategia_foda:
        intro_mej = "Desarrollar áreas internas para aprovechar oportunidades externas."
        obj_mej = "Programa de capacitación técnica para cerrar brechas en próximo trimestre."
    else:
        intro_mej = "Proteger posición actual, usando fortalezas para mitigar amenazas."
        obj_mej = "Plan de retención de clientes clave para reducir abandono en 10% en 6 meses."
    planes['Plan de Mejora'] = {'introduccion': intro_mej, 'objetivo': obj_mej}
    
    # Plan de Contingencia según PEST
    if pest_total < 2.5:
        intro_con = f"Entorno vulnerable (PEST: {pest_total:.2f}). Desarrollar planes de mitigación."
        obj_con = "Formar comité de riesgos que identifique 3 principales riesgos externos en 2 meses."
    else:
        intro_con = f"Buena respuesta al entorno (PEST: {pest_total:.2f}). Enfoque en vigilancia proactiva."
        obj_con = "Sistema de vigilancia trimestral y simulacro de crisis anual."
    planes['Plan de Contingencia'] = {'introduccion': intro_con, 'objetivo': obj_con}
    
    return planes

def generar_cuadro_de_mando(planes: Dict) -> pd.DataFrame:
    """Genera DataFrame del CMI basado en planes."""
    cmi_data = []
    
    for nombre_plan, datos_plan in planes.items():
        objetivo = datos_plan['objetivo'].lower()
        
        # Clasificación por perspectiva
        if any(k in objetivo for k in ['margen', 'costo', 'ingreso', 'financiar', 'cuota', 'rentabilidad']):
            perspectiva = 'Financiera'
        elif any(k in objetivo for k in ['cliente', 'retención', 'abandono', 'satisfacción']):
            perspectiva = 'Clientes'
        elif any(k in objetivo for k in ['capacitación', 'habilidades', 'liderazgo', 'cultura', 'innovación', 'ciberseguridad']):
            perspectiva = 'Aprendizaje y Crecimiento'
        else:
            perspectiva = 'Procesos Internos'
            
        cmi_data.append([
            perspectiva, 
            datos_plan['objetivo'], 
            "Por definir", 
            "Por definir", 
            f"Proyecto: {nombre_plan}"
        ])
    
    df_cmi = pd.DataFrame(cmi_data, columns=[
        'Perspectiva', 'Objetivo Estratégico', 'KPI', 'Meta', 'Iniciativa'
    ])
    
    perspectiva_orden = ['Financiera', 'Clientes', 'Procesos Internos', 'Aprendizaje y Crecimiento']
    df_cmi['Perspectiva'] = pd.Categorical(
        df_cmi['Perspectiva'], 
        categories=perspectiva_orden, 
        ordered=True
    )
    
    return df_cmi.sort_values(by='Perspectiva').reset_index(drop=True)

def generar_grafico_foda_radar(puntajes: pd.Series):
    """Genera gráfico radar para FODA."""
    if puntajes is None or puntajes.empty:
        return None
    
    labels = np.array(['Ofensiva\n(FO)', 'Defensiva\n(FA)', 'Adaptativa\n(DO)', 'Supervivencia\n(DA)'])
    stats = puntajes.reindex(['FO', 'FA', 'DO', 'DA']).fillna(0).values
    
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    stats = np.concatenate((stats, [stats[0]]))
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='blue', alpha=0.25)
    ax.plot(angles, stats, color='blue', linewidth=2)
    ax.set_yticklabels([])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_title("Posicionamiento Estratégico FODA", size=15, color='black', y=1.1)
    
    buf = BytesIO()
    plt.savefig(buf, format='PNG', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

def get_apa_styles():
    """Retorna estilos APA para PDF."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='APA_Body', 
        fontName='Times-Roman', 
        fontSize=12, 
        leading=24, 
        alignment=TA_JUSTIFY
    ))
    styles.add(ParagraphStyle(
        name='APA_H1', 
        parent=styles['APA_Body'], 
        fontName='Times-Bold', 
        fontSize=14, 
        alignment=TA_CENTER, 
        spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        name='APA_H2', 
        parent=styles['APA_Body'], 
        fontName='Times-Bold', 
        alignment=TA_LEFT, 
        spaceBefore=12, 
        spaceAfter=6
    ))
    return styles

def generar_pdf_completo(empresa_id: int, version: str, coordinador: str) -> BytesIO:
    """Genera PDF completo del plan estratégico."""
    with get_connection() as conn:
        empresa = pd.read_sql(
            "SELECT * FROM empresas WHERE id=?", 
            conn, 
            params=(empresa_id,)
        ).iloc[0]
        
        df_pest = pd.read_sql(
            """SELECT categoria, factor, tipo_foda, puntaje, importancia, valor_ponderado 
               FROM matrices WHERE empresa_id=? AND tipo_matriz='PEST'""", 
            conn, 
            params=(empresa_id,)
        )
        
        df_foda = pd.read_sql(
            "SELECT cuadrante, factor_fila, factor_columna, impacto FROM foda_cruzado WHERE empresa_id=?", 
            conn, 
            params=(empresa_id,)
        )
    
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer, 
        pagesize=A4, 
        leftMargin=1*inch, 
        rightMargin=1*inch, 
        topMargin=1*inch, 
        bottomMargin=1*inch
    )
    
    styles = get_apa_styles()
    story = []
    
    # Portada
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("Plan Estratégico", styles['APA_H1']))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(empresa['nombre'], styles['APA_H1']))
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph(f"Versión: {version}", styles['APA_Body']))
    story.append(Paragraph(f"Fecha: {pd.Timestamp.now().strftime('%Y-%m-%d')}", styles['APA_Body']))
    story.append(PageBreak())
    
    # Resumen Ejecutivo
    story.append(Paragraph("Resumen Ejecutivo", styles['APA_H1']))
    story.append(Paragraph(
        "Este resumen presenta los hallazgos y recomendaciones clave del diagnóstico estratégico.", 
        styles['APA_Body']
    ))
    story.append(Spacer(1, 24))
    
    analisis_foda_df, resumen_foda, estrategia_principal, puntajes_foda = analizar_foda(df_foda)
    pest_total = float(df_pest['valor_ponderado'].sum()) if not df_pest.empty else 0.0
    
    story.append(Paragraph("Diagnóstico Estratégico General", styles['APA_H2']))
    story.append(Paragraph(
        f"La estrategia principal recomendada es la <b>{estrategia_principal}</b>.", 
        styles['APA_Body']
    ))
    
    # Gráfico FODA
    grafico_foda = generar_grafico_foda_radar(puntajes_foda)
    if grafico_foda:
        story.append(Image(grafico_foda, width=5*inch, height=5*inch))
    story.append(PageBreak())
    
    # Factores críticos
    story.append(Paragraph("Factores Críticos de Éxito", styles['APA_H2']))
    if not df_pest.empty:
        pest_criticos = df_pest.nlargest(5, 'valor_ponderado')
        pest_data = [pest_criticos.columns.tolist()] + pest_criticos.values.tolist()
        pest_table = Table(pest_data, colWidths=[1.2*inch, 2*inch, 1*inch, 0.8*inch, 1*inch, 1*inch])
        pest_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), '#CCCCCC'), 
            ('GRID', (0,0), (-1,-1), 1, '#000000')
        ]))
        story.append(pest_table)
    story.append(PageBreak())
    
    # Objetivos
    story.append(Paragraph("Objetivos Estratégicos Propuestos", styles['APA_H2']))
    planes = generar_planes_por_plantilla(estrategia_principal, pest_total)
    
    for nombre_plan, datos_plan in planes.items():
        story.append(Paragraph(f"<b>{nombre_plan}:</b> {datos_plan['objetivo']}", styles['APA_Body']))
        story.append(Spacer(1, 6))
    story.append(PageBreak())
    
    # Conclusiones
    story.append(Paragraph("Conclusiones y Próximos Pasos", styles['APA_H2']))
    story.append(Paragraph(
        "El éxito de este plan depende de la ejecución disciplinada y el monitoreo constante.", 
        styles['APA_Body']
    ))
    story.append(PageBreak())
    
    # Anexos
    story.append(Paragraph("Anexos: Detalles del Plan Estratégico", styles['APA_H1']))
    story.append(Paragraph("Anexo A: Introducción y Cultura Organizacional", styles['APA_H2']))
    
    campos = [
        ('Nombre', 'nombre'), ('Giro', 'giro'), ('Misión', 'mision'),
        ('Visión', 'vision'), ('Valores', 'valores')
    ]
    
    for label, campo in campos:
        valor = empresa.get(campo, 'N/A') or 'N/A'
        story.append(Paragraph(f"<b>{label}:</b> {valor}", styles['APA_Body']))
    
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

def aplicacion_principal():
    """Función principal de la aplicación."""
    init_db()
    
    with st.sidebar:
        st.header("Gestión de Empresas")
        empresas_df = get_empresas()
        
        if empresas_df.empty:
            st.warning("No hay empresas creadas")
            empresa_seleccionada = None
            empresa_id = None
        else:
            empresa_seleccionada = st.selectbox(
                "Selecciona una Empresa", 
                empresas_df['nombre'], 
                index=None, 
                placeholder="Elige una opción"
            )
            empresa_id = empresas_df[empresas_df['nombre'] == empresa_seleccionada]['id'].iloc[0] if empresa_seleccionada else None
        
        st.divider()
        
        with st.expander("➕ Crear Nueva Empresa"):
            with st.form("new_empresa_form"):
                new_empresa_name = st.text_input("Nombre de la nueva empresa")
                if st.form_submit_button("Crear"):
                    if new_empresa_name:
                        try:
                            with get_connection() as conn:
                                conn.execute(
                                    "INSERT INTO empresas (nombre) VALUES (?)", 
                                    (new_empresa_name,)
                                )
                            st.success(f"Empresa '{new_empresa_name}' creada.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error(f"La empresa '{new_empresa_name}' ya existe.")
                    else:
                        st.warning("El nombre no puede estar vacío.")
        
        if empresa_id and st.button("❌ Eliminar Empresa Seleccionada", type="primary"):
            with get_connection() as conn:
                conn.execute("DELETE FROM empresas WHERE id=?", (empresa_id,))
            st.success(f"Empresa '{empresa_seleccionada}' eliminada.")
            st.rerun()
    
    if not empresa_id:
        st.info("👈 Por favor, selecciona o crea una empresa en el menú lateral para comenzar.")
        return
    
    # Tabs principales
    tab1, tab2, tab_est, tab3, tab4, tab5, tab6 = st.tabs([
        "1. Introducción", "2. Diagnóstico Situacional", "3. Estrategia", 
        "4. Planes Estratégicos", "5. CMI/Indicadores", 
        "6. Operativización/Presupuesto", "7. Resumen y Conclusiones"
    ])
    
    # Tab 1: Introducción
    with tab1:
        st.header("Introducción y Cultura Organizacional")
        
        with get_connection() as conn:
            empresa_data = pd.read_sql(
                "SELECT * FROM empresas WHERE id=?", 
                conn, 
                params=(empresa_id,)
            ).iloc[0]
        
        with st.form("form_intro"):
            st.subheader("Datos Generales")
            nombre = st.text_input("Nombre de la Empresa", empresa_data['nombre'])
            giro = st.text_input("Giro del Negocio", empresa_data['giro'] or "")
            logo_file = st.file_uploader("Subir Logo", type=['png', 'jpg', 'jpeg'])
            
            if empresa_data['logo']:
                st.image(BytesIO(empresa_data['logo']), width=150)
            
            st.divider()
            st.subheader("Cultura Organizacional")
            
            campos_cultura = {
                'objetivo_plan': st.text_area("Objetivo del Plan Estratégico", empresa_data.get('objetivo_plan', '') or ""),
                'mision': st.text_area("Misión", empresa_data['mision'] or ""),
                'vision': st.text_area("Visión", empresa_data['vision'] or ""),
                'obj_general': st.text_area("Objetivo General", empresa_data.get('obj_general', '') or ""),
                'obj_especificos': st.text_area("Objetivos Específicos", empresa_data.get('obj_especificos', '') or ""),
                'politicas': st.text_area("Políticas de la Empresa", empresa_data['politicas'] or ""),
                'valores': st.text_area("Valores y Principios", empresa_data['valores'] or "")
            }
            
            organigrama_file = st.file_uploader("Subir Organigrama", type=['png', 'jpg', 'jpeg'])
            if empresa_data['organigrama']:
                st.image(BytesIO(empresa_data['organigrama']))
            
            if st.form_submit_button("Guardar Introducción"):
                logo_bytes = save_image(logo_file) if logo_file else empresa_data['logo']
                org_bytes = save_image(organigrama_file) if organigrama_file else empresa_data['organigrama']
                
                with get_connection() as conn:
                    conn.execute('''
                        UPDATE empresas SET 
                            nombre=?, giro=?, logo=?, objetivo_plan=?, mision=?, vision=?, 
                            obj_general=?, obj_especificos=?, politicas=?, valores=?, organigrama=?
                        WHERE id=?
                    ''', (
                        nombre, giro, logo_bytes, 
                        campos_cultura['objetivo_plan'], 
                        campos_cultura['mision'], 
                        campos_cultura['vision'],
                        campos_cultura['obj_general'], 
                        campos_cultura['obj_especificos'], 
                        campos_cultura['politicas'], 
                        campos_cultura['valores'], 
                        org_bytes, 
                        empresa_id
                    ))
                st.success("Datos de introducción guardados.")
                st.rerun()
    
    # Tab 2: Diagnóstico
    with tab2:
        st.header("Diagnóstico Situacional (Análisis de Matrices)")
        
        with get_connection() as conn:
            analisis_data = pd.read_sql(
                """SELECT analisis_made, analisis_madi, analisis_posicionamiento, 
                          analisis_pest, analisis_foda 
                   FROM empresas WHERE id=?""", 
                conn, 
                params=(empresa_id,)
            ).iloc[0]
        
        diag_tab1, diag_tab2, diag_tab3, diag_tab4, diag_tab5 = st.tabs([
            "Matriz MADE", "Matriz MADI", "Matriz de Posicionamiento", 
            "Matriz PEST", "Matriz FODA Numérico"
        ])
        
        # Función auxiliar para procesar MADE/MADI
        def procesar_made_madi(data_str: str, tipo: str) -> pd.DataFrame:
            try:
                if isinstance(data_str, pd.DataFrame):
                    data_str = data_str.to_csv(sep='\t', index=False)
                df = pd.read_csv(StringIO(data_str), sep='\t')
                
                # Normalización de columnas
                df.columns = [unicodedata.normalize('NFKD', str(col))
                             .encode('ascii', 'ignore')
                             .decode('utf-8')
                             .lower()
                             .replace(' ', '_')
                             .replace('%', '_percent') for col in df.columns]
                
                mapeo = {
                    'n': 'n', 'variable': 'variable', 'factor': 'factor',
                    'producto': 'producto', 'precio': 'precio', 'plaza': 'plaza',
                    'promocion': 'promocion', 'rating': 'rating',
                    'weight__percent': 'weight_percent', 'weight_percent': 'weight_percent'
                }
                
                df = df.rename(columns=mapeo)
                
                # Procesamiento de columnas P
                p_cols = ['producto', 'precio', 'plaza', 'promocion']
                for col in p_cols:
                    if col not in df.columns:
                        df[col] = "no"
                    else:
                        df[col] = df[col].astype(str).str.lower()
                
                df['total'] = df[p_cols].apply(
                    lambda row: row.str.contains('si', na=False).sum(), axis=1
                )
                
                # Conversiones numéricas
                for col in ['rating', 'weight_percent']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(
                            df[col].astype(str).str.replace(',', '.'), 
                            errors='coerce'
                        ).fillna(0)
                
                df['valor'] = df.get('rating', 0) * (df.get('weight_percent', 0) / 100.0)
                df['empresa_id'] = empresa_id
                df['tipo_matriz'] = tipo
                
                # Seleccionar solo columnas necesarias
                cols_finales = [
                    'empresa_id', 'tipo_matriz', 'variable', 'factor', 
                    'producto', 'precio', 'plaza', 'promocion',
                    'rating', 'weight_percent', 'valor', 'total'
                ]
                return df[[c for c in cols_finales if c in df.columns]]
                
            except Exception as e:
                st.error(f"Error procesando datos: {e}")
                return pd.DataFrame()
        
        # MADE
        with diag_tab1:
            st.subheader("Análisis de Marketing Interno (MADE)")
            
            with st.expander("📋 Pegar datos de MADE desde Excel"):
                made_paste = st.text_area("Pega datos aquí", height=200, key="paste_MADE")
                if st.button("Procesar MADE"):
                    if made_paste:
                        df_made = procesar_made_madi(made_paste, 'MADE')
                        if not df_made.empty:
                            with get_connection() as conn:
                                conn.execute(
                                    "DELETE FROM matriz_marketing WHERE empresa_id=? AND tipo_matriz='MADE'", 
                                    (empresa_id,)
                                )
                                df_made.to_sql('matriz_marketing', conn, if_exists='append', index=False)
                            st.success(f"¡{len(df_made)} filas importadas!")
                            st.rerun()
            
            with get_connection() as conn:
                df_made_db = pd.read_sql(
                    "SELECT * FROM matriz_marketing WHERE empresa_id=? AND tipo_matriz='MADE'",
                    conn,
                    params=(empresa_id,)
                )
            
            if not df_made_db.empty:
                edited = st.data_editor(
                    df_made_db, 
                    key="edit_made",
                    num_rows="dynamic",
                    disabled=['id', 'empresa_id', 'tipo_matriz']
                )
                
                if st.button("💾 Guardar Cambios MADE"):
                    with get_connection() as conn:
                        conn.execute(
                            "DELETE FROM matriz_marketing WHERE empresa_id=? AND tipo_matriz='MADE'",
                            (empresa_id,)
                        )
                        edited.to_sql('matriz_marketing', conn, if_exists='append', index=False)
                    st.success("Guardado")
                    st.rerun()
                
                total = df_made_db['total'].sum()
                st.metric("Puntaje Total MADE", total)
                
                # Análisis automático
                if total >= 3.5:
                    st.success(f"Resultado Fuerte ({total})")
                elif total >= 2.5:
                    st.info(f"Resultado Promedio ({total})")
                else:
                    st.warning(f"Resultado Débil ({total})")
        
        # MADI (similar a MADE, resumido por espacio)
        with diag_tab2:
            st.subheader("Análisis de Marketing Externo (MADI)")
            # ... [Lógica similar a MADE] ...
            st.info("Mismo formato de procesamiento que MADE")
        
        # Posicionamiento
        with diag_tab3:
            st.subheader("Matriz de Posicionamiento")
            
            with get_connection() as conn:
                pos = pd.read_sql(
                    "SELECT posicionamiento_x, posicionamiento_y FROM empresas WHERE id=?",
                    conn,
                    params=(empresa_id,)
                ).iloc[0]
            
            with st.form("form_pos"):
                x = st.number_input("X", value=float(pos['posicionamiento_x'] or 0))
                y = st.number_input("Y", value=float(pos['posicionamiento_y'] or 0))
                if st.form_submit_button("Guardar"):
                    with get_connection() as conn:
                        conn.execute(
                            "UPDATE empresas SET posicionamiento_x=?, posicionamiento_y=? WHERE id=?",
                            (x, y, empresa_id)
                        )
                    st.success("Guardado")
                    st.rerun()
            
            fig, ax = plt.subplots()
            ax.axhline(0, color='gray', lw=1)
            ax.axvline(0, color='gray', lw=1)
            ax.plot(x, y, 'ro', markersize=10)
            ax.set_title("Posicionamiento")
            st.pyplot(fig)
            
            # Interpretación
            if x > 0 and y > 0:
                st.success("Cuadrante Superior Derecho: Diferenciación Premium")
            elif x < 0 and y > 0:
                st.info("Cuadrante Superior Izquierdo: Liderazgo en Valor")
            elif x < 0 and y < 0:
                st.warning("Cuadrante Inferior Izquierdo: Liderazgo en Costos")
            else:
                st.error("Cuadrante Inferior Derecho: Zona de Riesgo")
        
        # PEST
        with diag_tab4:
            st.subheader("Análisis PEST")
            # ... [Implementación similar] ...
        
        # FODA
        with diag_tab5:
            st.subheader("Análisis FODA Cruzado")
            # ... [Implementación similar con manejo de df_foda] ...
    
    # Tab Estrategia
    with tab_est:
        st.header("🎯 Formulación de Estrategias")
        st.info("Generación de 12 estrategias (3 por cuadrante) basadas en FODA Cruzado.")
        
        with get_connection() as conn:
            df_foda_est = pd.read_sql(
                "SELECT cuadrante, factor_fila, factor_columna, impacto FROM foda_cruzado WHERE empresa_id=?",
                conn,
                params=(empresa_id,)
            )
        
        if df_foda_est.empty:
            st.warning("Primero debe completar el Análisis FODA Cruzado.")
        else:
            if st.button("🤖 Generar 12 Estrategias con IA"):
                with st.spinner("Generando..."):
                    contexto = df_foda_est.to_string(index=False)
                    prompt = f"""Basado en este FODA: {contexto}, genera 12 estrategias (3 por cuadrante).
                    Formato: CUADRANTE|ESTRATEGIA|IMPORTANCIA|ACT1;ACT2;ACT3;ACT4;ACT5|PLAN"""
                    
                    resultado = generar_analisis(prompt)
                    
                    nuevas = []
                    for linea in resultado.strip().split("\n"):
                        partes = linea.split("|")
                        if len(partes) >= 5:
                            nuevas.append({
                                "empresa_id": empresa_id,
                                "cuadrante": partes[0].strip().upper(),
                                "estrategia": partes[1].strip(),
                                "importancia": partes[2].strip(),
                                "actividades": partes[3].strip(),
                                "plan_asignado": partes[4].strip()
                            })
                    
                    if nuevas:
                        with get_connection() as conn:
                            conn.execute(
                                "DELETE FROM estrategias_generadas WHERE empresa_id=?",
                                (empresa_id,)
                            )
                            pd.DataFrame(nuevas).to_sql(
                                'estrategias_generadas', 
                                conn, 
                                if_exists='append', 
                                index=False
                            )
                        st.success("Estrategias generadas")
                        st.rerun()
    
    # Tab Planes
    with tab3:
        st.header("Planes Estratégicos")
        st.info("Los planes se generan automáticamente basados en el diagnóstico.")
        
        # Calcular datos necesarios
        with get_connection() as conn:
            df_foda_temp = pd.read_sql(
                "SELECT cuadrante, impacto FROM foda_cruzado WHERE empresa_id=?",
                conn,
                params=(empresa_id,)
            )
            pest_val = pd.read_sql(
                "SELECT valor_ponderado FROM matrices WHERE empresa_id=? AND tipo_matriz='PEST'",
                conn,
                params=(empresa_id,)
            )
        
        _, _, estrategia, _ = analizar_foda(df_foda_temp) if not df_foda_temp.empty else (None, None, "Ofensiva", None)
        pest_score = pest_val['valor_ponderado'].sum() if not pest_val.empty else 3.0
        
        planes = generar_planes_por_plantilla(estrategia or "Ofensiva", pest_score)
        
        for plan, datos in planes.items():
            with st.expander(plan):
                st.write(f"**Objetivo:** {datos['objetivo']}")
    
    # Tab CMI
    with tab4:
        st.header("CMI / Indicadores")
        st.dataframe(generar_cuadro_de_mando(planes))
    
    # Tab Operativización
    with tab5:
        st.header("Operativización / Presupuesto")
        # ... [Implementación de operativización] ...
    
    # Tab Resumen
    with tab6:
        st.header("Resumen y Exportación")
        with st.form("pdf_form"):
            version = st.text_input("Versión", value="1.0")
            coord = st.text_input("Coordinador", value="Consultor")
            if st.form_submit_button("Generar PDF"):
                pdf = generar_pdf_completo(empresa_id, version, coord)
                st.session_state['pdf_file'] = pdf
                st.success("PDF generado")
        
        if st.session_state.get('pdf_file'):
            st.download_button(
                "Descargar PDF",
                st.session_state['pdf_file'],
                file_name=f"Plan_Estrategico_v{version}.pdf",
                mime="application/pdf"
            )

def pantalla_acceso():
    """Pantalla de login/registro."""
    st.sidebar.title("Estratega Pro")
    opcion = st.sidebar.radio("Acceso", ["Entrar", "Crear Cuenta"])
    
    if opcion == "Entrar":
        st.subheader("🔐 Iniciar Sesión")
        email = st.text_input("Correo")
        password = st.text_input("Contraseña", type="password")
        if st.button("Acceder"):
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email, 
                    "password": password
                })
                st.session_state.user = res.user
                st.session_state.logged_in = True
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.subheader("📝 Registro")
        # ... [Formulario de registro] ...

def main():
    init_session_state()
    
    if not st.session_state.logged_in:
        pantalla_acceso()
    else:
        with st.sidebar:
            st.title("♟️ Estratega Pro")
            if st.button("Cerrar Sesión"):
                st.session_state.logged_in = False
                st.rerun()
        aplicacion_principal()

if __name__ == "__main__":
    init_db()
    main()
