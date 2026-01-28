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
        # --- 4. FUNCIONES DE INTERACCIÓN CON LA BASE DE DATOS (SUPABASE) ---

def get_datos_empresa(empresa_id):
    """Obtiene todos los datos de una única empresa."""
    if supabase and empresa_id:
        try:
            response = supabase.table('empresas').select('*').eq('id', empresa_id).single().execute()
            return response.data
        except Exception as e:
            st.error(f"Error al cargar datos de la empresa: {e}")
    return {}

def get_datos_tabla(tabla, empresa_id, tipo_matriz_filter=None):
    """Función genérica para obtener datos de tablas secundarias, con filtro opcional."""
    if supabase and empresa_id:
        try:
            query = supabase.table(tabla).select('*').eq('empresa_id', empresa_id)
            if tipo_matriz_filter:
                query = query.eq('tipo_matriz', tipo_matriz_filter)
            
            response = query.execute()
            return pd.DataFrame(response.data) if response.data else pd.DataFrame()
        except Exception as e:
            st.error(f"Error al cargar datos de la tabla {tabla}: {e}")
    return pd.DataFrame()

def guardar_analisis_db(empresa_id, tipo_analisis, contenido):
    """Guarda un campo de análisis específico en la tabla de empresas."""
    if supabase and empresa_id:
        try:
            supabase.table('empresas').update({f'analisis_{tipo_analisis}': contenido}).eq('id', empresa_id).execute()
            st.success(f"Análisis de {tipo_analisis.upper()} guardado en la nube.")
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar análisis: {e}")
def get_empresas():
    """Obtiene las empresas a las que el usuario tiene acceso (propias y compartidas)."""
    if supabase and st.session_state.get("user"):
        try:
            # RLS filtra automáticamente los resultados según el usuario autenticado.
            response = supabase.table('empresas').select('id, nombre').execute()
            return pd.DataFrame(response.data) if response.data else pd.DataFrame(columns=['id', 'nombre'])
        except Exception as e:
            st.error(f"Error al cargar empresas: {e}")
    return pd.DataFrame(columns=['id', 'nombre'])

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
    empresa = get_datos_empresa(empresa_id)
    if not empresa:
        st.error("No se pueden generar el PDF, no se encontraron datos de la empresa.")
        return None
    df_pest = get_datos_tabla('matrices', empresa_id, tipo_matriz_filter='PEST')
    df_foda = get_datos_tabla('foda_cruzado', empresa_id)
    df_estrategias_pdf = get_datos_tabla('estrategias_generadas', empresa_id)
    
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

df_estrategias_pdf = get_datos_tabla('estrategias_generadas', empresa_id)
    
