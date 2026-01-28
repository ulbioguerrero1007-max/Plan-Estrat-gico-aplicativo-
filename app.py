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
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import unicodedata
import time
from supabase import create_client, Client

def get_ia_client():
    api_key = st.secrets.get("GEMINI_API_KEY")

    if not api_key:
        st.error("❌ No se encontró la API Key de Gemini en st.secrets")
        st.stop()
    
    genai.configure(api_key=api_key)
    return True # Retornamos True solo para indicar que está configurado

def generar_analisis_ia(tipo_matriz, datos_contexto):
    if not get_ia_client():
        return "Error: No se encontró la API Key de Gemini en st.secrets."
    
    prompt = f"Actúa como un consultor senior de estrategia. Analiza la siguiente matriz {tipo_matriz} y proporciona conclusiones estratégicas clave, riesgos y recomendaciones. Datos: {datos_contexto}"
    
    return generar_analisis(prompt)

def generar_analisis(prompt, client=None):
    errores = []
    # Limpiar el prompt para pedir texto sin formato excesivo
    prompt_limpio = prompt + "\n\nIMPORTANTE: Proporciona el análisis en texto claro y profesional. NO uses asteriscos (*), almohadillas (#), negritas ni ningún formato Markdown. Usa solo párrafos bien estructurados."
    
    try:
        modelos_disponibles = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        modelos_a_probar = []
        modelos_a_probar.extend([m for m in modelos_disponibles if 'flash' in m.lower()])
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
                # CORRECIÓN: Limpieza de formato Markdown solicitada
                texto = re.sub(r'\*+', '', texto)
                texto = re.sub(r'#+', '', texto)
                texto = re.sub(r'_+', '', texto)
                texto = texto.replace("****", "").replace("###", "").replace("##", "")
                return texto.strip()
            except Exception as e:
                errores.append(f"{nombre_modelo}: {str(e)}")
                continue
    except Exception as e:
        return f"Error de conexión: {str(e)}"
            
    return f"Error en análisis. Intentados: {', '.join(errores)}"

st.set_page_config( page_title="Estratega Pro | Business Intelligence", page_icon="♟️", layout="wide",
    initial_sidebar_state="expanded")
