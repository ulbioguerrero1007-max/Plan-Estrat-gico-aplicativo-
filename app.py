import streamlit as st
import pandas as pd
import sqlite3
import io
from io import StringIO, BytesIO
from reportlab.pdfgen import canvas
# --- CORRECCIÓN 1: Importar A4 en lugar de letter ---
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import navy, grey, red, green, black
# --- CORRECCIÓN 1: Importar TA_LEFT para los nuevos estilos ---
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
import matplotlib.pyplot as plt
import numpy as np

# --- DATABASE UTILS (Sin cambios) ---
def get_connection():
    return sqlite3.connect('strategic_plan.db', timeout=10)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS empresas (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE, giro TEXT, logo BLOB, introduccion TEXT, mision TEXT, vision TEXT, organigrama BLOB, politicas TEXT, valores TEXT, efi_score REAL, efe_score REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS matrices (id INTEGER PRIMARY KEY, empresa_id INTEGER, tipo_matriz TEXT NOT NULL, categoria TEXT, factor TEXT, tipo_foda TEXT, puntaje REAL, importancia REAL, valor_ponderado REAL, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS foda_cruzado (id INTEGER PRIMARY KEY, empresa_id INTEGER, cuadrante TEXT, factor_fila TEXT, factor_columna TEXT, impacto INTEGER, FOREIGN KEY (empresa_id) REFERENCES empresas (id) ON DELETE CASCADE)''')
        conn.commit()

def get_empresas():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, nombre FROM empresas", conn)

def save_image(uploaded_file):
    if uploaded_file:
        return uploaded_file.getvalue()
    return None

# --- ANALYSIS & GENERATION UTILS (Sin cambios) ---
def analizar_foda(df_foda):
    if df_foda.empty: return None, None, None, pd.Series(dtype='float64')
    estrategias = {'FO': 'Ofensiva (F+O)', 'FA': 'Defensiva (F+A)', 'DO': 'Adaptativa (D+O)', 'DA': 'Supervivencia (D+A)'}
    puntajes = df_foda.groupby('cuadrante')['impacto'].sum().reindex(estrategias.keys(), fill_value=0)
    analisis_df = pd.DataFrame({'Estrategia': [estrategias[c] for c in puntajes.index], 'Puntaje Total': puntajes.values}).sort_values(by='Puntaje Total', ascending=False).reset_index(drop=True)
    estrategia_principal = analisis_df.iloc[0]['Estrategia']
    resumen = f"La estrategia principal recomendada es **{analisis_df.iloc[0]['Estrategia']}** ({analisis_df.iloc[0]['Puntaje Total']} puntos), seguida por **{analisis_df.iloc[1]['Estrategia']}** ({analisis_df.iloc[1]['Puntaje Total']} puntos)."
    return analisis_df, resumen, estrategia_principal, puntajes

def generar_planes_por_plantilla(estrategia_foda, efi_score, efe_score, pest_total):
    planes = {}
    if efi_score < 2.5:
        intro = f"El bajo puntaje EFI ({efi_score:.2f}) sugiere debilidades internas en la estructura o procesos administrativos. Es prioritario abordar estas ineficiencias para fortalecer la base de la organización."
        obj = "Realizar una auditoría de procesos internos en los próximos 3 meses para identificar y rediseñar 2 flujos de trabajo clave, buscando una mejora medible en la eficiencia del 15%."
    else:
        intro = f"Con un sólido puntaje EFI de {efi_score:.2f}, la empresa demuestra una fuerte posición administrativa. El enfoque será consolidar esta ventaja y fomentar la innovación continua."
        obj = "Implementar un programa de formación en liderazgo y gestión de proyectos para los mandos medios en los próximos 6 meses."
    planes['Administrativo'] = {'introduccion': intro, 'objetivo': obj}
    if "Ofensiva" in estrategia_foda:
        intro = "La posición estratégica es Ofensiva. El plan debe centrarse en usar las fortalezas para capitalizar al máximo las oportunidades de mercado."
        obj = "Lanzar una nueva línea de producto/servicio que explote nuestras fortalezas en los próximos 12 meses, para capturar un 5% más de cuota de mercado."
    elif "Adaptativa" in estrategia_foda:
        intro = "La estrategia recomendada es Adaptativa. Se deben desarrollar áreas internas para poder aprovechar las oportunidades externas."
        obj = "Iniciar un programa de capacitación técnica en el próximo trimestre para cerrar brechas de debilidades y abordar 2 nuevas oportunidades de mercado."
    else:
        intro = "La estrategia es Defensiva/Supervivencia. La prioridad es proteger la posición actual, usando fortalezas para mitigar amenazas."
        obj = "Implementar un plan de retención de clientes clave en los próximos 6 meses, para reducir la tasa de abandono en un 10%."
    planes['Mejora'] = {'introduccion': intro, 'objetivo': obj}
    if pest_total < 2.5 or efe_score < 2.5:
        intro = f"El análisis del entorno (PEST: {pest_total:.2f}, EFE: {efe_score:.2f}) revela vulnerabilidad a factores externos. Es crucial desarrollar planes para mitigar riesgos."
        obj = "Formar un comité de gestión de riesgos que, en 2 meses, identifique los 3 principales riesgos externos y desarrolle un plan de respuesta específico."
    else:
        intro = f"La empresa muestra buena respuesta al entorno (PEST: {pest_total:.2f}, EFE: {efe_score:.2f}). El plan se enfocará en la monitorización proactiva de eventos inesperados."
        obj = "Establecer un sistema de vigilancia del entorno trimestral y realizar un simulacro de crisis anual."
    planes['Contingencia'] = {'introduccion': intro, 'objetivo': obj}
    if "Ofensiva" in estrategia_foda or "Adaptativa" in estrategia_foda:
        intro = "La estrategia de crecimiento requiere un apalancamiento tecnológico. Se debe invertir en innovación para ganar ventaja competitiva."
        obj = "Evaluar e implementar una nueva herramienta de CRM o ERP en los próximos 9 meses para mejorar la relación con clientes y la eficiencia operativa."
    else:
        intro = "La tecnología debe usarse para robustecer la operación y defender la posición actual. La prioridad es la seguridad y la estabilidad."
        obj = "Realizar una auditoría de ciberseguridad completa en el próximo trimestre y actualizar los sistemas críticos para mitigar vulnerabilidades."
    planes['Tecnológico'] = {'introduccion': intro, 'objetivo': obj}
    if efi_score < 2.5:
        intro = "Las debilidades internas (EFI: {:.2f}) impactan directamente en la operación. Es necesario optimizar la cadena de valor y los procesos productivos/de servicio.".format(efi_score)
        obj = "Mapear la cadena de valor actual para identificar y eliminar un cuello de botella principal en los próximos 4 meses, reduciendo los tiempos de ciclo en un 10%."
    else:
        intro = "La operación interna es un punto fuerte (EFI: {:.2f}). El plan se enfocará en escalar las operaciones de manera eficiente para soportar el crecimiento.".format(efi_score)
        obj = "Desarrollar un plan de escalabilidad operativa para aumentar la capacidad de producción/servicio en un 20% en el próximo año, sin sacrificar la calidad."
    planes['Operativo'] = {'introduccion': intro, 'objetivo': obj}
    if "Ofensiva" in estrategia_foda or "Adaptativa" in estrategia_foda:
        intro = "Dado que la estrategia implica nuevas iniciativas y crecimiento, se requiere un sistema de monitoreo ágil y riguroso para asegurar que los objetivos se cumplan."
        obj = "Implementar un dashboard de KPIs (Indicadores Clave) en tiempo real para los nuevos proyectos y establecer un ciclo de revisión estratégica mensual."
    else:
        intro = "El monitoreo debe centrarse en indicadores de alerta temprana y en el control de los factores críticos para la supervivencia del negocio."
        obj = "Definir 5 indicadores de riesgo clave (KRIs) y establecer un sistema de alertas automáticas para la alta dirección, con revisión semanal."
    planes['Monitoreo y control'] = {'introduccion': intro, 'objetivo': obj}
    if ("Ofensiva" in estrategia_foda or "Adaptativa" in estrategia_foda) and efe_score > 2.5:
        intro = "El entorno es favorable y la estrategia es de crecimiento. El plan financiero debe enfocarse en asegurar los fondos para la expansión."
        obj = "Preparar un caso de negocio y una ronda de financiación (o asegurar una línea de crédito) en los próximos 6 meses para financiar las nuevas iniciativas estratégicas."
    else:
        intro = "La situación financiera debe ser gestionada con prudencia. La prioridad es la optimización de costos, la gestión de la liquidez y la maximización de la rentabilidad actual."
        obj = "Implementar un plan de reducción de costos no esenciales para mejorar el margen de beneficio neto en un 2% en los próximos 6 meses, sin afectar la operación crítica."
    planes['Financiero'] = {'introduccion': intro, 'objetivo': obj}
    return planes

def generar_cuadro_de_mando(planes):
    cmi_data = []
    for nombre_plan, datos_plan in planes.items():
        objetivo = datos_plan['objetivo'].lower()
        perspectiva = 'Procesos Internos'
        if any(keyword in objetivo for keyword in ['margen', 'costo', 'ingreso', 'financiar', 'cuota de mercado', 'rentabilidad']):
            perspectiva = 'Financiera'
        elif any(keyword in objetivo for keyword in ['cliente', 'retención', 'abandono', 'propuesta de valor', 'satisfacción']):
            perspectiva = 'Clientes'
        elif any(keyword in objetivo for keyword in ['capacitación', 'habilidades', 'liderazgo', 'cultura', 'innovación', 'sistemas', 'ciberseguridad']):
            perspectiva = 'Aprendizaje y Crecimiento'
        kpi = "Por definir"
        meta = "Por definir"
        iniciativa = f"Proyecto derivado del Plan {nombre_plan}"
        cmi_data.append([perspectiva, datos_plan['objetivo'], kpi, meta, iniciativa])
    df_cmi = pd.DataFrame(cmi_data, columns=['Perspectiva', 'Objetivo Estratégico', 'KPI (Indicador)', 'Meta', 'Iniciativa'])
    perspectiva_orden = ['Financiera', 'Clientes', 'Procesos Internos', 'Aprendizaje y Crecimiento']
    df_cmi['Perspectiva'] = pd.Categorical(df_cmi['Perspectiva'], categories=perspectiva_orden, ordered=True)
    return df_cmi.sort_values(by='Perspectiva').reset_index(drop=True)

# --- PDF & GRAPHICS GENERATION UTILS (Sin cambios) ---
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

def generar_grafico_efi_efe(efi_score, efe_score):
    efi_score = efi_score or 0
    efe_score = efe_score or 0
    fig, ax = plt.subplots(figsize=(7, 2))
    ax.set_xlim(1, 4)
    ax.set_ylim(0, 2)
    ax.barh([1.5], [efe_score-1], left=1, height=0.5, color='skyblue', label='EFE')
    ax.text(efe_score if efe_score > 1.1 else 1.1, 1.5, f' {efe_score:.2f}', va='center')
    ax.barh([0.5], [efi_score-1], left=1, height=0.5, color='lightgreen', label='EFI')
    ax.text(efi_score if efi_score > 1.1 else 1.1, 0.5, f' {efi_score:.2f}', va='center')
    ax.axvline(2.5, color='red', linestyle='--', label='Promedio (2.5)')
    ax.set_yticks([0.5, 1.5])
    ax.set_yticklabels(['EFI (Interno)', 'EFE (Externo)'])
    ax.set_title('Posición Interna vs. Externa')
    ax.get_xaxis().set_visible(True)
    ax.legend(loc='lower right')
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

# --- CORRECCIÓN 1: Nueva función para estilos APA ---
def get_apa_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='APA_Body', fontName='Times-Roman', fontSize=12, leading=24, alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name='APA_H1', parent=styles['APA_Body'], fontName='Times-Bold', fontSize=14, alignment=TA_CENTER, spaceAfter=12))
    styles.add(ParagraphStyle(name='APA_H2', parent=styles['APA_Body'], fontName='Times-Bold', alignment=TA_LEFT, spaceBefore=12, spaceAfter=6))
    return styles

# REEMPLAZA LA FUNCIÓN ANTIGUA CON ESTA VERSIÓN MEJORADA Y DETALLADA

def generar_pdf_completo(empresa_id, version, coordinador):
    # 1. OBTENER TODOS LOS DATOS DE LA BASE DE DATOS
    with get_connection() as conn:
        empresa = pd.read_sql(f"SELECT * FROM empresas WHERE id={empresa_id}", conn).iloc[0]
        df_pest = pd.read_sql(f"SELECT categoria, factor, tipo_foda, puntaje, importancia, valor_ponderado FROM matrices WHERE empresa_id={empresa_id} AND tipo_matriz='PEST'", conn)
        df_foda = pd.read_sql(f"SELECT cuadrante, factor_fila, factor_columna, impacto FROM foda_cruzado WHERE empresa_id={empresa_id}", conn)

    # 2. PREPARAR ESTILOS Y DOCUMENTO
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, leftMargin=1*inch, rightMargin=1*inch, topMargin=1*inch, bottomMargin=1*inch)
    styles = get_apa_styles()
    story = []

    # 3. CONSTRUIR LA PORTADA
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("Plan Estratégico", styles['APA_H1']))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(empresa['nombre'], styles['APA_H1']))
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph(f"Versión: {version}", styles['APA_Body']))
    story.append(Paragraph(f"Fecha: {pd.Timestamp.now().strftime('%Y-%m-%d')}", styles['APA_Body']))
    story.append(PageBreak())

    # 4. CONSTRUIR EL RESUMEN EJECUTIVO (APROX. 5 PÁGINAS)
    story.append(Paragraph("Resumen Ejecutivo", styles['APA_H1']))
    story.append(Paragraph("Este resumen presenta los hallazgos y recomendaciones clave del diagnóstico estratégico. Está diseñado para proporcionar una visión general rápida y comprensible para la alta dirección, facilitando la toma de decisiones informadas.", styles['APA_Body']))
    story.append(Spacer(1, 24))

    # Análisis y gráficos
    analisis_foda_df, resumen_foda, estrategia_principal, puntajes_foda = analizar_foda(df_foda)
    pest_total = df_pest['valor_ponderado'].sum() if not df_pest.empty else 0
    efi_score = empresa.get('efi_score', 0)
    efe_score = empresa.get('efe_score', 0)

    # Página 2 del Resumen: Diagnóstico Gráfico y Análisis
    story.append(Paragraph("Diagnóstico Estratégico General", styles['APA_H2']))
    story.append(Paragraph(f"La estrategia principal recomendada, basada en el análisis FODA cruzado, es la <b>{estrategia_principal}</b>. Esto indica la postura que la empresa debería adoptar prioritariamente. El siguiente gráfico de radar ilustra la ponderación de las cuatro posibles estrategias.", styles['APA_Body']))
    grafico_foda = generar_grafico_foda_radar(puntajes_foda)
    if grafico_foda: story.append(Image(grafico_foda, width=5*inch, height=5*inch))
    
    story.append(Paragraph(f"La evaluación de factores internos (EFI) y externos (EFE) posiciona a la empresa de la siguiente manera. Un puntaje superior a 2.5 indica una posición fuerte en esa área. La empresa obtuvo un <b>EFI de {efi_score:.2f}</b> y un <b>EFE de {efe_score:.2f}</b>.", styles['APA_Body']))
    grafico_efi_efe = generar_grafico_efi_efe(efi_score, efe_score)
    if grafico_efi_efe: story.append(Image(grafico_efi_efe, width=6*inch, height=1.7*inch))
    story.append(PageBreak())

    # Página 3 del Resumen: Factores Críticos
    story.append(Paragraph("Factores Críticos de Éxito", styles['APA_H2']))
    story.append(Paragraph("A continuación, se destacan los factores más influyentes del análisis PEST, que representan las mayores oportunidades y amenazas del entorno.", styles['APA_Body']))
    if not df_pest.empty:
        pest_criticos = df_pest.sort_values(by='valor_ponderado', ascending=False).head(5)
        pest_data = [pest_criticos.columns.tolist()] + pest_criticos.values.tolist()
        pest_table = Table(pest_data, colWidths=[1.2*inch, 2*inch, 1*inch, 0.8*inch, 1*inch, 1*inch])
        pest_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), '#CCCCCC'), ('GRID', (0,0), (-1,-1), 1, '#000000')]))
        story.append(pest_table)
    story.append(Spacer(1, 24))
    
    # (Aquí se agregarían tablas similares para los factores críticos de EFI y EFE si estuvieran disponibles con ese detalle)
    story.append(PageBreak())

    # Página 4 del Resumen: Objetivos Estratégicos
    story.append(Paragraph("Objetivos Estratégicos Propuestos", styles['APA_H2']))
    story.append(Paragraph("Derivado del diagnóstico, se proponen los siguientes objetivos macro para cada área de planificación. Estos objetivos forman la base del Cuadro de Mando Integral.", styles['APA_Body']))
    planes = generar_planes_por_plantilla(estrategia_principal, efi_score, efe_score, pest_total)
    for nombre_plan, datos_plan in planes.items():
        story.append(Paragraph(f"<b>{nombre_plan}:</b> {datos_plan['objetivo']}", styles['APA_Body']))
        story.append(Spacer(1, 6))
    story.append(PageBreak())

    # Página 5 del Resumen: Conclusiones y Próximos Pasos
    story.append(Paragraph("Conclusiones y Próximos Pasos", styles['APA_H2']))
    story.append(Paragraph(f"<b>Conclusión General:</b> La empresa se encuentra en una posición estratégica <b>{estrategia_principal}</b>. Las fortalezas internas son {'adecuadas' if efi_score > 2.5 else 'insuficientes'} para la situación actual, y la capacidad de respuesta al entorno es {'fuerte' if efe_score > 2.5 else 'débil'}. Es imperativo actuar sobre los planes propuestos para capitalizar las ventajas y mitigar los riesgos.", styles['APA_Body']))
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>Recomendaciones Inmediatas:</b>", styles['APA_Body']))
    story.append(Paragraph("1. Revisar y aprobar el presente plan estratégico.", styles['APA_Body']))
    story.append(Paragraph("2. Asignar responsables y recursos para cada iniciativa del Cuadro de Mando Integral.", styles['APA_Body']))
    story.append(Paragraph("3. Establecer el ciclo de reuniones de monitoreo y control (recomendado: trimestral).", styles['APA_Body']))
    story.append(PageBreak())

    # 5. ANEXOS: TODA LA INFORMACIÓN DETALLADA
    story.append(Paragraph("Anexos: Detalles del Plan Estratégico", styles['APA_H1']))
    
    # Anexo A: Introducción y Cultura
    story.append(Paragraph("Anexo A: Introducción y Cultura Organizacional", styles['APA_H2']))
    story.append(Paragraph(f"<b>Nombre de la Empresa:</b> {empresa.get('nombre', 'N/A')}", styles['APA_Body']))
    story.append(Paragraph(f"<b>Giro del Negocio:</b> {empresa.get('giro', 'N/A')}", styles['APA_Body']))
    story.append(Paragraph(f"<b>Misión:</b> {empresa.get('mision', 'N/A')}", styles['APA_Body']))
    story.append(Paragraph(f"<b>Visión:</b> {empresa.get('vision', 'N/A')}", styles['APA_Body']))
    story.append(Paragraph(f"<b>Valores y Principios:</b> {empresa.get('valores', 'N/A')}", styles['APA_Body']))
    # ... y así con todos los campos de texto ...
    story.append(PageBreak())

    # Anexo B: Diagnóstico Detallado
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
        foda_table_full = Table(foda_data_full)
        foda_table_full.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), '#CCCCCC'), ('GRID', (0,0), (-1,-1), 1, '#000000')]))
        story.append(foda_table_full)
    story.append(PageBreak())

    # Anexo C: Planes Estratégicos y CMI
    story.append(Paragraph("Anexo C: Planes Estratégicos y Cuadro de Mando", styles['APA_H2']))
    story.append(Paragraph("<b>Cuadro de Mando Integral (CMI)</b>", styles['APA_Body']))
    df_cmi = generar_cuadro_de_mando(planes)
    cmi_data = [df_cmi.columns.tolist()] + df_cmi.values.tolist()
    cmi_table = Table(cmi_data, colWidths=[1.5*inch, 2.5*inch, 1*inch, 1*inch, 1.5*inch])
    cmi_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), '#CCCCCC'), ('GRID', (0,0), (-1,-1), 1, '#000000'), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(cmi_table)
    story.append(PageBreak())

    # 6. CONSTRUIR EL PDF
    logo_bytes = BytesIO(empresa['logo']) if empresa['logo'] else None
    doc.build(story, onFirstPage=lambda c, d: encabezado_pie_pagina(c, d, logo_bytes, empresa['nombre'], version, coordinador), 
                     onLaterPages=lambda c, d: encabezado_pie_pagina(c, d, logo_bytes, empresa['nombre'], version, coordinador))
    
    pdf_buffer.seek(0)
    return pdf_buffer

# --- MAIN APP (Sin cambios) ---
init_db()
st.set_page_config(layout="wide")
st.title("Asistente de Plan Estratégico ♟️")

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

tab1, tab2, tab3, tab4, tab5 = st.tabs(["1. Introducción", "2. Diagnóstico Situacional", "3. Planes Estratégicos", "4. Cuadro de Mando Integral", "5. Resumen y Conclusiones"])

with tab1:
    st.header("Introducción y Cultura Organizacional")
    with get_connection() as conn:
        empresa_data = pd.read_sql(f"SELECT * FROM empresas WHERE id={empresa_id}", conn).iloc[0]
    with st.form("form_intro"):
        st.subheader("Datos Generales")
        nombre = st.text_input("Nombre de la Empresa", empresa_data['nombre'])
        giro = st.text_input("Giro del Negocio", empresa_data['giro'])
        logo_file = st.file_uploader("Subir Logo", type=['png', 'jpg', 'jpeg'])
        if empresa_data['logo']: st.image(BytesIO(empresa_data['logo']), width=150)
        st.divider()
        st.subheader("Cultura Organizacional")
        intro = st.text_area("Porqué del Plan Estratégico", empresa_data['introduccion'])
        mision = st.text_area("Misión", empresa_data['mision'])
        vision = st.text_area("Visión", empresa_data['vision'])
        organigrama_file = st.file_uploader("Subir Organigrama", type=['png', 'jpg', 'jpeg'])
        if empresa_data['organigrama']: st.image(BytesIO(empresa_data['organigrama']))
        politicas = st.text_area("Políticas de la Empresa", empresa_data['politicas'])
        valores = st.text_area("Valores y Principios", empresa_data['valores'])
        if st.form_submit_button("Guardar Introducción"):
            logo_bytes = save_image(logo_file) if logo_file else empresa_data['logo']
            org_bytes = save_image(organigrama_file) if organigrama_file else empresa_data['organigrama']
            with get_connection() as conn:
                conn.execute('''UPDATE empresas SET nombre=?, giro=?, logo=?, introduccion=?, mision=?, vision=?, organigrama=?, politicas=?, valores=? WHERE id=?''', 
                             (nombre, giro, logo_bytes, intro, mision, vision, org_bytes, politicas, valores, empresa_id))
            st.success("Datos de introducción guardados."); st.rerun()

with tab2:
    st.header("Diagnóstico Situacional (Análisis de Matrices)")
    diag_tab1, diag_tab2, diag_tab3 = st.tabs(["Matriz PEST", "Matrices EFI y EFE", "Matriz FODA Cruzado"])
    with diag_tab1:
        st.subheader("Análisis PEST")
        with st.expander("📋 Pegar datos desde Excel"):
            st.info("Copia las columnas de tu Excel y pégalas aquí. Columnas: Categoría PEST, Factor, Tipo FODA, Puntaje, Importancia %")
            pest_paste_data = st.text_area("Pega tus datos aquí", height=200, key="pest_paste")
            if st.button("Procesar Datos Pegados de PEST"):
                try:
                    df_pasted = pd.read_csv(StringIO(pest_paste_data), sep='\t', header=None)
                    if "Puntaje" in str(df_pasted.iloc[0].values):
                        st.warning("Se detectó una fila de encabezado y se ha ignorado.")
                        df_pasted = pd.read_csv(StringIO(pest_paste_data), sep='\t', header=0)
                    df_pasted.columns = ['categoria', 'factor', 'tipo_foda', 'puntaje', 'importancia']
                    df_pasted['puntaje'] = pd.to_numeric(df_pasted['puntaje'])
                    df_pasted['importancia'] = pd.to_numeric(df_pasted['importancia'].astype(str).str.replace(',', '.'))
                    df_pasted['valor_ponderado'] = df_pasted['puntaje'] * (df_pasted['importancia'] / 100.0)
                    df_pasted['empresa_id'] = empresa_id
                    df_pasted['tipo_matriz'] = 'PEST'
                    with get_connection() as conn:
                        df_pasted.to_sql('matrices', conn, if_exists='append', index=False)
                    st.success(f"¡{len(df_pasted)} filas importadas a PEST exitosamente!"); st.rerun()
                except Exception as e:
                    st.error(f"Error al procesar los datos: {e}. Revisa que el formato sea correcto y que los números sean válidos.")
        with get_connection() as conn:
            df_pest = pd.read_sql(f"SELECT id, categoria, factor, tipo_foda, puntaje, importancia, valor_ponderado FROM matrices WHERE empresa_id={empresa_id} AND tipo_matriz='PEST'", conn)
        if not df_pest.empty:
            st.subheader("Factores PEST Registrados")
            # --- CORRECCIÓN 2: Advertencia de Streamlit ---
            st.dataframe(df_pest.drop(columns=['id']), use_container_width=True)
            total_importancia = df_pest['importancia'].sum()
            total_ponderado = df_pest['valor_ponderado'].sum()
            st.metric("Suma de Importancia (%)", f"{total_importancia:.2f}", help="La suma de los porcentajes.")
            st.metric("Puntaje Ponderado Total", f"{total_ponderado:.2f}", help="> 2.5 es fuerte, < 2.5 es débil.")
            if total_ponderado > 2.5: st.success("Análisis: La empresa responde efectivamente a factores externos.")
            else: st.warning("Análisis: La empresa es vulnerable a factores externos.")
            if st.button("🗑️ Limpiar Matriz PEST"):
                with get_connection() as conn: conn.execute("DELETE FROM matrices WHERE empresa_id=? AND tipo_matriz='PEST'", (empresa_id,));
                st.rerun()
        else:
            st.info("Aún no hay factores PEST.")
    with diag_tab2:
        st.subheader("Puntajes Totales de Matrices EFI y EFE")
        with get_connection() as conn:
            scores = pd.read_sql("SELECT efi_score, efe_score FROM empresas WHERE id=?", conn, params=(empresa_id,)).iloc[0]
        with st.form("form_scores"):
            efi_score = st.number_input("Puntaje Total Ponderado EFI", min_value=0.0, max_value=4.0, value=float(scores.get('efi_score') or 2.5), step=0.01)
            efe_score = st.number_input("Puntaje Total Ponderado EFE", min_value=0.0, max_value=4.0, value=float(scores.get('efe_score') or 2.5), step=0.01)
            if st.form_submit_button("Guardar Puntajes"):
                with get_connection() as conn:
                    conn.execute("UPDATE empresas SET efi_score=?, efe_score=? WHERE id=?", (efi_score, efe_score, empresa_id))
                st.success("Puntajes EFI y EFE guardados."); st.rerun()
        st.subheader("Análisis de Posición Estratégica")
        col1, col2 = st.columns(2)
        col1.metric("Puntaje EFI (Interno)", f"{efi_score:.2f}")
        if efi_score > 2.5: col1.success("Posición interna Fuerte.")
        else: col1.warning("Posición interna Débil.")
        col2.metric("Puntaje EFE (Externo)", f"{efe_score:.2f}")
        if efe_score > 2.5: col2.success("Respuesta externa Fuerte.")
        else: col2.warning("Respuesta externa Débil.")
    with diag_tab3:
        st.subheader("Análisis FODA Cruzado (Numérico)")
        with st.expander("📋 Pegar datos de FODA Cruzado desde Excel"):
            st.info("Copia las columnas de tu Excel (sin encabezados). Columnas: Cuadrante, Factor Fila, Factor Columna, Impacto")
            foda_paste_data = st.text_area("Pega tus datos de FODA aquí", height=200, key="foda_paste")
            if st.button("Procesar Datos Pegados de FODA"):
                # --- BLOQUE TRY...EXCEPT COMPLETO PARA MANEJAR ERRORES ---
                try:
                    df_foda_pasted = pd.read_csv(StringIO(foda_paste_data), sep='\t', header=None)
                    df_foda_pasted.columns = ['cuadrante', 'factor_fila', 'factor_columna', 'impacto']
                    
                    # --- SOLUCIÓN AL ERROR ArrowTypeError ---
                    # Forzar la columna 'impacto' a ser numérica de forma segura
                    df_foda_pasted['impacto'] = pd.to_numeric(df_foda_pasted['impacto'], errors='coerce').fillna(0).astype(int)
                    
                    df_foda_pasted['empresa_id'] = empresa_id
                    with get_connection() as conn:
                        df_foda_pasted.to_sql('foda_cruzado', conn, if_exists='append', index=False)
                    st.success(f"¡{len(df_foda_pasted)} filas importadas a FODA Cruzado!"); st.rerun()
                except Exception as e:
                    st.error(f"Error al procesar los datos: {e}. Asegúrate de que el formato de pegado sea correcto.")

        with get_connection() as conn:
            df_foda = pd.read_sql(f"SELECT id, cuadrante, factor_fila, factor_columna, impacto FROM foda_cruzado WHERE empresa_id={empresa_id}", conn)
        if not df_foda.empty:
            st.subheader("Datos de FODA Cruzado Registrados")
            # --- CORRECCIÓN 2: Advertencia de Streamlit ---
            st.dataframe(df_foda.drop(columns=['id']), use_container_width=True)
            st.divider()
            st.subheader("Análisis de Estrategia FODA")
            analisis_df, resumen, _, _ = analizar_foda(df_foda)
            if analisis_df is not None:
                st.table(analisis_df)
                st.info(resumen)
            if st.button("🗑️ Limpiar Matriz FODA Cruzado"):
                with get_connection() as conn: conn.execute("DELETE FROM foda_cruzado WHERE empresa_id=?", (empresa_id,));
                st.rerun()
        else:
            st.info("Aún no hay datos para el FODA Cruzado.")

with tab3:
    st.header("Planes Estratégicos")
    st.info("Genera un borrador de planes basado en tu diagnóstico. Luego, completa los campos de 'Matriz' y 'Finalización' para cada uno.")
    if st.button("⚙️ Generar Borrador de Planes"):
        with st.spinner("Analizando diagnóstico y construyendo planes..."):
            with get_connection() as conn:
                empresa_data = pd.read_sql(f"SELECT * FROM empresas WHERE id={empresa_id}", conn).iloc[0]
                df_pest = pd.read_sql(f"SELECT valor_ponderado FROM matrices WHERE empresa_id={empresa_id} AND tipo_matriz='PEST'", conn)
                df_foda = pd.read_sql(f"SELECT cuadrante, impacto FROM foda_cruzado WHERE empresa_id={empresa_id}", conn)
            pest_total = df_pest['valor_ponderado'].sum() if not df_pest.empty else 0
            _, _, estrategia_principal, _ = analizar_foda(df_foda)
            efi_score = empresa_data.get('efi_score') or 0
            efe_score = empresa_data.get('efe_score') or 0
            if not estrategia_principal:
                st.error("No se pueden generar los planes. Faltan los datos del Análisis FODA Cruzado.")
            else:
                st.session_state['generated_plans_dict'] = generar_planes_por_plantilla(estrategia_principal, efi_score, efe_score, pest_total)
    if 'generated_plans_dict' in st.session_state:
        st.subheader("Borrador de Planes Generado")
        for plan_nombre, plan_datos in st.session_state['generated_plans_dict'].items():
            with st.expander(f"**Plan {plan_nombre}**"):
                st.markdown("##### Introducción del Plan")
                st.info(plan_datos['introduccion'])
                st.markdown("##### Objetivo del Plan")
                st.success(plan_datos['objetivo'])
                st.markdown("##### Matriz del Plan")
                st.text_area("Define aquí las acciones, responsables, plazos y recursos.", key=f"matriz_{plan_nombre}", height=150)
                st.markdown("##### Finalización del Plan")
                st.text_area("Describe aquí los entregables, métricas de éxito y criterios de cierre.", key=f"final_{plan_nombre}", height=100)

with tab4:
    st.header("Cuadro de Mando Integral (Balanced Scorecard)")
    st.info("Esta sección genera automáticamente un Cuadro de Mando Integral basado en los objetivos de los planes estratégicos generados en la pestaña anterior.")
    if 'generated_plans_dict' not in st.session_state:
        st.warning("Primero debes generar los planes en la Pestaña 3 para poder construir el Cuadro de Mando Integral.")
    else:
        if st.button("📊 Generar Cuadro de Mando Integral"):
            with st.spinner("Clasificando objetivos y construyendo el CMI..."):
                df_cmi = generar_cuadro_de_mando(st.session_state['generated_plans_dict'])
                st.session_state['df_cmi'] = df_cmi
        if 'df_cmi' in st.session_state:
            st.subheader("Cuadro de Mando Integral Propuesto")
            st.markdown("Este es un punto de partida. Debes refinar los KPIs, Metas e Iniciativas para cada objetivo.")
            df_cmi_display = st.session_state['df_cmi'].style.apply(
                lambda row: ['background-color: #E6F3FF'] * len(row) if row['Perspectiva'] == 'Financiera' else
                            ['background-color: #E6FFF3'] * len(row) if row['Perspectiva'] == 'Clientes' else
                            ['background-color: #FFF3E6'] * len(row) if row['Perspectiva'] == 'Procesos Internos' else
                            ['background-color: #F3E6FF'] * len(row),
                axis=1
            )
            # --- CORRECCIÓN 2: Advertencia de Streamlit ---
            st.dataframe(df_cmi_display, use_container_width=True, height=500)
            
with tab5:
    st.header("Resumen, Conclusiones y Exportación")
    st.subheader("📥 Exportar Plan Estratégico a PDF")
    st.info("Asegúrate de haber completado todas las secciones anteriores para un informe completo. El formato será A4 con estilos APA.")
    with st.form("pdf_form"):
        pdf_version = st.text_input("Versión del Plan Estratégico", "1.0")
        pdf_coordinador = st.text_input("Nombre del Coordinador que revisa", "Jefe de Proyecto")
        submitted = st.form_submit_button("🚀 Generar y Descargar PDF")
        if submitted:
            with st.spinner("Recopilando datos, generando gráficos y construyendo el PDF..."):
                pdf_bytes = generar_pdf_completo(empresa_id, pdf_version, pdf_coordinador)
                st.session_state['pdf_file'] = pdf_bytes
    if 'pdf_file' in st.session_state:
        st.download_button(
            label="✅ Descargar PDF Ahora",
            data=st.session_state['pdf_file'],
            file_name=f"Plan_Estrategico_{empresa_seleccionada.replace(' ', '_')}_V{pdf_version}.pdf",
            mime="application/pdf"
        )