if not df_estrategias_pdf.empty:
        df_cmi = generar_cuadro_de_mando_ia(df_estrategias_pdf)
        if not df_cmi.empty:
            cmi_data = [df_cmi.columns.tolist()] + df_cmi.values.tolist()
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

    logo_bytes_data = empresa.get('logo')
    logo_bytes = None
    if logo_bytes_data:
        try:
            # Asumiendo que el logo se guarda como BLOB (bytes) en Supabase
            logo_bytes = BytesIO(logo_bytes_data) 
        except:
            # Si se guarda como texto (hex), se usaría la otra lógica
            try:
                logo_bytes = BytesIO(bytes.fromhex(logo_bytes_data.replace('\\x', '')))
            except:
                pass
    
    doc.build(story, onFirstPage=lambda c, d: encabezado_pie_pagina(c, d, logo_bytes, empresa.get('nombre', ''), version, coordinador), 
                     onLaterPages=lambda c, d: encabezado_pie_pagina(c, d, logo_bytes, empresa.get('nombre', ''), version, coordinador))
    
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
        # --- INICIO DEL BLOQUE DE REEMPLAZO PARA EL SIDEBAR ---
    with st.sidebar:
        st.header("Gestión de Empresas")
        empresas_df = get_empresas()
        
        # Manejo seguro por si empresas_df está vacío
        nombres_empresas = []
        if not empresas_df.empty:
            nombres_empresas = empresas_df['nombre'].tolist()

        empresa_seleccionada = st.selectbox("Selecciona una Empresa", nombres_empresas, index=None, placeholder="Elige una opción")
        
        empresa_id = None
        if empresa_seleccionada and not empresas_df.empty:
            empresa_id = int(empresas_df[empresas_df['nombre'] == empresa_seleccionada]['id'].iloc[0])

        st.divider()

        with st.expander("➕ Crear Nueva Empresa"):
            with st.form("new_empresa_form"):
                new_empresa_name = st.text_input("Nombre de la nueva empresa")
                if st.form_submit_button("Crear"):
                    if new_empresa_name and supabase and st.session_state.get("user"):
                        try:
                            user_id = st.session_state.user.id
                            supabase.table('empresas').insert({
                                "nombre": new_empresa_name,
                                "propietario_id": user_id
                            }).execute()
                            st.success(f"Empresa '{new_empresa_name}' creada en la nube.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al crear la empresa: {e}")
                    else:
                        st.warning("El nombre no puede estar vacío.")

        if empresa_id:
            # Este bloque solo se muestra si se ha seleccionado una empresa
            if st.button("❌ Eliminar Empresa Seleccionada", type="primary"):
                if supabase:
                    try:
                        # RLS se encarga de verificar que solo el propietario pueda borrar
                        supabase.table('empresas').delete().eq('id', empresa_id).execute()
                        st.success(f"Empresa '{empresa_seleccionada}' eliminada.")
                        # Forzar un rerun para que la empresa desaparezca de la lista
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar la empresa: {e}")

    # --- FIN DEL BLOQUE DE REEMPLAZO PARA EL SIDEBAR ---
                
if not empresa_id:
        st.info("👈 Por favor, selecciona o crea una empresa en el menú lateral para comenzar.")
        st.stop()

empresa_data = get_datos_empresa(empresa_id)
if not empresa_data:
        st.error("No se pudieron cargar los datos de la empresa. Verifica tus permisos.")
        st.stop()

# Definir permisos para deshabilitar widgets
es_propietario = empresa_data.get('propietario_id') == st.session_state.user.id
es_editor = False
if not es_propietario:
    try:
        res = supabase.table('empresas_compartidas').select('permiso').eq('empresa_id', empresa_id).eq('usuario_compartido_id', st.session_state.user.id).single().execute()
        if res.data and res.data['permiso'] == 'editor':
            es_editor = True
    except: # PostgrestError si no se encuentra la fila
        es_editor = False

puede_editar = es_propietario or es_editor

    # --- INICIO DEL BLOQUE DE REEMPLAZO ---

tab1, tab2, tab_est, tab3, tab4, tab5, tab_dash, tab6 = st.tabs(["1. Introducción", "2. Diagnóstico Situacional", "3. Estrategia", "4. Planes Estratégicos", "5. CMI/Indicadores", "6. Operativización/Presupuesto", "7. Dashboard de Análisis", "8. Resumen y Conclusiones"])

    # --- PESTAÑA 1: INTRODUCCIÓN ---