st.markdown("""
    <style>
    .main { background-color:
    .stButton>button { width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color:
        color: white;
        border: none;}
    h1, h2, h3 { color:
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
    return sqlite3.connect('strategic_plan.db', timeout=10)
def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS empresas (
                            id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE, giro TEXT, logo BLOB, 
                            objetivo_plan TEXT, mision TEXT, vision TEXT, obj_general TEXT, obj_especificos TEXT,
                            organigrama BLOB, politicas TEXT, valores TEXT,
                            posicionamiento_x REAL, posicionamiento_y REAL, analisis_posicionamiento TEXT,
                            analisis_pest TEXT, analisis_foda TEXT, analisis_made TEXT, analisis_madi TEXT
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS matrices (id INTEGER PRIMARY KEY, empresa_id INTEGER, tipo_matriz TEXT NOT NULL, categoria TEXT, factor TEXT, tipo_foda TEXT, puntaje REAL, importancia REAL, valor_ponderado REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS foda_cruzado (id INTEGER PRIMARY KEY, empresa_id INTEGER, cuadrante TEXT, factor_fila TEXT, factor_columna TEXT, impacto INTEGER, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS finanzas_planes (id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL, nombre_plan TEXT NOT NULL, costo_implementacion REAL, beneficio_anual_esperado REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE, UNIQUE(empresa_id, nombre_plan))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS operativizacion ( id INTEGER PRIMARY KEY,
                            empresa_id INTEGER NOT NULL, plan TEXT, estrategia TEXT, actividades TEXT, plazo TEXT,
                            responsable TEXT, recurso TEXT, costo REAL,
                            FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS perdida_ganancia ( id INTEGER PRIMARY KEY,
                            empresa_id INTEGER NOT NULL, anio TEXT, ingresos REAL, egresos REAL, resultado REAL,
                            FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS flujo_caja ( id INTEGER PRIMARY KEY, empresa_id INTEGER NOT NULL,
                            anio_proyeccion INTEGER, saldo_inicial REAL, ingreso REAL, egreso REAL, flujo_neto REAL,
                            saldo_final REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS punto_equilibrio ( id INTEGER PRIMARY KEY,
                            empresa_id INTEGER NOT NULL, costo_fijo_total REAL, precio_venta_unidad REAL,
                            costo_variable_unidad REAL, unidades_producidas REAL,
                            FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS matriz_marketing ( id INTEGER PRIMARY KEY,
                            empresa_id INTEGER NOT NULL, tipo_matriz TEXT NOT NULL, variable TEXT, factor TEXT,
                            producto TEXT, precio TEXT, plaza TEXT, promocion TEXT, rating REAL, weight_percent REAL,
                            valor REAL, total INTEGER,
                            FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS estrategias_generadas (
                            id INTEGER PRIMARY KEY,
                            empresa_id INTEGER NOT NULL,
                            cuadrante TEXT NOT NULL,
                            estrategia TEXT NOT NULL,
                            importancia TEXT NOT NULL,
                            actividades TEXT NOT NULL,
                            plan_asignado TEXT,
                            FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
                          )''')
        columnas_existentes = [c[1] for c in cursor.execute("PRAGMA table_info(empresas)").fetchall()]
        nuevas_columnas = ['objetivo_plan', 'obj_general', 'obj_especificos', 'posicionamiento_x', 'posicionamiento_y', 'analisis_posicionamiento', 'analisis_pest', 'analisis_foda', 'analisis_made', 'analisis_madi', 'analisis_cmi', 'analisis_operativo']
        for col in nuevas_columnas:
            if col not in columnas_existentes:
                cursor.execute(f"ALTER TABLE empresas ADD COLUMN {col} TEXT")
        
        # Verificar columna plan_asignado en estrategias_generadas
        cols_estrategias = [c[1] for c in cursor.execute("PRAGMA table_info(estrategias_generadas)").fetchall()]
        if 'plan_asignado' not in cols_estrategias:
            cursor.execute("ALTER TABLE estrategias_generadas ADD COLUMN plan_asignado TEXT")
        conn.commit()
def get_empresas():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, nombre FROM empresas", conn)
def save_image(uploaded_file):
    if uploaded_file:
        return uploaded_file.getvalue()
    return None
def analizar_foda(df_foda):
    if df_foda.empty: return None, None, None, pd.Series(dtype='float64')
    estrategias = {'FO': 'Ofensiva (F+O)', 'FA': 'Defensiva (F+A)', 'DO': 'Adaptativa (D+O)', 'DA': 'Supervivencia (D+A)'}
    puntajes = df_foda.groupby('cuadrante')['impacto'].sum().reindex(estrategias.keys(), fill_value=0)
    # Ordenar puntajes de mayor a menor para el radar y el análisis
    puntajes_ordenados = puntajes.sort_values(ascending=False)
    analisis_df = pd.DataFrame({
        'Estrategia': [estrategias[c] for c in puntajes_ordenados.index],
        'Puntaje Total': puntajes_ordenados.values
    }).reset_index(drop=True)
    estrategia_principal = analisis_df.iloc[0]['Estrategia']
    resumen = f"La estrategia principal recomendada es **{analisis_df.iloc[0]['Estrategia']}** ({analisis_df.iloc[0]['Puntaje Total']} puntos), seguida por **{analisis_df.iloc[1]['Estrategia']}** ({analisis_df.iloc[1]['Puntaje Total']} puntos)."
    return analisis_df, resumen, estrategia_principal, puntajes_ordenados
def generar_planes_por_plantilla(estrategia_foda, pest_total):
    planes = {}
    
    # 1. Plan Administrativo
    planes['Plan Administrativo'] = {
        'introduccion': "El plan administrativo se enfocará en fortalecer la base de la organización y fomentar la innovación continua.",
        'objetivo': "Implementar un programa de formación en liderazgo y gestión de proyectos para los mandos medios en los próximos 6 meses."
    }
    
    # 2. Plan Operativo
    planes['Plan Operativo'] = {
        'introduccion': "El plan operativo se enfocará en optimizar la cadena de valor y escalar las operaciones de manera eficiente para soportar el crecimiento.",
        'objetivo': "Optimizar los procesos críticos de producción/servicio para reducir los tiempos de entrega en un 15% en el próximo año."
    }
    
    # 3. Plan Tecnológico
    if "Ofensiva" in estrategia_foda or "Adaptativa" in estrategia_foda:
        intro_tec = "La estrategia de crecimiento requiere un apalancamiento tecnológico. Se debe invertir en innovación para ganar ventaja competitiva."
        obj_tec = "Evaluar e implementar una nueva herramienta de CRM o ERP en los próximos 9 meses para mejorar la relación con clientes y la eficiencia operativa."
    else:
        intro_tec = "La tecnología debe usarse para robustecer la operación y defender la posición actual. La prioridad es la seguridad y la estabilidad."
        obj_tec = "Realizar una auditoría de ciberseguridad completa en el próximo trimestre y actualizar los sistemas críticos para mitigar vulnerabilidades."
    planes['Plan Tecnológico'] = {'introduccion': intro_tec, 'objetivo': obj_tec}
    
    # 4. Plan Financiero
    if "Ofensiva" in estrategia_foda or "Adaptativa" in estrategia_foda:
        intro_fin = "El entorno es favorable y la estrategia es de crecimiento. El plan financiero debe enfocarse en asegurar los fondos para la expansión."
        obj_fin = "Preparar un caso de negocio y una ronda de financiación (o asegurar una línea de crédito) en los próximos 6 meses para financiar las nuevas iniciativas estratégicas."
    else:
        intro_fin = "La situación financiera debe ser gestionada con prudencia. La prioridad es la optimización de costos, la gestión de la liquidez y la maximización de la rentabilidad actual."
        obj_fin = "Implementar un plan de reducción de costos no esenciales para mejorar el margen de beneficio neto en un 2% en los próximos 6 meses, sin afectar la operación crítica."
    planes['Plan Financiero'] = {'introduccion': intro_fin, 'objetivo': obj_fin}
    
    # 5. Plan de Monitoreo y control
    planes['Plan de Monitoreo y control'] = {
        'introduccion': "Dado que la estrategia implica nuevas iniciativas y crecimiento, se requiere un sistema de monitoreo ágil y riguroso para asegurar que los objetivos se cumplan.",
        'objetivo': "Implementar un dashboard de KPIs (Indicadores Clave) en tiempo real para los nuevos proyectos y establecer un ciclo de revisión estratégica mensual."
    }
    
    # 6. Plan de Mejora
    if "Ofensiva" in estrategia_foda:
        intro_mej = "La posición estratégica es Ofensiva. El plan debe centrarse en usar las fortalezas para capitalizar al máximo las oportunidades de mercado."
        obj_mej = "Lanzar una nueva línea de producto/servicio que explote nuestras fortalezas en los próximos 12 meses, para capturar un 5% más de cuota de mercado."
    elif "Adaptativa" in estrategia_foda:
        intro_mej = "La estrategia recomendada es Adaptativa. Se deben desarrollar áreas internas para poder aprovechar las oportunidades externas."
        obj_mej = "Iniciar un programa de capacitación técnica en el próximo trimestre para cerrar brechas de debilidades y abordar 2 nuevas oportunidades de mercado."
    else:
        intro_mej = "La estrategia es Defensiva/Supervivencia. La prioridad es proteger la posición actual, usando fortalezas para mitigar amenazas."
        obj_mej = "Implementar un plan de retención de clientes clave en los próximos 6 meses, para reducir la tasa de abandono en un 10%."
    planes['Plan de Mejora'] = {'introduccion': intro_mej, 'objetivo': obj_mej}
    
    # 7. Plan de Contingencia
    if pest_total < 2.5:
        intro_con = f"El análisis del entorno (PEST: {pest_total:.2f}) revela vulnerabilidad a factores externos. Es crucial desarrollar planes para mitigar riesgos."
        obj_con = "Formar un comité de gestión de riesgos que, en 2 meses, identifique los 3 principales riesgos externos y desarrolle un plan de respuesta específico."
    else:
        intro_con = f"La empresa muestra buena respuesta al entorno (PEST: {pest_total:.2f}). El plan se enfocará en la monitorización proactiva de eventos inesperados."
        obj_con = "Establecer un sistema de vigilancia del entorno trimestral y realizar un simulacro de crisis anual."
    planes['Plan de Contingencia'] = {'introduccion': intro_con, 'objetivo': obj_con}
    
    return planes

def generar_cuadro_de_mando_ia(estrategias_df):
    """
    Genera el CMI utilizando IA basado en las estrategias generadas.
    """
    if estrategias_df.empty:
        return pd.DataFrame(columns=['Estrategia', 'Perspectiva', 'KPIs', 'Formulas', 'Frecuencia', 'LI', 'LC', 'LS'])
    
    contexto_estrategias = ""
    for _, row in estrategias_df.iterrows():
        contexto_estrategias += f"- Estrategia: {row['estrategia']} (Plan: {row['plan_asignado']})\n"
    
    prompt = f"""Actúa como un experto en Balanced Scorecard. Basado en las siguientes estrategias:
{contexto_estrategias}

Genera una tabla de Cuadro de Mando Integral (CMI) con las siguientes columnas exactas:
1. (estrategia): La estrategia proporcionada.
2. (perspectiva): A qué perspectiva corresponde (Financiera, Cliente, Procesos, Aprendizaje y Control).
3. (KPIs): El indicador clave de desempeño que medirá la estrategia.
4. (Formulas): La fórmula de cálculo del KPI.
5. (Frecuencia): Cada cuánto se mide (Mensual, Trimestral, etc.).
6. (LI): Límite Inferior (Rojo/Crítico).
7. (LC): Límite de Control (Amarillo/Preventivo).
8. (LS): Límite Superior (Verde/Satisfactorio).

Formato de salida: ESTRATEGIA|PERSPECTIVA|KPI|FORMULA|FRECUENCIA|LI|LC|LS
No incluyas encabezados ni texto adicional, solo las líneas de datos separadas por pipe (|)."""

    resultado_ia = generar_analisis(prompt)
    
    cmi_rows = []
    for line in resultado_ia.strip().split("\n"):
        partes = line.split("|")
        if len(partes) >= 8:
            cmi_rows.append({
                "Estrategia": partes[0].strip(),
                "Perspectiva": partes[1].strip(),
                "KPIs": partes[2].strip(),
                "Formulas": partes[3].strip(),
                "Frecuencia": partes[4].strip(),
                "LI": partes[5].strip(),
                "LC": partes[6].strip(),
                "LS": partes[7].strip()
            })
    
    df_cmi = pd.DataFrame(cmi_rows)
    perspectiva_orden = ['Financiera', 'Cliente', 'Procesos', 'Aprendizaje y Control']
    df_cmi['Perspectiva'] = pd.Categorical(df_cmi['Perspectiva'], categories=perspectiva_orden, ordered=True)
    return df_cmi.sort_values(by='Perspectiva').reset_index(drop=True)
def generar_grafico_foda_radar(puntajes):
    if puntajes is None or puntajes.empty: return None
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
def generar_grafico_pest_bar(df_pest):
    if df_pest.empty: return None
    pest_scores = df_pest.groupby('categoria')['valor_ponderado'].sum()
    fig, ax = plt.subplots(figsize=(7, 4))
    pest_scores.plot(kind='barh', ax=ax, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'])
    ax.set_title('Puntuación Ponderada por Categoría PEST')
    ax.set_xlabel('Suma de Valores Ponderados')
    buf = BytesIO()
    plt.savefig(buf, format='PNG', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf
def encabezado_pie_pagina(canvas, doc, logo_bytes, nombre_empresa, version, coordinador):
    canvas.saveState()
    canvas.setFont('Helvetica-Bold', 14)
    if logo_bytes:
        logo = Image(logo_bytes, width=0.7*inch, height=0.7*inch, hAlign='LEFT')
        logo.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - 0.4*inch)
    canvas.drawString(doc.leftMargin + 0.8*inch, doc.height + doc.topMargin - 0.35*inch, nombre_empresa)
    canvas.setFont('Helvetica', 10)
    canvas.drawRightString(doc.width + doc.leftMargin, doc.height + doc.topMargin - 0.35*inch, f"Versión: {version}")
    canvas.line(doc.leftMargin, doc.height + doc.topMargin - 0.6*inch, doc.width + doc.leftMargin, doc.height + doc.topMargin - 0.6*inch)
    canvas.restoreState()
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.line(doc.leftMargin, doc.bottomMargin - 0.1*inch, doc.width + doc.leftMargin, doc.bottomMargin - 0.1*inch)
    canvas.drawString(doc.leftMargin, 0.5*inch, "Elaborado por: AE4-002")
    canvas.drawCentredString(doc.width/2 + doc.leftMargin, 0.5*inch, f"Revisado por: {coordinador}")
    canvas.drawRightString(doc.width + doc.leftMargin, 0.5*inch, "Aprobado por: Ing. Monica Legarda")
    canvas.restoreState()
def get_apa_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='APA_Body', fontName='Times-Roman', fontSize=12, leading=24, alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name='APA_H1', parent=styles['APA_Body'], fontName='Times-Bold', fontSize=14, alignment=TA_CENTER, spaceAfter=12))
    styles.add(ParagraphStyle(name='APA_H2', parent=styles['APA_Body'], fontName='Times-Bold', alignment=TA_LEFT, spaceBefore=12, spaceAfter=6))
    return styles
def generar_pdf_completo(empresa_id, version, coordinador):
    with get_connection() as conn:
        empresa = pd.read_sql(f"SELECT * FROM empresas WHERE id={empresa_id}", conn).iloc[0]
        df_pest = pd.read_sql(f"SELECT categoria, factor, tipo_foda, puntaje, importancia, valor_ponderado FROM matrices WHERE empresa_id={empresa_id} AND tipo_matriz='PEST'", conn)
        df_foda = pd.read_sql(f"SELECT cuadrante, factor_fila, factor_columna, impacto FROM foda_cruzado WHERE empresa_id={empresa_id}", conn)
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, leftMargin=1*inch, rightMargin=1*inch, topMargin=1*inch, bottomMargin=1*inch)
    styles = get_apa_styles()
    story = []
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("Plan Estratégico", styles['APA_H1']))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(empresa['nombre'], styles['APA_H1']))
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph(f"Versión: {version}", styles['APA_Body']))
    story.append(Paragraph(f"Fecha: {pd.Timestamp.now().strftime('%Y-%m-%d')}", styles['APA_Body']))
    story.append(PageBreak())
    story.append(Paragraph("Resumen Ejecutivo", styles['APA_H1']))
    story.append(Paragraph("Este resumen presenta los hallazgos y recomendaciones clave del diagnóstico estratégico. Está diseñado para proporcionar una visión general rápida y comprensible para la alta dirección, facilitando la toma de decisiones informadas.", styles['APA_Body']))
    story.append(Spacer(1, 24))
    analisis_foda_df, resumen_foda, estrategia_principal, puntajes_foda = analizar_foda(df_foda)
    pest_total = df_pest['valor_ponderado'].sum() if not df_pest.empty else 0
    story.append(Paragraph("Diagnóstico Estratégico General", styles['APA_H2']))
    story.append(Paragraph(f"La estrategia principal recomendada, basada en el análisis FODA cruzado, es la <b>{estrategia_principal}</b>. Esto indica la postura que la empresa debería adoptar prioritariamente. El siguiente gráfico de radar ilustra la ponderación de las cuatro posibles estrategias.", styles['APA_Body']))
    grafico_foda = generar_grafico_foda_radar(puntajes_foda)
    if grafico_foda: story.append(Image(grafico_foda, width=5*inch, height=5*inch))
    story.append(PageBreak())
    story.append(Paragraph("Factores Críticos de Éxito", styles['APA_H2']))
    story.append(Paragraph("A continuación, se destacan los factores más influyentes del análisis PEST, que representan las mayores oportunidades y amenazas del entorno.", styles['APA_Body']))
    if not df_pest.empty:
        pest_criticos = df_pest.sort_values(by='valor_ponderado', ascending=False).head(5)
        pest_data = [pest_criticos.columns.tolist()] + pest_criticos.values.tolist()
        pest_table = Table(pest_data, colWidths=[1.2*inch, 2*inch, 1*inch, 0.8*inch, 1*inch, 1*inch])
        pest_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), '#CCCCCC'), ('GRID', (0,0), (-1,-1), 1, '#000000')]))
        story.append(pest_table)
    story.append(Spacer(1, 24))
    story.append(PageBreak())
    story.append(Paragraph("Objetivos Estratégicos Propuestos", styles['APA_H2']))
    story.append(Paragraph("Derivado del diagnóstico, se proponen los siguientes objetivos macro para cada área de planificación. Estos objetivos forman la base del Cuadro de Mando Integral.", styles['APA_Body']))
    planes = generar_planes_por_plantilla(estrategia_principal, pest_total)
    for nombre_plan, datos_plan in planes.items():
        story.append(Paragraph(f"<b>{nombre_plan}:</b> {datos_plan['objetivo']}", styles['APA_Body']))
        story.append(Spacer(1, 6))
    story.append(PageBreak())
    story.append(Paragraph("Conclusiones y Próximos Pasos", styles['APA_H2']))
    story.append(Paragraph("El éxito de este plan estratégico depende de la ejecución disciplinada y el monitoreo constante. Se recomienda iniciar con la operativización de las estrategias de mayor impacto y establecer los indicadores del CMI para medir el progreso desde el primer mes.", styles['APA_Body']))
    story.append(PageBreak())
    story.append(Paragraph("Anexos: Detalles del Plan Estratégico", styles['APA_H1']))
    story.append(Paragraph("Anexo A: Introducción y Cultura Organizacional", styles['APA_H2']))
    story.append(Paragraph(f"<b>Nombre de la Empresa:</b> {empresa.get('nombre', 'N/A')}", styles['APA_Body']))
    story.append(Paragraph(f"<b>Giro del Negocio:</b> {empresa.get('giro', 'N/A')}", styles['APA_Body']))
    story.append(Paragraph(f"<b>Misión:</b> {empresa.get('mision', 'N/A')}", styles['APA_Body']))
    story.append(Paragraph(f"<b>Visión:</b> {empresa.get('vision', 'N/A')}", styles['APA_Body']))
    story.append(Paragraph(f"<b>Valores y Principios:</b> {empresa.get('valores', 'N/A')}", styles['APA_Body']))
    story.append(PageBreak())
    story.append(Paragraph("Anexo B: Diagnóstico Situacional Detallado", styles['APA_H2']))
    story.append(Paragraph("<b>Matriz PEST Completa</b>", styles['APA_Body']))
    if not df_pest.empty:
        pest_data_full = [df_pest.columns.tolist()] + df_pest.values.tolist()
        pest_table_full = Table(pest_data_full, colWidths=[1.2*inch, 2*inch, 1*inch, 0.8*inch, 1*inch, 1*inch])
        pest_table_full.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), '#CCCCCC'), ('GRID', (0,0), (-1,-1), 1, '#000000')]))
        story.append(pest_table_full)
    story.append(PageBreak())
    story.append(Paragraph("<b>Matriz FODA Cruzado Completa</b>", styles['APA_Body']))
    if not df_foda.empty:
        foda_data_full = [df_foda.columns.tolist()] + df_foda.values.tolist()
        foda_table_full = Table(foda_data_full, colWidths=[1.2*inch, 2*inch, 2*inch, 1*inch])
        foda_table_full.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), '#CCCCCC'), ('GRID', (0,0), (-1,-1), 1, '#000000')]))
        story.append(foda_table_full)
    story.append(PageBreak())
    story.append(Paragraph("Anexo C: Planes Estratégicos y Cuadro de Mando", styles['APA_H2']))
    story.append(Paragraph("<b>Cuadro de Mando Integral (CMI)</b>", styles['APA_Body']))
    
    with get_connection() as conn:
        df_estrategias_pdf = pd.read_sql(f"SELECT estrategia, plan_asignado FROM estrategias_generadas WHERE empresa_id={empresa_id}", conn)
    
    if not df_estrategias_pdf.empty:
        df_cmi = generar_cuadro_de_mando_ia(df_estrategias_pdf)
        cmi_data = [df_cmi.columns.tolist()] + df_cmi.values.tolist()
        # Ajustar anchos de columna para las 8 columnas
        col_widths = [1.2*inch, 1*inch, 1*inch, 1*inch, 0.8*inch, 0.5*inch, 0.5*inch, 0.5*inch]
        cmi_table = Table(cmi_data, colWidths=col_widths)
        cmi_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), '#CCCCCC'),
            ('GRID', (0,0), (-1,-1), 0.5, '#000000'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('LEADINGS', (0,0), (-1,-1), 10)
        ]))
        story.append(cmi_table)
    else:
        story.append(Paragraph("No hay estrategias generadas para construir el CMI.", styles['APA_Body']))
    story.append(PageBreak())
    logo_bytes = BytesIO(empresa['logo']) if empresa['logo'] else None
    doc.build(story, onFirstPage=lambda c, d: encabezado_pie_pagina(c, d, logo_bytes, empresa['nombre'], version, coordinador), 
                     onLaterPages=lambda c, d: encabezado_pie_pagina(c, d, logo_bytes, empresa['nombre'], version, coordinador))
    pdf_buffer.seek(0)
    return pdf_buffer

# NUEVA FUNCIÓN: Mostrar último análisis guardado desde la base de datos
def mostrar_ultimo_analisis_guardado(empresa_id, tipo_analisis):
    """
    Muestra el último análisis guardado desde la base de datos.
    tipo_analisis: 'made', 'madi', 'posicionamiento', 'pest', 'foda', 'cmi', 'operativo'
    """
    try:
        with get_connection() as conn:
            # Consultar el análisis específico
            query = f"SELECT analisis_{tipo_analisis} FROM empresas WHERE id=?"
            resultado = pd.read_sql(query, conn, params=(empresa_id,))
            
            if not resultado.empty:
                contenido = resultado.iloc[0][f'analisis_{tipo_analisis}']
                if contenido and str(contenido).strip():
                    st.markdown("---")
                    st.markdown(f"**📄 Último análisis de {tipo_analisis.upper()} guardado:**")
                    if tipo_analisis == 'cmi' and '|' in str(contenido):
                        try:
                            df_view = pd.read_csv(io.StringIO(contenido), sep="|")
                            st.table(df_view)
                        except:
                            st.text_area(f"contenido_guardado_{tipo_analisis}", value=contenido, height=200, disabled=True, label_visibility="collapsed")
                    else:
                        st.text_area(f"contenido_guardado_{tipo_analisis}", value=contenido, height=200, disabled=True, label_visibility="collapsed")
                else:
                    st.markdown("---")
                    st.info(f"ℹ️ No hay análisis de {tipo_analisis.upper()} guardado aún en la base de datos.")
            else:
                st.error("No se encontró la empresa en la base de datos.")
    except Exception as e:
        st.error(f"Error al cargar el último análisis guardado: {e}")

def aplicacion_principal():
    init_db()
    with st.sidebar:
        st.header("Gestión de Empresas")
        empresas_df = get_empresas()
        empresa_seleccionada = st.selectbox("Selecciona una Empresa", empresas_df['nombre'], index=None, placeholder="Elige una opción")
        empresa_id = int(empresas_df[empresas_df['nombre'] == empresa_seleccionada]['id'].iloc[0]) if empresa_seleccionada else None
        st.divider()
        with st.expander("➕ Crear Nueva Empresa"):
            with st.form("new_empresa_form"):
                new_empresa_name = st.text_input("Nombre de la nueva empresa")
                if st.form_submit_button("Crear"):
                    if new_empresa_name:
                        try:
                            with get_connection() as conn:
                                conn.execute("INSERT INTO empresas (nombre) VALUES (?)", (new_empresa_name,))
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
        st.stop()
    tab1, tab2, tab_est, tab3, tab4, tab5, tab_dash, tab6 = st.tabs(["1. Introducción", "2. Diagnóstico Situacional", "3. Estrategia", "4. Planes Estratégicos", "5. CMI/Indicadores", "6. Operativización/Presupuesto", "7. Dashboard de Análisis", "8. Resumen y Conclusiones"])
    with tab1:
        st.header("Introducción y Cultura Organizacional")
        with get_connection() as conn:
            empresa_data = pd.read_sql(f"SELECT * FROM empresas WHERE id={empresa_id}", conn).iloc[0]
        with st.form("form_intro"):
            st.subheader("Datos Generales")
            nombre = st.text_input("Nombre de la Empresa", empresa_data['nombre'])
            giro = st.text_input("Giro del Negocio", empresa_data['giro'])
            logo_file = st.file_uploader("Subir Logo", type=['png', 'jpg', 'jpeg'])
            if empresa_data['logo']:
                st.image(BytesIO(empresa_data['logo']), width=150)
            st.divider()
            st.subheader("Cultura Organizacional")
            objetivo_plan = st.text_area("Objetivo del Plan Estratégico", empresa_data.get('objetivo_plan', ''))
            mision = st.text_area("Misión", empresa_data['mision'])
            vision = st.text_area("Visión", empresa_data['vision'])
            obj_gen = st.text_area("Objetivo General", empresa_data.get('obj_general', ''))
            obj_esp = st.text_area("Objetivos Específicos", empresa_data.get('obj_especificos', ''))
            politicas = st.text_area("Políticas de la Empresa", empresa_data['politicas'])
            valores = st.text_area("Valores y Principios", empresa_data['valores'])
            organigrama_file = st.file_uploader("Subir Organigrama", type=['png', 'jpg', 'jpeg'])
            if empresa_data['organigrama']:
                st.image(BytesIO(empresa_data['organigrama']))
            if st.form_submit_button("Guardar Introducción"):
                logo_bytes = save_image(logo_file) if logo_file else empresa_data['logo']
                org_bytes = save_image(organigrama_file) if organigrama_file else empresa_data['organigrama']
                with get_connection() as conn:
                    conn.execute('''UPDATE empresas SET 
                                    nombre=?, giro=?, logo=?, objetivo_plan=?, mision=?, vision=?, 
                                    obj_general=?, obj_especificos=?, politicas=?, valores=?, organigrama=?
                                    WHERE id=?''', (nombre, giro, logo_bytes, objetivo_plan, mision, vision,
                                  obj_gen, obj_esp, politicas, valores, org_bytes, empresa_id))
                st.success("Datos de introducción guardados."); st.rerun()
    with tab2:
        st.header("Diagnóstico Situacional (Análisis de Matrices)")
        with get_connection() as conn:
            analisis_data = pd.read_sql(f"SELECT analisis_made, analisis_madi, analisis_posicionamiento, analisis_pest, analisis_foda FROM empresas WHERE id={empresa_id}", conn).iloc[0]
        def procesar_made_madi(data_str, tipo):
            if isinstance(data_str, pd.DataFrame):
                data_str = data_str.to_csv(sep='\t', index=False)
            df = pd.read_csv(StringIO(data_str), sep='\t', header=0)
            def normalize_text(text):
                if text is None: return ""
                return unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('utf-8').lower().replace(' ', '_').replace('%', '_percent')
            df.columns = [normalize_text(col) for col in df.columns]
            column_mapping = { 'n': 'N', 'variable': 'Variable', 'factor': 'Factor', 'producto': 'Producto',
                'precio': 'Precio', 'plaza': 'Plaza', 'promocion': 'Promocion',
                'rating': 'Rating', 'weight__percent': 'Weight %', 'weight_percent': 'Weight %'}
            df.rename(columns=column_mapping, inplace=True)
            p_cols = ['Producto', 'Precio', 'Plaza', 'Promocion']
            for col in p_cols:
                if col not in df.columns:
                    df[col] = "no"
                else:
                    df[col] = df[col].astype(str).str.lower()
            df['Total'] = df[p_cols].apply(lambda row: row.str.contains('si', na=False)).sum(axis=1)
            numeric_cols = ['Rating', 'Weight %']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
            df['Valor'] = df.get('Rating', 0) * (df.get('Weight %', 0) / 100.0)
            df['empresa_id'] = empresa_id
            df['tipo_matriz'] = tipo
            df_to_db = df.rename(columns={
                'Variable': 'variable', 'Factor': 'factor', 'Producto': 'producto', 'Precio': 'precio',
                'Plaza': 'plaza', 'Promocion': 'promocion', 'Rating': 'rating', 'Weight %': 'weight_percent',
                'Valor': 'valor', 'Total': 'total'
            })
            columnas_bd = ['empresa_id', 'tipo_matriz', 'variable', 'factor', 'producto', 'precio', 'plaza', 'promocion', 'rating', 'weight_percent', 'valor', 'total']
            columnas_presentes = [col for col in columnas_bd if col in df_to_db.columns]
            df_to_db = df_to_db[columnas_presentes]
            return df_to_db
        def display_and_edit_matrix(tipo_matriz, analisis_propio_data):
            with get_connection() as conn:
                df_db = pd.read_sql(f"SELECT * FROM matriz_marketing WHERE empresa_id=? AND tipo_matriz='{tipo_matriz}'", conn, params=(empresa_id,))
            if not df_db.empty:
                st.info("Puedes editar los datos directamente en la tabla.")
                df_display = df_db.rename(columns={
                    'variable': 'Variable', 'factor': 'Factor', 'producto': 'Producto', 'precio': 'Precio',
                    'plaza': 'Plaza', 'promocion': 'Promoción', 'rating': 'Rating', 'weight_percent': 'Weight %',
                    'valor': 'Valor', 'total': 'Total'
                })
                edited_df = st.data_editor(
                    df_display, key=f"editor_{tipo_matriz}", num_rows="dynamic", use_container_width=True,
                    disabled=['id', 'empresa_id', 'tipo_matriz', 'Valor', 'Total'])
                if st.button(f"💾 Guardar Cambios en {tipo_matriz}"):
                    with get_connection() as conn:
                        conn.execute(f"DELETE FROM matriz_marketing WHERE empresa_id=? AND tipo_matriz='{tipo_matriz}'", (empresa_id,))
                        df_to_save = procesar_made_madi(edited_df, tipo_matriz)
                        df_to_save.to_sql('matriz_marketing', conn, if_exists='append', index=False)
                    st.success(f"Cambios en {tipo_matriz} guardados."); st.rerun()
                total_score = df_db['total'].sum()
                st.metric(f"Puntaje Total {tipo_matriz}", f"{total_score}")
                st.subheader("Análisis Automático Sugerido")
                if tipo_matriz == 'MADE':
                    if total_score >= 3.5:
                        st.success(f"**Resultado Fuerte ({total_score}):** La empresa demuestra una excelente gestión de su marketing mix interno.")
                    elif 2.5 <= total_score < 3.5:
                        st.info(f"**Resultado Promedio ({total_score}):** La gestión de marketing interno es adecuada.")
                    else:
                        st.warning(f"**Resultado Débil ({total_score}):** La empresa presenta deficiencias significativas en su marketing mix interno.")
                elif tipo_matriz == 'MADI':
                    if total_score >= 3.5:
                        st.success(f"**Resultado Favorable ({total_score}):** El entorno de marketing es muy favorable.")
                    elif 2.5 <= total_score < 3.5:
                        st.info(f"**Resultado Moderado ({total_score}):** El entorno de marketing es estable.")
                    else:
                        st.warning(f"**Resultado Desfavorable ({total_score}):** El entorno presenta amenazas considerables.")
                
                with st.form(f"form_analisis_{tipo_matriz.lower()}"):
                    st.subheader("Análisis Estratégico")
                    if st.form_submit_button("🤖 Generar Análisis con IA"):
                        with st.spinner("La IA está analizando los datos..."):
                            contexto = df_db.to_string()
                            analisis_ia = generar_analisis_ia(tipo_matriz, contexto)
                            st.session_state[f"ia_analisis_{tipo_matriz}"] = analisis_ia
                    
                    current_analisis = st.session_state.get(f"ia_analisis_{tipo_matriz}", analisis_propio_data)
                    analisis_propio = st.text_area(f"Conclusiones sobre la matriz {tipo_matriz}.", value=current_analisis, height=300)
                    if st.form_submit_button("Guardar Análisis"):

                        with get_connection() as conn:
                            conn.execute(f"UPDATE empresas SET analisis_{tipo_matriz.lower()}=? WHERE id=?", (analisis_propio, empresa_id))
                        st.success(f"Análisis de {tipo_matriz} guardado."); st.rerun()
            else:
                st.info(f"Aún no hay datos para la Matriz {tipo_matriz}. Pega los datos desde Excel para comenzar.")
        diag_tab1, diag_tab2, diag_tab3, diag_tab4, diag_tab5 = st.tabs([
            "Matriz MADE", "Matriz MADI", "Matriz de Posicionamiento", "Matriz PEST", "Matriz FODA Numérico"
        ])
        with diag_tab1:
            st.subheader("Análisis de Marketing Interno (MADE)")
            with st.expander("📋 Pegar datos de MADE desde Excel"):
                made_paste_data = st.text_area("Pega tus datos de MADE aquí", height=200, key="paste_MADE")
                if st.button("Procesar y Reemplazar Datos de MADE", key="process_made"):
                    try:
                        df_made = procesar_made_madi(made_paste_data, 'MADE')
                        with get_connection() as conn:
                            conn.execute("DELETE FROM matriz_marketing WHERE empresa_id=? AND tipo_matriz='MADE'", (empresa_id,))
                            df_made.to_sql('matriz_marketing', conn, if_exists='append', index=False)
                        st.success(f"¡{len(df_made)} filas importadas a MADE exitosamente!"); st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar datos de MADE: {e}")
            display_and_edit_matrix('MADE', analisis_data.get('analisis_made', ''))
            # NUEVO: Mostrar último análisis guardado de MADE
            mostrar_ultimo_analisis_guardado(empresa_id, 'made')
        with diag_tab2:
            st.subheader("Análisis de Marketing Externo (MADI)")
            with st.expander("📋 Pegar datos de MADI desde Excel"):
                madi_paste_data = st.text_area("Pega tus datos de MADI aquí", height=200, key="paste_MADI")
                if st.button("Procesar y Reemplazar Datos de MADI", key="process_madi"):
                    try:
                        df_madi = procesar_made_madi(madi_paste_data, 'MADI')
                        with get_connection() as conn:
                            conn.execute("DELETE FROM matriz_marketing WHERE empresa_id=? AND tipo_matriz='MADI'", (empresa_id,))
                            df_madi.to_sql('matriz_marketing', conn, if_exists='append', index=False)
                        st.success(f"¡{len(df_madi)} filas importadas a MADI exitosamente!"); st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar datos de MADI: {e}")
            display_and_edit_matrix('MADI', analisis_data.get('analisis_madi', ''))
            # NUEVO: Mostrar último análisis guardado de MADI
            mostrar_ultimo_analisis_guardado(empresa_id, 'madi')
        with diag_tab3:
            st.subheader("Matriz de Posicionamiento")
            with get_connection() as conn:
                pos_data = pd.read_sql("SELECT posicionamiento_x, posicionamiento_y FROM empresas WHERE id=?", conn, params=(empresa_id,)).iloc[0]
            with st.form("form_posicionamiento"):
                coord_x = st.number_input("Coordenada X", value=float(pos_data.get('posicionamiento_x') or 0))
                coord_y = st.number_input("Coordenada Y", value=float(pos_data.get('posicionamiento_y') or 0))
                if st.form_submit_button("Guardar y Generar Gráfico"):
                    with get_connection() as conn:
                        conn.execute("UPDATE empresas SET posicionamiento_x=?, posicionamiento_y=? WHERE id=?", (coord_x, coord_y, empresa_id))
                    st.success("Coordenadas guardadas."); st.rerun()
            fig, ax = plt.subplots()
            ax.axhline(0, color='gray', lw=1); ax.axvline(0, color='gray', lw=1)
            ax.plot(coord_x, coord_y, 'ro', markersize=10)
            ax.set_title("Matriz de Posicionamiento"); ax.set_xlabel("Eje X"); ax.set_ylabel("Eje Y")
            ax.grid(True, which='both', linestyle='--', linewidth=0.5)
            st.pyplot(fig)
            st.subheader("📌 Diagnóstico Estratégico de Posicionamiento")
            interpretaciones = {
                "Superior Derecho": {"titulo": "Estrategia de Diferenciación Premium", "color": "success", "texto": "La organización se ubica en un cuadrante de alto valor percibido."},
                "Superior Izquierdo": {"titulo": "Estrategia de Liderazgo en Valor (Eficiencia)", "color": "info", "texto": "Esta es una posición altamente competitiva: alta calidad a precios accesibles."},
                "Inferior Izquierdo": {"titulo": "Estrategia de Liderazgo en Costos / Economía", "color": "warning", "texto": "La empresa compite en el segmento de volumen y eficiencia."},
                "Inferior Derecho": {"titulo": "Zona de Riesgo Estratégico", "color": "error", "texto": "Esta posición es críticamente insostenible."}
            }
            if coord_x > 0 and coord_y > 0: key = "Superior Derecho"
            elif coord_x < 0 and coord_y > 0: key = "Superior Izquierdo"
            elif coord_x < 0 and coord_y < 0: key = "Inferior Izquierdo"
            elif coord_x > 0 and coord_y < 0: key = "Inferior Derecho"
            else: key = None
            if key:
                res = interpretaciones[key]
                if res['color'] == "success": st.success(f"**{res['titulo']}**")
                elif res['color'] == "info": st.info(f"**{res['titulo']}**")
                elif res['color'] == "warning": st.warning(f"**{res['titulo']}**")
                else: st.error(f"**{res['titulo']}**")
                st.write(f"**Análisis Ejecutivo:** {res['texto']}")
            with st.form("form_analisis_pos"):
                st.subheader("Análisis Estratégico")
                if st.form_submit_button("🤖 Generar Análisis con IA"):
                    with st.spinner("La IA está analizando la posición..."):
                        contexto_pos = f"Coordenada X: {coord_x}, Coordenada Y: {coord_y}. Cuadrante: {key}. Interpretación: {interpretaciones.get(key, {}).get('texto', '')}"
                        analisis_ia_pos = generar_analisis_ia("Posicionamiento", contexto_pos)
                        st.session_state["ia_analisis_posicionamiento"] = analisis_ia_pos
                
                current_analisis_pos = st.session_state.get("ia_analisis_posicionamiento", analisis_data.get('analisis_posicionamiento', ''))
                analisis_propio_pos = st.text_area("Conclusiones sobre el posicionamiento.", value=current_analisis_pos, height=300)
                if st.form_submit_button("Guardar Análisis de Posicionamiento"):
                    with get_connection() as conn:
                        conn.execute("UPDATE empresas SET analisis_posicionamiento=? WHERE id=?", (analisis_propio_pos, empresa_id))
                    st.success("Análisis de Posicionamiento guardado."); st.rerun()
            # NUEVO: Mostrar último análisis guardado de Posicionamiento
            mostrar_ultimo_analisis_guardado(empresa_id, 'posicionamiento')
        with diag_tab4:
            st.subheader("Análisis PEST")
            with st.expander("📋 Pegar datos desde Excel"):
                pest_paste_data = st.text_area("Pega tus datos aquí", height=200, key="pest_input_secondary")
                if st.button("Procesar Datos Pegados de PEST"):
                    try:
                        df_pasted = pd.read_csv(StringIO(pest_paste_data), sep='\t', header=0)
                        df_pasted.columns = ['categoria', 'factor', 'tipo_foda', 'puntaje', 'importancia']
                        df_pasted['valor_ponderado'] = df_pasted['puntaje'] * (df_pasted['importancia'] / 100.0)
                        df_pasted['empresa_id'] = empresa_id
                        df_pasted['tipo_matriz'] = 'PEST'
                        with get_connection() as conn:
                            conn.execute("DELETE FROM matrices WHERE empresa_id=? AND tipo_matriz='PEST'", (empresa_id,))
                            df_pasted.to_sql('matrices', conn, if_exists='append', index=False)
                        st.success(f"¡{len(df_pasted)} filas importadas a PEST exitosamente!"); st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar los datos: {e}.")
            with get_connection() as conn:
                df_pest = pd.read_sql(f"SELECT * FROM matrices WHERE empresa_id={empresa_id} AND tipo_matriz='PEST'", conn)
            if not df_pest.empty:
                edited_pest = st.data_editor(df_pest, num_rows="dynamic", key="editor_pest_v2", use_container_width=True, disabled=['id', 'empresa_id', 'tipo_matriz'])
                if st.button("💾 Guardar Cambios en PEST"):
                    with get_connection() as conn:
                        conn.execute("DELETE FROM matrices WHERE empresa_id=? AND tipo_matriz='PEST'", (empresa_id,))
                        edited_pest.to_sql('matrices', conn, if_exists='append', index=False)
                    st.success("Cambios en PEST guardados."); st.rerun()
                total_ponderado = df_pest['valor_ponderado'].sum()
                st.metric("Puntaje Ponderado Total PEST", f"{total_ponderado:.2f}")
                if total_ponderado > 2.5:
                    st.success(f"**Perfil de Adaptación Proactiva ({total_ponderado:.2f})**")
                else:
                    st.warning(f"**Perfil de Vulnerabilidad Externa ({total_ponderado:.2f})**")
            with st.form("form_analisis_pest"):
                st.subheader("Análisis Estratégico")
                if st.form_submit_button("🤖 Generar Análisis con IA"):
                    with st.spinner("La IA está analizando el entorno PEST..."):
                        contexto_pest = df_pest.to_string()
                        analisis_ia_pest = generar_analisis_ia("PEST", contexto_pest)
                        st.session_state["ia_analisis_pest"] = analisis_ia_pest
                
                current_analisis_pest = st.session_state.get("ia_analisis_pest", analisis_data.get('analisis_pest', ''))
                analisis_propio_pest = st.text_area("Conclusiones sobre la matriz PEST.", value=current_analisis_pest, height=300)
                if st.form_submit_button("Guardar Análisis"):
                    with get_connection() as conn:
                        conn.execute("UPDATE empresas SET analisis_pest=? WHERE id=?", (analisis_propio_pest, empresa_id))
                    st.success("Análisis de PEST guardado."); st.rerun()
            # NUEVO: Mostrar último análisis guardado de PEST
            mostrar_ultimo_analisis_guardado(empresa_id, 'pest')
        with diag_tab5:
            st.subheader("Análisis FODA Cruzado (Numérico)")
            with st.expander("📋 Pegar datos de FODA Cruzado desde Excel"):
                foda_paste_data = st.text_area("Pega tus datos de FODA aquí", height=200, key="foda_paste_area")
                if st.button("Procesar Datos Pegados de FODA"):
                    try:
                        df_foda_pasted = pd.read_csv(StringIO(foda_paste_data), sep='\t', header=0)
                        df_foda_pasted.columns = ['cuadrante', 'factor_fila', 'factor_columna', 'impacto']
                        df_foda_pasted['impacto'] = pd.to_numeric(df_foda_pasted['impacto'], errors='coerce').fillna(0).astype(int)
                        df_foda_pasted['empresa_id'] = empresa_id
                        with get_connection() as conn:
                            conn.execute("DELETE FROM foda_cruzado WHERE empresa_id=?", (empresa_id,))
                            df_foda_pasted.to_sql('foda_cruzado', conn, if_exists='append', index=False)
                        st.success(f"¡{len(df_foda_pasted)} filas importadas a FODA Cruzado!"); st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar los datos: {e}.")
            with get_connection() as conn:
                df_foda = pd.read_sql(f"SELECT * FROM foda_cruzado WHERE empresa_id={empresa_id}", conn)
            if not df_foda.empty:
                edited_foda = st.data_editor(df_foda, num_rows="dynamic", key="editor_foda", use_container_width=True, disabled=['id', 'empresa_id'])
                if st.button("💾 Guardar Cambios en FODA"):
                    with get_connection() as conn:
                        conn.execute("DELETE FROM foda_cruzado WHERE empresa_id=?", (empresa_id,))
                        edited_foda.to_sql('foda_cruzado', conn, if_exists='append', index=False)
                    st.success("Cambios en FODA guardados."); st.rerun()
                analisis_df, _, estrategia_principal, puntajes_foda = analizar_foda(df_foda)
                if analisis_df is not None:
                    st.subheader("🎯 Postura Competitiva Sugerida")
                    st.info(f"Estrategia Principal: {estrategia_principal}")
                    st.dataframe(analisis_df, use_container_width=True)
                    grafico_foda = generar_grafico_foda_radar(puntajes_foda)
                    if grafico_foda: st.image(grafico_foda)
            with st.form("form_analisis_foda"):
                st.subheader("Análisis Estratégico")
                if st.form_submit_button("🤖 Generar Análisis con IA"):
                    with st.spinner("La IA está analizando el FODA Cruzado..."):
                        contexto_foda = df_foda.to_string()
                        analisis_ia_foda = generar_analisis_ia("FODA Cruzado", contexto_foda)
                        st.session_state["ia_analisis_foda"] = analisis_ia_foda
                
                current_analisis_foda = st.session_state.get("ia_analisis_foda", analisis_data.get('analisis_foda', ''))
                analisis_propio_foda = st.text_area("Conclusiones sobre la matriz FODA.", value=current_analisis_foda, height=300)
                if st.form_submit_button("Guardar Análisis"):
                    with get_connection() as conn:
                        conn.execute("UPDATE empresas SET analisis_foda=? WHERE id=?", (analisis_propio_foda, empresa_id))
                    st.success("Análisis de FODA guardado."); st.rerun()
            # NUEVO: Mostrar último análisis guardado de FODA
            mostrar_ultimo_analisis_guardado(empresa_id, 'foda')

        with tab_est:
            st.header("🎯 Formulación de Estrategias")
            st.info("En esta sección se generan 12 estrategias (3 por cuadrante) basadas en el FODA Cruzado, cada una con 5 actividades específicas.")
            
            if "df_estrategias_temp" not in st.session_state:
                with get_connection() as conn:
                    st.session_state.df_estrategias_temp = pd.read_sql(f"SELECT * FROM estrategias_generadas WHERE empresa_id={empresa_id}", conn)

            with get_connection() as conn:
                df_foda_final = pd.read_sql(f"SELECT cuadrante, factor_fila, factor_columna, impacto FROM foda_cruzado WHERE empresa_id={empresa_id}", conn)

            if df_foda_final.empty:
                st.warning("Primero debe completar el Análisis FODA Cruzado en la pestaña de Diagnóstico Situacional.")
            else:
                if st.button("🤖 Generar 12 Estrategias Maestras con IA"):
                    with st.spinner("La IA está diseñando las estrategias y actividades..."):
                        client = get_ia_client()
                        contexto_reducido = df_foda_final[["cuadrante", "factor_fila", "factor_columna"]].to_string(index=False)
                        
                        prompt_est = f"""Actúa como Director de Estrategia. Basado en este FODA Cruzado:
                        {contexto_reducido}
                        Genera 12 estrategias (3 por cuadrante: FO, FA, DO, DA).
                        Para cada una, define 5 actividades cortas y asígnale uno de estos 7 PLANES:
                        1. Plan Administrativo
                        2. Plan Operativo
                        3. Plan Tecnológico
                        4. Plan Financiero
                        5. Plan de Monitoreo y control
                        6. Plan de Mejora
                        7. Plan de Contingencia
                        
                        Asigna también una IMPORTANCIA basada en el impacto (Alta, Media Alta, Media Baja, Baja).
                        Formato: CUADRANTE|ESTRATEGIA|IMPORTANCIA|ACT1;ACT2;ACT3;ACT4;ACT5|PLAN
                        No incluyas nada más que las 12 líneas de texto."""
                        
                        resultado_ia = generar_analisis(prompt_est, client)
                        
                        nuevas_filas = []
                        for line in resultado_ia.strip().split("\n"):
                            partes = line.split("|")
                            if len(partes) >= 5:
                                nuevas_filas.append({
                                    "cuadrante": partes[0].strip().upper(),
                                    "estrategia": partes[1].strip(),
                                    "importancia": partes[2].strip(),
                                    "actividades": partes[3].strip(),
                                    "plan_asignado": partes[4].strip(),
                                    "empresa_id": empresa_id
                                })
                            elif len(partes) == 4:
                                nuevas_filas.append({
                                    "cuadrante": partes[0].strip().upper(),
                                    "estrategia": partes[1].strip(),
                                    "importancia": partes[2].strip(),
                                    "actividades": partes[3].strip(),
                                    "plan_asignado": "Estratégico",
                                    "empresa_id": empresa_id
                                })
                        
                        if nuevas_filas:
                            df_nuevas = pd.DataFrame(nuevas_filas)
                            with get_connection() as conn:
                                conn.execute("DELETE FROM estrategias_generadas WHERE empresa_id=?", (empresa_id,))
                                df_nuevas.to_sql("estrategias_generadas", conn, if_exists="append", index=False)
                            st.session_state.df_estrategias_temp = df_nuevas
                            st.success("Estrategias generadas."); st.rerun()
                        else:
                            st.error("Error en formato de IA. Revisa la conexión.")

                st.subheader("Edición de Estrategias Generadas")
                df_editor = st.session_state.df_estrategias_temp.copy()
                for col in ["cuadrante", "estrategia", "importancia", "actividades", "plan_asignado"]:
                    if col not in df_editor.columns: df_editor[col] = ""
                
                edited_df = st.data_editor(
                    df_editor, num_rows="dynamic", key="editor_v5", use_container_width=True,
                    disabled=["id", "empresa_id"],
                    column_config={
                        "cuadrante": st.column_config.SelectboxColumn("Cuadrante", options=["FO", "FA", "DO", "DA"]),
                        "importancia": st.column_config.SelectboxColumn("Importancia", options=["Alta", "Media Alta", "Media Baja", "Baja"]),
                        "plan_asignado": st.column_config.SelectboxColumn("Plan Asignado", options=["Plan Administrativo", "Plan Operativo", "Plan Tecnológico", "Plan Financiero", "Plan de Monitoreo y control", "Plan de Mejora", "Plan de Contingencia"]),
                    }
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Guardar Cambios"):
                        with get_connection() as conn:
                            conn.execute("DELETE FROM estrategias_generadas WHERE empresa_id=?", (empresa_id,))
                            df_to_save = edited_df.copy()
                            if "id" in df_to_save.columns:
                                df_to_save = df_to_save.drop(columns=["id"])
                            df_to_save["empresa_id"] = empresa_id
                            df_to_save.to_sql("estrategias_generadas", conn, if_exists="append", index=False)
                        st.success("Estrategias guardadas.")
                        st.rerun()

                with col2:
                    if st.button("🚀 Enviar a Operativización"):
                        if edited_df.empty:
                            st.warning("No hay estrategias para enviar.")
                        else:
                            try:
                                with get_connection() as conn:
                                    # 1. Borramos TODO lo anterior de esta empresa
                                    conn.execute("DELETE FROM operativizacion WHERE empresa_id = ?", (empresa_id,))

                                    # 2. Insertamos solo lo que hay ahora
                                    filas_insertadas = 0
                                    for _, row in edited_df.iterrows():
                                        plan = row.get("plan_asignado", "Sin asignar").strip()
                                        estrategia = row.get("estrategia", "").strip()
                                        actividades_str = str(row.get("actividades", "")).strip()

                                        if not actividades_str:
                                            continue

                                        for act in [a.strip() for a in actividades_str.split(";") if a.strip()]:
                                            conn.execute("""
                                                INSERT INTO operativizacion 
                                                (empresa_id, plan, estrategia, actividades, plazo, responsable, recurso, costo)
                                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                            """, (
                                                empresa_id,
                                                plan,
                                                estrategia,
                                                act,
                                                "Por definir",
                                                "Por definir",
                                                "Por definir",
                                                0.0
                                            ))
                                            filas_insertadas += 1

                                    conn.commit()

                                if filas_insertadas > 0:
                                    st.success(f"Operativización actualizada con {filas_insertadas} actividades.")
                                else:
                                    st.info("No se insertaron actividades (verifica la columna 'actividades').")

                                st.rerun()

                            except Exception as e:
                                st.error(f"Error al transferir a operativización: {str(e)}")        
                            else:
                                st.warning("No hay datos para enviar.")
        with tab3:
            st.header("Planes Estratégicos")
            with st.form("form_planes"):
                if st.form_submit_button("🤖 Generar Planes con IA"):
                    with st.spinner("La IA está diseñando los planes basados en el diagnóstico..."):
                        with get_connection() as conn:
                            df_pest = pd.read_sql(f"SELECT valor_ponderado FROM matrices WHERE empresa_id={empresa_id} AND tipo_matriz='PEST'", conn)
                            df_foda = pd.read_sql(f"SELECT cuadrante, impacto FROM foda_cruzado WHERE empresa_id={empresa_id}", conn)
                            analisis_previos = pd.read_sql(f"SELECT analisis_pest, analisis_foda FROM empresas WHERE id={empresa_id}", conn).iloc[0]
                        
                        contexto = f"PEST: {df_pest.to_string()}. FODA: {df_foda.to_string()}. Análisis previo: {analisis_previos.to_string()}"
                        prompt_planes = f"""Basado en este diagnóstico: {contexto}, genera un Plan Estratégico Maestro detallado que aborde los siguientes 7 planes específicos:
                        1. Plan Administrativo
                        2. Plan Operativo
                        3. Plan Tecnológico
                        4. Plan Financiero
                        5. Plan de Monitoreo y control
                        6. Plan de Mejora
                        7. Plan de Contingencia
                        
                        Para cada plan, define objetivos estratégicos, justificación y acciones clave."""
                        st.session_state["ia_analisis_operativo"] = generar_analisis(prompt_planes)
                
                current_analisis_operativo = st.session_state.get("ia_analisis_operativo", analisis_data.get('analisis_operativo', ''))
                analisis_propio_operativo = st.text_area("Edite el Plan Estratégico Maestro", value=current_analisis_operativo, height=400)
                
                if st.form_submit_button("💾 Guardar Plan Maestro"):
                    with get_connection() as conn:
                        conn.execute("UPDATE empresas SET analisis_operativo=? WHERE id=?", (analisis_propio_operativo, empresa_id))
                    st.success("Plan Estratégico guardado."); st.rerun()
            # NUEVO: Mostrar último análisis guardado de Planes Operativos
            mostrar_ultimo_analisis_guardado(empresa_id, 'operativo')
        with tab4:
            st.header("CMI / Indicadores")
            with st.form("form_cmi"):
                if st.form_submit_button("🤖 Generar CMI con IA"):
                    with st.spinner("La IA está diseñando el Cuadro de Mando Integral..."):
                        with get_connection() as conn:
                            df_estrategias = pd.read_sql(f"SELECT estrategia, plan_asignado FROM estrategias_generadas WHERE empresa_id={empresa_id}", conn)
                        
                        if df_estrategias.empty:
                            st.warning("No se encontraron estrategias generadas. Por favor, genérelas en la pestaña 'Estrategia' primero.")
                        else:
                            df_cmi_ia = generar_cuadro_de_mando_ia(df_estrategias)
                            # Convertimos a CSV para que sea fácil de editar y guardar sin dependencias externas
                            st.session_state["ia_analisis_cmi"] = df_cmi_ia.to_csv(index=False, sep="|")
                
                current_analisis_cmi = st.session_state.get("ia_analisis_cmi", analisis_data.get('analisis_cmi', ''))
                
                # Mostramos un editor de datos si hay contenido, de lo contrario un área de texto
                if current_analisis_cmi:
                    try:
                        df_editor = pd.read_csv(io.StringIO(current_analisis_cmi), sep="|")
                        st.write("### Vista Previa y Edición del CMI")
                        df_edited = st.data_editor(df_editor, use_container_width=True, num_rows="dynamic")
                        # Actualizamos el valor para guardar
                        analisis_propio_cmi = df_edited.to_csv(index=False, sep="|")
                    except:
                        analisis_propio_cmi = st.text_area("Edite el Cuadro de Mando Integral (Formato CSV con |)", value=current_analisis_cmi, height=400)
                else:
                    analisis_propio_cmi = st.text_area("Edite el Cuadro de Mando Integral", value=current_analisis_cmi, height=400)
                
                if st.form_submit_button("💾 Guardar CMI"):
                    with get_connection() as conn:
                        conn.execute("UPDATE empresas SET analisis_cmi=? WHERE id=?", (analisis_propio_cmi, empresa_id))
                    st.success("CMI guardado."); st.rerun()
            # NUEVO: Mostrar último análisis guardado de CMI
            mostrar_ultimo_analisis_guardado(empresa_id, 'cmi')
        with tab5:
            st.header("Operativización / Presupuesto")
            st.subheader("📝 Cuadro de Operativización y Presupuesto (Cascada)")
            st.info("Estructura: Plan -> Estrategia -> Actividad. Los costos se suman por actividad.")
            with get_connection() as conn:
                df_oper = pd.read_sql(f"SELECT id, plan, estrategia, actividades, plazo, responsable, recurso, costo FROM operativizacion WHERE empresa_id={empresa_id}", conn)
            edited_oper = st.data_editor( df_oper, num_rows="dynamic", key="editor_oper_cascada", use_container_width=True,
                disabled=['id'], column_config={
                    "plan": st.column_config.SelectboxColumn("Plan", options=["Plan Administrativo", "Plan Operativo", "Plan Tecnológico", "Plan Financiero", "Plan de Monitoreo y control", "Plan de Mejora", "Plan de Contingencia"], help="Seleccione el Plan Maestro"),
                    "estrategia": st.column_config.TextColumn("Estrategia", help="Estrategia específica para el plan"),
                    "actividades": st.column_config.TextColumn("Actividad", help="Actividad para cumplir la estrategia"),
                    "costo": st.column_config.NumberColumn("Costo", format="$%.2f")})
            if st.button("💾 Guardar Operativización"):
                with get_connection() as conn:
                    conn.execute("DELETE FROM operativizacion WHERE empresa_id=?", (empresa_id,))
                    edited_oper['empresa_id'] = empresa_id
                    if 'id' in edited_oper.columns: edited_oper = edited_oper.drop(columns=['id'])
                    edited_oper.to_sql('operativizacion', conn, if_exists='append', index=False)
                st.success("Operativización guardada correctamente."); st.rerun()
            total_inversion = edited_oper['costo'].sum() if not edited_oper.empty else 0
            st.metric("Inversión Total Requerida (Suma de Actividades)", f"${total_inversion:,.2f}")
            st.divider()
            st.subheader("📊 Estado de Pérdidas y Ganancias (Último Año)")
            with get_connection() as conn:
                df_pg = pd.read_sql(f"SELECT id, anio, ingresos, egresos, resultado FROM perdida_ganancia WHERE empresa_id={empresa_id}", conn)
            if df_pg.empty:
                df_pg = pd.DataFrame([{'anio': '2025', 'ingresos': 0.0, 'egresos': 0.0, 'resultado': 0.0}])
            edited_pg = st.data_editor(df_pg, num_rows="dynamic", key="editor_pg_v2", use_container_width=True, disabled=['id', 'resultado'])
            if st.button("💾 Guardar P&G"):
                edited_pg['resultado'] = edited_pg['ingresos'] - edited_pg['egresos']
                with get_connection() as conn:
                    conn.execute("DELETE FROM perdida_ganancia WHERE empresa_id=?", (empresa_id,))
                    edited_pg['empresa_id'] = empresa_id
                    if 'id' in edited_pg.columns: edited_pg = edited_pg.drop(columns=['id'])
                    edited_pg.to_sql('perdida_ganancia', conn, if_exists='append', index=False)
                st.success("Datos de P&G guardados."); st.rerun()
            st.divider()
            st.subheader("📈 Flujo de Caja Proyectado")
            anios_proy = st.selectbox("A cuántos años desea proyectar?", [1, 2, 3, 4, 5], index=2, key="sel_anios")
            with get_connection() as conn:
                df_fc = pd.read_sql(f"SELECT id, anio_proyeccion, saldo_inicial, ingreso, egreso, flujo_neto, saldo_final FROM flujo_caja WHERE empresa_id={empresa_id}", conn)
            if len(df_fc) != anios_proy:
                df_fc = pd.DataFrame([{'anio_proyeccion': i+1, 'saldo_inicial': 0.0, 'ingreso': 0.0, 'egreso': 0.0, 'flujo_neto': 0.0, 'saldo_final': 0.0} for i in range(anios_proy)])
            edited_fc = st.data_editor(df_fc, num_rows="fixed", key="editor_fc_v2", use_container_width=True, disabled=['id', 'anio_proyeccion', 'flujo_neto', 'saldo_final'])
            if st.button("🧮 Calcular y Guardar Flujo"):
                for idx in range(len(edited_fc)):
                    if idx > 0: edited_fc.at[idx, 'saldo_inicial'] = edited_fc.at[idx-1, 'saldo_final']
                    edited_fc.at[idx, 'flujo_neto'] = edited_fc.at[idx, 'ingreso'] - edited_fc.at[idx, 'egreso']
                    edited_fc.at[idx, 'saldo_final'] = edited_fc.at[idx, 'saldo_inicial'] + edited_fc.at[idx, 'flujo_neto']
                with get_connection() as conn:
                    conn.execute("DELETE FROM flujo_caja WHERE empresa_id=?", (empresa_id,))
                    edited_fc['empresa_id'] = empresa_id
                    if 'id' in edited_fc.columns: edited_fc = edited_fc.drop(columns=['id'])
                    edited_fc.to_sql('flujo_caja', conn, if_exists='append', index=False)
                st.success("Flujo de caja guardado."); st.rerun()
            st.divider()
            st.subheader("💰 Análisis de Costo / Beneficio (C/B)")
            with get_connection() as conn:
                pe_data = pd.read_sql(f"SELECT * FROM punto_equilibrio WHERE empresa_id={empresa_id}", conn)
            if pe_data.empty:
                pe_data = pd.DataFrame([{'costo_fijo_total': total_inversion, 'precio_venta_unidad': 0.0, 'costo_variable_unidad': 0.0, 'unidades_producidas': 0.0}])
            with st.form("form_cb"):
                col1, col2 = st.columns(2)
                with col1:
                    cf = st.number_input("Costo Fijo Total (Inversión)", value=float(total_inversion), help="Tomado automáticamente de la Operativización")
                    pv = st.number_input("Precio de Venta por Unidad ($)", value=float(pe_data.iloc[0]['precio_venta_unidad']))
                with col2:
                    cv = st.number_input("Costo Variable por Unidad ($)", value=float(pe_data.iloc[0]['costo_variable_unidad']))
                    unidades = st.number_input("Unidades Producidas/Vendidas estimadas", value=float(pe_data.iloc[0]['unidades_producidas']))
                if st.form_submit_button("📊 Calcular Punto de Equilibrio y Retorno"):
                    with get_connection() as conn:
                        conn.execute("DELETE FROM punto_equilibrio WHERE empresa_id=?", (empresa_id,))
                        conn.execute("INSERT INTO punto_equilibrio (empresa_id, costo_fijo_total, precio_venta_unidad, costo_variable_unidad, unidades_producidas) VALUES (?,?,?,?,?)", 
                                     (empresa_id, cf, pv, cv, unidades))
                    st.success("Datos de C/B guardados."); st.rerun()
            cf = float(pe_data.iloc[0]['costo_fijo_total'])
            pv = float(pe_data.iloc[0]['precio_venta_unidad'])
            cv = float(pe_data.iloc[0]['costo_variable_unidad'])
            margen_contribucion = pv - cv
            if margen_contribucion > 0:
                pe_unidades = cf / margen_contribucion
                pe_dolares = pe_unidades * pv
                flujo_neto_total = edited_fc['flujo_neto'].sum() if not edited_fc.empty else 0
                flujo_promedio_mensual = (flujo_neto_total / (len(edited_fc) * 12)) if len(edited_fc) > 0 else 0
                tiempo_retorno = (cf / flujo_promedio_mensual) if flujo_promedio_mensual > 0 else 0
                c1, c2, c3 = st.columns(3)
                c1.metric("Punto de Equilibrio (Unidades)", f"{pe_unidades:,.0f} und")
                c2.metric("Punto de Equilibrio (Dólares)", f"${pe_dolares:,.2f}")
                c3.metric("Tiempo de Retorno Est.", f"{tiempo_retorno:.1f} meses" if tiempo_retorno > 0 else "N/A")
                st.write(f"**Análisis:** Para recuperar la inversión de **${cf:,.2f}**, la empresa debe vender al menos **{pe_unidades:,.0f} unidades**, lo que representa una facturación de **${pe_dolares:,.2f}**.")
            else:
                st.warning("El Precio de Venta debe ser mayor al Costo Variable para calcular el Punto de Equilibrio.")
        
        with tab_dash:
            st.header("📊 Dashboard de Análisis Estratégico")
            st.info("Visualización interactiva de los indicadores clave de la empresa.")
            
            with get_connection() as conn:
                df_est_dash = pd.read_sql(f"SELECT cuadrante, importancia, plan_asignado FROM estrategias_generadas WHERE empresa_id={empresa_id}", conn)
                df_pg_dash = pd.read_sql(f"SELECT anio, ingresos, egresos, resultado FROM perdida_ganancia WHERE empresa_id={empresa_id}", conn)
                df_fc_dash = pd.read_sql(f"SELECT anio_proyeccion, flujo_neto, saldo_final FROM flujo_caja WHERE empresa_id={empresa_id}", conn)
            
            col_d1, col_d2, col_d3 = st.columns(3)
            if not df_pg_dash.empty:
                total_ingresos = df_pg_dash['ingresos'].sum()
                total_egresos = df_pg_dash['egresos'].sum()
                margen = ((total_ingresos - total_egresos) / total_ingresos * 100) if total_ingresos > 0 else 0
                col_d1.metric("Ingresos Totales", f"${total_ingresos:,.2f}")
                col_d2.metric("Egresos Totales", f"${total_egresos:,.2f}")
                col_d3.metric("Margen Global", f"{margen:.1f}%")

            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🎯 Distribución de Estrategias")
                if not df_est_dash.empty:
                    fig_pie = px.pie(df_est_dash, names='cuadrante', title='Estrategias por Cuadrante', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.warning("No hay datos de estrategias.")
            
            with c2:
                st.subheader("💰 Proyección de Flujo Neto")
                if not df_fc_dash.empty:
                    fig_line = px.line(df_fc_dash, x='anio_proyeccion', y='flujo_neto', title='Flujo Neto por Año', markers=True)
                    fig_line.update_traces(line_color='green')
                    st.plotly_chart(fig_line, use_container_width=True)
                else:
                    st.warning("No hay datos de flujo de caja.")

            st.divider()
            
            c3, c4 = st.columns(2)
            with c3:
                st.subheader("📈 Ingresos vs Egresos")
                if not df_pg_dash.empty:
                    df_melted = df_pg_dash.melt(id_vars='anio', value_vars=['ingresos', 'egresos'], var_name='Tipo', value_name='Monto')
                    fig_bar = px.bar(df_melted, x='anio', y='Monto', color='Tipo', barmode='group', title='Comparativa Anual')
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.warning("No hay datos financieros.")
            
            with c4:
                st.subheader("📋 Planes Maestros")
                if not df_est_dash.empty:
                    fig_sun = px.sunburst(df_est_dash, path=['plan_asignado', 'importancia'], title='Jerarquía de Planes e Importancia')
                    st.plotly_chart(fig_sun, use_container_width=True)
                else:
                    st.warning("No hay datos de planes.")

        with tab6:
            st.header("Resumen, Conclusiones y Exportación")
            with st.form("pdf_form"):
                pdf_version = st.text_input("Versión del Plan", value="1.0")
                pdf_coordinador = st.text_input("Coordinador del Plan", value="Consultor Estratégico")
                if st.form_submit_button("🚀 Generar y Descargar PDF"):
                    pdf_bytes = generar_pdf_completo(empresa_id, pdf_version, pdf_coordinador)
                    st.session_state['pdf_file'] = pdf_bytes
            if 'pdf_file' in st.session_state:
                st.download_button(label="✅ Descargar PDF Ahora", data=st.session_state['pdf_file'], file_name=f"Plan_Estrategico_V{pdf_version}.pdf", mime="application/pdf")
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
                    res = supabase.auth.sign_up({ "email": correo, "password": clave, "options": { "data": {
                                "full_name": nombre, "username": usuario.lower().strip()}}
                    })
                    if res.user:
                        st.success("¡Registro solicitado con éxito!")
                        st.info("Si has configurado la confirmación por correo, por favor revísalo. Si no, ya puedes intentar iniciar sesión.")
                    else:
                        st.error("No se pudo completar el registro en el servidor.")
                except Exception as e:
                    st.error(f"Error en el registro: {e}")
            else:
                st.warning("Por favor, llena todos los campos.")
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
        aplicacion_principal()
if __name__ == "__main__":
    init_db()
    main()
