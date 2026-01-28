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
    return True

def generar_analisis_ia(tipo_matriz, datos_contexto):
    if not get_ia_client():
        return "Error: No se encontró la API Key de Gemini en st.secrets."
    prompt = f"Actúa como un consultor senior de estrategia. Analiza la siguiente matriz {tipo_matriz} y proporciona conclusiones estratégicas clave, riesgos y recomendaciones. Datos: {datos_contexto}"
    return generar_analisis(prompt)

def generar_analisis(prompt, client=None):
    errores = []
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

st.set_page_config(page_title="Estratega Pro | Business Intelligence", page_icon="♟️", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
    <style>
    .main { background-color: #f5f5f5; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    h1, h2, h3 { color: #1f77b4; }
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

def get_datos_empresa(empresa_id):
    if supabase and empresa_id:
        try:
            response = supabase.table('empresas').select('*').eq('id', empresa_id).single().execute()
            return response.data
        except Exception as e:
            st.error(f"Error al cargar datos de la empresa: {e}")
    return {}

def get_datos_tabla(tabla, empresa_id, tipo_matriz_filter=None):
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
    if supabase and empresa_id:
        try:
            supabase.table('empresas').update({f'analisis_{tipo_analisis}': contenido}).eq('id', empresa_id).execute()
            st.success(f"✅ Análisis de {tipo_analisis.upper()} guardado en la nube.")
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar análisis: {e}")

def get_empresas():
    if supabase and st.session_state.get("user"):
        try:
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
    resumen = f"La estrategia principal recomendada es **{analisis_df.iloc[0]['Estrategia']}** ({analisis_df.iloc[0]['Puntaje Total']} puntos), seguida por **{analisis_df.iloc[1]['Estrategia']}** ({analisis_df.iloc[1]['Puntaje Total']} puntos)."
    return analisis_df, resumen, estrategia_principal, puntajes_ordenados

def generar_planes_por_plantilla(estrategia_foda, pest_total):
    planes = {}
    planes['Plan Administrativo'] = {
        'introduccion': "El plan administrativo se enfocará en fortalecer la base de la organización y fomentar la innovación continua.",
        'objetivo': "Implementar un programa de formación en liderazgo y gestión de proyectos para los mandos medios en los próximos 6 meses."
    }
    planes['Plan Operativo'] = {
        'introduccion': "El plan operativo se enfocará en optimizar la cadena de valor y escalar las operaciones de manera eficiente para soportar el crecimiento.",
        'objetivo': "Optimizar los procesos críticos de producción/servicio para reducir los tiempos de entrega en un 15% en el próximo año."
    }
    if "Ofensiva" in estrategia_foda or "Adaptativa" in estrategia_foda:
        intro_tec = "La estrategia de crecimiento requiere un apalancamiento tecnológico. Se debe invertir en innovación para ganar ventaja competitiva."
        obj_tec = "Evaluar e implementar una nueva herramienta de CRM o ERP en los próximos 9 meses para mejorar la relación con clientes y la eficiencia operativa."
    else:
        intro_tec = "La tecnología debe usarse para robustecer la operación y defender la posición actual. La prioridad es la seguridad y la estabilidad."
        obj_tec = "Realizar una auditoría de ciberseguridad completa en el próximo trimestre y actualizar los sistemas críticos para mitigar vulnerabilidades."
    planes['Plan Tecnológico'] = {'introduccion': intro_tec, 'objetivo': obj_tec}
    
    if "Ofensiva" in estrategia_foda or "Adaptativa" in estrategia_foda:
        intro_fin = "El entorno es favorable y la estrategia es de crecimiento. El plan financiero debe enfocarse en asegurar los fondos para la expansión."
        obj_fin = "Preparar un caso de negocio y una ronda de financiación (o asegurar una línea de crédito) en los próximos 6 meses para financiar las nuevas iniciativas estratégicas."
    else:
        intro_fin = "La situación financiera debe ser gestionada con prudencia. La prioridad es la optimización de costos, la gestión de la liquidez y la maximización de la rentabilidad actual."
        obj_fin = "Implementar un plan de reducción de costos no esenciales para mejorar el margen de beneficio neto en un 2% en los próximos 6 meses, sin afectar la operación crítica."
    planes['Plan Financiero'] = {'introduccion': intro_fin, 'objetivo': obj_fin}
    
    planes['Plan de Monitoreo y control'] = {
        'introduccion': "Dado que la estrategia implica nuevas iniciativas y crecimiento, se requiere un sistema de monitoreo ágil y riguroso para asegurar que los objetivos se cumplan.",
        'objetivo': "Implementar un dashboard de KPIs (Indicadores Clave) en tiempo real para los nuevos proyectos y establecer un ciclo de revisión estratégica mensual."
    }
    
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
    
    if pest_total < 2.5:
        intro_con = f"El análisis del entorno (PEST: {pest_total:.2f}) revela vulnerabilidad a factores externos. Es crucial desarrollar planes para mitigar riesgos."
        obj_con = "Formar un comité de gestión de riesgos que, en 2 meses, identifique los 3 principales riesgos externos y desarrolle un plan de respuesta específico."
    else:
        intro_con = f"La empresa muestra buena respuesta al entorno (PEST: {pest_total:.2f}). El plan se enfocará en la monitorización proactiva de eventos inesperados."
        obj_con = "Establecer un sistema de vigilancia del entorno trimestral y realizar un simulacro de crisis anual."
    planes['Plan de Contingencia'] = {'introduccion': intro_con, 'objetivo': obj_con}
    return planes

def generar_cuadro_de_mando_ia(estrategias_df):
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

def generar_grafico_pest_bar(df_pest):
    if df_pest.empty: 
        return None
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

    # --- PESTAÑA 8: RESUMEN Y CONCLUSIONES (MODIFICADA) ---
    with tab6:
        st.header("Resumen, Conclusiones y Exportación")
        
        st.subheader("📄 Generar Documento Final (Formato APA)")
        
        with st.form("pdf_form"):
            col1, col2 = st.columns(2)
            with col1:
                pdf_version = st.text_input("Versión del Plan", value="1.0")
                pdf_elaborado = st.text_input("Elaborado por", value="Consultor Estratégico")
            with col2:
                pdf_revisado = st.text_input("Revisado por", value="Director de Planeación")
                pdf_aprobado = st.text_input("Aprobado por", value="Director General")
            
            st.info("""
            **Estructura del documento generado:**
            - **Resumen Ejecutivo** (máx. 5 hojas): Diagnóstico clave, estrategias prioritarias y recomendación
            - **Plan Estratégico** (máx. 30 hojas): Introducción, estrategias, planes, CMI, operativización
            - **Anexos** (ilimitado): Análisis detallados, matrices, dashboards y proyecciones
            
            **Formato:** Tamaño carta (A4), Times New Roman 12pt, interlineado doble, márgenes de 1 pulgada
            """)
            
            if st.form_submit_button("🚀 Generar PDF Profesional"):
                with st.spinner("Generando documento con formato APA. Esto puede tomar un momento..."):
                    pdf_bytes = generar_pdf_completo_mejorado(
                        empresa_id, 
                        pdf_version, 
                        pdf_elaborado, 
                        pdf_revisado, 
                        pdf_aprobado
                    )
                    if pdf_bytes:
                        st.session_state['pdf_file'] = pdf_bytes
                        st.session_state['pdf_nombre'] = f"Plan_Estrategico_{empresa.get('nombre', 'Empresa')}_V{pdf_version}.pdf"
                        st.success("✅ PDF generado correctamente con formato APA.")
        
        if 'pdf_file' in st.session_state:
            col1, col2 = st.columns([1, 3])
            with col1:
                st.download_button(
                    label="⬇️ Descargar PDF", 
                    data=st.session_state['pdf_file'], 
                    file_name=st.session_state.get('pdf_nombre', 'plan_estrategico.pdf'), 
                    mime="application/pdf",
                    type="primary"
                )
            with col2:
                st.success(f"Documento listo: {st.session_state.get('pdf_nombre', 'plan_estrategico.pdf')}")
                st.caption("El documento incluye encabezado con logo, pie de página con firmas, y todas las secciones requeridas.")
def mostrar_ultimo_analisis_guardado(empresa_data, tipo_analisis):
    """
    Muestra el último análisis guardado desde el diccionario de datos de la empresa.
    """
    contenido = empresa_data.get(f'analisis_{tipo_analisis}')
    if contenido and str(contenido).strip():
        st.markdown("---")
        st.markdown(f"**📄 Último análisis de {tipo_analisis.upper()} guardado:**")
        if tipo_analisis == 'cmi' and '|' in str(contenido):
            try:
                df_view = pd.read_csv(io.StringIO(contenido), sep="|")
                st.table(df_view)
            except Exception as e:
                st.text_area(f"contenido_guardado_{tipo_analisis}", value=contenido, height=200, disabled=True, label_visibility="collapsed")
        else:
            st.text_area(f"contenido_guardado_{tipo_analisis}", value=contenido, height=200, disabled=True, label_visibility="collapsed")

def aplicacion_principal():
    with st.sidebar:
        st.header("Gestión de Empresas")
        empresas_df = get_empresas()
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
            if st.button("❌ Eliminar Empresa Seleccionada", type="primary"):
                if supabase:
                    try:
                        supabase.table('empresas').delete().eq('id', empresa_id).execute()
                        st.success(f"Empresa '{empresa_seleccionada}' eliminada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar la empresa: {e}")
                
    if not empresa_id:
        st.info("👈 Por favor, selecciona o crea una empresa en el menú lateral para comenzar.")
        st.stop()

    empresa_data = get_datos_empresa(empresa_id)
    if not empresa_data:
        st.error("No se pudieron cargar los datos de la empresa. Verifica tus permisos.")
        st.stop()

    es_propietario = empresa_data.get('propietario_id') == st.session_state.user.id
    es_editor = False
    if not es_propietario:
        try:
            res = supabase.table('empresas_compartidas').select('permiso').eq('empresa_id', empresa_id).eq('usuario_compartido_id', st.session_state.user.id).single().execute()
            if res.data and res.data['permiso'] == 'editor':
                es_editor = True
        except:
            es_editor = False
    puede_editar = es_propietario or es_editor

    tab1, tab2, tab_est, tab3, tab4, tab5, tab_dash, tab6 = st.tabs([
        "1. Introducción", "2. Diagnóstico Situacional", "3. Estrategia", 
        "4. Planes Estratégicos", "5. CMI/Indicadores", "6. Operativización/Presupuesto", 
        "7. Dashboard de Análisis", "8. Resumen y Conclusiones"
    ])

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
                except: 
                    pass
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
                except: 
                    pass
            if st.form_submit_button("Guardar Introducción", disabled=not puede_editar):
                update_data = {
                    "nombre": nombre, "giro": giro, "objetivo_plan": objetivo_plan, "mision": mision, 
                    "vision": vision, "obj_general": obj_gen, "obj_especificos": obj_esp, 
                    "politicas": politicas, "valores": valores
                }
                if logo_file:
                    logo_bytes = save_image(logo_file)
                    update_data['logo'] = logo_bytes.hex()
                if organigrama_file:
                    org_bytes = save_image(organigrama_file)
                    update_data['organigrama'] = org_bytes.hex()
                try:
                    supabase.table('empresas').update(update_data).eq('id', empresa_id).execute()
                    st.success("Datos de introducción guardados en la nube."); 
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    # --- PESTAÑA 2: DIAGNÓSTICO SITUACIONAL ---
    with tab2:
        st.header("Diagnóstico Situacional (Análisis de Matrices)")

        def procesar_made_madi(data_str, tipo):
            if isinstance(data_str, pd.DataFrame):
                df = data_str.copy()
            else:
                try:
                    df = pd.read_csv(StringIO(data_str), sep='\t', header=0)
                except Exception as e:
                    st.error(f"Error al leer los datos pegados. Error: {e}")
                    return pd.DataFrame()
            def normalizar_nombre(nombre):
                nombre_sin_tildes = unicodedata.normalize('NFKD', str(nombre)).encode('ascii', 'ignore').decode('utf-8')
                return nombre_sin_tildes.lower().replace(' ', '_').replace('%', '_percent').replace('°', '')
            df.columns = [normalizar_nombre(c) for c in df.columns]
            mapeo_columnas = {
                'n': 'n_temp', 'variable': 'variable', 'factor': 'factor', 'producto': 'producto',
                'precio': 'precio', 'plaza': 'plaza', 'promocion': 'promocion', 'rating': 'rating',
                'weight__percent': 'weight_percent', 'weight_percent': 'weight_percent', 
                'valor': 'valor', 'total': 'total'
            }
            df.rename(columns=mapeo_columnas, inplace=True)
            numeric_cols = ['rating', 'weight_percent', 'valor', 'total']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            df.replace({np.nan: None}, inplace=True)
            columnas_finales_bd = ['variable', 'factor', 'producto', 'precio', 'plaza', 'promocion', 'rating', 'weight_percent', 'valor', 'total']
            for col in columnas_finales_bd:
                if col not in df.columns:
                    df[col] = None
            return df[columnas_finales_bd]

        def display_and_edit_matrix(tipo_matriz, analisis_propio_data):
            df_db = get_datos_tabla('matriz_marketing', empresa_id, tipo_matriz_filter=tipo_matriz)
            if not df_db.empty:
                st.info("Puedes editar los datos directamente en la tabla.")
                df_display = df_db.rename(columns={
                    'variable': 'Variable', 'factor': 'Factor', 'producto': 'Producto', 'precio': 'Precio',
                    'plaza': 'Plaza', 'promocion': 'Promoción', 'rating': 'Rating', 'weight_percent': 'Weight %',
                    'valor': 'Valor', 'total': 'Total'
                })
                columnas_a_mostrar = [c for c in df_display.columns if c not in ['id', 'empresa_id', 'tipo_matriz']]
                edited_df_display = st.data_editor(df_display[columnas_a_mostrar], key=f"editor_{tipo_matriz}", num_rows="dynamic", use_container_width=True, disabled=not puede_editar)
                if st.button(f"💾 Guardar Cambios en {tipo_matriz}", disabled=not puede_editar, key=f"save_{tipo_matriz}"):
                    try:
                        df_to_save = edited_df_display.rename(columns={
                            'Variable': 'variable', 'Factor': 'factor', 'Producto': 'producto', 'Precio': 'precio',
                            'Plaza': 'plaza', 'Promoción': 'promocion', 'Rating': 'rating', 'Weight %': 'weight_percent',
                            'Valor': 'valor', 'Total': 'total'
                        })
                        df_to_save = procesar_made_madi(df_to_save.to_csv(sep='\t', index=False), tipo_matriz)
                        supabase.table('matriz_marketing').delete().eq('empresa_id', empresa_id).eq('tipo_matriz', tipo_matriz).execute()
                        df_to_save['empresa_id'] = empresa_id
                        df_to_save['tipo_matriz'] = tipo_matriz
                        supabase.table('matriz_marketing').insert(df_to_save.to_dict(orient='records')).execute()
                        st.success(f"Cambios en {tipo_matriz} guardados."); 
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar {tipo_matriz}: {e}")
                total_score = pd.to_numeric(df_db['total'], errors='coerce').sum()
                st.metric(f"Puntaje Total {tipo_matriz}", f"{total_score}")
            else:
                st.info(f"Aún no hay datos para la Matriz {tipo_matriz}. Pega los datos desde Excel para comenzar.")
        
        diag_tab1, diag_tab2, diag_tab3, diag_tab4, diag_tab5 = st.tabs([
            "Matriz MADE", "Matriz MADI", "Matriz de Posicionamiento", "Matriz PEST", "Matriz FODA Numérico"
        ])

        # --- MADE ---
        with diag_tab1:
            st.subheader("Análisis de Marketing Interno (MADE)")
            # 1. Entrada de datos
            with st.expander("📋 Pegar datos de MADE desde Excel"):
                made_paste_data = st.text_area("Pega tus datos de MADE aquí", height=200, key="paste_MADE")
                if st.button("Procesar y Guardar Datos de MADE", key="process_made", disabled=not puede_editar):
                    if made_paste_data:
                        try:
                            df_made = procesar_made_madi(made_paste_data, 'MADE')
                            supabase.table('matriz_marketing').delete().eq('empresa_id', empresa_id).eq('tipo_matriz', 'MADE').execute()
                            df_made['empresa_id'] = empresa_id
                            df_made['tipo_matriz'] = 'MADE'
                            supabase.table('matriz_marketing').insert(df_made.to_dict(orient='records')).execute()
                            st.success(f"¡{len(df_made)} filas importadas a MADE exitosamente!"); 
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al procesar datos de MADE: {e}")
            # 2. Mostrar datos existentes
            df_made_actual = get_datos_tabla('matriz_marketing', empresa_id, tipo_matriz_filter='MADE')
            if not df_made_actual.empty:
                st.write("**Datos Actuales:**")
                st.dataframe(df_made_actual.drop(columns=['id', 'empresa_id', 'tipo_matriz'], errors='ignore'), use_container_width=True)
            
            st.divider()
            # 3. Análisis con IA
            st.subheader("📊 Análisis de MADE")
            if st.button("🤖 Generar Análisis MADE con IA", key="gen_made_ia", disabled=not puede_editar):
                with st.spinner("Analizando Marketing Interno..."):
                    contexto = df_made_actual.to_string() if not df_made_actual.empty else "Sin datos numéricos"
                    analisis_generado = generar_analisis_ia("MADE (Marketing Interno)", contexto)
                    st.session_state['made_analisis_temp'] = analisis_generado
                    st.rerun()
            
            # 4. Formulario para guardar análisis
            with st.form("form_analisis_made"):
                analisis_made_val = st.session_state.get('made_analisis_temp', empresa_data.get('analisis_made', ''))
                analisis_made_text = st.text_area("Análisis de Marketing Interno (MADE)", value=analisis_made_val, height=200, disabled=not puede_editar)
                if st.form_submit_button("💾 Guardar Análisis MADE", disabled=not puede_editar):
                    guardar_analisis_db(empresa_id, 'made', analisis_made_text)
            
            # 5. Mostrar último análisis
            mostrar_ultimo_analisis_guardado(empresa_data, 'made')

            # --- MADI ---
        with diag_tab2:
            st.subheader("Análisis de Marketing Externo (MADI)")
            with st.expander("📋 Pegar datos de MADI desde Excel"):
                madi_paste_data = st.text_area("Pega tus datos de MADI aquí", height=200, key="paste_MADI")
                if st.button("Procesar y Guardar Datos de MADI", key="process_madi", disabled=not puede_editar):
                    if madi_paste_data:
                        try:
                            df_madi = procesar_made_madi(madi_paste_data, 'MADI')
                            supabase.table('matriz_marketing').delete().eq('empresa_id', empresa_id).eq('tipo_matriz', 'MADI').execute()
                            df_madi['empresa_id'] = empresa_id
                            df_madi['tipo_matriz'] = 'MADI'
                            supabase.table('matriz_marketing').insert(df_madi.to_dict(orient='records')).execute()
                            st.success(f"¡{len(df_madi)} filas importadas a MADI exitosamente!"); 
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al procesar datos de MADI: {e}")
                    else:
                        st.warning("El área de texto está vacía. Pega tus datos para procesar.")
            
            # Mostrar datos existentes (fuera del expander)
            df_madi_actual = get_datos_tabla('matriz_marketing', empresa_id, tipo_matriz_filter='MADI')
            if not df_madi_actual.empty:
                st.write("**Datos Actuales:**")
                st.dataframe(df_madi_actual.drop(columns=['id', 'empresa_id', 'tipo_matriz'], errors='ignore'), use_container_width=True)
            
            st.divider()
            # Análisis con IA
            st.subheader("📊 Análisis de MADI")
            if st.button("🤖 Generar Análisis MADI con IA", key="gen_madi_ia", disabled=not puede_editar):
                with st.spinner("Analizando Marketing Externo..."):
                    contexto = df_madi_actual.to_string() if not df_madi_actual.empty else "Sin datos numéricos"
                    analisis_generado = generar_analisis_ia("MADI (Marketing Externo)", contexto)
                    st.session_state['madi_analisis_temp'] = analisis_generado
                    st.rerun()
            
            with st.form("form_analisis_madi"):
                analisis_madi_val = st.session_state.get('madi_analisis_temp', empresa_data.get('analisis_madi', ''))
                analisis_madi_text = st.text_area("Análisis de Marketing Externo (MADI)", value=analisis_madi_val, height=200, disabled=not puede_editar)
                if st.form_submit_button("💾 Guardar Análisis MADI", disabled=not puede_editar):
                    guardar_analisis_db(empresa_id, 'madi', analisis_madi_text)
            
            mostrar_ultimo_analisis_guardado(empresa_data, 'madi')

        # --- POSICIONAMIENTO ---
        with diag_tab3:
            st.subheader("Matriz de Posicionamiento")
            coord_x_val = float(empresa_data.get('posicionamiento_x') or 0)
            coord_y_val = float(empresa_data.get('posicionamiento_y') or 0)
            
            # 1. Entrada de datos
            with st.form("form_posicionamiento"):
                coord_x = st.number_input("Coordenada X", value=coord_x_val, disabled=not puede_editar)
                coord_y = st.number_input("Coordenada Y", value=coord_y_val, disabled=not puede_editar)
                if st.form_submit_button("Guardar Coordenadas", disabled=not puede_editar):
                    try:
                        supabase.table('empresas').update({
                            "posicionamiento_x": coord_x, 
                            "posicionamiento_y": coord_y
                        }).eq('id', empresa_id).execute()
                        st.success("Coordenadas guardadas."); 
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar coordenadas: {e}")
            
            # 2. Visualización
            fig, ax = plt.subplots()
            ax.axhline(0, color='gray', lw=1); ax.axvline(0, color='gray', lw=1)
            ax.plot(coord_x_val, coord_y_val, 'ro', markersize=10)
            ax.set_title("Matriz de Posicionamiento"); ax.set_xlabel("Eje X"); ax.set_ylabel("Eje Y")
            ax.grid(True, which='both', linestyle='--', linewidth=0.5)
            st.pyplot(fig)
            
            st.divider()
            # 3. Análisis IA
            st.subheader("📊 Análisis de Posicionamiento")
            if st.button("🤖 Generar Análisis de Posicionamiento con IA", key="gen_pos_ia", disabled=not puede_editar):
                with st.spinner("Analizando posición competitiva..."):
                    contexto = f"Coordenadas X: {coord_x_val}, Y: {coord_y_val}"
                    analisis_generado = generar_analisis_ia("Posicionamiento Competitivo", contexto)
                    st.session_state['posicionamiento_analisis_temp'] = analisis_generado
                    st.rerun()
            
            with st.form("form_analisis_pos"):
                analisis_pos_val = st.session_state.get('posicionamiento_analisis_temp', empresa_data.get('analisis_posicionamiento', ''))
                analisis_pos_text = st.text_area("Análisis de Posicionamiento Competitivo", value=analisis_pos_val, height=200, disabled=not puede_editar)
                if st.form_submit_button("💾 Guardar Análisis", disabled=not puede_editar):
                    guardar_analisis_db(empresa_id, 'posicionamiento', analisis_pos_text)
            
            mostrar_ultimo_analisis_guardado(empresa_data, 'posicionamiento')

        # --- PEST ---
        with diag_tab4:
            st.subheader("Análisis PEST")
            with st.expander("📋 Pegar datos desde Excel"):
                pest_paste_data = st.text_area("Pega tus datos PEST aquí (columnas: categoria, factor, tipo_foda, puntaje, importancia)", height=200, key="pest_input")
                if st.button("Procesar y Guardar Datos PEST", key="process_pest", disabled=not puede_editar):
                    if pest_paste_data:
                        try:
                            df_pasted = pd.read_csv(StringIO(pest_paste_data), sep='\t', header=0)
                            df_pasted.columns = ['categoria', 'factor', 'tipo_foda', 'puntaje', 'importancia']
                            df_pasted['valor_ponderado'] = pd.to_numeric(df_pasted['puntaje'], errors='coerce') * (pd.to_numeric(df_pasted['importancia'], errors='coerce') / 100.0)
                            df_pasted['empresa_id'] = empresa_id
                            df_pasted['tipo_matriz'] = 'PEST'
                            supabase.table('matrices').delete().eq('empresa_id', empresa_id).eq('tipo_matriz', 'PEST').execute()
                            supabase.table('matrices').insert(df_pasted.to_dict(orient='records')).execute()
                            st.success(f"¡{len(df_pasted)} filas importadas a PEST exitosamente!"); 
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al procesar los datos: {e}.")
            
            df_pest = get_datos_tabla('matrices', empresa_id, tipo_matriz_filter='PEST')
            if not df_pest.empty:
                st.write("**Datos PEST Actuales:**")
                edited_pest = st.data_editor(df_pest.drop(columns=['id', 'empresa_id', 'tipo_matriz'], errors='ignore'), num_rows="dynamic", key="editor_pest", use_container_width=True, disabled=not puede_editar)
                if st.button("💾 Guardar Cambios en PEST", key="save_pest_changes", disabled=not puede_editar):
                    try:
                        supabase.table('matrices').delete().eq('empresa_id', empresa_id).eq('tipo_matriz', 'PEST').execute()
                        if not edited_pest.empty:
                            edited_pest['empresa_id'] = empresa_id
                            edited_pest['tipo_matriz'] = 'PEST'
                            supabase.table('matrices').insert(edited_pest.to_dict(orient='records')).execute()
                        st.success("Cambios en PEST guardados."); 
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar PEST: {e}")
                total_ponderado = pd.to_numeric(df_pest['valor_ponderado'], errors='coerce').sum()
                st.metric("Puntaje Ponderado Total PEST", f"{total_ponderado:.2f}")
            
            st.divider()
            st.subheader("📊 Análisis PEST")
            if st.button("🤖 Generar Análisis PEST con IA", key="gen_pest_ia", disabled=not puede_editar):
                with st.spinner("Analizando entorno PEST..."):
                    contexto = df_pest.to_string() if not df_pest.empty else "Sin datos numéricos"
                    analisis_generado = generar_analisis_ia("PEST (Político, Económico, Social, Tecnológico)", contexto)
                    st.session_state['pest_analisis_temp'] = analisis_generado
                    st.rerun()
            
            with st.form("form_analisis_pest"):
                analisis_pest_val = st.session_state.get('pest_analisis_temp', empresa_data.get('analisis_pest', ''))
                analisis_pest_text = st.text_area("Análisis del Entorno PEST", value=analisis_pest_val, height=200, disabled=not puede_editar)
                if st.form_submit_button("💾 Guardar Análisis PEST", disabled=not puede_editar):
                    guardar_analisis_db(empresa_id, 'pest', analisis_pest_text)
            
            mostrar_ultimo_analisis_guardado(empresa_data, 'pest')

        # --- FODA ---
        with diag_tab5:
            st.subheader("Análisis FODA Cruzado (Numérico)")
            with st.expander("📋 Pegar datos de FODA Cruzado desde Excel"):
                foda_paste_data = st.text_area("Pega tus datos de FODA aquí (columnas: cuadrante, factor_fila, factor_columna, impacto)", height=200, key="foda_paste")
                if st.button("Procesar y Guardar Datos FODA", key="process_foda", disabled=not puede_editar):
                    if foda_paste_data:
                        try:
                            df_foda_pasted = pd.read_csv(StringIO(foda_paste_data), sep='\t', header=0)
                            df_foda_pasted.columns = ['cuadrante', 'factor_fila', 'factor_columna', 'impacto']
                            df_foda_pasted['impacto'] = pd.to_numeric(df_foda_pasted['impacto'], errors='coerce').fillna(0).astype(int)
                            df_foda_pasted['empresa_id'] = empresa_id
                            supabase.table('foda_cruzado').delete().eq('empresa_id', empresa_id).execute()
                            supabase.table('foda_cruzado').insert(df_foda_pasted.to_dict(orient='records')).execute()
                            st.success(f"¡{len(df_foda_pasted)} filas importadas a FODA Cruzado!"); 
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al procesar los datos: {e}.")
            
            df_foda = get_datos_tabla('foda_cruzado', empresa_id)
            if not df_foda.empty:
                st.write("**Datos FODA Actuales:**")
                edited_foda = st.data_editor(df_foda.drop(columns=['id', 'empresa_id'], errors='ignore'), num_rows="dynamic", key="editor_foda", use_container_width=True, disabled=not puede_editar)
                if st.button("💾 Guardar Cambios en FODA", key="save_foda_changes", disabled=not puede_editar):
                    try:
                        supabase.table('foda_cruzado').delete().eq('empresa_id', empresa_id).execute()
                        if not edited_foda.empty:
                            edited_foda['empresa_id'] = empresa_id
                            supabase.table('foda_cruzado').insert(edited_foda.to_dict(orient='records')).execute()
                        st.success("Cambios en FODA guardados."); 
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar FODA: {e}")
                
                analisis_df, _, estrategia_principal, puntajes_foda = analizar_foda(df_foda)
                if analisis_df is not None:
                    st.subheader("🎯 Postura Competitiva Sugerida")
                    st.info(f"Estrategia Principal: {estrategia_principal}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.dataframe(analisis_df, use_container_width=True)
                    with col2:
                        grafico_foda = generar_grafico_foda_radar(puntajes_foda)
                        if grafico_foda: 
                            st.image(grafico_foda)
            
            st.divider()
            st.subheader("📊 Análisis FODA")
            if st.button("🤖 Generar Análisis FODA con IA", key="gen_foda_ia", disabled=not puede_editar):
                with st.spinner("Analizando matrices FODA..."):
                    contexto = df_foda.to_string() if not df_foda.empty else "Sin datos numéricos"
                    analisis_generado = generar_analisis_ia("FODA Cruzado", contexto)
                    st.session_state['foda_analisis_temp'] = analisis_generado
                    st.rerun()
            
            with st.form("form_analisis_foda"):
                analisis_foda_val = st.session_state.get('foda_analisis_temp', empresa_data.get('analisis_foda', ''))
                analisis_foda_text = st.text_area("Análisis FODA Cruzado", value=analisis_foda_val, height=200, disabled=not puede_editar)
                if st.form_submit_button("💾 Guardar Análisis FODA", disabled=not puede_editar):
                    guardar_analisis_db(empresa_id, 'foda', analisis_foda_text)
            
            mostrar_ultimo_analisis_guardado(empresa_data, 'foda')

    # --- PESTAÑA 3: ESTRATEGIA (CORREGIDA CON GENERACIÓN IA) ---
    with tab_est:
        st.header("🎯 Formulación de Estrategias")
        
        df_estrategias = get_datos_tabla('estrategias_generadas', empresa_id)
        df_foda_estrategia = get_datos_tabla('foda_cruzado', empresa_id)
        
        if df_estrategias.empty:
            st.info("No hay estrategias generadas. Utiliza el botón de abajo para generarlas automáticamente con IA basándose en el análisis FODA.")
            
            if st.button("🤖 Generar Estrategias con IA (3 por cuadrante)", disabled=not puede_editar, type="primary"):
                if df_foda_estrategia.empty:
                    st.error("Primero debes cargar los datos del FODA Cruzado en la pestaña anterior.")
                else:
                    with st.spinner("Generando 12 estrategias estratégicas (3 por cuadrante)..."):
                        # Obtener factores por cuadrante para contexto
                        contexto_foda = df_foda_estrategia.to_string()
                        
                        prompt_estrategias = f"""Basado en el siguiente análisis FODA Cruzado:
{contexto_foda}

Genera exactamente 3 estrategias para cada uno de los 4 cuadrantes (FO, FA, DO, DA), total 12 estrategias.
Para cada estrategia proporciona:
1. Cuadrante (FO, FA, DO, o DA)
2. Estrategia: Descripción clara y específica de la estrategia
3. Importancia: Selecciona una de (Alta, Media Alta, Media Baja, Baja)
4. Actividades: Lista de actividades clave para implementarla (máximo 3 líneas)
5. Plan Asignado: Selecciona uno de (Plan Administrativo, Plan Operativo, Plan Tecnológico, Plan Financiero, Plan de Monitoreo y control, Plan de Mejora, Plan de Contingencia)

Formato de salida EXACTO (una estrategia por línea):
CUADRANTE|ESTRATEGIA|IMPORTANCIA|ACTIVIDADES|PLAN_ASIGNADO

Ejemplo:
FO|Expandir mercado en nuevas regiones utilizando fortalezas tecnológicas|Alta|Investigar mercados potenciales, Adaptar producto, Lanzar campaña marketing|Plan Operativo
FO|Alianza estratégica con proveedores clave|Media Alta|Identificar proveedores, Negociar contratos, Implementar integración|Plan Administrativo
FA|Programa de retención de clientes ante nueva competencia|Alta|Analizar churn, Crear programa fidelización, Capacitar equipo ventas|Plan de Mejora

Genera exactamente 12 líneas (3 por cada cuadrante FO, FA, DO, DA). No uses encabezados."""
                        
                        resultado = generar_analisis(prompt_estrategias)
                        
                        # Parsear resultado
                        estrategias_list = []
                        lineas = [l.strip() for l in resultado.split('\n') if l.strip() and '|' in l]
                        
                        for linea in lineas[:12]:  # Máximo 12 estrategias
                            partes = linea.split('|')
                            if len(partes) >= 5:
                                estrategias_list.append({
                                    'empresa_id': empresa_id,
                                    'cuadrante': partes[0].strip().upper(),
                                    'estrategia': partes[1].strip(),
                                    'importancia': partes[2].strip(),
                                    'actividades': partes[3].strip(),
                                    'plan_asignado': partes[4].strip()
                                })
                        
                        if estrategias_list:
                            try:
                                # Guardar en Supabase
                                supabase.table('estrategias_generadas').delete().eq('empresa_id', empresa_id).execute()
                                supabase.table('estrategias_generadas').insert(estrategias_list).execute()
                                st.success(f"✅ {len(estrategias_list)} estrategias generadas y guardadas exitosamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al guardar estrategias: {e}")
                        else:
                            st.error("No se pudieron parsear las estrategias generadas. Intenta nuevamente.")
        else:
            # Mostrar estrategias existentes en editor
            st.success(f"Se encontraron {len(df_estrategias)} estrategias generadas.")
            st.write("**Editar Estrategias:**")
            
            edited_df = st.data_editor(
                df_estrategias.drop(columns=['id', 'empresa_id'], errors='ignore'), 
                num_rows="dynamic", 
                key="editor_estrategias", 
                use_container_width=True,
                disabled=not puede_editar,
                column_config={
                    "cuadrante": st.column_config.SelectboxColumn("Cuadrante", options=["FO", "FA", "DO", "DA"]),
                    "importancia": st.column_config.SelectboxColumn("Importancia", options=["Alta", "Media Alta", "Media Baja", "Baja"]),
                    "plan_asignado": st.column_config.SelectboxColumn("Plan Asignado", 
                        options=["Plan Administrativo", "Plan Operativo", "Plan Tecnológico", "Plan Financiero", 
                                "Plan de Monitoreo y control", "Plan de Mejora", "Plan de Contingencia"]),
                    "estrategia": st.column_config.TextColumn("Estrategia", width="large"),
                    "actividades": st.column_config.TextColumn("Actividades", width="large")
                }
            )
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💾 Guardar Cambios", disabled=not puede_editar):
                    try:
                        supabase.table('estrategias_generadas').delete().eq('empresa_id', empresa_id).execute()
                        if not edited_df.empty:
                            df_to_save = edited_df.copy()
                            df_to_save['empresa_id'] = empresa_id
                            supabase.table('estrategias_generadas').insert(df_to_save.to_dict(orient='records')).execute()
                        st.success("Estrategias actualizadas."); 
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar estrategias: {e}")
            with col2:
                if st.button("🗑️ Eliminar Todas", type="secondary", disabled=not puede_editar):
                    try:
                        supabase.table('estrategias_generadas').delete().eq('empresa_id', empresa_id).execute()
                        st.success("Estrategias eliminadas."); 
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
            with col3:
                if st.button("🔄 Regenerar con IA", disabled=not puede_editar):
                    # Eliminar actuales y regenerar
                    try:
                        supabase.table('estrategias_generadas').delete().eq('empresa_id', empresa_id).execute()
                        st.rerun()
                    except:
                        pass

    # --- PESTAÑA 4: PLANES ESTRATÉGICOS ---
    with tab3:
        st.header("Planes Estratégicos")
        
        # Obtener estrategia principal del FODA para generar planes contextuales
        df_foda_temp = get_datos_tabla('foda_cruzado', empresa_id)
        analisis_df_temp, _, estrategia_principal, _ = analizar_foda(df_foda_temp)
        
        if st.button("🤖 Generar Planes Estratégicos con IA", disabled=not puede_editar):
            with st.spinner("Generando planes estratégicos personalizados..."):
                prompt_planes = f"Genera planes estratégicos detallados basados en la estrategia: {estrategia_principal}. Incluye objetivos específicos para cada área."
                planes_generados = generar_analisis(prompt_planes)
                st.session_state['operativo_analisis_temp'] = planes_generados
                st.rerun()
        
        with st.form("form_planes"):
            current_analisis_operativo = st.session_state.get("operativo_analisis_temp", empresa_data.get('analisis_operativo', ''))
            analisis_propio_operativo = st.text_area("Plan Estratégico Maestro", value=current_analisis_operativo, height=400, disabled=not puede_editar)
            if st.form_submit_button("💾 Guardar Plan Maestro", disabled=not puede_editar):
                guardar_analisis_db(empresa_id, 'operativo', analisis_propio_operativo)
        
        mostrar_ultimo_analisis_guardado(empresa_data, 'operativo')
    
    # --- PESTAÑA 5: CMI/INDICADORES ---
    with tab4:
        st.header("CMI / Indicadores")
        df_estrategias_cmi = get_datos_tabla('estrategias_generadas', empresa_id)
        
        if not df_estrategias_cmi.empty:
            if st.button("🤖 Generar CMI con IA", disabled=not puede_editar):
                with st.spinner("Generando Cuadro de Mando Integral..."):
                    df_cmi_generado = generar_cuadro_de_mando_ia(df_estrategias_cmi)
                    if not df_cmi_generado.empty:
                        # Convertir a formato pipe-separated para guardar
                        cmi_texto = df_cmi_generado.to_csv(sep="|", index=False)
                        st.session_state['cmi_analisis_temp'] = cmi_texto
                        st.success("CMI generado. Guarda el análisis para confirmar.")
                        st.rerun()
            
            with st.form("form_cmi"):
                current_analisis_cmi = st.session_state.get("cmi_analisis_temp", empresa_data.get('analisis_cmi', ''))
                analisis_propio_cmi = st.text_area("Cuadro de Mando Integral (formato texto o pipe-separated)", value=current_analisis_cmi, height=400, disabled=not puede_editar)
                if st.form_submit_button("💾 Guardar CMI", disabled=not puede_editar):
                    guardar_analisis_db(empresa_id, 'cmi', analisis_propio_cmi)
            
            mostrar_ultimo_analisis_guardado(empresa_data, 'cmi')
        else:
            st.warning("No hay estrategias disponibles para generar el CMI. Genera estrategias primero en la pestaña anterior.")
    
    # --- PESTAÑA 6: OPERATIVIZACIÓN/PRESUPUESTO ---
    with tab5:
        st.header("Operativización / Presupuesto")
        
        # Obtener estrategias generadas
        df_estrategias_oper = get_datos_tabla('estrategias_generadas', empresa_id)
        
        if df_estrategias_oper.empty:
            st.warning("No hay estrategias disponibles. Genera estrategias primero en la pestaña 'Estrategia'.")
            st.stop()
        
        st.info(f"📋 Se encontraron {len(df_estrategias_oper)} estrategias para operativizar.")
        
        # Botón para generar/poblar el cuadro de operativización automáticamente
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("🔄 Generar/Actualizar Cuadro de Operativización", type="primary", disabled=not puede_editar):
                with st.spinner("Desglosando estrategias en actividades..."):
                    try:
                        # Obtener operativización existente para preservar datos ya ingresados
                        df_oper_existente = get_datos_tabla('operativizacion', empresa_id)
                        datos_existentes = {}
                        if not df_oper_existente.empty:
                            for _, row in df_oper_existente.iterrows():
                                key = f"{row.get('estrategia_id', '')}_{row.get('numero_actividad', '')}"
                                datos_existentes[key] = {
                                    'plazo': row.get('plazo', ''),
                                    'responsable': row.get('responsable', ''),
                                    'costo': row.get('costo', 0)
                                }
                        
                        # Eliminar operativización anterior
                        supabase.table('operativizacion').delete().eq('empresa_id', empresa_id).execute()
                        
                        nuevas_actividades = []
                        
                        for _, estrategia in df_estrategias_oper.iterrows():
                            # Dividir las actividades de la estrategia
                            actividades_texto = estrategia.get('actividades', '')
                            import re
                            lista_actividades = re.split(r'[,;\n]+', actividades_texto)
                            lista_actividades = [act.strip() for act in lista_actividades if act.strip()]
                            
                            if not lista_actividades:
                                lista_actividades = ["Implementación general de la estrategia"]
                            
                            for num_act, actividad in enumerate(lista_actividades, 1):
                                key = f"{estrategia['id']}_{num_act}"
                                datos_previos = datos_existentes.get(key, {})
                                
                                nueva_act = {
                                    'empresa_id': empresa_id,
                                    'estrategia_id': estrategia['id'],
                                    'cuadrante': estrategia['cuadrante'],
                                    'estrategia_nombre': estrategia['estrategia'],
                                    'plan_asignado': estrategia['plan_asignado'],
                                    'numero_actividad': num_act,
                                    'descripcion_actividad': actividad,
                                    'plazo': datos_previos.get('plazo', ''),
                                    'responsable': datos_previos.get('responsable', ''),
                                    'costo': datos_previos.get('costo', 0),
                                    'importancia': estrategia.get('importancia', 'Media')
                                }
                                nuevas_actividades.append(nueva_act)
                        
                        if nuevas_actividades:
                            supabase.table('operativizacion').insert(nuevas_actividades).execute()
                            st.success(f"✅ {len(nuevas_actividades)} actividades generadas de {len(df_estrategias_oper)} estrategias.")
                            st.rerun()
                    
                    except Exception as e:
                        st.error(f"Error al generar operativización: {e}")
        
        with col2:
            st.caption("Este botón desglosa cada estrategia en sus actividades específicas para que solo edites plazo, responsable y costo.")
        
        st.divider()
        
        # Mostrar y editar el cuadro de operativización
        st.subheader("📋 Cuadro de Operativización por Actividades")
        
        df_oper = get_datos_tabla('operativizacion', empresa_id)
        
        if not df_oper.empty:
            # Calcular totales
            total_costo = pd.to_numeric(df_oper['costo'], errors='coerce').fillna(0).sum()
            total_actividades = len(df_oper)
            
            # Métricas resumen
            col_met1, col_met2, col_met3, col_met4 = st.columns(4)
            with col_met1:
                st.metric("💰 Costo Total", f"${total_costo:,.2f}")
            with col_met2:
                st.metric("📊 Total Actividades", total_actividades)
            with col_met3:
                st.metric("🎯 Estrategias", df_oper['estrategia_id'].nunique())
            with col_met4:
                promedio_costo = total_costo / total_actividades if total_actividades > 0 else 0
                st.metric("💵 Promedio por Actividad", f"${promedio_costo:,.2f}")
            
            st.divider()
            
            # Preparar datos para el editor
            df_oper['ref_estrategia'] = df_oper['cuadrante'] + " - " + df_oper['estrategia_nombre'].str[:50] + "..."
            
            # Ordenar por cuadrante y número de actividad
            orden_cuadrantes = {'FO': 1, 'FA': 2, 'DO': 3, 'DA': 4}
            df_oper['orden_cuadrante'] = df_oper['cuadrante'].map(orden_cuadrantes)
            df_oper = df_oper.sort_values(['orden_cuadrante', 'estrategia_id', 'numero_actividad'])
            
            # Seleccionar y renombrar columnas para mostrar
            columnas_mostrar = [
                'ref_estrategia', 'numero_actividad', 'descripcion_actividad', 
                'plazo', 'responsable', 'costo', 'plan_asignado', 'importancia'
            ]
            
            df_display = df_oper[columnas_mostrar].copy()
            df_display.columns = [
                'Estrategia (Referencia)', 'N°', 'Actividad', 
                'Plazo', 'Responsable', 'Costo ($)', 'Plan Asignado', 'Importancia'
            ]
            
            # Editor de datos
            st.write("**Edita directamente el Plazo, Responsable y Costo de cada actividad:**")
            
            edited_df = st.data_editor(
                df_display,
                num_rows="fixed",
                key="editor_oper_actividades",
                use_container_width=True,
                disabled=not puede_editar,
                column_config={
                    'Estrategia (Referencia)': st.column_config.TextColumn("Estrategia", disabled=True, width="medium"),
                    'N°': st.column_config.NumberColumn("N°", disabled=True, width="small"),
                    'Actividad': st.column_config.TextColumn("Descripción de la Actividad", disabled=True, width="large"),
                    'Plazo': st.column_config.TextColumn("⏱️ Plazo", width="medium"),
                    'Responsable': st.column_config.TextColumn("👤 Responsable", width="medium"),
                    'Costo ($)': st.column_config.NumberColumn("💰 Costo ($)", min_value=0, step=100, format="$%.2f", width="medium"),
                    'Plan Asignado': st.column_config.TextColumn("Plan", disabled=True, width="small"),
                    'Importancia': st.column_config.TextColumn("Importancia", disabled=True, width="small")
                },
                hide_index=True
            )
            
            # Botón para guardar cambios
            if st.button("💾 Guardar Cambios del Cuadro de Operativización", type="primary", disabled=not puede_editar):
                try:
                    # Reconstruir el dataframe completo con IDs
                    df_completo = df_oper.copy()
                    
                    # Actualizar solo las columnas editables
                    df_completo['plazo'] = edited_df['Plazo'].values
                    df_completo['responsable'] = edited_df['Responsable'].values
                    df_completo['costo'] = edited_df['Costo ($)'].values
                    
                    # Eliminar datos anteriores
                    supabase.table('operativizacion').delete().eq('empresa_id', empresa_id).execute()
                    
                    # Insertar datos actualizados
                    columnas_guardar = [
                        'empresa_id', 'estrategia_id', 'cuadrante', 'estrategia_nombre',
                        'plan_asignado', 'numero_actividad', 'descripcion_actividad',
                        'plazo', 'responsable', 'costo', 'importancia'
                    ]
                    
                    datos_guardar = df_completo[columnas_guardar].to_dict(orient='records')
                    supabase.table('operativizacion').insert(datos_guardar).execute()
                    
                    st.success("✅ Cuadro de operativización guardado correctamente.")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
            
            st.divider()
            
            # Vista resumen por estrategia
            with st.expander("📊 Ver Resumen por Estrategia"):
                resumen = df_oper.groupby(['cuadrante', 'estrategia_nombre']).agg({
                    'costo': 'sum',
                    'descripcion_actividad': 'count',
                    'plazo': lambda x: list(x.unique()),
                    'responsable': lambda x: list(x.dropna().unique())
                }).reset_index()
                
                resumen.columns = ['Cuadrante', 'Estrategia', 'Costo Total', 'N° Actividades', 'Plazos', 'Responsables']
                
                for _, row in resumen.iterrows():
                    with st.container():
                        col_r1, col_r2, col_r3 = st.columns([3, 1, 1])
                        with col_r1:
                            st.write(f"**{row['Cuadrante']}**: {row['Estrategia'][:60]}...")
                        with col_r2:
                            st.write(f"💰 ${row['Costo Total']:,.2f}")
                        with col_r3:
                            st.write(f"📋 {int(row['N° Actividades'])} act.")
                    st.divider()
            
            # Vista resumen por plan asignado
            with st.expander("📈 Ver Distribución por Plan"):
                fig = px.pie(
                    df_oper, 
                    names='plan_asignado', 
                    values='costo',
                    title='Distribución de Costos por Plan Estratégico',
                    hole=0.4
                )
                st.plotly_chart(fig, use_container_width=True)
                
                tabla_planes = df_oper.groupby('plan_asignado').agg({
                    'costo': 'sum',
                    'descripcion_actividad': 'count'
                }).reset_index()
                tabla_planes.columns = ['Plan', 'Costo Total', 'N° Actividades']
                st.dataframe(tabla_planes, use_container_width=True, hide_index=True)
        
        else:
            st.info("👆 Haz clic en 'Generar/Actualizar Cuadro de Operativización' para crear el cuadro con todas las estrategias y sus actividades.")
        
        st.divider()
        
        # Estado de Pérdidas y Ganancias del ÚLTIMO AÑO
        st.subheader("💰 Estado de Pérdidas y Ganancias (Último Año Real)")
        
        with st.expander("📊 Ingresar Datos del Último Año"):
            with st.form("form_pygn"):
                st.write("**Ingresa los datos reales del último año fiscal:**")
                
                col1, col2 = st.columns(2)
                with col1:
                    ingresos_ventas = st.number_input("Ingresos por Ventas", min_value=0.0, step=1000.0, key="pg_ingresos")
                    costos_ventas = st.number_input("Costos de Ventas (COGS)", min_value=0.0, step=1000.0, key="pg_costos")
                    gastos_operativos = st.number_input("Gastos Operativos", min_value=0.0, step=1000.0, key="pg_gop")
                with col2:
                    gastos_admin = st.number_input("Gastos Administrativos", min_value=0.0, step=1000.0, key="pg_gadm")
                    gastos_ventas_marketing = st.number_input("Gastos de Ventas y Marketing", min_value=0.0, step=1000.0, key="pg_gvta")
                    otros_ingresos = st.number_input("Otros Ingresos", min_value=0.0, step=1000.0, key="pg_oting")
                
                impuestos = st.number_input("Impuestos sobre la Renta", min_value=0.0, step=1000.0, key="pg_imp")
                utilidad_retenida = st.number_input("Utilidad Retenida del Año Anterior", min_value=0.0, step=1000.0, key="pg_uti_ret")
                
                submitted_pg = st.form_submit_button("💾 Guardar Estado P&G", disabled=not puede_editar)
            
            if submitted_pg:
                try:
                    utilidad_bruta = ingresos_ventas - costos_ventas
                    utilidad_operativa = utilidad_bruta - gastos_operativos - gastos_admin - gastos_ventas_marketing
                    utilidad_antes_impuestos = utilidad_operativa + otros_ingresos
                    utilidad_neta = utilidad_antes_impuestos - impuestos
                    
                    datos_pg = {
                        'empresa_id': empresa_id,
                        'ingresos_ventas': ingresos_ventas,
                        'costos_ventas': costos_ventas,
                        'gastos_operativos': gastos_operativos,
                        'gastos_administrativos': gastos_admin,
                        'gastos_ventas': gastos_ventas_marketing,
                        'otros_ingresos': otros_ingresos,
                        'impuestos': impuestos,
                        'utilidad_retenida_anterior': utilidad_retenida,
                        'utilidad_bruta': utilidad_bruta,
                        'utilidad_operativa': utilidad_operativa,
                        'utilidad_antes_impuestos': utilidad_antes_impuestos,
                        'utilidad_neta': utilidad_neta
                    }
                    
                    supabase.table('perdida_ganancia').delete().eq('empresa_id', empresa_id).execute()
                    supabase.table('perdida_ganancia').insert(datos_pg).execute()
                    st.success("✅ Estado de Pérdidas y Ganancias guardado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar P&G: {e}")
        
        df_pg = get_datos_tabla('perdida_ganancia', empresa_id)
        if not df_pg.empty:
            st.write("**Resumen del Último Año:**")
            datos_pg = df_pg.iloc[0]
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Ingresos", f"${datos_pg['ingresos_ventas']:,.2f}")
            with col2:
                st.metric("Utilidad Bruta", f"${datos_pg['utilidad_bruta']:,.2f}")
            with col3:
                st.metric("Utilidad Operativa", f"${datos_pg['utilidad_operativa']:,.2f}")
            with col4:
                st.metric("Utilidad Neta", f"${datos_pg['utilidad_neta']:,.2f}")
        
        st.divider()
        
        # PROYECCIÓN con Análisis Costo-Beneficio
        st.subheader("📈 Proyección y Análisis Costo-Beneficio")
        
        if not df_pg.empty and not df_oper.empty:
            datos_base = df_pg.iloc[0]
            
            with st.form("form_proyeccion"):
                st.write("**Parámetros de Proyección:**")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    crecimiento_ventas = st.slider("Crecimiento en Ventas (%)", -50, 100, 10, key="proj_crec") / 100
                    reduccion_costos = st.slider("Reducción de Costos (%)", 0, 50, 5, key="proj_red") / 100
                with col2:
                    periodos_proyeccion = st.selectbox("Período de Proyección", ["1 año", "2 años", "3 años", "5 años"], key="proj_per")
                    unidades_proyectadas = st.number_input("Unidades Totales Proyectadas", min_value=1, value=1000, key="proj_unid")
                with col3:
                    inversion_total = st.number_input("Inversión Total Requerida ($)", min_value=0.0, value=float(total_costo), key="proj_inv")
                    tasa_descuento = st.slider("Tasa de Descuento Anual (%)", 0, 30, 10, key="proj_tasa") / 100
                
                submitted_proj = st.form_submit_button("🚀 Calcular Proyección y Costo-Beneficio", disabled=not puede_editar)
            
            # El procesamiento va FUERA del with st.form()
            if submitted_proj:
                try:
                    anios = int(periodos_proyeccion.split()[0])
                    
                    proyecciones = []
                    ingreso_actual = datos_base['ingresos_ventas']
                    costo_actual = datos_base['costos_ventas']
                    
                    flujos_futuros = []
                    
                    for anio_num in range(1, anios + 1):
                        ingreso_proy = ingreso_actual * ((1 + crecimiento_ventas) ** anio_num)
                        costo_proy = costo_actual * ((1 - reduccion_costos) ** anio_num) * ((1 + crecimiento_ventas) ** anio_num)
                        utilidad_bruta_proy = ingreso_proy - costo_proy
                        gastos_proy = (datos_base['gastos_operativos'] + datos_base['gastos_administrativos'] + datos_base['gastos_ventas']) * ((1 + crecimiento_ventas * 0.5) ** anio_num)
                        utilidad_neta_proy = utilidad_bruta_proy - gastos_proy - (utilidad_bruta_proy * 0.25)
                        
                        flujos_futuros.append(utilidad_neta_proy)
                        
                        proyecciones.append({
                            'anio': anio_num,
                            'ingresos_proyectados': ingreso_proy,
                            'costos_proyectados': costo_proy,
                            'utilidad_neta_proyectada': utilidad_neta_proy
                        })
                    
                    df_proyeccion = pd.DataFrame(proyecciones)
                    
                    # Guardar proyección
                    supabase.table('proyeccion_financiera').delete().eq('empresa_id', empresa_id).execute()
                    for _, row in df_proyeccion.iterrows():
                        row_dict = {
                            'empresa_id': empresa_id,
                            'anio': int(row['anio']),
                            'ingresos_proyectados': float(row['ingresos_proyectados']),
                            'costos_proyectados': float(row['costos_proyectados']),
                            'utilidad_neta_proyectada': float(row['utilidad_neta_proyectada'])
                        }
                        supabase.table('proyeccion_financiera').insert(row_dict).execute()
                    
                    # Calcular Costo-Beneficio
                    vpn = sum([f / ((1 + tasa_descuento) ** (i+1)) for i, f in enumerate(flujos_futuros)])
                    
                    if inversion_total > 0:
                        relacion_cb_dolares = vpn / inversion_total
                    else:
                        relacion_cb_dolares = float('inf') if vpn > 0 else 0
                    
                    flujo_acumulado = 0
                    payback_anios = None
                    for i, flujo in enumerate(flujos_futuros):
                        flujo_acumulado += flujo
                        if flujo_acumulado >= inversion_total:
                            exceso = flujo_acumulado - inversion_total
                            fraccion_anio = 1 - (exceso / flujo) if flujo > 0 else 0
                            payback_anios = i + fraccion_anio
                            break
                    
                    if unidades_proyectadas > 0 and inversion_total > 0:
                        beneficio_por_unidad = vpn / unidades_proyectadas
                        costo_por_unidad = inversion_total / unidades_proyectadas
                        relacion_cb_unidades = beneficio_por_unidad / costo_por_unidad if costo_por_unidad > 0 else 0
                    else:
                        beneficio_por_unidad = 0
                        costo_por_unidad = 0
                        relacion_cb_unidades = 0
                    
                    # Guardar análisis CB
                    analisis_cb = {
                        'empresa_id': empresa_id,
                        'inversion_total': float(inversion_total),
                        'vpn_total': float(vpn),
                        'relacion_costo_beneficio_dolares': float(relacion_cb_dolares),
                        'payback_periodo_anios': float(payback_anios) if payback_anios else None,
                        'unidades_proyectadas': int(unidades_proyectadas),
                        'beneficio_por_unidad': float(beneficio_por_unidad),
                        'costo_por_unidad': float(costo_por_unidad),
                        'relacion_cb_unidades': float(relacion_cb_unidades),
                        'tasa_descuento': float(tasa_descuento)
                    }
                    
                    supabase.table('analisis_costo_beneficio').delete().eq('empresa_id', empresa_id).execute()
                    supabase.table('analisis_costo_beneficio').insert(analisis_cb).execute()
                    
                    st.success("✅ Proyección y análisis Costo-Beneficio calculados y guardados.")
                    st.session_state['mostrar_resultados_cb'] = True
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error en el cálculo: {e}")
            
            # Mostrar resultados si existen
            if st.session_state.get('mostrar_resultados_cb', False):
                df_cb = get_datos_tabla('analisis_costo_beneficio', empresa_id)
                df_proy = get_datos_tabla('proyeccion_financiera', empresa_id)
                
                if not df_cb.empty and not df_proy.empty:
                    datos_cb = df_cb.iloc[0]
                    
                    st.divider()
                    st.subheader("📊 Resultados del Análisis Costo-Beneficio")
                    
                    # Renombrar columnas para mostrar
                    df_proy_display = df_proy.rename(columns={
                        'anio': 'Año',
                        'ingresos_proyectados': 'Ingresos Proyectados',
                        'costos_proyectados': 'Costos Proyectados',
                        'utilidad_neta_proyectada': 'Utilidad Neta Proyectada'
                    })
                    
                    st.write("**Proyección Financiera:**")
                    st.dataframe(df_proy_display, use_container_width=True, hide_index=True)
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df_proy['anio'], y=df_proy['ingresos_proyectados'], 
                                           mode='lines+markers', name='Ingresos', line=dict(color='green')))
                    fig.add_trace(go.Scatter(x=df_proy['anio'], y=df_proy['costos_proyectados'], 
                                           mode='lines+markers', name='Costos', line=dict(color='red')))
                    fig.add_trace(go.Scatter(x=df_proy['anio'], y=df_proy['utilidad_neta_proyectada'], 
                                           mode='lines+markers', name='Utilidad Neta', line=dict(color='blue')))
                    fig.update_layout(title="Proyección Financiera", xaxis_title="Año", yaxis_title="Monto ($)")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.write("**Indicadores Costo-Beneficio:**")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("### 💵 En DÓLARES")
                        st.metric("Relación C-B", f"{float(datos_cb['relacion_costo_beneficio_dolares']):.2f}")
                        st.write(f"**Inversión:** ${float(datos_cb['inversion_total']):,.2f}")
                        st.write(f"**VPN Total:** ${float(datos_cb['vpn_total']):,.2f}")
                        if datos_cb['relacion_costo_beneficio_dolares'] >= 1:
                            st.success(f"✅ Por cada $1 invertido, se recuperan ${float(datos_cb['relacion_costo_beneficio_dolares']):.2f}")
                        else:
                            st.error(f"❌ Por cada $1 invertido, solo se recuperan ${float(datos_cb['relacion_costo_beneficio_dolares']):.2f}")
                    
                    with col2:
                        st.markdown("### ⏱️ En TIEMPO")
                        if datos_cb['payback_periodo_anios']:
                            st.metric("Periodo de Recuperación", f"{float(datos_cb['payback_periodo_anios']):.1f} años")
                            if datos_cb['payback_periodo_anios'] <= 2:
                                st.success("✅ Recuperación rápida")
                            elif datos_cb['payback_periodo_anios'] <= 5:
                                st.info("ℹ️ Recuperación moderada")
                            else:
                                st.warning("⚠️ Recuperación lenta")
                        else:
                            st.metric("Periodo de Recuperación", "No recuperable")
                            st.error("❌ Inversión no recuperable")
                    
                    with col3:
                        st.markdown("### 📦 En UNIDADES")
                        st.metric("Beneficio/Unidad", f"${float(datos_cb['beneficio_por_unidad']):,.2f}")
                        st.metric("Costo/Unidad", f"${float(datos_cb['costo_por_unidad']):,.2f}")
                        st.metric("Relación C-B", f"{float(datos_cb['relacion_cb_unidades']):.2f}")
                        if datos_cb['relacion_cb_unidades'] >= 1:
                            st.success("✅ Rentable por unidad")
                        else:
                            st.error("❌ No rentable por unidad")
                    
                    st.divider()
                    st.subheader("📝 Interpretación Ejecutiva")
                    
                    interpretaciones = []
                    if datos_cb['relacion_costo_beneficio_dolares'] >= 1.5:
                        interpretaciones.append("**Rentabilidad Excelente:** Retorno significativo de la inversión.")
                    elif datos_cb['relacion_costo_beneficio_dolares'] >= 1:
                        interpretaciones.append("**Rentabilidad Aceptable:** El proyecto es viable.")
                    else:
                        interpretaciones.append("**Alerta:** El proyecto no es viable financieramente.")
                    
                    if datos_cb['payback_periodo_anios'] and datos_cb['payback_periodo_anios'] <= 3:
                        interpretaciones.append("**Liquidez:** Recuperación rápida del capital.")
                    
                    for interp in interpretaciones:
                        st.write(f"• {interp}")
                    
                    puntos_positivos = sum([
                        datos_cb['relacion_costo_beneficio_dolares'] >= 1,
                        datos_cb['payback_periodo_anios'] is not None and datos_cb['payback_periodo_anios'] <= 5,
                        datos_cb['relacion_cb_unidades'] >= 1
                    ])
                    
                    if puntos_positivos >= 2:
                        st.success("### ✅ RECOMENDACIÓN: APROBAR PROYECTO")
                    elif puntos_positivos == 1:
                        st.warning("### ⚠️ RECOMENDACIÓN: EVALUAR CON PRECAUCIÓN")
                    else:
                        st.error("### ❌ RECOMENDACIÓN: RECHAZAR PROYECTO")
        
        else:
            st.warning("Completa el Estado de Pérdidas y Ganancias y genera el Cuadro de Operativización para realizar la proyección.")

    
    # --- PESTAÑA 7: DASHBOARD ---
    with tab_dash:
        st.header("📊 Dashboard de Análisis Estratégico")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Estrategias", len(get_datos_tabla('estrategias_generadas', empresa_id)))
        with col2:
            st.metric("Factores PEST", len(get_datos_tabla('matrices', empresa_id, tipo_matriz_filter='PEST')))
        with col3:
            st.metric("Factores FODA", len(get_datos_tabla('foda_cruzado', empresa_id)))
        
        st.divider()
        df_foda_dash = get_datos_tabla('foda_cruzado', empresa_id)
        if not df_foda_dash.empty:
            st.subheader("Distribución de Estrategias FODA")
            fig = px.bar(df_foda_dash, x='cuadrante', y='impacto', color='cuadrante', title="Impacto por Cuadrante FODA")
            st.plotly_chart(fig, use_container_width=True)
        
    # --- PESTAÑA 8: RESUMEN Y CONCLUSIONES ---
    with tab6:
        st.header("Resumen, Conclusiones y Exportación")
        
        st.subheader("📄 Generar Documento Final")
        with st.form("pdf_form"):
            pdf_version = st.text_input("Versión del Plan", value="1.0")
            pdf_coordinador = st.text_input("Coordinador del Plan", value="Consultor Estratégico")
            if st.form_submit_button("🚀 Generar PDF Completo"):
                with st.spinner("Generando documento PDF..."):
                    pdf_bytes = generar_pdf_completo_mejorado(empresa_id, pdf_version, pdf_elaborado, pdf_revisado, pdf_aprobado)
                    if pdf_bytes:
                        st.session_state['pdf_file'] = pdf_bytes
                        st.success("PDF generado correctamente.")
        
        if 'pdf_file' in st.session_state:
            col1, col2 = st.columns([1,3])
            with col1:
                st.download_button(
                    label="⬇️ Descargar PDF", 
                    data=st.session_state['pdf_file'], 
                    file_name=f"Plan_Estrategico_{empresa_data.get('nombre', 'Empresa')}_V{pdf_version}.pdf", 
                    mime="application/pdf"
                )
            with col2:
                st.success("Documento listo para descargar.")

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
        st.image("https://i.imgur.com/gYv2k3C.png", width=200)

def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if not st.session_state.get("logged_in"):
        pantalla_acceso()
    else:
        aplicacion_principal()

if __name__ == "__main__":
    supabase = init_supabase()
    if supabase:
        main()
    else:
        st.error("La aplicación no puede iniciarse. Revisa la conexión con la base de datos (Supabase).")