with tab1:
        st.header("Introducción y Cultura Organizacional")
        with st.form("form_intro"):
            st.subheader("Datos Generales")
            nombre = st.text_input("Nombre de la Empresa", empresa_data.get('nombre', ''), disabled=not puede_editar)
            giro = st.text_input("Giro del Negocio", empresa_data.get('giro', ''), disabled=not puede_editar)
            logo_file = st.file_uploader("Subir Logo", type=['png', 'jpg', 'jpeg'], disabled=not puede_editar)
            
            logo_actual = empresa_data.get('logo')
            if logo_actual:
                try:
                    st.image(BytesIO(bytes.fromhex(logo_actual.replace('\\x', ''))), width=150)
                except: pass

            st.divider()
            st.subheader("Cultura Organizacional")
            objetivo_plan = st.text_area("Objetivo del Plan Estratégico", empresa_data.get('objetivo_plan', ''), disabled=not puede_editar)
            mision = st.text_area("Misión", empresa_data.get('mision', ''), disabled=not puede_editar)
            vision = st.text_area("Visión", empresa_data.get('vision', ''), disabled=not puede_editar)
            obj_gen = st.text_area("Objetivo General", empresa_data.get('obj_general', ''), disabled=not puede_editar)
            obj_esp = st.text_area("Objetivos Específicos", empresa_data.get('obj_especificos', ''), disabled=not puede_editar)
            politicas = st.text_area("Políticas de la Empresa", empresa_data.get('politicas', ''), disabled=not puede_editar)
            valores = st.text_area("Valores y Principios", empresa_data.get('valores', ''), disabled=not puede_editar)
            organigrama_file = st.file_uploader("Subir Organigrama", type=['png', 'jpg', 'jpeg'], disabled=not puede_editar)
            
            org_actual = empresa_data.get('organigrama')
            if org_actual:
                try:
                    st.image(BytesIO(bytes.fromhex(org_actual.replace('\\x', ''))))
                except: pass

            if st.form_submit_button("Guardar Introducción", disabled=not puede_editar):
                update_data = {
                    "nombre": nombre, "giro": giro, "objetivo_plan": objetivo_plan, "mision": mision, 
                    "vision": vision, "obj_general": obj_gen, "obj_especificos": obj_esp, 
                    "politicas": politicas, "valores": valores
                }
                
                logo_bytes = save_image(logo_file)
                if logo_bytes: update_data['logo'] = logo_bytes
                
                org_bytes = save_image(organigrama_file)
                if org_bytes: update_data['organigrama'] = org_bytes

                try:
                    supabase.table('empresas').update(update_data).eq('id', empresa_id).execute()
                    st.success("Datos de introducción guardados."); st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    # --- PESTAÑA 2: DIAGNÓSTICO SITUACIONAL (CORREGIDA) ---
