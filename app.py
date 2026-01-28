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
from functools import wraps

# Configuración de página
st.set_page_config(
    page_title="Estratega Pro | Business Intelligence", 
    page_icon="♟️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    .permiso-badge { padding: 0.2em 0.6em; border-radius: 0.3em; font-size: 0.8em; font-weight: bold; }
    .permiso-dueño { background-color: #28a745; color: white; }
    .permiso-editor { background-color: #ffc107; color: black; }
    .permiso-lectura { background-color: #17a2b8; color: white; }
    </style>
    """, unsafe_allow_html=True)

def init_supabase():
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
    return sqlite3.connect('strategic_plan.db', timeout=10, check_same_thread=False)

def init_db():
    """Inicializa la base de datos con soporte multi-usuario."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Tabla empresas con user_id (dueño)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS empresas (
                id INTEGER PRIMARY KEY, 
                nombre TEXT NOT NULL, 
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
                analisis_operativo TEXT,
                user_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(nombre, user_id)
            )
        ''')
        
        # Tabla para compartidos: empresa_id, user_email (destinatario), permiso
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS empresa_compartidos (
                id INTEGER PRIMARY KEY,
                empresa_id INTEGER NOT NULL,
                user_email TEXT NOT NULL,
                permiso TEXT NOT NULL CHECK(permiso IN ('lectura', 'editor')),
                shared_by TEXT NOT NULL,
                fecha_compartido TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE,
                UNIQUE(empresa_id, user_email)
            )
        ''')
        
        # Tablas existentes...
        cursor.execute('''
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
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS foda_cruzado (
                id INTEGER PRIMARY KEY, 
                empresa_id INTEGER, 
                cuadrante TEXT, 
                factor_fila TEXT, 
                factor_columna TEXT, 
                impacto INTEGER,
                FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
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
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS perdida_ganancia (
                id INTEGER PRIMARY KEY,
                empresa_id INTEGER NOT NULL, 
                anio TEXT, 
                ingresos REAL, 
                egresos REAL, 
                resultado REAL,
                FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
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
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS punto_equilibrio (
                id INTEGER PRIMARY KEY,
                empresa_id INTEGER NOT NULL, 
                costo_fijo_total REAL, 
                precio_venta_unidad REAL,
                costo_variable_unidad REAL, 
                unidades_producidas REAL,
                FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
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
        ''')
        
        cursor.execute('''
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
        
        # Verificar y agregar columnas faltantes
        try:
            cursor.execute("SELECT user_id FROM empresas LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE empresas ADD COLUMN user_id TEXT")
            
        columnas = ['objetivo_plan', 'obj_general', 'obj_especificos', 
                   'analisis_cmi', 'analisis_operativo']
        for col in columnas:
            try:
                cursor.execute(f"SELECT {col} FROM empresas LIMIT 1")
            except:
                cursor.execute(f"ALTER TABLE empresas ADD COLUMN {col} TEXT")
        
        conn.commit()

def get_user_permissions(empresa_id, user_email):
    """
    Retorna el nivel de permiso del usuario sobre la empresa.
    'dueño', 'editor', 'lectura', o None
    """
    if not user_email:
        return None
        
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar si es dueño
        cursor.execute(
            "SELECT 1 FROM empresas WHERE id=? AND user_id=?", 
            (empresa_id, user_email)
        )
        if cursor.fetchone():
            return 'dueño'
        
        # Verificar si tiene permisos compartidos
        cursor.execute(
            "SELECT permiso FROM empresa_compartidos WHERE empresa_id=? AND user_email=?",
            (empresa_id, user_email)
        )
        result = cursor.fetchone()
        if result:
            return result[0]
    
    return None

def can_edit(permiso):
    """Verifica si el permiso permite editar."""
    return permiso in ['dueño', 'editor']

def can_share(permiso):
    """Solo el dueño puede compartir."""
    return permiso == 'dueño'

def can_delete(permiso):
    """Solo el dueño puede eliminar."""
    return permiso == 'dueño'

def get_empresas_para_usuario(user_email):
    """Retorna empresas donde el usuario es dueño o tiene acceso compartido."""
    if not user_email:
        return pd.DataFrame()
    
    with get_connection() as conn:
        # Empresas donde es dueño o compartido, con indicador de permiso
        query = """
        SELECT DISTINCT 
            e.id, 
            e.nombre, 
            e.giro,
            e.user_id,
            CASE 
                WHEN e.user_id = ? THEN 'Dueño'
                ELSE ec.permiso 
            END as permiso,
            CASE 
                WHEN e.user_id = ? THEN 0 
                ELSE 1 
            END as orden
        FROM empresas e
        LEFT JOIN empresa_compartidos ec ON e.id = ec.empresa_id AND ec.user_email = ?
        WHERE e.user_id = ? OR ec.user_email = ?
        ORDER BY orden, e.nombre
        """
        return pd.read_sql(query, conn, params=(user_email, user_email, user_email, user_email, user_email))

def compartir_empresa(empresa_id, email_destinatario, permiso, shared_by):
    """Comparte empresa con otro usuario."""
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO empresa_compartidos 
                   (empresa_id, user_email, permiso, shared_by) 
                   VALUES (?, ?, ?, ?)""",
                (empresa_id, email_destinatario.lower().strip(), permiso, shared_by)
            )
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Error al compartir: {e}")
        return False

def eliminar_compartido(empresa_id, email_usuario):
    """Elimina acceso compartido."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM empresa_compartidos WHERE empresa_id=? AND user_email=?",
            (empresa_id, email_usuario)
        )
        conn.commit()

def get_compartidos_empresa(empresa_id):
    """Lista usuarios con quienes se compartió la empresa."""
    with get_connection() as conn:
        return pd.read_sql(
            "SELECT user_email, permiso, fecha_compartido FROM empresa_compartidos WHERE empresa_id=?",
            conn,
            params=(empresa_id,)
        )

def get_ia_client():
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("❌ No se encontró la API Key de Gemini en st.secrets")
        st.stop()
    genai.configure(api_key=api_key)
    return True

def generar_analisis(prompt):
    if not get_ia_client():
        return "Error: No se pudo configurar el cliente de IA."
    
    prompt_limpio = prompt + "\n\nIMPORTANTE: Proporciona el análisis en texto claro y profesional. NO uses asteriscos (*), almohadillas (#), negritas ni ningún formato Markdown."
    
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
                texto = re.sub(r'[\*#_`]', '', texto)
                return texto.strip()
            except Exception:
                continue
    except Exception as e:
        return f"Error de conexión: {str(e)}"
            
    return "Error en análisis. No se pudo generar contenido."

def generar_analisis_ia(tipo_matriz, datos_contexto):
    prompt = f"Actúa como un consultor senior de estrategia. Analiza la siguiente matriz {tipo_matriz} y proporciona conclusiones estratégicas clave, riesgos y recomendaciones. Datos: {datos_contexto}"
    return generar_analisis(prompt)

def save_image(uploaded_file):
    if uploaded_file:
        return uploaded_file.getvalue()
    return None

def analizar_foda(df_foda):
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

def generar_planes_por_plantilla(estrategia_foda, pest_total):
    planes = {}
    
    planes['Plan Administrativo'] = {
        'introduccion': "Fortalecer la base organizacional y fomentar innovación continua.",
        'objetivo': "Implementar programa de formación en liderazgo para mandos medios en 6 meses."
    }
    
    planes['Plan Operativo'] = {
        'introduccion': "Optimizar cadena de valor y escalar operaciones eficientemente.",
        'objetivo': "Reducir tiempos de entrega en 15% durante el próximo año."
    }
    
    if "Ofensiva" in estrategia_foda or "Adaptativa" in estrategia_foda:
        intro_tec = "Invertir en innovación tecnológica para ganar ventaja competitiva."
        obj_tec = "Implementar CRM/ERP en 9 meses para mejorar eficiencia."
    else:
        intro_tec = "Robustecer operación actual, priorizando seguridad y estabilidad."
        obj_tec = "Auditoría de ciberseguridad completa y actualización de sistemas críticos."
    planes['Plan Tecnológico'] = {'introduccion': intro_tec, 'objetivo': obj_tec}
    
    if "Ofensiva" in estrategia_foda or "Adaptativa" in estrategia_foda:
        intro_fin = "Asegurar fondos para expansión."
        obj_fin = "Preparar ronda de financiación o línea de crédito en 6 meses."
    else:
        intro_fin = "Gestión prudente con enfoque en optimización de costos y liquidez."
        obj_fin = "Reducir costos no esenciales para mejorar margen neto en 2% en 6 meses."
    planes['Plan Financiero'] = {'introduccion': intro_fin, 'objetivo': obj_fin}
    
    planes['Plan de Monitoreo y control'] = {
        'introduccion': "Sistema de monitoreo ágil para asegurar cumplimiento de objetivos.",
        'objetivo': "Dashboard de KPIs en tiempo real y revisión estratégica mensual."
    }
    
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
    
    if pest_total < 2.5:
        intro_con = f"Entorno vulnerable (PEST: {pest_total:.2f}). Desarrollar planes de mitigación."
        obj_con = "Formar comité de riesgos que identifique 3 principales riesgos externos en 2 meses."
    else:
        intro_con = f"Buena respuesta al entorno (PEST: {pest_total:.2f}). Enfoque en vigilancia proactiva."
        obj_con = "Sistema de vigilancia trimestral y simulacro de crisis anual."
    planes['Plan de Contingencia'] = {'introduccion': intro_con, 'objetivo': obj_con}
    
    return planes

def generar_cuadro_de_mando(planes):
    cmi_data = []
    for nombre_plan, datos_plan in planes.items():
        objetivo = datos_plan['objetivo'].lower()
        perspectiva = 'Procesos Internos'
        if any(k in objetivo for k in ['margen', 'costo', 'ingreso', 'financiar', 'cuota', 'rentabilidad']):
            perspectiva = 'Financiera'
        elif any(k in objetivo for k in ['cliente', 'retención', 'abandono', 'satisfacción']):
            perspectiva = 'Clientes'
        elif any(k in objetivo for k in ['capacitación', 'habilidades', 'liderazgo', 'cultura', 'innovación']):
            perspectiva = 'Aprendizaje y Crecimiento'
        cmi_data.append([perspectiva, datos_plan['objetivo'], "Por definir", "Por definir", f"Proyecto: {nombre_plan}"])
    
    df_cmi = pd.DataFrame(cmi_data, columns=['Perspectiva', 'Objetivo Estratégico', 'KPI', 'Meta', 'Iniciativa'])
    perspectiva_orden = ['Financiera', 'Clientes', 'Procesos Internos', 'Aprendizaje y Crecimiento']
    df_cmi['Perspectiva'] = pd.Categorical(df_cmi['Perspectiva'], categories=perspectiva_orden, ordered=True)
    return df_cmi.sort_values(by='Perspectiva').reset_index(drop=True)

def generar_grafico_foda_radar(puntajes):
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
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='APA_Body', fontName='Times-Roman', fontSize=12, leading=24, alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name='APA_H1', parent=styles['APA_Body'], fontName='Times-Bold', fontSize=14, alignment=TA_CENTER, spaceAfter=12))
    styles.add(ParagraphStyle(name='APA_H2', parent=styles['APA_Body'], fontName='Times-Bold', alignment=TA_LEFT, spaceBefore=12, spaceAfter=6))
    return styles

def generar_pdf_completo(empresa_id, version, coordinador):
    with get_connection() as conn:
        empresa = pd.read_sql("SELECT * FROM empresas WHERE id=?", conn, params=(empresa_id,)).iloc[0]
        df_pest = pd.read_sql("SELECT * FROM matrices WHERE empresa_id=? AND tipo_matriz='PEST'", conn, params=(empresa_id,))
        df_foda = pd.read_sql("SELECT * FROM foda_cruzado WHERE empresa_id=?", conn, params=(empresa_id,))
    
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, leftMargin=1*inch, rightMargin=1*inch, topMargin=1*inch, bottomMargin=1*inch)
    styles = get_apa_styles()
    story = []
    
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("Plan Estratégico", styles['APA_H1']))
    story.append(Paragraph(empresa['nombre'], styles['APA_H1']))
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph(f"Versión: {version}", styles['APA_Body']))
    story.append(PageBreak())
    
    analisis_foda_df, resumen_foda, estrategia_principal, puntajes_foda = analizar_foda(df_foda)
    pest_total = df_pest['valor_ponderado'].sum() if not df_pest.empty else 0
    
    story.append(Paragraph("Resumen Ejecutivo", styles['APA_H1']))
    story.append(Paragraph(f"Estrategia principal: {estrategia_principal}", styles['APA_Body']))
    
    grafico_foda = generar_grafico_foda_radar(puntajes_foda)
    if grafico_foda:
        story.append(Image(grafico_foda, width=5*inch, height=5*inch))
    
    planes = generar_planes_por_plantilla(estrategia_principal, pest_total)
    for nombre_plan, datos_plan in planes.items():
        story.append(Paragraph(f"<b>{nombre_plan}:</b> {datos_plan['objetivo']}", styles['APA_Body']))
    
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

def aplicacion_principal():
    init_db()
    
    user_email = st.session_state.user.email if st.session_state.user else None
    
    with st.sidebar:
        st.header("Gestión de Empresas")
        
        empresas_df = get_empresas_para_usuario(user_email)
        
        if empresas_df.empty:
            st.info("No tienes empresas. Crea una nueva.")
            empresa_seleccionada = None
            empresa_id = None
            permiso_actual = None
        else:
            # Mostrar con indicador de permiso
            opciones = []
            for _, row in empresas_df.iterrows():
                permiso_icon = "👑" if row['permiso'] == 'Dueño' else ("✏️" if row['permiso'] == 'editor' else "👁️")
                opciones.append(f"{permiso_icon} {row['nombre']} ({row['permiso']})")
            
            seleccion = st.selectbox("Selecciona Empresa", opciones, index=None, placeholder="Elige una opción")
            
            if seleccion:
                # Extraer nombre de la selección
                nombre_sel = seleccion.split(" (")[0][2:]  # Quitar icono y permiso
                empresa_row = empresas_df[empresas_df['nombre'] == nombre_sel].iloc[0]
                empresa_id = int(empresa_row['id'])
                permiso_actual = empresa_row['permiso']
                st.session_state['empresa_id'] = empresa_id
                st.session_state['permiso'] = permiso_actual
            else:
                empresa_id = None
                permiso_actual = None
        
        st.divider()
        
        # Información de permiso actual
        if permiso_actual:
            color_class = f"permiso-{permiso_actual.lower()}" if permiso_actual != 'Dueño' else "permiso-dueño"
            st.markdown(f"""
            <div style='text-align: center;'>
                <span class='permiso-badge {color_class}'>
                    {permiso_actual}
                </span>
            </div>
            """, unsafe_allow_html=True)
            
            if permiso_actual == 'lectura':
                st.info("🔒 Modo Solo Lectura. No puedes modificar datos.")
            elif permiso_actual == 'editor':
                st.info("✏️ Modo Editor. Puedes modificar pero no eliminar.")
        
        st.divider()
        
        # Crear nueva empresa (disponible para todos)
        with st.expander("➕ Crear Nueva Empresa"):
            with st.form("new_empresa_form"):
                new_empresa_name = st.text_input("Nombre de la nueva empresa")
                if st.form_submit_button("Crear"):
                    if new_empresa_name:
                        try:
                            with get_connection() as conn:
                                conn.execute(
                                    "INSERT INTO empresas (nombre, user_id) VALUES (?, ?)", 
                                    (new_empresa_name, user_email)
                                )
                                conn.commit()
                            st.success(f"Empresa '{new_empresa_name}' creada.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error(f"Ya tienes una empresa con ese nombre.")
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.warning("El nombre no puede estar vacío.")
        
        # Opciones solo para dueño
        if empresa_id and can_delete(permiso_actual):
            if st.button("❌ Eliminar Empresa", type="primary"):
                with get_connection() as conn:
                    conn.execute("DELETE FROM empresas WHERE id=?", (empresa_id,))
                    conn.commit()
                st.success("Empresa eliminada.")
                st.rerun()
            
            st.divider()
            st.subheader("🔗 Compartir Empresa")
            
            with st.form("compartir_form"):
                email_share = st.text_input("Email del usuario")
                tipo_permiso = st.selectbox("Permiso", ["lectura", "editor"])
                if st.form_submit_button("Compartir"):
                    if email_share and email_share != user_email:
                        if compartir_empresa(empresa_id, email_share, tipo_permiso, user_email):
                            st.success(f"Compartido con {email_share} como {tipo_permiso}")
                            st.rerun()
                    else:
                        st.error("Email inválido o es tu propio email")
            
            # Mostrar compartidos actuales
            compartidos = get_compartidos_empresa(empresa_id)
            if not compartidos.empty:
                st.caption("Actualmente compartido con:")
                for _, comp in compartidos.iterrows():
                    cols = st.columns([3, 2, 1])
                    cols[0].write(comp['user_email'])
                    cols[1].badge(comp['permiso'])
                    if cols[2].button("🗑️", key=f"del_{comp['user_email']}"):
                        eliminar_compartido(empresa_id, comp['user_email'])
                        st.rerun()
    
    if not empresa_id:
        st.info("👈 Selecciona o crea una empresa para comenzar.")
        return
    
    # Verificar permisos antes de cargar datos
    permiso = st.session_state.get('permiso')
    puede_editar = can_edit(permiso)
    es_dueño = can_delete(permiso)  # Solo dueño puede eliminar
    
    # Cargar datos
    with get_connection() as conn:
        empresa_data_full = pd.read_sql("SELECT * FROM empresas WHERE id=?", conn, params=(empresa_id,))
        if empresa_data_full.empty:
            st.error("Error: Empresa no encontrada.")
            return
        empresa_data = empresa_data_full.iloc[0]
    
    # Tabs
    tabs = ["1. Introducción", "2. Diagnóstico", "3. Estrategia", "4. Planes", "5. CMI", "6. Operativización", "7. Resumen"]
    tab1, tab2, tab_est, tab3, tab4, tab5, tab6 = st.tabs(tabs)
    
    with tab1:
        st.header("Introducción y Cultura Organizacional")
        
        if not puede_editar:
            st.warning("🔒 Solo lectura. Contacta al dueño para modificar.")
        
        with st.form("form_intro"):
            nombre = st.text_input("Nombre", empresa_data['nombre'], disabled=not puede_editar)
            giro = st.text_input("Giro", empresa_data['giro'] or "", disabled=not puede_editar)
            
            if empresa_data['logo']:
                st.image(BytesIO(empresa_data['logo']), width=150)
            
            if puede_editar:
                logo_file = st.file_uploader("Subir Logo", type=['png', 'jpg', 'jpeg'])
            else:
                logo_file = None
            
            objetivo_plan = st.text_area("Objetivo del Plan", empresa_data.get('objetivo_plan', '') or "", disabled=not puede_editar)
            mision = st.text_area("Misión", empresa_data['mision'] or "", disabled=not puede_editar)
            vision = st.text_area("Visión", empresa_data['vision'] or "", disabled=not puede_editar)
            
            if puede_editar:
                if st.form_submit_button("Guardar"):
                    logo_bytes = save_image(logo_file) if logo_file else empresa_data['logo']
                    with get_connection() as conn:
                        conn.execute('''
                            UPDATE empresas SET 
                                nombre=?, giro=?, logo=?, objetivo_plan=?, mision=?, vision=?
                            WHERE id=?
                        ''', (nombre, giro, logo_bytes, objetivo_plan, mision, vision, empresa_id))
                        conn.commit()
                    st.success("Guardado.")
                    st.rerun()
            else:
                st.form_submit_button("Guardar", disabled=True)
    
    with tab2:
        st.header("Diagnóstico Situacional")
        
        diag_tab1, diag_tab2 = st.tabs(["MADE", "MADI"])
        
        with diag_tab1:
            st.subheader("Matriz MADE")
            if not puede_editar:
                st.info("Modo lectura")
            # Aquí iría el código de MADE con disabled=not puede_editar
        
        with diag_tab2:
            st.subheader("Matriz MADI")
            if not puede_editar:
                st.info("Modo lectura")
    
    with tab_est:
        st.header("Estrategias")
        # Similar con controles de permiso
    
    with tab3:
        st.header("Planes Estratégicos")
    
    with tab4:
        st.header("CMI")
    
    with tab5:
        st.header("Operativización")
        if not puede_editar:
            st.warning("No tienes permisos para editar la operativización.")
    
    with tab6:
        st.header("Resumen y Exportación")
        if st.button("Generar PDF"):
            pdf = generar_pdf_completo(empresa_id, "1.0", "Consultor")
            st.download_button("Descargar", pdf, "plan.pdf")

def pantalla_acceso():
    st.sidebar.title("Estratega Pro")
    opcion = st.sidebar.radio("Acceso", ["Entrar", "Crear Cuenta"])
    
    if opcion == "Entrar":
        st.subheader("🔐 Iniciar Sesión")
        email = st.text_input("Correo")
        password = st.text_input("Contraseña", type="password")
        if st.button("Acceder"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.session_state.logged_in = True
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.subheader("📝 Registro")
        nombre = st.text_input("Nombre Completo")
        correo = st.text_input("Correo")
        clave = st.text_input("Contraseña", type="password")
        if st.button("Registrarse"):
            try:
                res = supabase.auth.sign_up({
                    "email": correo, 
                    "password": clave,
                    "options": {"data": {"full_name": nombre}}
                })
                st.success("Registrado. Verifica tu email.")
            except Exception as e:
                st.error(f"Error: {e}")

def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user = None
    
    if not st.session_state.logged_in:
        pantalla_acceso()
    else:
        with st.sidebar:
            st.title("♟️ Estratega Pro")
            st.write(f"Usuario: {st.session_state.user.email}")
            if st.button("Cerrar Sesión"):
                st.session_state.logged_in = False
                st.session_state.user = None
                st.rerun()
        aplicacion_principal()

if __name__ == "__main__":
    init_db()
    main()