with tab2:
        st.header("Diagnóstico Situacional (Análisis de Matrices)")

        # La variable 'empresa_data' ya está cargada al principio de aplicacion_principal()
        # La variable 'puede_editar' también está definida y disponible.

        # Función interna para procesar datos pegados (se mantiene igual)
        def procesar_made_madi(data_str, tipo):
            # ... (Tu lógica original para procesar datos de Excel va aquí)
            # Asegúrate de que esta función devuelva un DataFrame de Pandas.
            # Por ejemplo:
            df = pd.read_csv(StringIO(data_str), sep='\t', header=0)
            # ... más procesamiento ...
            return df # df_to_db en tu código original

        def display_and_edit_matrix(tipo_matriz, analisis_propio_data):
            df_db = get_datos_tabla('matriz_marketing', empresa_id, tipo_matriz_filter=tipo_matriz)
            
            if not df_db.empty:
                st.info("Puedes editar los datos directamente en la tabla.")
                df_display = df_db.drop(columns=['id', 'empresa_id', 'tipo_matriz'], errors='ignore')
                edited_df = st.data_editor(df_display, key=f"editor_{tipo_matriz}", num_rows="dynamic", use_container_width=True, disabled=not puede_editar)
                
                if st.button(f"💾 Guardar Cambios en {tipo_matriz}", disabled=not puede_editar, key=f"save_{tipo_matriz}"):
                    try:
                        supabase.table('matriz_marketing').delete().eq('empresa_id', empresa_id).eq('tipo_matriz', tipo_matriz).execute()
                        if not edited_df.empty:
                            df_to_save = procesar_made_madi(edited_df.to_csv(sep='\t', index=False), tipo_matriz) # Re-procesar para asegurar consistencia
                            df_to_save['empresa_id'] = empresa_id
                            df_to_save['tipo_matriz'] = tipo_matriz
                            supabase.table('matriz_marketing').insert(df_to_save.to_dict(orient='records')).execute()
                        st.success(f"Cambios en {tipo_matriz} guardados."); st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar {tipo_matriz}: {e}")
                
                total_score = df_db['total'].sum() if 'total' in df_db.columns else 0
                st.metric(f"Puntaje Total {tipo_matriz}", f"{total_score}")
                # ... (resto de tu lógica de análisis automático)
            else:
                st.info(f"Aún no hay datos para la Matriz {tipo_matriz}. Pega los datos desde Excel para comenzar.")
        
        diag_tab1, diag_tab2, diag_tab3, diag_tab4, diag_tab5 = st.tabs([
            "Matriz MADE", "Matriz MADI", "Matriz de Posicionamiento", "Matriz PEST", "Matriz FODA Numérico"
        ])

        with diag_tab1:
            st.subheader("Análisis de Marketing Interno (MADE)")
            with st.expander("📋 Pegar datos de MADE desde Excel"):
                made_paste_data = st.text_area("Pega tus datos de MADE aquí", height=200, key="paste_MADE")
                if st.button("Procesar y Reemplazar Datos de MADE", key="process_made", disabled=not puede_editar):
                    try:
                        df_made = procesar_made_madi(made_paste_data, 'MADE')
                        supabase.table('matriz_marketing').delete().eq('empresa_id', empresa_id).eq('tipo_matriz', 'MADE').execute()
                        df_made['empresa_id'] = empresa_id
                        df_made['tipo_matriz'] = 'MADE'
                        supabase.table('matriz_marketing').insert(df_made.to_dict(orient='records')).execute()
                        st.success(f"¡{len(df_made)} filas importadas a MADE exitosamente!"); st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar datos de MADE: {e}")
            display_and_edit_matrix('MADE', empresa_data.get('analisis_made', ''))
            mostrar_ultimo_analisis_guardado(empresa_id, 'made')

        with diag_tab2:
            st.subheader("Análisis de Marketing Externo (MADI)")
            with st.expander("📋 Pegar datos de MADI desde Excel"):
                madi_paste_data = st.text_area("Pega tus datos de MADI aquí", height=200, key="paste_MADI")
                if st.button("Procesar y Reemplazar Datos de MADI", key="process_madi", disabled=not puede_editar):
                    try:
                        df_madi = procesar_made_madi(madi_paste_data, 'MADI')
                        supabase.table('matriz_marketing').delete().eq('empresa_id', empresa_id).eq('tipo_matriz', 'MADI').execute()
                        df_madi['empresa_id'] = empresa_id
                        df_madi['tipo_matriz'] = 'MADI'
                        supabase.table('matriz_marketing').insert(df_madi.to_dict(orient='records')).execute()
                        st.success(f"¡{len(df_madi)} filas importadas a MADI exitosamente!"); st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar datos de MADI: {e}")
            display_and_edit_matrix('MADI', empresa_data.get('analisis_madi', ''))
            mostrar_ultimo_analisis_guardado(empresa_id, 'madi')

        with diag_tab3:
            st.subheader("Matriz de Posicionamiento")
            # Los datos ya no se leen aquí, se usan los de 'empresa_data'
            coord_x_val = float(empresa_data.get('posicionamiento_x') or 0)
            coord_y_val = float(empresa_data.get('posicionamiento_y') or 0)

            with st.form("form_posicionamiento"):
                coord_x = st.number_input("Coordenada X", value=coord_x_val, disabled=not puede_editar)
                coord_y = st.number_input("Coordenada Y", value=coord_y_val, disabled=not puede_editar)
                if st.form_submit_button("Guardar y Generar Gráfico", disabled=not puede_editar):
                    try:
                        supabase.table('empresas').update({"posicionamiento_x": coord_x, "posicionamiento_y": coord_y}).eq('id', empresa_id).execute()
                        st.success("Coordenadas guardadas."); st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar coordenadas: {e}")
            
            fig, ax = plt.subplots()
            ax.axhline(0, color='gray', lw=1); ax.axvline(0, color='gray', lw=1)
            ax.plot(coord_x_val, coord_y_val, 'ro', markersize=10)
            ax.set_title("Matriz de Posicionamiento"); ax.set_xlabel("Eje X"); ax.set_ylabel("Eje Y")
            ax.grid(True, which='both', linestyle='--', linewidth=0.5)
            st.pyplot(fig)
            
            st.subheader("📌 Diagnóstico Estratégico de Posicionamiento")
            # ... (Tu lógica de interpretaciones se mantiene igual)
            
            with st.form("form_analisis_pos"):
                st.subheader("Análisis Estratégico")
                if st.form_submit_button("🤖 Generar Análisis con IA"):
                    with st.spinner("La IA está analizando la posición..."):
                        # ... (Tu lógica de generación de análisis con IA)
                        pass
                
                current_analisis_pos = st.session_state.get("ia_analisis_posicionamiento", empresa_data.get('analisis_posicionamiento', ''))
                analisis_propio_pos = st.text_area("Conclusiones sobre el posicionamiento.", value=current_analisis_pos, height=300, disabled=not puede_editar)
                if st.form_submit_button("Guardar Análisis de Posicionamiento", disabled=not puede_editar):
                    guardar_analisis_db(empresa_id, 'posicionamiento', analisis_propio_pos)
            
            mostrar_ultimo_analisis_guardado(empresa_id, 'posicionamiento')

        with diag_tab4:
            st.subheader("Análisis PEST")
            with st.expander("📋 Pegar datos desde Excel"):
                pest_paste_data = st.text_area("Pega tus datos aquí", height=200, key="pest_input_secondary")
                if st.button("Procesar Datos Pegados de PEST", disabled=not puede_editar):
                    try:
                        df_pasted = pd.read_csv(StringIO(pest_paste_data), sep='\t', header=0)
                        df_pasted.columns = ['categoria', 'factor', 'tipo_foda', 'puntaje', 'importancia']
                        df_pasted['valor_ponderado'] = pd.to_numeric(df_pasted['puntaje'], errors='coerce') * (pd.to_numeric(df_pasted['importancia'], errors='coerce') / 100.0)
                        df_pasted['empresa_id'] = empresa_id
                        df_pasted['tipo_matriz'] = 'PEST'
                        
                        supabase.table('matrices').delete().eq('empresa_id', empresa_id).eq('tipo_matriz', 'PEST').execute()
                        supabase.table('matrices').insert(df_pasted.to_dict(orient='records')).execute()
                        st.success(f"¡{len(df_pasted)} filas importadas a PEST exitosamente!"); st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar los datos: {e}.")
            
            df_pest = get_datos_tabla('matrices', empresa_id, tipo_matriz_filter='PEST')
            if not df_pest.empty:
                edited_pest = st.data_editor(df_pest.drop(columns=['id', 'empresa_id', 'tipo_matriz'], errors='ignore'), num_rows="dynamic", key="editor_pest_v2", use_container_width=True, disabled=not puede_editar)
                if st.button("💾 Guardar Cambios en PEST", disabled=not puede_editar):
                    try:
                        supabase.table('matrices').delete().eq('empresa_id', empresa_id).eq('tipo_matriz', 'PEST').execute()
                        if not edited_pest.empty:
                            edited_pest['empresa_id'] = empresa_id
                            edited_pest['tipo_matriz'] = 'PEST'
                            supabase.table('matrices').insert(edited_pest.to_dict(orient='records')).execute()
                        st.success("Cambios en PEST guardados."); st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar PEST: {e}")
                
                total_ponderado = pd.to_numeric(df_pest['valor_ponderado'], errors='coerce').sum()
                st.metric("Puntaje Ponderado Total PEST", f"{total_ponderado:.2f}")
                # ... (Tu lógica de análisis de perfil)
            
            with st.form("form_analisis_pest"):
                st.subheader("Análisis Estratégico")
                if st.form_submit_button("🤖 Generar Análisis con IA"):
                    with st.spinner("La IA está analizando el entorno PEST..."):
                        # ... (Tu lógica de generación de análisis)
                        pass
                
                current_analisis_pest = st.session_state.get("ia_analisis_pest", empresa_data.get('analisis_pest', ''))
                analisis_propio_pest = st.text_area("Conclusiones sobre la matriz PEST.", value=current_analisis_pest, height=300, disabled=not puede_editar)
                if st.form_submit_button("Guardar Análisis", disabled=not puede_editar):
                    guardar_analisis_db(empresa_id, 'pest', analisis_propio_pest)
            
            mostrar_ultimo_analisis_guardado(empresa_id, 'pest')

        with diag_tab5:
            st.subheader("Análisis FODA Cruzado (Numérico)")
            with st.expander("📋 Pegar datos de FODA Cruzado desde Excel"):
                foda_paste_data = st.text_area("Pega tus datos de FODA aquí", height=200, key="foda_paste_area")
                if st.button("Procesar Datos Pegados de FODA", disabled=not puede_editar):
                    try:
                        df_foda_pasted = pd.read_csv(StringIO(foda_paste_data), sep='\t', header=0)
                        df_foda_pasted.columns = ['cuadrante', 'factor_fila', 'factor_columna', 'impacto']
                        df_foda_pasted['impacto'] = pd.to_numeric(df_foda_pasted['impacto'], errors='coerce').fillna(0).astype(int)
                        df_foda_pasted['empresa_id'] = empresa_id
                        
                        supabase.table('foda_cruzado').delete().eq('empresa_id', empresa_id).execute()
                        supabase.table('foda_cruzado').insert(df_foda_pasted.to_dict(orient='records')).execute()
                        st.success(f"¡{len(df_foda_pasted)} filas importadas a FODA Cruzado!"); st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar los datos: {e}.")
            
            df_foda = get_datos_tabla('foda_cruzado', empresa_id)
            if not df_foda.empty:
                edited_foda = st.data_editor(df_foda.drop(columns=['id', 'empresa_id'], errors='ignore'), num_rows="dynamic", key="editor_foda", use_container_width=True, disabled=not puede_editar)
                if st.button("💾 Guardar Cambios en FODA", disabled=not puede_editar):
                    try:
                        supabase.table('foda_cruzado').delete().eq('empresa_id', empresa_id).execute()
                        if not edited_foda.empty:
                            edited_foda['empresa_id'] = empresa_id
                            supabase.table('foda_cruzado').insert(edited_foda.to_dict(orient='records')).execute()
                        st.success("Cambios en FODA guardados."); st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar FODA: {e}")
                
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
                        # ... (Tu lógica de generación de análisis)
                        pass
                
                current_analisis_foda = st.session_state.get("ia_analisis_foda", empresa_data.get('analisis_foda', ''))
                analisis_propio_foda = st.text_area("Conclusiones sobre la matriz FODA.", value=current_analisis_foda, height=300, disabled=not puede_editar)
                if st.form_submit_button("Guardar Análisis", disabled=not puede_editar):
                    guardar_analisis_db(empresa_id, 'foda', analisis_propio_foda)
            
            mostrar_ultimo_analisis_guardado(empresa_id, 'foda')            
    # --- PESTAÑA 3: ESTRATEGIA ---
with tab_est:
        st.header("🎯 Formulación de Estrategias")
        # ... (Tu lógica de generación de estrategias con IA)
        
        df_estrategias = get_datos_tabla('estrategias_generadas', empresa_id)
        edited_df = st.data_editor(
            df_estrategias.drop(columns=['id', 'empresa_id'], errors='ignore'), num_rows="dynamic", key="editor_v5", use_container_width=True,
            disabled=not puede_editar,
            column_config={
                "cuadrante": st.column_config.SelectboxColumn("Cuadrante", options=["FO", "FA", "DO", "DA"]),
                "importancia": st.column_config.SelectboxColumn("Importancia", options=["Alta", "Media Alta", "Media Baja", "Baja"]),
                "plan_asignado": st.column_config.SelectboxColumn("Plan Asignado", options=["Plan Administrativo", "Plan Operativo", "Plan Tecnológico", "Plan Financiero", "Plan de Monitoreo y control", "Plan de Mejora", "Plan de Contingencia"]),
            }
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Guardar Cambios", disabled=not puede_editar):
                try:
                    supabase.table('estrategias_generadas').delete().eq('empresa_id', empresa_id).execute()
                    if not edited_df.empty:
                        edited_df['empresa_id'] = empresa_id
                        supabase.table('estrategias_generadas').insert(edited_df.to_dict(orient='records')).execute()
                    st.success("Estrategias guardadas."); st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar estrategias: {e}")

        with col2:
            if st.button("🚀 Enviar a Operativización", disabled=not puede_editar):
                # ... (Tu lógica para enviar a operativización, usando 'edited_df')
                pass
    
    # --- PESTAÑA 4: PLANES ESTRATÉGICOS ---
with tab3:
        st.header("Planes Estratégicos")
        with st.form("form_planes"):
            if st.form_submit_button("🤖 Generar Planes con IA"):
                # ... (Tu lógica de generación de planes)
                pass
            
            current_analisis_operativo = st.session_state.get("ia_analisis_operativo", empresa_data.get('analisis_operativo', ''))
            analisis_propio_operativo = st.text_area("Edite el Plan Estratégico Maestro", value=current_analisis_operativo, height=400, disabled=not puede_editar)
            
            if st.form_submit_button("💾 Guardar Plan Maestro", disabled=not puede_editar):
                guardar_analisis_db(empresa_id, 'operativo', analisis_propio_operativo)
        
        mostrar_ultimo_analisis_guardado(empresa_data, 'operativo')
    
    # --- PESTAÑA 5: CMI/INDICADORES ---
with tab4:
        st.header("CMI / Indicadores")
        with st.form("form_cmi"):
            if st.form_submit_button("🤖 Generar CMI con IA"):
                # ... (Tu lógica de generación de CMI)
                pass
            
            current_analisis_cmi = st.session_state.get("ia_analisis_cmi", empresa_data.get('analisis_cmi', ''))
            analisis_propio_cmi = st.text_area("Edite el Cuadro de Mando Integral", value=current_analisis_cmi, height=400, disabled=not puede_editar)
            
            if st.form_submit_button("💾 Guardar CMI", disabled=not puede_editar):
                guardar_analisis_db(empresa_id, 'cmi', analisis_propio_cmi)
        
        mostrar_ultimo_analisis_guardado(empresa_data, 'cmi')
    
    # --- PESTAÑA 6: OPERATIVIZACIÓN/PRESUPUESTO ---
with tab5:
        st.header("Operativización / Presupuesto")
        
        # Cuadro de Operativización
        df_oper = get_datos_tabla('operativizacion', empresa_id)
        edited_oper = st.data_editor(df_oper.drop(columns=['id', 'empresa_id'], errors='ignore'), num_rows="dynamic", key="editor_oper_cascada", use_container_width=True, disabled=not puede_editar)
        if st.button("💾 Guardar Operativización", disabled=not puede_editar):
            try:
                supabase.table('operativizacion').delete().eq('empresa_id', empresa_id).execute()
                if not edited_oper.empty:
                    edited_oper['empresa_id'] = empresa_id
                    supabase.table('operativizacion').insert(edited_oper.to_dict(orient='records')).execute()
                st.success("Operativización guardada."); st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")
        
        # Estado de Pérdidas y Ganancias
        df_pg = get_datos_tabla('perdida_ganancia', empresa_id)
        edited_pg = st.data_editor(df_pg.drop(columns=['id', 'empresa_id'], errors='ignore'), num_rows="dynamic", key="editor_pg_v2", use_container_width=True, disabled=not puede_editar)
        if st.button("💾 Guardar P&G", disabled=not puede_editar):
            try:
                supabase.table('perdida_ganancia').delete().eq('empresa_id', empresa_id).execute()
                if not edited_pg.empty:
                    edited_pg['empresa_id'] = empresa_id
                    supabase.table('perdida_ganancia').insert(edited_pg.to_dict(orient='records')).execute()
                st.success("Datos de P&G guardados."); st.rerun()
            except Exception as e:
                st.error(f"Error al guardar P&G: {e}")

        # Flujo de Caja Proyectado
        df_fc = get_datos_tabla('flujo_caja', empresa_id)
        edited_fc = st.data_editor(df_fc.drop(columns=['id', 'empresa_id'], errors='ignore'), num_rows="fixed", key="editor_fc_v2", use_container_width=True, disabled=not puede_editar)
        if st.button("🧮 Calcular y Guardar Flujo", disabled=not puede_editar):
            # ... (Tu lógica de cálculo de flujo)
            try:
                supabase.table('flujo_caja').delete().eq('empresa_id', empresa_id).execute()
                if not edited_fc.empty:
                    edited_fc['empresa_id'] = empresa_id
                    supabase.table('flujo_caja').insert(edited_fc.to_dict(orient='records')).execute()
                st.success("Flujo de caja guardado."); st.rerun()
            except Exception as e:
                st.error(f"Error al guardar flujo de caja: {e}")

        # Análisis de Costo / Beneficio
        pe_data = get_datos_tabla('punto_equilibrio', empresa_id)
        # ... (Tu lógica de C/B y punto de equilibrio, usando 'pe_data')
        
    # --- PESTAÑA 7: DASHBOARD DE ANÁLISIS ---
with tab_dash:
        st.header("📊 Dashboard de Análisis Estratégico")
        df_est_dash = get_datos_tabla('estrategias_generadas', empresa_id)
        df_pg_dash = get_datos_tabla('perdida_ganancia', empresa_id)
        df_fc_dash = get_datos_tabla('flujo_caja', empresa_id)
        # ... (Toda tu lógica de visualización con Plotly se mantiene intacta)
        
    # --- PESTAÑA 8: RESUMEN Y CONCLUSIONES ---
with tab6:
        st.header("Resumen, Conclusiones y Exportación")
        with st.form("pdf_form"):
            pdf_version = st.text_input("Versión del Plan", value="1.0")
            pdf_coordinador = st.text_input("Coordinador del Plan", value="Consultor Estratégico")
            if st.form_submit_button("🚀 Generar y Descargar PDF"):
                pdf_bytes = generar_pdf_completo(empresa_id, pdf_version, pdf_coordinador)
                if pdf_bytes:
                    st.session_state['pdf_file'] = pdf_bytes
        
        if 'pdf_file' in st.session_state:
            st.download_button(label="✅ Descargar PDF Ahora", data=st.session_state['pdf_file'], file_name=f"Plan_Estrategico_V{pdf_version}.pdf", mime="application/pdf")
    
    # --- FIN DEL BLOQUE DE REEMPLAZO ---
def pantalla_acceso():
    st.sidebar.title("Estratega Pro")
    opcion = st.sidebar.radio("Acceso al Sistema", ["Entrar", "Crear Cuenta"])
    
    col1, col2 = st.columns([2,1])
    with col1:
        if opcion == "Entrar":
            st.subheader("🔐 Iniciar Sesión")
            with st.form("login_form"):
                email = st.text_input("Correo Electrónico")
                password = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Acceder"):
                    if supabase:
                        try:
                            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                            st.session_state.user = res.user
                            st.session_state.logged_in = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al iniciar sesión: {e}")
        else:
            st.subheader("📝 Registro de Nuevo Consultor")
            with st.form("signup_form"):
                nombre = st.text_input("Nombre Completo")
                email = st.text_input("Correo Electrónico")
                password = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Finalizar Registro"):
                    if nombre and email and password and supabase:
                        try:
                            res = supabase.auth.sign_up({"email": email, "password": password, "options": {"data": {"full_name": nombre}}})
                            if res.user:
                                st.success("¡Registro exitoso! Ya puedes iniciar sesión.")
                            else:
                                st.error("No se pudo completar el registro.")
                        except Exception as e:
                            st.error(f"Error en el registro: {e}")
                    else:
                        st.warning("Por favor, llena todos los campos.")
    with col2:
        st.image("https://i.imgur.com/gYv2k3C.png", width=200 )
def main():
    """Función principal que controla el flujo de la aplicación."""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    
    if not st.session_state.get("logged_in"):
        pantalla_acceso()
    else:
        aplicacion_principal()

if __name__ == "__main__":
    if supabase:
        main()
    else:
        st.error("La aplicación no puede iniciarse. Revisa la conexión con la base de datos (Supabase).")

