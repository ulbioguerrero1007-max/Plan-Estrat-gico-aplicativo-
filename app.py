import streamlit as st
import re
import google.generativeai as genai
import pandas as pd
import sqlite3
import io
from io import StringIO, BytesIO  # <-- Asegúrate de tener esta línea
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import navy, grey, red, green, black
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    """
    Obtiene las empresas del usuario actual:
    - Empresas creadas por el usuario
    - Empresas compartidas con el usuario (como lector o editor)
    """
    if supabase and st.session_state.get("user"):
        try:
            user_id = st.session_state.user.id

            # 1. Obtener empresas creadas por el usuario
            response_propias = supabase.table('empresas').select('id, nombre, propietario_id').eq('propietario_id', user_id).execute()
            empresas_propias = response_propias.data if response_propias.data else []

            # 2. Obtener empresas compartidas con el usuario
            response_compartidas = supabase.table('empresas_compartidas').select('empresa_id, permiso').eq('usuario_compartido_id', user_id).execute()
            compartidas = response_compartidas.data if response_compartidas.data else []

            # 3. Obtener detalles de las empresas compartidas
            empresas_compartidas_list = []
            for comp in compartidas:
                try:
                    resp_emp = supabase.table('empresas').select('id, nombre, propietario_id').eq('id', comp['empresa_id']).single().execute()
                    if resp_emp.data:
                        emp_data = resp_emp.data
                        emp_data['permiso_compartido'] = comp['permiso']  # 'lector' o 'editor'
                        empresas_compartidas_list.append(emp_data)
                except:
                    continue

            # 4. Combinar y marcar propiedad
            todas_empresas = []

            # Agregar propias
            for emp in empresas_propias:
                emp['es_propietario'] = True
                emp['permiso'] = 'propietario'
                todas_empresas.append(emp)

            # Agregar compartidas (evitar duplicados si es propietario y compartida)
            ids_existentes = {e['id'] for e in todas_empresas}
            for emp in empresas_compartidas_list:
                if emp['id'] not in ids_existentes:
                    emp['es_propietario'] = False
                    emp['permiso'] = emp.get('permiso_compartido', 'lector')
                    todas_empresas.append(emp)

            return pd.DataFrame(todas_empresas) if todas_empresas else pd.DataFrame(columns=['id', 'nombre', 'es_propietario', 'permiso'])

        except Exception as e:
            st.error(f"Error al cargar empresas: {e}")
    return pd.DataFrame(columns=['id', 'nombre', 'es_propietario', 'permiso'])

def compartir_empresa(empresa_id, email_usuario, permiso='lector'):
    """
    Comparte una empresa con otro usuario.
    """
    if supabase and empresa_id and email_usuario:
        try:
            # Buscar el usuario por email
            resp_usuario = supabase.rpc('get_user_id_by_email', {'email_input': email_usuario}).execute()
            
            if not resp_usuario.data:
                return False, "Usuario no encontrado. Asegúrate de que el email esté registrado."
            
            usuario_compartir_id = resp_usuario.data
            
            # Verificar que no sea el propietario
            resp_empresa = supabase.table('empresas').select('propietario_id').eq('id', empresa_id).single().execute()
            if resp_empresa.data and resp_empresa.data['propietario_id'] == usuario_compartir_id:
                return False, "No puedes compartir con el propietario"

            # Verificar si ya está compartida
            resp_existente = supabase.table('empresas_compartidas').select('*').eq('empresa_id', empresa_id).eq('usuario_compartido_id', usuario_compartir_id).execute()
            if resp_existente.data:
                # Actualizar permiso y guardar email
                supabase.table('empresas_compartidas').update({
                    'permiso': permiso,
                    'email_compartido': email_usuario  # <-- Guardar email
                }).eq('empresa_id', empresa_id).eq('usuario_compartido_id', usuario_compartir_id).execute()
                return True, "Permiso actualizado"

            # Crear nuevo registro con email
            supabase.table('empresas_compartidas').insert({
                'empresa_id': empresa_id,
                'usuario_compartido_id': usuario_compartir_id,
                'email_compartido': email_usuario,  # <-- Guardar email aquí
                'permiso': permiso
            }).execute()

            return True, f"Empresa compartida con {email_usuario} como {permiso}"

        except Exception as e:
            return False, f"Error al compartir: {e}"
    return False, "Datos incompletos"


def eliminar_compartir(empresa_id, usuario_compartido_id):
    """Elimina el acceso compartido a un usuario."""
    if supabase and empresa_id and usuario_compartido_id:
        try:
            supabase.table('empresas_compartidas').delete().eq('empresa_id', empresa_id).eq('usuario_compartido_id', usuario_compartido_id).execute()
            return True, "Acceso eliminado"
        except Exception as e:
            return False, f"Error: {e}"
    return False, "Datos incompletos"


def get_usuarios_compartidos(empresa_id):
    """Obtiene la lista de usuarios con quienes se compartió la empresa."""
    if supabase and empresa_id:
        try:
            resp = supabase.table('empresas_compartidas').select('*').eq('empresa_id', empresa_id).execute()
            
            if resp.data:
                usuarios = []
                for comp in resp.data:
                    try:
                        usuario_id = comp.get('usuario_compartido_id', 'unknown')
                        permiso = comp.get('permiso', 'lector')
                        
                        # PRIORIDAD 1: Usar email_compartido si existe
                        # PRIORIDAD 2: Usar email si existe  
                        # PRIORIDAD 3: Mostrar ID truncado como fallback
                        email = comp.get('email_compartido') or comp.get('email') or f"ID: {str(usuario_id)[:8]}..."
                        
                        usuarios.append({
                            'usuario_id': usuario_id,
                            'email': email,
                            'permiso': permiso
                        })
                    except Exception as e:
                        print(f"Error procesando registro: {e}")
                        continue
                return usuarios
        except Exception as e:
            st.error(f"Error al cargar usuarios compartidos: {e}")
    return []
    
def save_image(uploaded_file):
    """
    Guarda una imagen subida y retorna los bytes listos para guardar en BD.
    """
    if uploaded_file is not None:
        try:
            # Leer los bytes directamente
            bytes_data = uploaded_file.getvalue()
            return bytes_data  # Retornar bytes directamente
        except Exception as e:
            st.error(f"Error al procesar imagen: {e}")
            return None
    return None

def mostrar_imagen_bd(imagen_data, caption="Imagen", width=None):
    """Muestra imagen guardada en base64"""
    if not imagen_data:
        return False
    try:
        import base64
        if isinstance(imagen_data, str):
            img_bytes = base64.b64decode(imagen_data)
            st.image(img_bytes, caption=caption, width=width)
            return True
    except Exception as e:
        pass
    return False
    
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

def get_apa_styles():
    """
    Estilos según normas APA 7ma edición:
    - Times New Roman 12pt
    - Interlineado doble (leading=24)
    - Márgenes de 1 pulgada (2.54 cm)
    """
    styles = getSampleStyleSheet()
    
    # Estilo base para todo el documento
    styles.add(ParagraphStyle(
        name='APA_Base',
        fontName='Times-Roman',
        fontSize=12,
        leading=24,  # Interlineado doble
        alignment=TA_JUSTIFY,
        spaceAfter=12,
        firstLineIndent=0,  # Sin sangría en base
    ))
    
    # Título principal (Portada)
    styles.add(ParagraphStyle(
        name='APA_Title',
        parent=styles['APA_Base'],
        fontName='Times-Bold',
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=24,
        leading=24,
        firstLineIndent=0,
    ))
    
    # Encabezados nivel 1 (Centrados, negrita)
    styles.add(ParagraphStyle(
        name='APA_H1',
        parent=styles['APA_Base'],
        fontName='Times-Bold',
        fontSize=13,
        alignment=TA_CENTER,
        spaceBefore=72,
        spaceAfter=24,
        leading=24,
        firstLineIndent=0,
    ))
    
    # Encabezados nivel 2 (Izquierda, negrita)
    styles.add(ParagraphStyle(
        name='APA_H2',
        parent=styles['APA_Base'],
        fontName='Times-Bold',
        fontSize=12,
        alignment=TA_LEFT,
        spaceBefore=36,
        spaceAfter=18,
        leading=24,
        firstLineIndent=0,
    ))
    
    # Encabezados nivel 3 (Indentado, negrita)
    styles.add(ParagraphStyle(
        name='APA_H3',
        parent=styles['APA_Base'],
        fontName='Times-Bold',
        alignment=TA_LEFT,
        spaceBefore=24,
        spaceAfter=12,
        leading=24,
        firstLineIndent=0.5*inch,
    ))
    
    # Texto normal (cuerpo)
    styles.add(ParagraphStyle(
        name='APA_Body',
        parent=styles['APA_Base'],
        fontName='Times-Roman',
        alignment=TA_JUSTIFY,
        spaceAfter=0,
        leading=24,
    ))
    
    # Texto sin sangría
    styles.add(ParagraphStyle(
        name='APA_Body_No_Indent',
        parent=styles['APA_Body'],
        firstLineIndent=0,
    ))
    
    # Lista con viñetas
    styles.add(ParagraphStyle(
        name='APA_List',
        parent=styles['APA_Body'],
        leftIndent=0.5*inch,
        firstLineIndent=-0.25*inch,
        spaceAfter=6,
    ))
    
    # Pie de página
    styles.add(ParagraphStyle(
        name='APA_Footer',
        fontName='Times-Roman',
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
    ))
    
    # Encabezado
    styles.add(ParagraphStyle(
        name='APA_Header',
        fontName='Times-Roman',
        fontSize=10,
        leading=12,
        alignment=TA_RIGHT,
    ))
    
    return styles

def encabezado_pie_pagina(canvas, doc, logo_bytes, nombre_empresa, version, elaborado, revisado, aprobado, fecha):
    """
    Dibuja encabezado y pie de página en cada página según formato formal.
    """
    canvas.saveState()
    
    # ENCABEZADO
    # Línea superior
    canvas.line(doc.leftMargin, letter[1] - 0.6*inch, 
                doc.width + doc.leftMargin, letter[1] - 0.6*inch)
    
    # Logo (izquierda)
    if logo_bytes:
        try:
            logo = Image(logo_bytes, width=0.6*inch, height=0.6*inch)
            logo.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - 0.2*inch)
        except:
            pass
    
    # Nombre de empresa (centro)
    canvas.setFont('Times-Bold', 11)
    canvas.drawCentredString(doc.width/2 + doc.leftMargin, 
                            letter[1] - 0.6*inch, 
                            nombre_empresa[:50])
    
    # Versión y fecha (derecha)
    canvas.setFont('Times-Roman', 9)
    canvas.drawRightString(doc.width + doc.leftMargin, 
                          letter[1] - 0.6*inch, 
                          f"Versión: {version}")
    canvas.drawRightString(doc.width + doc.leftMargin, 
                          doc.height + doc.topMargin - 0.7*inch, 
                          f"Fecha: {fecha}")
    
    # Línea inferior del encabezado
    canvas.line(doc.leftMargin, doc.height + doc.topMargin - 1.0*inch, 
                doc.width + doc.leftMargin, doc.height + doc.topMargin - 1.0*inch)
    
    # PIE DE PÁGINA
    # Línea superior del pie
    canvas.line(doc.leftMargin, 0.8*inch, 
                doc.width + doc.leftMargin, 0.8*inch)
    
    # Texto del pie (tres columnas)
    canvas.setFont('Times-Roman', 9)
    
    # Elaborado por (izquierda)
    canvas.drawString(doc.leftMargin, doc.bottomMargin + 0.3*inch, 
                     f"Elaborado por: {elaborado}")
    
    # Revisado por (centro)
    canvas.drawCentredString(doc.width/2 + doc.leftMargin, 
                            doc.bottomMargin + 0.3*inch, 
                            f"Revisado por: {revisado}")
    
    # Aprobado por (derecha)
    canvas.drawRightString(doc.width + doc.leftMargin, 
                          doc.bottomMargin + 0.3*inch, 
                          f"Aprobado por: {aprobado}")
    
    # Número de página (centro, abajo)
    canvas.setFont('Times-Roman', 10)
    canvas.drawCentredString(doc.width/2 + doc.leftMargin, 
                            doc.bottomMargin + 0.1*inch, 
                            f"Página {doc.page}")
    
    canvas.restoreState()

def generar_grafico_foda_radar_pdf(puntajes):
    """Genera gráfico de radar FODA para el PDF."""
    if puntajes is None or puntajes.empty: 
        return None
    
    labels = np.array(['Ofensiva\n(FO)', 'Defensiva\n(FA)', 'Adaptativa\n(DO)', 'Supervivencia\n(DA)'])
    stats = puntajes.reindex(['FO', 'FA', 'DO', 'DA']).fillna(0).values
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    stats = np.concatenate((stats, [stats[0]]))
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='#1f77b4', alpha=0.25)
    ax.plot(angles, stats, color='#1f77b4', linewidth=2, marker='o')
    ax.set_yticklabels([])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_title("Posicionamiento Estratégico FODA", size=12, color='black', y=1.1, fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.7)
    
    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='PNG', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf

def generar_grafico_barras_pest(df_pest):
    """Genera gráfico de barras PEST para el PDF."""
    if df_pest.empty: 
        return None
    
    pest_scores = df_pest.groupby('categoria')['valor_ponderado'].sum().sort_values(ascending=True)
    
    fig, ax = plt.subplots(figsize=(7, 4))
    colors = {'Político': '#d62728', 'Económico': '#ff7f0e', 'Social': '#2ca02c', 'Tecnológico': '#1f77b4'}
    bar_colors = [colors.get(cat, '#1f77b4') for cat in pest_scores.index]
    
    bars = ax.barh(pest_scores.index, pest_scores.values, color=bar_colors, edgecolor='black', linewidth=0.5)
    ax.set_title('Análisis PEST - Puntuación por Categoría', fontsize=12, fontweight='bold', pad=15)
    ax.set_xlabel('Suma de Valores Ponderados', fontsize=10)
    ax.set_ylabel('')
    
    # Agregar valores en las barras
    for i, (bar, val) in enumerate(zip(bars, pest_scores.values)):
        ax.text(val + 0.5, i, f'{val:.1f}', va='center', fontsize=9)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='PNG', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf

def generar_grafico_proyeccion(df_proy):
    """Genera gráfico de proyección financiera para el PDF."""
    if df_proy.empty:
        return None
    
    fig, ax = plt.subplots(figsize=(8, 5))
    
    ax.plot(df_proy['anio'], df_proy['ingresos_proyectados'], 
            marker='o', linewidth=2.5, label='Ingresos Proyectados', color='#2ca02c')
    ax.plot(df_proy['anio'], df_proy['costos_proyectados'], 
            marker='s', linewidth=2.5, label='Costos Proyectados', color='#d62728')
    ax.plot(df_proy['anio'], df_proy['utilidad_neta_proyectada'], 
            marker='^', linewidth=2.5, label='Utilidad Neta', color='#1f77b4')
    
    ax.set_title('Proyección Financiera a 5 Años', fontsize=12, fontweight='bold', pad=15)
    ax.set_xlabel('Año', fontsize=10)
    ax.set_ylabel('Monto ($)', fontsize=10)
    ax.legend(loc='best', framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1e6:.1f}M' if x >= 1e6 else f'${x/1e3:.0f}K'))
    
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='PNG', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf

def create_table_pdf(data, col_widths=None, style=None):
    """Crea una tabla formateada para PDF."""
    from reportlab.lib.colors import HexColor
    
    if col_widths is None:
        col_widths = [1.5*inch] * len(data[0])
    
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    if style is None:
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), HexColor('#F2F2F2')),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#000000')),
            ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ])
    
    table.setStyle(style)
    return table

def generar_pdf_completo_mejorado(empresa_id, version, elaborado, revisado, aprobado):
    """
    Genera PDF profesional usando WeasyPrint (HTML → PDF).
    Mantiene TODO tu análisis existente, solo mejora el renderizado.
    """
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    from datetime import datetime
    import base64
    from io import BytesIO
    
    empresa = get_datos_empresa(empresa_id)
    if not empresa:
        st.error("No se encontraron datos de la empresa")
        return None
    
    fecha_actual = datetime.now().strftime('%d/%m/%Y')
    
    # Obtener todos los datos (TU LÓGICA EXISTENTE - NO CAMBIA)
    df_pest = get_datos_tabla('matrices', empresa_id, tipo_matriz_filter='PEST')
    df_foda = get_datos_tabla('foda_cruzado', empresa_id)
    df_estrategias = get_datos_tabla('estrategias_generadas', empresa_id)
    df_oper = get_datos_tabla('operativizacion', empresa_id)
    df_pg = get_datos_tabla('perdida_ganancia', empresa_id)
    df_proy = get_datos_tabla('proyeccion_financiera', empresa_id)
    df_cb = get_datos_tabla('analisis_costo_beneficio', empresa_id)
    df_made = get_datos_tabla('matriz_marketing', empresa_id, tipo_matriz_filter='MADE')
    df_madi = get_datos_tabla('matriz_marketing', empresa_id, tipo_matriz_filter='MADI')
    
    # Análisis FODA (TU LÓGICA EXISTENTE)
    analisis_foda_df, resumen_foda, estrategia_principal, puntajes_foda = analizar_foda(df_foda)
    pest_total = df_pest['valor_ponderado'].sum() if not df_pest.empty else 0
    total_costo = pd.to_numeric(df_oper['costo'], errors='coerce').fillna(0).sum() if not df_oper.empty else 0
    
    # Función helper para imágenes base64
    def get_image_base64(data):
        if not data:
            return None
        try:
            if isinstance(data, str):
                # Limpiar prefijos hex/base64
                data = data.replace('\\x', '').replace("'", "").strip()
                try:
                    return base64.b64encode(bytes.fromhex(data)).decode()
                except:
                    return base64.b64encode(base64.b64decode(data)).decode()
            elif isinstance(data, bytes):
                return base64.b64encode(data).decode()
        except:
            return None
        return None
    
    # Generar gráficos y convertir a base64
    def grafico_to_base64(fig):
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    
    # Generar gráficos (reutilizando tus funciones existentes)
    graficos_base64 = {}
    
    # Gráfico FODA Radar
    if puntajes_foda is not None and not puntajes_foda.empty:
        fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
        labels = ['Ofensiva\n(FO)', 'Defensiva\n(FA)', 'Adaptativa\n(DO)', 'Supervivencia\n(DA)']
        stats = puntajes_foda.reindex(['FO', 'FA', 'DO', 'DA']).fillna(0).values
        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
        stats = np.concatenate((stats, [stats[0]]))
        angles += angles[:1]
        ax.fill(angles, stats, color='#1f77b4', alpha=0.25)
        ax.plot(angles, stats, color='#1f77b4', linewidth=2, marker='o')
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_title("Posicionamiento Estratégico FODA", pad=20, fontsize=11, fontweight='bold')
        graficos_base64['foda'] = grafico_to_base64(fig)
        plt.close()
    
    # Gráfico PEST
    if not df_pest.empty:
        pest_scores = df_pest.groupby('categoria')['valor_ponderado'].sum().sort_values(ascending=True)
        fig, ax = plt.subplots(figsize=(7, 4))
        colors = {'Político': '#d62728', 'Económico': '#ff7f0e', 'Social': '#2ca02c', 'Tecnológico': '#1f77b4'}
        bar_colors = [colors.get(cat, '#1f77b4') for cat in pest_scores.index]
        bars = ax.barh(pest_scores.index, pest_scores.values, color=bar_colors, edgecolor='black', linewidth=0.5)
        ax.set_title('Análisis PEST - Puntuación por Categoría', fontsize=11, fontweight='bold', pad=15)
        ax.set_xlabel('Suma de Valores Ponderados')
        for i, (bar, val) in enumerate(zip(bars, pest_scores.values)):
            ax.text(val + 0.5, i, f'{val:.1f}', va='center', fontsize=9)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        graficos_base64['pest'] = grafico_to_base64(fig)
        plt.close()
    
    # Gráfico Proyección
    if not df_proy.empty:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(df_proy['anio'], df_proy['ingresos_proyectados'], marker='o', linewidth=2.5, label='Ingresos', color='#2ca02c')
        ax.plot(df_proy['anio'], df_proy['costos_proyectados'], marker='s', linewidth=2.5, label='Costos', color='#d62728')
        ax.plot(df_proy['anio'], df_proy['utilidad_neta_proyectada'], marker='^', linewidth=2.5, label='Utilidad Neta', color='#1f77b4')
        ax.set_title('Proyección Financiera a 5 Años', fontsize=11, fontweight='bold', pad=15)
        ax.set_xlabel('Año')
        ax.set_ylabel('Monto ($)')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1e6:.1f}M' if abs(x) >= 1e6 else f'${x/1e3:.0f}K'))
        plt.tight_layout()
        graficos_base64['proyeccion'] = grafico_to_base64(fig)
        plt.close()
    
    # Logo y organigrama
    logo_b64 = get_image_base64(empresa.get('logo'))
    org_b64 = get_image_base64(empresa.get('organigrama'))
    
    # ===== CONSTRUIR HTML =====
    # Esta es la magia: HTML semántico con CSS de impresión profesional
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Plan Estratégico - {empresa.get('nombre', 'Empresa')}</title>
        <style>
            /* CONFIGURACIÓN DE PÁGINA */
            @page {{
                size: A4;
                margin: 2.5cm 2cm 3cm 2cm; /* top right bottom left */
                
                @top-center {{
                    content: "{empresa.get('nombre', 'Empresa')} | Versión: {version}";
                    font-size: 9pt;
                    color: #666;
                    border-bottom: 0.5pt solid #999;
                    padding-bottom: 5pt;
                }}
                
                @bottom-left {{
                    content: "Elaborado: {elaborado}";
                    font-size: 8pt;
                    color: #666;
                }}
                
                @bottom-center {{
                    content: "Página " counter(page);
                    font-size: 9pt;
                }}
                
                @bottom-right {{
                    content: "Revisado: {revisado} | Aprobado: {aprobado}";
                    font-size: 8pt;
                    color: #666;
                    text-align: right;
                }}
            }}
            
            @page :first {{
                @top-center {{ content: none; }}
                @bottom-left {{ content: none; }}
                @bottom-center {{ content: none; }}
                @bottom-right {{ content: none; }}
            }}
            
            /* TIPOGRAFÍA Y BASE */
            * {{
                box-sizing: border-box;
            }}
            
            body {{
                font-family: "Times New Roman", Times, serif;
                font-size: 11pt;
                line-height: 1.6;
                color: #333;
                text-align: justify;
                hyphens: auto;
            }}
            
            /* PORTADA */
            .portada {{
                page-break-after: always;
                text-align: center;
                padding-top: 4cm;
            }}
            
            .portada h1 {{
                font-size: 24pt;
                font-weight: bold;
                margin-bottom: 0.5cm;
                text-transform: uppercase;
                letter-spacing: 2pt;
            }}
            
            .portada .empresa-nombre {{
                font-size: 20pt;
                color: #1f4e79;
                margin-bottom: 2cm;
                font-weight: bold;
            }}
            
            .portada .info-doc {{
                font-size: 12pt;
                margin: 0.3cm 0;
            }}
            
            .portada .logo {{
                max-width: 4cm;
                max-height: 4cm;
                margin: 1cm auto;
            }}
            
            /* TÍTULOS */
            h1 {{
                font-size: 16pt;
                font-weight: bold;
                color: #1f4e79;
                text-align: center;
                margin-top: 1.5cm;
                margin-bottom: 0.8cm;
                page-break-after: avoid;
                border-bottom: 2pt solid #1f4e79;
                padding-bottom: 0.3cm;
            }}
            
            h2 {{
                font-size: 13pt;
                font-weight: bold;
                color: #2e5c8a;
                margin-top: 1cm;
                margin-bottom: 0.5cm;
                page-break-after: avoid;
            }}
            
            h3 {{
                font-size: 11pt;
                font-weight: bold;
                color: #333;
                margin-top: 0.8cm;
                margin-bottom: 0.4cm;
                page-break-after: avoid;
            }}
            
            /* PÁRRAFOS */
            p {{
                margin-bottom: 0.5cm;
                text-indent: 1cm;
            }}
            
            p.no-indent {{
                text-indent: 0;
            }}
            
            /* TABLAS - ESTILO PROFESIONAL */
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 0.5cm 0;
                font-size: 9pt;
                page-break-inside: auto;
            }}
            
            tr {{
                page-break-inside: avoid;
            }}
            
            thead {{
                display: table-header-group;
            }}
            
            th {{
                background-color: #1f4e79;
                color: white;
                font-weight: bold;
                padding: 8pt;
                text-align: left;
                border: 0.5pt solid #1f4e79;
            }}
            
            td {{
                padding: 6pt 8pt;
                border: 0.5pt solid #ccc;
                vertical-align: top;
            }}
            
            tr:nth-child(even) {{
                background-color: #f5f5f5;
            }}
            
            /* IMÁGENES */
            .figura {{
                text-align: center;
                margin: 0.8cm 0;
                page-break-inside: avoid;
            }}
            
            .figura img {{
                max-width: 100%;
                max-height: 8cm;
            }}
            
            .figura-caption {{
                font-size: 10pt;
                font-style: italic;
                color: #555;
                margin-top: 0.3cm;
            }}
            
            /* LISTAS */
            ul, ol {{
                margin-left: 1cm;
                margin-bottom: 0.5cm;
            }}
            
            li {{
                margin-bottom: 0.2cm;
            }}
            
            /* SECCIONES ESPECIALES */
            .resumen-box {{
                background-color: #f0f7ff;
                border-left: 3pt solid #1f4e79;
                padding: 0.5cm;
                margin: 0.5cm 0;
            }}
            
            .estrategia-item {{
                margin-bottom: 0.8cm;
                padding: 0.4cm;
                background-color: #fafafa;
                border: 0.5pt solid #ddd;
            }}
            
            .estrategia-header {{
                font-weight: bold;
                color: #1f4e79;
                margin-bottom: 0.2cm;
            }}
            
            /* SALTOS DE PÁGINA */
            .page-break {{
                page-break-before: always;
            }}
            
            /* ANEXOS */
            .anexo {{
                font-size: 10pt;
            }}
            
            .anexo h2 {{
                font-size: 12pt;
            }}
            
            /* TABLA DE DATOS GENERALES */
            .datos-gen td:first-child {{
                font-weight: bold;
                background-color: #e8f0f7;
                width: 35%;
            }}
        </style>
    </head>
    <body>
    
    <!-- PORTADA -->
    <div class="portada">
        <h1>Plan Estratégico</h1>
        <div class="empresa-nombre">{empresa.get('nombre', 'EMPRESA').upper()}</div>
        
        {f'<img src="data:image/png;base64,{logo_b64}" class="logo" />' if logo_b64 else ''}
        
        <div style="margin-top: 2cm;">
            <div class="info-doc"><strong>Versión:</strong> {version}</div>
            <div class="info-doc"><strong>Fecha:</strong> {fecha_actual}</div>
        </div>
        
        <div style="margin-top: 3cm; font-size: 11pt;">
            <div class="info-doc"><strong>Elaborado por:</strong> {elaborado}</div>
            <div class="info-doc"><strong>Revisado por:</strong> {revisado}</div>
            <div class="info-doc"><strong>Aprobado por:</strong> {aprobado}</div>
        </div>
    </div>
    
    <!-- RESUMEN EJECUTIVO -->
    <h1>Resumen Ejecutivo</h1>
    
    <p>El presente documento constituye el Plan Estratégico de <strong>{empresa.get('nombre', 'la empresa')}</strong>, 
    elaborado con fecha {fecha_actual}. Este resumen ejecutivo presenta los hallazgos más relevantes 
    del diagnóstico estratégico y las recomendaciones prioritarias para la alta dirección.</p>
    
    <h2>Diagnóstico Estratégico Clave</h2>
    
    {f'<p><strong>Estrategia Principal Recomendada:</strong> {estrategia_principal}. '
     f'Esta postura estratégica se determina a partir del análisis FODA cruzado y representa '
     f'la orientación prioritaria para el período de planificación.</p>' if estrategia_principal else ''}
    
    {f'''
    <div class="figura">
        <img src="data:image/png;base64,{graficos_base64['foda']}" />
        <div class="figura-caption">Figura 1. Posicionamiento estratégico según análisis FODA cruzado.</div>
    </div>
    ''' if 'foda' in graficos_base64 else ''}
    
    <h2>Factores Críticos del Entorno</h2>
    
    {f'''
    <ul>
    {''.join([f"<li><strong>{row['categoria']}</strong>: {row['factor'][:100]}...</li>" 
              for _, row in df_pest.nlargest(3, 'valor_ponderado').iterrows()])}
    </ul>
    ''' if not df_pest.empty else '<p>No hay datos PEST disponibles.</p>'}
    
    {f'''
    <div class="figura">
        <img src="data:image/png;base64,{graficos_base64['pest']}" />
        <div class="figura-caption">Figura 2. Distribución de factores PEST por impacto.</div>
    </div>
    ''' if 'pest' in graficos_base64 else ''}
    
    <h2>Estrategias Prioritarias</h2>
    
    {f'''
    <div class="estrategias-lista">
    {''.join([f"""
        <div class="estrategia-item">
            <div class="estrategia-header">[{row['cuadrante']}] {row['plan_asignado']}</div>
            <p class="no-indent">{row['estrategia'][:150]}...</p>
        </div>
    """ for _, row in df_estrategias[df_estrategias['importancia'].isin(['Alta', 'Media Alta'])].head(5).iterrows()])}
    </div>
    ''' if not df_estrategias.empty else '<p>No hay estrategias definidas.</p>'}
    
    <h2>Viabilidad Financiera</h2>
    
    {f'''
    <table>
        <thead>
            <tr>
                <th>Indicador</th>
                <th>Valor</th>
                <th>Interpretación</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Relación Costo-Beneficio</td>
                <td>{float(df_cb.iloc[0]['relacion_costo_beneficio_dolares']):.2f}</td>
                <td>{'Rentable' if df_cb.iloc[0]['relacion_costo_beneficio_dolares'] >= 1 else 'No rentable'}</td>
            </tr>
            <tr>
                <td>Periodo de Recuperación</td>
                <td>{f"{float(df_cb.iloc[0]['payback_periodo_anios']):.1f} años" if df_cb.iloc[0]['payback_periodo_anios'] else 'N/A'}</td>
                <td>{'Aceptable' if df_cb.iloc[0]['payback_periodo_anios'] and df_cb.iloc[0]['payback_periodo_anios'] <= 5 else 'Revisar'}</td>
            </tr>
            <tr>
                <td>Inversión Total</td>
                <td>${float(df_cb.iloc[0]['inversion_total']):,.2f}</td>
                <td>Requerimiento de capital</td>
            </tr>
        </tbody>
    </table>
    
    {f"""
    <div class='figura'>
        <img src='data:image/png;base64,{graficos_base64['proyeccion']}' />
        <div class='figura-caption'>Figura 3. Proyección financiera del plan estratégico.</div>
    </div>
    """ if 'proyeccion' in graficos_base64 else ''}
    
    ''' if not df_cb.empty else '<p>No hay análisis financiero disponible.</p>'}
    
    <h2>Recomendación Ejecutiva</h2>
    
    {f'''
    <div class="resumen-box">
        <p class="no-indent"><strong>{'APROBAR EL PROYECTO' if sum([
            df_cb.iloc[0]['relacion_costo_beneficio_dolares'] >= 1,
            df_cb.iloc[0]['payback_periodo_anios'] is not None and df_cb.iloc[0]['payback_periodo_anios'] <= 5,
            df_cb.iloc[0]['relacion_cb_unidades'] >= 1
        ]) >= 2 else 'EVALUAR CON PRECAUCIÓN' if sum([
            df_cb.iloc[0]['relacion_costo_beneficio_dolares'] >= 1,
            df_cb.iloc[0]['payback_periodo_anios'] is not None and df_cb.iloc[0]['payback_periodo_anios'] <= 5,
            df_cb.iloc[0]['relacion_cb_unidades'] >= 1
        ]) == 1 else 'RECHAZAR O REPLANTEAR'}.</strong> 
        El análisis integral indica que el Plan Estratégico es 
        {'viable financieramente' if sum([
            df_cb.iloc[0]['relacion_costo_beneficio_dolares'] >= 1,
            df_cb.iloc[0]['payback_periodo_anios'] is not None and df_cb.iloc[0]['payback_periodo_anios'] <= 5,
            df_cb.iloc[0]['relacion_cb_unidades'] >= 1
        ]) >= 2 else 'viable con riesgos moderados' if sum([
            df_cb.iloc[0]['relacion_costo_beneficio_dolares'] >= 1,
            df_cb.iloc[0]['payback_periodo_anios'] is not None and df_cb.iloc[0]['payback_periodo_anios'] <= 5,
            df_cb.iloc[0]['relacion_cb_unidades'] >= 1
        ]) == 1 else 'no viable en su forma actual'}.
        Se recomienda {'iniciar la implementación priorizando las estrategias de alta importancia' if sum([
            df_cb.iloc[0]['relacion_costo_beneficio_dolares'] >= 1,
            df_cb.iloc[0]['payback_periodo_anios'] is not None and df_cb.iloc[0]['payback_periodo_anios'] <= 5,
            df_cb.iloc[0]['relacion_cb_unidades'] >= 1
        ]) >= 2 else 'revisar los supuestos críticos antes de aprobar' if sum([
            df_cb.iloc[0]['relacion_costo_beneficio_dolares'] >= 1,
            df_cb.iloc[0]['payback_periodo_anios'] is not None and df_cb.iloc[0]['payback_periodo_anios'] <= 5,
            df_cb.iloc[0]['relacion_cb_unidades'] >= 1
        ]) == 1 else 'replantear la estrategia o buscar alternativas de menor inversión'}.</p>
    </div>
    ''' if not df_cb.empty else ''}
    
    <!-- PLAN ESTRATÉGICO DETALLADO -->
    <div class="page-break"></div>
    
    <h1>Plan Estratégico</h1>
    <p style="text-align: center; font-size: 14pt; color: #1f4e79; margin-bottom: 1cm;">
        <strong>{empresa.get('nombre', 'EMPRESA').upper()}</strong>
    </p>
    
    <!-- 1. INTRODUCCIÓN -->
    <h2>1. Introducción y Fundamentos</h2>
    
    <h3>1.1 Datos Generales de la Empresa</h3>
    
    <table class="datos-gen">
        <tr>
            <td>Nombre de la Empresa</td>
            <td>{empresa.get('nombre', 'N/A')}</td>
        </tr>
        <tr>
            <td>Giro del Negocio</td>
            <td>{empresa.get('giro', 'N/A')}</td>
        </tr>
        <tr>
            <td>Fecha del Plan</td>
            <td>{fecha_actual}</td>
        </tr>
        <tr>
            <td>Versión del Documento</td>
            <td>{version}</td>
        </tr>
    </table>
    
    {f'''
    <h3>Logo de la Empresa</h3>
    <div class="figura">
        <img src="data:image/png;base64,{logo_b64}" style="max-height: 3cm;" />
    </div>
    ''' if logo_b64 else ''}
    
    <h3>1.2 Elementos Orientadores de la Cultura Organizacional</h3>
    
    {f'''
    <h4>Misión</h4>
    <p>{empresa.get('mision')}</p>
    ''' if empresa.get('mision') else ''}
    
    {f'''
    <h4>Visión</h4>
    <p>{empresa.get('vision')}</p>
    ''' if empresa.get('vision') else ''}
    
    {f'''
    <h4>Valores</h4>
    <p>{empresa.get('valores')}</p>
    ''' if empresa.get('valores') else ''}
    
    {f'''
    <h3>1.3 Organigrama de la Empresa</h3>
    <div class="figura">
        <img src="data:image/png;base64,{org_b64}" />
        <div class="figura-caption">Figura 1.1. Estructura organizacional de la empresa.</div>
    </div>
    ''' if org_b64 else ''}
    
    <!-- 2. ANÁLISIS SITUACIONAL -->
    <div class="page-break"></div>
    
    <h2>2. Análisis Situacional</h2>
    <p>El análisis situacional examina tanto los factores internos como externos que afectan 
    a la organización, permitiendo identificar fortalezas, debilidades, oportunidades y amenazas.</p>
    
    <h3>2.1 Diagnóstico Interno</h3>
    
    <h4>2.1.1 Análisis de Marketing Interno (MADE)</h4>
    <p>La matriz MADE evalúa las variables internas de marketing: Producto, Precio, Plaza y Promoción.</p>
    
    {f'''
    <table>
        <thead>
            <tr>
                <th>Variable</th>
                <th>Factor</th>
                <th>Rating</th>
                <th>Ponderación</th>
            </tr>
        </thead>
        <tbody>
            {''.join([f"""
            <tr>
                <td>{row.get('variable', '')[:20]}</td>
                <td>{row.get('factor', '')[:30]}</td>
                <td>{row.get('rating', '')}</td>
                <td>{row.get('weight_percent', '')}%</td>
            </tr>
            """ for _, row in df_made.head(10).iterrows()])}
        </tbody>
    </table>
    ''' if not df_made.empty else '<p>No hay datos MADE disponibles.</p>'}
    
    {f'''
    <h4>Análisis de Marketing Interno</h4>
    <p>{empresa.get('analisis_made', '')}</p>
    ''' if empresa.get('analisis_made') else ''}
    
    <h3>2.2 Diagnóstico Externo</h3>
    
    <h4>2.2.1 Análisis de Marketing Externo (MADI)</h4>
    <p>La matriz MADI evalúa las variables externas de marketing que impactan en la posición competitiva.</p>
    
    {f'''
    <table>
        <thead>
            <tr>
                <th>Variable</th>
                <th>Factor</th>
                <th>Rating</th>
                <th>Ponderación</th>
            </tr>
        </thead>
        <tbody>
            {''.join([f"""
            <tr>
                <td>{row.get('variable', '')[:20]}</td>
                <td>{row.get('factor', '')[:30]}</td>
                <td>{row.get('rating', '')}</td>
                <td>{row.get('weight_percent', '')}%</td>
            </tr>
            """ for _, row in df_madi.head(10).iterrows()])}
        </tbody>
    </table>
    ''' if not df_madi.empty else '<p>No hay datos MADI disponibles.</p>'}
    
    <h4>2.2.2 Análisis del Entorno PEST</h4>
    <p>El análisis PEST examina los factores Políticos, Económicos, Sociales y Tecnológicos.</p>
    
    {f'''
    <table>
        <thead>
            <tr>
                <th>Categoría</th>
                <th>Factor</th>
                <th>Tipo FODA</th>
                <th>Puntaje</th>
                <th>Ponderado</th>
            </tr>
        </thead>
        <tbody>
            {''.join([f"""
            <tr>
                <td>{row['categoria']}</td>
                <td>{row['factor'][:35]}{'...' if len(row['factor']) > 35 else ''}</td>
                <td>{row['tipo_foda']}</td>
                <td>{row['puntaje']}</td>
                <td>{row['valor_ponderado']:.2f}</td>
            </tr>
            """ for _, row in df_pest.head(15).iterrows()])}
        </tbody>
    </table>
    
    <div class="figura">
        <img src="data:image/png;base64,{graficos_base64['pest']}" />
        <div class="figura-caption">Figura 2.1. Análisis PEST - Distribución por categoría.</div>
    </div>
    ''' if not df_pest.empty else '<p>No hay datos PEST disponibles.</p>'}
    
    {f'''
    <h4>Interpretación del Análisis PEST</h4>
    <p>{empresa.get('analisis_pest', '')}</p>
    ''' if empresa.get('analisis_pest') else ''}
    
    <h3>2.3 Matriz FODA Cruzado</h3>
    <p>El análisis FODA cruzado identifica estrategias a partir de la combinación de 
    fortalezas, debilidades, oportunidades y amenazas.</p>
    
    {f'''
    <table>
        <thead>
            <tr>
                <th>Cuadrante</th>
                <th>Factor Fila</th>
                <th>Factor Columna</th>
                <th>Impacto</th>
            </tr>
        </thead>
        <tbody>
            {''.join([f"""
            <tr>
                <td>{row['cuadrante']}</td>
                <td>{str(row['factor_fila'])[:30]}{'...' if len(str(row['factor_fila'])) > 30 else ''}</td>
                <td>{str(row['factor_columna'])[:30]}{'...' if len(str(row['factor_columna'])) > 30 else ''}</td>
                <td>{row['impacto']}</td>
            </tr>
            """ for _, row in df_foda.head(20).iterrows()])}
        </tbody>
    </table>
    
    <div class="figura">
        <img src="data:image/png;base64,{graficos_base64['foda']}" />
        <div class="figura-caption">Figura 2.2. Posicionamiento estratégico según FODA cruzado.</div>
    </div>
    ''' if not df_foda.empty else '<p>No hay datos FODA disponibles.</p>'}
    
    {f'''
    <h4>Postura Estratégica Recomendada</h4>
    <p>Basado en el análisis cruzado, la estrategia principal recomendada es 
    <strong>{estrategia_principal}</strong>. La distribución de puntajes por estrategia es:</p>
    
    <table>
        <thead>
            <tr>
                <th>Estrategia</th>
                <th>Puntaje Total</th>
            </tr>
        </thead>
        <tbody>
            {''.join([f"<tr><td>{row['Estrategia']}</td><td>{row['Puntaje Total']}</td></tr>" 
                      for _, row in analisis_foda_df.iterrows()]) if analisis_foda_df is not None else ''}
        </tbody>
    </table>
    ''' if estrategia_principal else ''}
    
    {f'''
    <h4>Interpretación del Análisis FODA</h4>
    <p>{empresa.get('analisis_foda', '')}</p>
    ''' if empresa.get('analisis_foda') else ''}
    
    <!-- 3. ESTRATEGIAS -->
    <div class="page-break"></div>
    
    <h2>3. Estrategias</h2>
    <p>Las estrategias representan las acciones específicas diseñadas para alcanzar los objetivos 
    organizacionales, derivadas del análisis situacional.</p>
    
    {f'''
    <p>Se han formulado {len(df_estrategias)} estrategias distribuidas en los cuatro cuadrantes 
    del análisis FODA cruzado. La estrategia principal recomendada es <strong>{estrategia_principal}</strong>.</p>
    
    <h3>3.1 Resumen de Estrategias por Cuadrante</h3>
    
    <table>
        <thead>
            <tr>
                <th>Cuadrante</th>
                <th>N° Estrategias</th>
                <th>Planes Asignados</th>
            </tr>
        </thead>
        <tbody>
            {''.join([f"""
            <tr>
                <td>{row['cuadrante']}</td>
                <td>{row['estrategia']}</td>
                <td>{row['plan_asignado']}</td>
            </tr>
            """ for _, row in df_estrategias.groupby('cuadrante').agg({
                'estrategia': 'count',
                'plan_asignado': lambda x: ', '.join(x.unique())
            }).reset_index().iterrows()])}
        </tbody>
    </table>
    
    <h3>3.2 Estrategias Detalladas</h3>
    
    {''.join([f"""
    <div class="estrategia-item">
        <div class="estrategia-header">Estrategia {idx + 1}: [{row['cuadrante']}] {row['estrategia']}</div>
        <p class="no-indent"><strong>Plan asignado:</strong> {row['plan_asignado']}</p>
        <p class="no-indent"><strong>Importancia:</strong> {row['importancia']}</p>
        <p class="no-indent"><strong>Actividades clave:</strong> {row['actividades']}</p>
    </div>
    """ for idx, row in df_estrategias.iterrows()])}
    
    ''' if not df_estrategias.empty else '<p>No se han generado estrategias.</p>'}
    
    <!-- 4. PLAN DE ACCIÓN -->
    <div class="page-break"></div>
    
    <h2>4. Plan de Acción</h2>
    <p>El plan de acción detalla las actividades específicas, responsables, tiempos y recursos 
    necesarios para implementar las estrategias formuladas.</p>
    
    <h3>4.1 Planes Funcionales Estratégicos</h3>
    
    {f'''
    <p>La operativización detalla {len(df_oper)} actividades derivadas de las estrategias formuladas, 
    con una inversión total estimada de <strong>${total_costo:,.2f}</strong>.</p>
    
    <h3>4.3.1 Resumen de Inversión por Plan</h3>
    
    <table>
        <thead>
            <tr>
                <th>Plan Estratégico</th>
                <th>Costo Total</th>
                <th>N° Actividades</th>
            </tr>
        </thead>
        <tbody>
            {''.join([f"""
            <tr>
                <td>{row['plan_asignado']}</td>
                <td>${row['costo']:,.2f}</td>
                <td>{int(row['descripcion_actividad'])}</td>
            </tr>
            """ for _, row in df_oper.groupby('plan_asignado').agg({
                'costo': 'sum',
                'descripcion_actividad': 'count'
            }).reset_index().iterrows()])}
        </tbody>
    </table>
    
    <h3>4.3.2 Cuadro de Operativización Detallado</h3>
    
    <table>
        <thead>
            <tr>
                <th>Estrategia</th>
                <th>Actividad</th>
                <th>Plazo</th>
                <th>Responsable</th>
                <th>Costo</th>
            </tr>
        </thead>
        <tbody>
            {''.join([f"""
            <tr>
                <td>{row['estrategia_nombre'][:25]}{'...' if len(row['estrategia_nombre']) > 25 else ''}</td>
                <td>{row['descripcion_actividad'][:35]}{'...' if len(row['descripcion_actividad']) > 35 else ''}</td>
                <td>{row['plazo'] or 'Pendiente'}</td>
                <td>{row['responsable'] or 'Sin asignar'}</td>
                <td>${row['costo']:,.2f}</td>
            </tr>
            """ for _, row in df_oper.head(30).iterrows()])}
        </tbody>
    </table>
    
    {f'<p style="font-size: 9pt; font-style: italic;">Nota: Se muestran 30 de {len(df_oper)} actividades. '
     f'El detalle completo está en los anexos.</p>' if len(df_oper) > 30 else ''}
    
    <h3>4.3.3 Actividades de Mayor Inversión</h3>
    
    <ul>
    {''.join([f"""
        <li><strong>${row['costo']:,.2f}</strong> - {row['descripcion_actividad'][:80]}... 
        ({row['responsable'] or 'Sin asignar'})</li>
    """ for _, row in df_oper.nlargest(5, 'costo').iterrows()])}
    </ul>
    
    ''' if not df_oper.empty else '<p>No se ha completado la operativización.</p>'}
    
    <!-- 5. EVALUACIÓN Y CONTROL -->
    <div class="page-break"></div>
    
    <h2>5. Evaluación y Control</h2>
    <p>La evaluación y control permiten monitorear el desempeño de las estrategias mediante 
    indicadores clave de desempeño (KPIs) y sistemas de alerta temprana.</p>
    
    {f'''
    <h3>5.1 Cuadro de Mando Integral (CMI)</h3>
    <p>El Cuadro de Mando Integral traduce las estrategias en indicadores medibles 
    desde cuatro perspectivas: Financiera, Cliente, Procesos Internos, y Aprendizaje y Crecimiento.</p>
    ''' if not df_estrategias.empty else ''}
    
    <h3>5.2 Semaforización Estratégica</h3>
    {f'<p>{empresa.get("analisis_semaforo_resumen", "")}</p>' if empresa.get('analisis_semaforo_resumen') else 
     '<p>El sistema de semaforización evalúa el estado de cada estrategia considerando alineación '
     'con objetivos, recursos asignados y contexto externo.</p>'}
    
    <!-- ANEXOS -->
    <div class="page-break"></div>
    
    <div class="anexo">
        <h1>Anexos</h1>
        
        <h2>Anexo A. Análisis Detallados de Matrices</h2>
        
        {f'''
        <h3>A.1 Matriz MADE (Marketing Interno) - Datos Completos</h3>
        <table>
            <thead>
                <tr>
                    <th>Variable</th>
                    <th>Factor</th>
                    <th>Producto</th>
                    <th>Precio</th>
                    <th>Plaza</th>
                    <th>Promoción</th>
                    <th>Rating</th>
                    <th>Peso %</th>
                    <th>Valor</th>
                </tr>
            </thead>
            <tbody>
                {''.join([f"""
                <tr>
                    <td>{str(row.get('variable', ''))[:15]}</td>
                    <td>{str(row.get('factor', ''))[:25]}</td>
                    <td>{str(row.get('producto', ''))[:10]}</td>
                    <td>{str(row.get('precio', ''))[:10]}</td>
                    <td>{str(row.get('plaza', ''))[:10]}</td>
                    <td>{str(row.get('promocion', ''))[:10]}</td>
                    <td>{row.get('rating', '')}</td>
                    <td>{row.get('weight_percent', '')}%</td>
                    <td>{row.get('valor', '')}</td>
                </tr>
                """ for _, row in df_made.iterrows()])}
            </tbody>
        </table>
        ''' if not df_made.empty else ''}
        
        {f'''
        <h3>A.2 Matriz MADI (Marketing Externo) - Datos Completos</h3>
        <table>
            <thead>
                <tr>
                    <th>Variable</th>
                    <th>Factor</th>
                    <th>Producto</th>
                    <th>Precio</th>
                    <th>Plaza</th>
                    <th>Promoción</th>
                    <th>Rating</th>
                    <th>Peso %</th>
                    <th>Valor</th>
                </tr>
            </thead>
            <tbody>
                {''.join([f"""
                <tr>
                    <td>{str(row.get('variable', ''))[:15]}</td>
                    <td>{str(row.get('factor', ''))[:25]}</td>
                    <td>{str(row.get('producto', ''))[:10]}</td>
                    <td>{str(row.get('precio', ''))[:10]}</td>
                    <td>{str(row.get('plaza', ''))[:10]}</td>
                    <td>{str(row.get('promocion', ''))[:10]}</td>
                    <td>{row.get('rating', '')}</td>
                    <td>{row.get('weight_percent', '')}%</td>
                    <td>{row.get('valor', '')}</td>
                </tr>
                """ for _, row in df_madi.iterrows()])}
            </tbody>
        </table>
        ''' if not df_madi.empty else ''}
        
        {f'''
        <h3>A.3 Análisis PEST Completo</h3>
        <table>
            <thead>
                <tr>
                    <th>Categoría</th>
                    <th>Factor</th>
                    <th>Tipo FODA</th>
                    <th>Puntaje</th>
                    <th>Importancia</th>
                    <th>Ponderado</th>
                </tr>
            </thead>
            <tbody>
                {''.join([f"""
                <tr>
                    <td>{row['categoria']}</td>
                    <td>{row['factor'][:40]}{'...' if len(row['factor']) > 40 else ''}</td>
                    <td>{row['tipo_foda']}</td>
                    <td>{row['puntaje']}</td>
                    <td>{row['importancia']}%</td>
                    <td>{row['valor_ponderado']:.2f}</td>
                </tr>
                """ for _, row in df_pest.iterrows()])}
            </tbody>
        </table>
        ''' if not df_pest.empty else ''}
        
        {f'''
        <h3>A.4 Matriz FODA Cruzado Completa</h3>
        <table>
            <thead>
                <tr>
                    <th>Cuadrante</th>
                    <th>Factor Fila</th>
                    <th>Factor Columna</th>
                    <th>Impacto</th>
                </tr>
            </thead>
            <tbody>
                {''.join([f"""
                <tr>
                    <td>{row['cuadrante']}</td>
                    <td>{str(row['factor_fila'])[:50]}{'...' if len(str(row['factor_fila'])) > 50 else ''}</td>
                    <td>{str(row['factor_columna'])[:50]}{'...' if len(str(row['factor_columna'])) > 50 else ''}</td>
                    <td>{row['impacto']}</td>
                </tr>
                """ for _, row in df_foda.iterrows()])}
            </tbody>
        </table>
        ''' if not df_foda.empty else ''}
        
        <h2>Anexo B. Dashboards de Análisis Estratégico</h2>
        
        {f'''
        <h3>B.1 Distribución de Estrategias por Cuadrante</h3>
        <div class="figura">
            <img src="data:image/png;base64,{graficos_base64['foda']}" />
        </div>
        ''' if 'foda' in graficos_base64 else ''}
        
        {f'''
        <h3>B.2 Proyección Financiera Detallada</h3>
        <div class="figura">
            <img src="data:image/png;base64,{graficos_base64['proyeccion']}" />
        </div>
        <table>
            <thead>
                <tr>
                    <th>Año</th>
                    <th>Ingresos Proyectados</th>
                    <th>Costos Proyectados</th>
                    <th>Utilidad Neta Proyectada</th>
                </tr>
            </thead>
            <tbody>
                {''.join([f"""
                <tr>
                    <td>{int(row['anio'])}</td>
                    <td>${row['ingresos_proyectados']:,.0f}</td>
                    <td>${row['costos_proyectados']:,.0f}</td>
                    <td>${row['utilidad_neta_proyectada']:,.0f}</td>
                </tr>
                """ for _, row in df_proy.iterrows()])}
            </tbody>
        </table>
        ''' if not df_proy.empty else ''}
        
        {f'''
        <h3>B.3 Análisis Costo-Beneficio Detallado</h3>
        <table>
            <thead>
                <tr>
                    <th>Indicador</th>
                    <th>Valor</th>
                    <th>Umbral Aceptable</th>
                    <th>Estado</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Relación C-B ($)</td>
                    <td>{float(df_cb.iloc[0]['relacion_costo_beneficio_dolares']):.2f}</td>
                    <td>≥ 1.0</td>
                    <td>{'Aceptable' if df_cb.iloc[0]['relacion_costo_beneficio_dolares'] >= 1 else 'No aceptable'}</td>
                </tr>
                <tr>
                    <td>Payback (años)</td>
                    <td>{f"{float(df_cb.iloc[0]['payback_periodo_anios']):.1f}" if df_cb.iloc[0]['payback_periodo_anios'] else 'N/A'}</td>
                    <td>≤ 5</td>
                    <td>{'Aceptable' if df_cb.iloc[0]['payback_periodo_anios'] and df_cb.iloc[0]['payback_periodo_anios'] <= 5 else 'Revisar'}</td>
                </tr>
                <tr>
                    <td>VPN Total</td>
                    <td>${float(df_cb.iloc[0]['vpn_total']):,.2f}</td>
                    <td>> 0</td>
                    <td>{'Positivo' if df_cb.iloc[0]['vpn_total'] > 0 else 'Negativo'}</td>
                </tr>
                <tr>
                    <td>Inversión Total</td>
                    <td>${float(df_cb.iloc[0]['inversion_total']):,.2f}</td>
                    <td>-</td>
                    <td>Requerimiento</td>
                </tr>
                <tr>
                    <td>Beneficio/Unidad</td>
                    <td>${float(df_cb.iloc[0]['beneficio_por_unidad']):,.2f}</td>
                    <td>≥ Costo/Unidad</td>
                    <td>{'Rentable' if df_cb.iloc[0]['relacion_cb_unidades'] >= 1 else 'No rentable'}</td>
                </tr>
            </tbody>
        </table>
        ''' if not df_cb.empty else ''}
        
        {f'''
        <h2>Anexo C. Cuadro de Operativización Completo</h2>
        <table>
            <thead>
                <tr>
                    <th>N°</th>
                    <th>Estrategia</th>
                    <th>Actividad</th>
                    <th>Plazo</th>
                    <th>Responsable</th>
                    <th>Costo</th>
                </tr>
            </thead>
            <tbody>
                {''.join([f"""
                <tr>
                    <td>{idx + 1}</td>
                    <td>{row['estrategia_nombre'][:30]}{'...' if len(row['estrategia_nombre']) > 30 else ''}</td>
                    <td>{row['descripcion_actividad'][:40]}{'...' if len(row['descripcion_actividad']) > 40 else ''}</td>
                    <td>{row['plazo'] or 'Pendiente'}</td>
                    <td>{row['responsable'] or 'Sin asignar'}</td>
                    <td>${row['costo']:,.2f}</td>
                </tr>
                """ for idx, row in df_oper.iterrows()])}
            </tbody>
        </table>
        '' if not df_oper.empty else ''}
        
    </div> <!-- fin anexo -->
    
    </body>
    </html>
    """
    
    # Generar PDF con WeasyPrint
    try:
        font_config = FontConfiguration()
        html_doc = HTML(string=html_content)
        
        # CSS adicional para mejorar la renderización
        css_content = """
        @page {
            @footnote {
                border-top: 0.5pt solid #999;
                padding-top: 0.3cm;
            }
        }
        ""
        
        pdf_buffer = BytesIO()
        html_doc.write_pdf(
            pdf_buffer,
            font_config=font_config,
            stylesheets=[CSS(string=css_content)]
        )
        pdf_buffer.seek(0)
        return pdf_buffer
        
    except Exception as e:
        st.error(f"Error al generar PDF con WeasyPrint: {e}")
        st.error("Verifica que WeasyPrint esté instalado correctamente.")
        return None

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
        st.header("Estratega Pro UG-UCE")
        empresas_df = get_empresas()

        # Mostrar empresas con indicador de permiso
        opciones_empresas = []
        empresa_info = {}

        if not empresas_df.empty:
            for _, row in empresas_df.iterrows():
                es_propietario = row.get('es_propietario', False)
                permiso = row.get('permiso', 'lector')

                if es_propietario:
                    label = f"👑 {row['nombre']} (Propietario)"
                elif permiso == 'editor':
                    label = f"✏️ {row['nombre']} (Editor)"
                else:
                    label = f"👁️ {row['nombre']} (Lector)"

                opciones_empresas.append(label)
                empresa_info[label] = {
                    'id': row['id'],
                    'nombre': row['nombre'],
                    'es_propietario': es_propietario,
                    'permiso': permiso
                }

        empresa_seleccionada_label = st.selectbox("Selecciona una Empresa", opciones_empresas, index=None, placeholder="Elige una opción")

        empresa_id = None
        empresa_seleccionada = None
        es_propietario = False
        permiso_actual = None

        if empresa_seleccionada_label and empresa_seleccionada_label in empresa_info:
            info = empresa_info[empresa_seleccionada_label]
            empresa_id = info['id']
            empresa_seleccionada = info['nombre']
            es_propietario = info['es_propietario']
            permiso_actual = info['permiso']

            # Mostrar badge de permiso
            if es_propietario:
                st.success("👑 Eres el propietario de esta empresa")
            elif permiso_actual == 'editor':
                st.info("✏️ Tienes permiso de Editor")
            else:
                st.info("👁️ Tienes permiso de Lector (solo ver)")

        st.divider()

        # Sección de crear empresa (solo para propietarios)
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

        # Opciones solo para propietarios
        if empresa_id and es_propietario:
            st.divider()

            # Compartir empresa
            with st.expander("🔗 Compartir Empresa"):
                st.write("Comparte esta empresa con otros usuarios:")

                with st.form("form_compartir"):
                    email_compartir = st.text_input("Email del usuario")
                    permiso_compartir = st.selectbox("Permiso", ["lector", "editor"], 
                                                    format_func=lambda x: "👁️ Lector (solo ver)" if x == "lector" else "✏️ Editor (puede modificar)")

                    if st.form_submit_button("Compartir"):
                        if email_compartir:
                            exito, mensaje = compartir_empresa(empresa_id, email_compartir, permiso_compartir)
                            if exito:
                                st.success(mensaje)
                                st.rerun()
                            else:
                                st.error(mensaje)
                        else:
                            st.warning("Ingresa un email")

                # Mostrar usuarios con quienes se compartió
                usuarios_comp = get_usuarios_compartidos(empresa_id)
                
                if usuarios_comp:
                    st.write("---")
                    st.markdown("**👥 Usuarios con acceso compartido**")
                    
                    for uc in usuarios_comp:
                        with st.container():
                            # Fila principal: Email, Rol, Eliminar
                            col1, col2, col3 = st.columns([4, 2, 1])
                            
                            with col1:
                                icono = "✏️" if uc['permiso'] == 'editor' else "👁️"
                                # Mostrar email completo, no truncado
                                email_display = uc['email']
                                st.markdown(f"{icono} **{email_display}**")
                            
                            with col2:
                                # Badge del rol
                                color_badge = "#2196f3" if uc['permiso'] == 'editor' else "#757575"
                                st.markdown(
                                    f"<span style='background-color: {color_badge}; color: white; "
                                    f"padding: 4px 12px; border-radius: 12px; font-size: 11px;'>"
                                    f"{uc['permiso'].upper()}</span>",
                                    unsafe_allow_html=True
                                )
                            
                            with col3:
                                user_id = uc['usuario_id']
                                if st.button("🗑️", key=f"del_{user_id}", help="Eliminar acceso"):
                                    try:
                                        supabase.table('empresas_compartidas').delete().eq(
                                            'empresa_id', empresa_id
                                        ).eq('usuario_compartido_id', user_id).execute()
                                        st.success("✓ Eliminado")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {str(e)[:50]}")
                            
                            # Fila de cambio de rol
                            col_cambio1, col_cambio2 = st.columns([3, 2])
                            
                            with col_cambio1:
                                user_id = uc['usuario_id']
                                rol_actual = uc['permiso']
                                
                                nuevo_rol = st.selectbox(
                                    "Cambiar a:",
                                    ["lector", "editor"],
                                    index=0 if rol_actual == 'lector' else 1,
                                    key=f"rol_{user_id}",
                                    label_visibility="collapsed"
                                )
                            
                            with col_cambio2:
                                user_id = uc['usuario_id']
                                rol_actual = uc['permiso']
                                
                                if nuevo_rol != rol_actual:
                                    if st.button("💾 Guardar", key=f"save_{user_id}", type="primary"):
                                        try:
                                            supabase.table('empresas_compartidas').update({
                                                'permiso': nuevo_rol
                                                # También actualizamos el email por si acaso
                                            }).eq('empresa_id', empresa_id).eq('usuario_compartido_id', user_id).execute()
                                            st.success(f"✓ {nuevo_rol}")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error: {str(e)[:50]}")
                                else:
                                    st.caption("✓ Actual")
                        
                        st.divider()
                else:
                    st.info("ℹ️ Esta empresa no está compartida con ningún usuario todavía.")
                    
            
            # Eliminar empresa (solo propietario) - CON CONFIRMACIÓN
            if "confirmar_eliminacion" not in st.session_state:
                st.session_state.confirmar_eliminacion = False
            
            if not st.session_state.confirmar_eliminacion:
                if st.button("❌ Eliminar Empresa", type="primary"):
                    st.session_state.confirmar_eliminacion = True
                    st.rerun()
            else:
                # Mostrar diálogo de confirmación
                st.error(f"⚠️ ¿ESTÁS SEGURO de eliminar '{empresa_seleccionada}'?")
                st.warning("🚨 Esta acción NO se puede deshacer. Se perderán todos los datos permanentemente.")
                
                col_confirm1, col_confirm2 = st.columns(2)
                with col_confirm1:
                    if st.button("✅ SÍ, Eliminar Definitivamente", type="primary", use_container_width=True):
                        if supabase:
                            try:
                                # Primero eliminar registros compartidos
                                supabase.table('empresas_compartidas').delete().eq('empresa_id', empresa_id).execute()
                                # Luego eliminar empresa
                                supabase.table('empresas').delete().eq('id', empresa_id).execute()
                                st.success(f"Empresa '{empresa_seleccionada}' eliminada.")
                                # Limpiar estado
                                st.session_state.confirmar_eliminacion = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al eliminar la empresa: {e}")
                
                with col_confirm2:
                    if st.button("❌ NO, Cancelar", type="secondary", use_container_width=True):
                        st.session_state.confirmar_eliminacion = False
                        st.info("Eliminación cancelada.")
                        st.rerun()
                        
        # Mensaje para no propietarios
        elif empresa_id and not es_propietario:
            st.divider()
            st.info("ℹ️ Solo el propietario puede compartir o eliminar esta empresa")
        
        # BOTÓN DE CERRAR SESIÓN (AL FINAL DEL SIDEBAR)
        st.divider()
        st.subheader("Sesión")
        
        # Mostrar usuario actual si existe
        if st.session_state.get("user"):
            st.caption(f"👤 {st.session_state.user.email}")
        
        if st.button("🚪 Cerrar Sesión", type="secondary", use_container_width=True):
            # Limpiar toda la sesión
            keys_to_delete = [k for k in st.session_state.keys()]
            for key in keys_to_delete:
                del st.session_state[key]
            st.success("Sesión cerrada correctamente")
            st.rerun()
                
    if not empresa_id:
        st.info("👈 Por favor, selecciona o crea una empresa en el menú lateral para comenzar.")
        st.stop()


    empresa_data = get_datos_empresa(empresa_id)
    if not empresa_data:
        st.error("No se pudieron cargar los datos de la empresa. Verifica tus permisos.")
        st.stop()

    # Verificar permisos usando la información ya obtenida en get_empresas
    es_propietario = empresa_data.get('propietario_id') == st.session_state.user.id

    # Si no es propietario, verificar si tiene acceso compartido
    if not es_propietario:
        try:
            res = supabase.table('empresas_compartidas').select('permiso').eq('empresa_id', empresa_id).eq('usuario_compartido_id', st.session_state.user.id).single().execute()
            if not res.data:
                st.error("No tienes permiso para ver esta empresa.")
                st.stop()
            permiso_usuario = res.data['permiso']
            es_editor = (permiso_usuario == 'editor')
        except:
            st.error("No tienes permiso para ver esta empresa.")
            st.stop()
    else:
        es_editor = False

    puede_editar = es_propietario or es_editor

    tab1, tab2, tab_est, tab3, tab4, tab5, tab6, tab_dash, tab7 = st.tabs([
        "1. Introducción", "2. Diagnóstico Situacional", "3. Estrategia", 
        "4. Planes", "5. CMI/Indicadores", "6. Semaforización", 
        "7. Operativización/Presupuesto", "8. Dashboard de Análisis", "9. Resumen y Conclusiones"
    ])
    
    # --- PESTAÑA 1: INTRODUCCION ---
    with tab1:
        st.header("Introduccion y Cultura Organizacional")
        
        with st.form("form_intro"):
            st.subheader("Datos Generales")
            nombre = st.text_input("Nombre de la Empresa", empresa_data.get('nombre', ''), disabled=not puede_editar)
            giro = st.text_input("Giro del Negocio", empresa_data.get('giro', ''), disabled=not puede_editar)
            
            # LOGO
            st.divider()
            st.subheader("Logo de la Empresa")
            
            logo_actual = empresa_data.get('logo')
            if logo_actual:
                try:
                    import base64
                    logo_bytes = base64.b64decode(logo_actual)
                    st.image(logo_bytes, width=150, caption="Logo guardado")
                except Exception as e:
                    st.info("No hay logo guardado")
            else:
                st.info("No hay logo guardado. Sube uno nuevo.")
            
            logo_file = st.file_uploader("Subir Logo", type=['png', 'jpg', 'jpeg'], disabled=not puede_editar)
            
            # CULTURA ORGANIZACIONAL
            st.divider()
            st.subheader("Cultura Organizacional")
            objetivo_plan = st.text_area("Objetivo del Plan", empresa_data.get('objetivo_plan', ''), disabled=not puede_editar)
            mision = st.text_area("Mision", empresa_data.get('mision', ''), disabled=not puede_editar)
            vision = st.text_area("Vision", empresa_data.get('vision', ''), disabled=not puede_editar)
            obj_gen = st.text_area("Objetivo General", empresa_data.get('obj_general', ''), disabled=not puede_editar)
            obj_esp = st.text_area("Objetivos Especificos", empresa_data.get('obj_especificos', ''), disabled=not puede_editar)
            politicas = st.text_area("Politicas", empresa_data.get('politicas', ''), disabled=not puede_editar)
            valores = st.text_area("Valores", empresa_data.get('valores', ''), disabled=not puede_editar)
            
            # ORGANIGRAMA (AL FINAL)
            st.divider()
            st.subheader("Organigrama")
            
            org_actual = empresa_data.get('organigrama')
            if org_actual:
                try:
                    import base64
                    org_bytes = base64.b64decode(org_actual)
                    st.image(org_bytes, width=600, caption="Organigrama guardado")
                except Exception as e:
                    st.info("No hay organigrama guardado")
            else:
                st.info("No hay organigrama. Sube uno.")
            
            org_file = st.file_uploader("Subir Organigrama", type=['png', 'jpg', 'jpeg'], disabled=not puede_editar)
            
            # BOTON GUARDAR
            submitted = st.form_submit_button("Guardar Todo", disabled=not puede_editar)
            
            if submitted:
                update_data = {
                    "nombre": nombre, 
                    "giro": giro, 
                    "objetivo_plan": objetivo_plan, 
                    "mision": mision, 
                    "vision": vision, 
                    "obj_general": obj_gen, 
                    "obj_especificos": obj_esp, 
                    "politicas": politicas, 
                    "valores": valores
                }
                
                # Logo nuevo
                if logo_file is not None:
                    try:
                        import base64
                        update_data['logo'] = base64.b64encode(logo_file.getvalue()).decode('utf-8')
                    except Exception as e:
                        st.error(f"Error logo: {e}")
                
                # Organigrama nuevo
                if org_file is not None:
                    try:
                        import base64
                        update_data['organigrama'] = base64.b64encode(org_file.getvalue()).decode('utf-8')
                    except Exception as e:
                        st.error(f"Error organigrama: {e}")
                
                # Guardar
                try:
                    supabase.table('empresas').update(update_data).eq('id', empresa_id).execute()
                    st.success("Guardado!")
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
            
            if st.button("🤖 Generar Estrategias con IA (3 por cuadrante = 12 estrategias)", disabled=not puede_editar, type="primary"):
                if df_foda_estrategia.empty:
                    st.error("Primero debes cargar los datos del FODA Cruzado en la pestaña anterior.")
                else:
                    with st.spinner("Generando 12 estrategias estratégicas (3 por cuadrante) con 5 actividades cada una..."):
                        # Obtener factores por cuadrante para contexto
                        contexto_foda = df_foda_estrategia.to_string()
                        
                        prompt_estrategias = (
                            "Basado en el siguiente análisis FODA Cruzado:\n"
                            f"{contexto_foda}\n\n"
                            "Genera exactamente 3 estrategias para cada uno de los 4 cuadrantes (FO, FA, DO, DA), total 12 estrategias.\n"
                            "Para cada estrategia proporciona:\n"
                            "1. Cuadrante (FO, FA, DO, o DA)\n"
                            "2. Estrategia: Descripción clara y específica de la estrategia\n"
                            "3. Importancia: Selecciona una de (Alta, Media Alta, Media Baja, Baja)\n"
                            "4. Actividades: Lista de EXACTAMENTE 5 actividades clave separadas por punto y coma (;) para implementar la estrategia\n"
                            "5. Plan Asignado: Selecciona uno de (Plan Administrativo, Plan Operativo, Plan Tecnológico, Plan Financiero, Plan de Monitoreo y control, Plan de Mejora, Plan de Contingencia)\n\n"
                            "Formato de salida EXACTO (una estrategia por línea):\n"
                            "CUADRANTE|ESTRATEGIA|IMPORTANCIA|ACTIVIDAD|PLAN_ASIGNADO\n\n"
                            "Ejemplo:\n"
                            "FO|Expandir mercado en nuevas regiones utilizando fortalezas tecnológicas|Alta|Investigar mercados potenciales;Adaptar producto a nuevas necesidades;Lanzar campaña marketing digital;Capacitar equipo de ventas;Establecer alianzas locales|Plan Operativo\n"
                            "FO|Alianza estratégica con proveedores clave|Media Alta|Identificar proveedores potenciales;Negociar contratos marco;Implementar integración de sistemas;Capacitar personal en nuevos procesos;Evaluar desempeño de proveedores|Plan Administrativo\n"
                            "FA|Programa de retención de clientes ante nueva competencia|Alta|Analizar tasa de churn actual;Crear programa fidelización;Capacitar equipo de servicio al cliente;Implementar encuestas satisfacción;Diseñar promociones exclusivas|Plan de Mejora\n\n"
                            "Genera exactamente 12 líneas (3 por cada cuadrante FO, FA, DO, DA). Cada estrategia debe tener EXACTAMENTE 5 actividades separadas por punto y coma (;). No uses encabezados."
                        )                        
                        resultado = generar_analisis(prompt_estrategias)
                        
                        # Parsear resultado
                        estrategias_list = []
                        lineas = [l.strip() for l in resultado.split('\n') if l.strip() and '|' in l]
                        
                        for linea in lineas[:12]:  # Máximo 12 estrategias
                            partes = linea.split('|')
                            if len(partes) >= 5:
                                # Asegurar que hay 5 actividades
                                actividades = partes[3].strip()
                                # Contar actividades separadas por ;
                                num_actividades = len([a for a in actividades.split(';') if a.strip()])
                                
                                estrategias_list.append({
                                    'empresa_id': empresa_id,
                                    'cuadrante': partes[0].strip().upper(),
                                    'estrategia': partes[1].strip(),
                                    'importancia': partes[2].strip(),
                                    'actividades': actividades,
                                    'plan_asignado': partes[4].strip()
                                })
                        
                        if estrategias_list:
                            try:
                                # Guardar en Supabase
                                supabase.table('estrategias_generadas').delete().eq('empresa_id', empresa_id).execute()
                                supabase.table('estrategias_generadas').insert(estrategias_list).execute()
                                
                                total_actividades = sum([len([a for a in est['actividades'].split(';') if a.strip()]) for est in estrategias_list])
                                st.success(f"✅ {len(estrategias_list)} estrategias generadas y guardadas exitosamente.")
                                st.info(f"📋 Total de actividades generadas: {total_actividades} (objetivo: 60 actividades)")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al guardar estrategias: {e}")
                        else:
                            st.error("No se pudieron parsear las estrategias generadas. Intenta nuevamente.")
        else:
            # Mostrar estrategias existentes en editor
            st.success(f"Se encontraron {len(df_estrategias)} estrategias generadas.")
            
            # Calcular total de actividades
            total_actividades = 0
            for _, est in df_estrategias.iterrows():
                acts = str(est.get('actividades', ''))
                total_actividades += len([a for a in acts.split(';') if a.strip()])
            
            st.info(f"📋 Total de actividades: {total_actividades} (objetivo: 60 actividades = 12 estrategias × 5 actividades)")
            
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
                    "actividades": st.column_config.TextColumn("Actividades (separar con ;)", width="large")
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
        st.header("📋 Planes Estratégicos Funcionales")
        
        # Importar re al inicio de la pestaña para evitar UnboundLocalError
        import re
        
        # Obtener datos necesarios para contextualizar
        df_foda_temp = get_datos_tabla('foda_cruzado', empresa_id)
        analisis_df_temp, _, estrategia_principal, puntajes_foda = analizar_foda(df_foda_temp)
        df_estrategias_planes = get_datos_tabla('estrategias_generadas', empresa_id)
        empresa_datos = get_datos_empresa(empresa_id)
        
        # Calcular puntaje PEST para contexto
        df_pest_temp = get_datos_tabla('matrices', empresa_id, tipo_matriz_filter='PEST')
        pest_total = df_pest_temp['valor_ponderado'].sum() if not df_pest_temp.empty else 0
        
        # Determinar contexto estratégico
        es_ofensiva = "Ofensiva" in str(estrategia_principal)
        es_adaptativa = "Adaptativa" in str(estrategia_principal)
        es_defensiva = "Defensiva" in str(estrategia_principal)
        es_supervivencia = "Supervivencia" in str(estrategia_principal)
        
        contexto_empresa = {
            'nombre': empresa_datos.get('nombre', 'La empresa'),
            'giro': empresa_datos.get('giro', 'su sector'),
            'estrategia_principal': estrategia_principal or 'No definida',
            'pest_total': pest_total,
            'postura': 'crecimiento' if (es_ofensiva or es_adaptativa) else 'consolidación/defensa'
        }
        
        st.info(f"""
        **Contexto Estratégico Detectado:**
        - Estrategia Principal: **{contexto_empresa['estrategia_principal']}**
        - Postura: **{contexto_empresa['postura'].upper()}**
        - Entorno PEST: **{'Favorable' if pest_total > 2.5 else 'Desafiante'}** ({pest_total:.2f})
        """)
        
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("🤖 Generar 7 Planes Funcionales Profesionales", disabled=not puede_editar, type="primary"):
                with st.spinner("Elaborando planes estratégicos detallados con IA. Esto puede tomar 1-2 minutos..."):
                    
                    # Preparar contexto de estrategias generadas
                    contexto_estrategias = ""
                    if not df_estrategias_planes.empty:
                        for idx, row in df_estrategias_planes.iterrows():
                            contexto_estrategias += f"\n{idx+1}. [{row['cuadrante']}] {row['estrategia']} -> {row['plan_asignado']}"
                    
                    # Construir prompt como lista de líneas para evitar problemas con triple comillas
                    lineas_prompt = [
                        "Actúa como un consultor senior de estrategia empresarial con 20 años de experiencia.",
                        f"Elabora 7 PLANES FUNCIONALES ESTRATÉGICOS de alto nivel para {contexto_empresa['nombre']},",
                        f"empresa del sector {contexto_empresa['giro']}.",
                        "",
                        "CONTEXTO ESTRATÉGICO:",
                        f"- Estrategia principal FODA: {contexto_empresa['estrategia_principal']}",
                        f"- Postura estratégica: {contexto_empresa['postura']}",
                        f"- Entorno PEST score: {contexto_empresa['pest_total']:.2f}",
                        f"- Estrategias generadas: {contexto_estrategias if contexto_estrategias else 'No hay estrategias previas'}",
                        "",
                        "ESTRUCTURA REQUERIDA PARA CADA PLAN (7 planes totales):",
                        "",
                        "1. PLAN ADMINISTRATIVO",
                        "2. PLAN OPERATIVO",
                        "3. PLAN TECNOLÓGICO",
                        "4. PLAN FINANCIERO",
                        "5. PLAN DE MONITOREO Y CONTROL",
                        "6. PLAN DE MEJORA",
                        "7. PLAN DE CONTINGENCIA",
                        "",
                        "PARA CADA PLAN DEBES INCLUIR EXACTAMENTE:",
                        "",
                        "=== [NOMBRE DEL PLAN] ===",
                        "",
                        "1. FUNDAMENTO ESTRATÉGICO",
                        "[Explicación de por qué este plan es crítico para la empresa en su contexto actual, 3-4 párrafos profundos]",
                        "",
                        "2. OBJETIVO GENERAL DEL PLAN",
                        "[Objetivo SMART específico]",
                        "",
                        "3. OBJETIVOS ESPECÍFICOS (mínimo 3)",
                        "- Objetivo 1",
                        "- Objetivo 2",
                        "- Objetivo 3",
                        "",
                        "4. ESTRATEGIAS DE IMPLEMENTACIÓN (mínimo 4 estrategias concretas)",
                        "A. [Nombre estrategia 1]",
                        "   - Descripción detallada",
                        "   - Acciones clave",
                        "B. [Nombre estrategia 2]",
                        "   - Descripción detallada",
                        "   - Acciones clave",
                        "[C continuar...]",
                        "",
                        "5. KPIs Y METAS (mínimo 5 KPIs por plan)",
                        "- KPI 1: [Nombre] | Meta: [X] | Frecuencia: [mensual/trimestral]",
                        "- KPI 2: [Nombre] | Meta: [X] | Frecuencia: [mensual/trimestral]",
                        "[Continuar...]",
                        "",
                        "6. RECURSOS REQUERIDOS",
                        "- Humanos: [Detalle]",
                        "- Financieros: [Presupuesto estimado]",
                        "- Tecnológicos: [Infraestructura]",
                        "- Temporales: [Cronograma]",
                        "",
                        "7. RESPONSABLES Y GOBIERNO",
                        "- Responsable principal: [Rol]",
                        "- Comité de seguimiento: [Miembros]",
                        "- Frecuencia de revisión: [Semanal/Mensual]",
                        "",
                        "8. RIESGOS Y MITIGACIÓN",
                        "- Riesgo 1: [Descripción] | Mitigación: [Acción]",
                        "- Riesgo 2: [Descripción] | Mitigación: [Acción]",
                        "",
                        "9. ALINEACIÓN CON ESTRATEGIA FODA",
                        "[Cómo este plan contribuye específicamente a FO, FA, DO o DA]",
                        "",
                        "REQUISITOS DE CALIDAD:",
                        "- Lenguaje ejecutivo y profesional",
                        "- Contenido específico, no genérico",
                        "- Cada plan debe tener 800-1200 palabras mínimo",
                        "- Los KPIs deben ser cuantificables y realistas",
                        "- Las estrategias deben ser accionables",
                        "- Considerar el contexto PEST y FODA proporcionado",
                        "- NO usar frases vacías como 'mejorar procesos' sin especificar cómo",
                        "",
                        "GENERA LOS 7 PLANES COMPLETOS AHORA:"
                    ]
                    
                    prompt_planes_maestros = "\n".join(lineas_prompt)
                    
                    planes_generados = generar_analisis(prompt_planes_maestros)
                    st.session_state['planes_maestros_generados'] = planes_generados
                    st.success("✅ Planes funcionales generados con éxito")
                    st.rerun()
        
        with col2:
            st.caption("""
            **Los 7 Planes Funcionales:**
            1. 📊 Administrativo
            2. ⚙️ Operativo
            3. 💻 Tecnológico
            4. 💰 Financiero
            5. 📈 Monitoreo y Control
            6. 🚀 Mejora
            7. 🛡️ Contingencia
            """)
        
        # Mostrar y editar planes
        planes_actuales = st.session_state.get('planes_maestros_generados', empresa_data.get('analisis_operativo', ''))
        
        if planes_actuales:
            st.divider()
            st.subheader("📄 Planes Estratégicos Funcionales - Documento Maestro")
            
            # Mostrar en tabs los 7 planes si se detectan en el texto
            planes_str = str(planes_actuales)
            if "===" in planes_str:
                # Intentar dividir por planes
                try:
                    # Patrón más flexible para detectar planes
                    patron_planes = r'={2,}\s*(PLAN\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+)*)\s*={2,}'
                    planes_secciones = re.split(patron_planes, planes_str, flags=re.IGNORECASE)
                    
                    if len(planes_secciones) > 1:
                        # Crear tabs para cada plan detectado
                        nombres_planes = []
                        contenidos_planes = []
                        
                        for i in range(1, len(planes_secciones), 2):
                            if i < len(planes_secciones):
                                nombre = planes_secciones[i].strip()
                                contenido = planes_secciones[i+1] if i+1 < len(planes_secciones) else ""
                                # Limpiar nombre
                                nombre_limpio = re.sub(r'[^\w\s-]', '', nombre).strip()
                                if nombre_limpio and len(nombre_limpio) < 60:
                                    nombres_planes.append(nombre_limpio)
                                    contenidos_planes.append(contenido)
                        
                        if nombres_planes:
                            tabs_planes = st.tabs(nombres_planes)
                            for tab, nombre, contenido in zip(tabs_planes, nombres_planes, contenidos_planes):
                                with tab:
                                    st.markdown(f"### {nombre}")
                                    st.markdown(contenido)
                                    
                                    # Botón para copiar contenido específico
                                    key_segura = re.sub(r'[^\w]', '_', nombre)[:30]
                                    if st.button(f"📋 Copiar contenido", key=f"copy_{key_segura}"):
                                        st.code(contenido, language='markdown')
                        else:
                            st.info("Se generaron los planes pero no se pudieron separar automáticamente. Revisa el documento completo abajo.")
                    else:
                        st.info("No se detectaron separadores de planes. Mostrando documento completo.")
                        
                except Exception as e:
                    st.warning(f"No se pudieron dividir los planes automáticamente: {e}")
                    st.info("Mostrando documento completo para edición manual.")
            
            # Editor completo
            with st.form("form_planes_maestros"):
                st.write("**Editar Documento Completo de Planes:**")
                planes_editados = st.text_area(
                    "Planes Estratégicos Funcionales", 
                    value=planes_str, 
                    height=800, 
                    disabled=not puede_editar,
                    help="Edite los 7 planes funcionales. Use === NOMBRE DEL PLAN === para separar secciones."
                )
                
                col_save, col_regen = st.columns(2)
                with col_save:
                    submitted_save = st.form_submit_button("💾 Guardar Planes Maestros", disabled=not puede_editar)
                    if submitted_save:
                        guardar_analisis_db(empresa_id, 'operativo', planes_editados)
                        st.session_state['planes_maestros_generados'] = planes_editados
                
                with col_regen:
                    submitted_regen = st.form_submit_button("🔄 Regenerar Todo", disabled=not puede_editar)
                    if submitted_regen:
                        if 'planes_maestros_generados' in st.session_state:
                            del st.session_state['planes_maestros_generados']
                        st.rerun()
            
            # Vista previa estructurada
            with st.expander("📊 Ver Resumen Estructurado de Planes"):
                try:
                    # Extraer KPIs mencionados
                    kpis_encontrados = re.findall(r'KPI\s*\d*[:.-]\s*([^\n|]+)', planes_str, re.IGNORECASE)
                    if kpis_encontrados:
                        st.write("**KPIs Detectados (primeros 20):**")
                        for i, kpi in enumerate(kpis_encontrados[:20], 1):
                            texto_kpi = kpi.strip()[:100]
                            st.write(f"{i}. {texto_kpi}...")
                    
                    # Contar estrategias
                    estrategias_count = len(re.findall(r'^[A-Z][.-]\s+', planes_str, re.MULTILINE))
                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        st.metric("Estrategias Detectadas", estrategias_count)
                    
                    # Contar planes
                    planes_count = len(re.findall(r'={2,}\s*PLAN', planes_str, re.IGNORECASE))
                    with col_m2:
                        st.metric("Planes Detectados", planes_count if planes_count > 0 else "No detectado")
                    
                    # Contar objetivos
                    objetivos_count = len(re.findall(r'^\s*[-•]\s*Objetivo', planes_str, re.MULTILINE | re.IGNORECASE))
                    with col_m3:
                        st.metric("Objetivos Detectados", objetivos_count)
                        
                except Exception as e:
                    st.error(f"Error al analizar el contenido: {e}")
        
        else:
            st.info("""
            👆 **Haz clic en "Generar 7 Planes Funcionales Profesionales"** para crear:
            
            **Plan Administrativo**: Estructura organizacional, gestión del talento, cultura corporativa
            
            **Plan Operativo**: Procesos productivos, cadena de suministro, calidad, logística
            
            **Plan Tecnológico**: Infraestructura digital, transformación digital, ciberseguridad, innovación
            
            **Plan Financiero**: Presupuesto, flujo de caja, inversión, rentabilidad, control financiero
            
            **Plan de Monitoreo y Control**: Dashboards, indicadores, auditorías, seguimiento estratégico
            
            **Plan de Mejora**: Metodologías (Kaizen, Six Sigma), optimización continua, capacitación
            
            **Plan de Contingencia**: Gestión de riesgos, continuidad del negocio, planes de respuesta
            """)
        
        # Mostrar último guardado
        mostrar_ultimo_analisis_guardado(empresa_data, 'operativo')        
        
    # --- PESTAÑA 5: CMI/INDICADORES ---
    with tab4:
        st.header("CMI / Indicadores")
        df_estrategias_cmi = get_datos_tabla('estrategias_generadas', empresa_id)
        
        if not df_estrategias_cmi.empty:
            # Verificar si ya existe un CMI guardado
            cmi_guardado = empresa_data.get('analisis_cmi', '')
            df_cmi_actual = pd.DataFrame()
            
            # Si hay CMI guardado, convertirlo a DataFrame
            if cmi_guardado and '|' in str(cmi_guardado):
                try:
                    df_cmi_actual = pd.read_csv(io.StringIO(cmi_guardado), sep="|")
                    st.success("📋 CMI cargado desde datos guardados")
                except Exception as e:
                    st.warning(f"Error al cargar CMI guardado: {e}")
                    df_cmi_actual = pd.DataFrame()
            
            # Botón para regenerar con IA
            col1, col2 = st.columns([1, 2])
            with col1:
                if st.button("🤖 Regenerar CMI con IA", disabled=not puede_editar, type="primary"):
                    with st.spinner("Generando Cuadro de Mando Integral..."):
                        df_cmi_generado = generar_cuadro_de_mando_ia(df_estrategias_cmi)
                        if not df_cmi_generado.empty:
                            st.session_state['cmi_df_temp'] = df_cmi_generado
                            st.success("CMI generado por IA. Edita la tabla y guarda los cambios.")
                            st.rerun()
                        else:
                            st.error("No se pudo generar el CMI. Verifica las estrategias.")
            
            with col2:
                if 'cmi_df_temp' in st.session_state:
                    st.info("💡 Estás viendo el CMI generado por IA. Edita los valores y guarda.")
                elif not df_cmi_actual.empty:
                    st.info("💡 Puedes editar directamente la tabla y guardar los cambios.")
                else:
                    st.info("👆 Genera el CMI con IA para comenzar")
            
            # Determinar qué DataFrame mostrar (temporal de IA o guardado)
            if 'cmi_df_temp' in st.session_state:
                df_cmi_editar = st.session_state['cmi_df_temp'].copy()
            elif not df_cmi_actual.empty:
                df_cmi_editar = df_cmi_actual.copy()
            else:
                df_cmi_editar = pd.DataFrame()
            
            # Mostrar editor de tabla si hay datos
            if not df_cmi_editar.empty:
                st.divider()
                st.subheader("📊 Cuadro de Mando Integral - Editable")
                
                # Definir columnas esperadas
                columnas_cmi = ['Estrategia', 'Perspectiva', 'KPIs', 'Formulas', 'Frecuencia', 'LI', 'LC', 'LS']
                
                # Asegurar que todas las columnas existan
                for col in columnas_cmi:
                    if col not in df_cmi_editar.columns:
                        df_cmi_editar[col] = ''
                
                # Reordenar columnas
                df_cmi_editar = df_cmi_editar[columnas_cmi]
                
                # Editor de datos
                edited_cmi = st.data_editor(
                    df_cmi_editar,
                    num_rows="dynamic",
                    key="editor_cmi",
                    use_container_width=True,
                    disabled=not puede_editar,
                    column_config={
                        'Estrategia': st.column_config.TextColumn("Estrategia", width="large"),
                        'Perspectiva': st.column_config.SelectboxColumn(
                            "Perspectiva", 
                            options=['Financiera', 'Cliente', 'Procesos', 'Aprendizaje y Control'],
                            width="medium"
                        ),
                        'KPIs': st.column_config.TextColumn("KPIs", width="large"),
                        'Formulas': st.column_config.TextColumn("Fórmulas", width="medium"),
                        'Frecuencia': st.column_config.SelectboxColumn(
                            "Frecuencia",
                            options=['Diaria', 'Semanal', 'Mensual', 'Trimestral', 'Semestral', 'Anual'],
                            width="small"
                        ),
                        'LI': st.column_config.TextColumn("Límite Inferior", width="small"),
                        'LC': st.column_config.TextColumn("Límite Control", width="small"),
                        'LS': st.column_config.TextColumn("Límite Superior", width="small")
                    },
                    hide_index=True
                )
                
                # Botones de acción
                col_guardar, col_cancelar, col_nuevo = st.columns(3)
                
                with col_guardar:
                    if st.button("💾 Guardar CMI", type="primary", disabled=not puede_editar):
                        try:
                            # Validar que no esté vacío
                            if edited_cmi.empty:
                                st.error("No se puede guardar un CMI vacío")
                            else:
                                # Convertir a formato pipe-separated para guardar
                                cmi_texto = edited_cmi.to_csv(sep="|", index=False)
                                
                                # Guardar en base de datos
                                guardar_analisis_db(empresa_id, 'cmi', cmi_texto)
                                
                                # Limpiar temporal
                                if 'cmi_df_temp' in st.session_state:
                                    del st.session_state['cmi_df_temp']
                                
                                st.success("✅ CMI guardado correctamente.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar CMI: {e}")
                
                with col_cancelar:
                    if st.button("❌ Cancelar", disabled=not puede_editar):
                        if 'cmi_df_temp' in st.session_state:
                            del st.session_state['cmi_df_temp']
                        st.rerun()
                
                with col_nuevo:
                    if st.button("➕ Agregar Fila", disabled=not puede_editar):
                        nueva_fila = pd.DataFrame([{
                            'Estrategia': '',
                            'Perspectiva': 'Procesos',
                            'KPIs': '',
                            'Formulas': '',
                            'Frecuencia': 'Mensual',
                            'LI': '',
                            'LC': '',
                            'LS': ''
                        }])
                        # Actualizar el temporal con la nueva fila
                        if 'cmi_df_temp' in st.session_state:
                            st.session_state['cmi_df_temp'] = pd.concat([st.session_state['cmi_df_temp'], nueva_fila], ignore_index=True)
                        else:
                            st.session_state['cmi_df_temp'] = pd.concat([edited_cmi, nueva_fila], ignore_index=True)
                        st.rerun()
                
                # Vista previa de gráfico o resumen
                st.divider()
                with st.expander("📈 Ver Resumen del CMI"):
                    # Contar KPIs por perspectiva
                    if 'Perspectiva' in edited_cmi.columns and not edited_cmi.empty:
                        resumen_perspectiva = edited_cmi.groupby('Perspectiva').agg({
                            'KPIs': 'count',
                            'Estrategia': 'nunique'
                        }).reset_index()
                        resumen_perspectiva.columns = ['Perspectiva', 'N° KPIs', 'N° Estrategias']
                        
                        col_res1, col_res2 = st.columns(2)
                        with col_res1:
                            st.dataframe(resumen_perspectiva, use_container_width=True, hide_index=True)
                        with col_res2:
                            # Gráfico simple de distribución
                            if not resumen_perspectiva.empty:
                                fig = px.pie(
                                    resumen_perspectiva, 
                                    names='Perspectiva', 
                                    values='N° KPIs',
                                    title='Distribución de KPIs por Perspectiva',
                                    hole=0.4
                                )
                                st.plotly_chart(fig, use_container_width=True)
            
            else:
                st.info("👆 Haz clic en 'Regenerar CMI con IA' para generar el cuadro automáticamente basado en tus estrategias.")
        
        else:
            st.warning("No hay estrategias disponibles para generar el CMI. Genera estrategias primero en la pestaña anterior.")    

    # --- PESTAÑA 5: ANÁLISIS DE SEMAFORIZACIÓN ESTRATÉGICA (NUEVA) ---
    with tab5:
        st.header("🚦 Análisis de Semaforización Estratégica")
        st.markdown("""
        *Análisis inteligente del estado de tus estrategias basado en el CMI, FODA y contexto empresarial*
        """)
        
        import re
        
        # Obtener todos los datos necesarios automáticamente
        df_cmi = get_datos_tabla('estrategias_generadas', empresa_id)
        df_foda = get_datos_tabla('foda_cruzado', empresa_id)
        df_pest = get_datos_tabla('matrices', empresa_id, tipo_matriz_filter='PEST')
        empresa_info = get_datos_empresa(empresa_id)
        
        # Verificar si hay datos suficientes
        if df_cmi.empty:
            st.warning("⚠️ No hay estrategias ni CMI configurado. Genera primero el CMI en la pestaña anterior.")
            st.stop()
        
        # Calcular métricas de contexto automáticamente
        analisis_foda_df, resumen_foda, estrategia_principal, puntajes_foda = analizar_foda(df_foda)
        pest_total = df_pest['valor_ponderado'].sum() if not df_pest.empty else 0
        
        # Contexto completo para la IA
        contexto_empresarial = {
            'nombre': empresa_info.get('nombre', 'La empresa'),
            'giro': empresa_info.get('giro', 'No especificado'),
            'estrategia_foda': estrategia_principal or 'No definida',
            'pest_score': pest_total,
            'num_estrategias': len(df_cmi),
            'postura': 'ofensiva' if 'Ofensiva' in str(estrategia_principal) else 
                      'defensiva' if 'Defensiva' in str(estrategia_principal) else 
                      'mixta'
        }
        
        # Mostrar contexto detectado
        with st.expander("📋 Contexto Estratégico Detectado (Automático)"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Estrategia Principal", contexto_empresarial['estrategia_foda'])
            with col2:
                st.metric("Entorno PEST", f"{contexto_empresarial['pest_score']:.2f}")
            with col3:
                st.metric("Estrategias a Analizar", contexto_empresarial['num_estrategias'])
        
        st.divider()
        
        # Botón para generar análisis completo con IA
        if st.button("🤖 Generar Análisis Completo de Semaforización", type="primary"):
            with st.spinner("Analizando todas las estrategias con IA... Esto puede tomar 1-2 minutos"):
                
                resultados_semaforo = []
                
                # Procesar cada estrategia del CMI
                for idx, estrategia in df_cmi.iterrows():
                    
                    # Preparar prompt enriquecido con TODO el contexto disponible
                    prompt_analisis = f"""Actúa como un Director de Planeación Estratégica senior analizando el desempeño de una estrategia específica.

CONTEXTO EMPRESARIAL COMPLETO:
- Empresa: {contexto_empresarial['nombre']} ({contexto_empresarial['giro']})
- Postura Estratégica General: {contexto_empresarial['estrategia_foda']}
- Entorno PEST: {'Favorable' if contexto_empresarial['pest_score'] > 2.5 else 'Desafiante'} ({contexto_empresarial['pest_score']:.2f})
- Postura: {contexto_empresarial['postura']}

ESTRATEGIA A ANALIZAR:
- Nombre: {estrategia['estrategia']}
- Cuadrante FODA: {estrategia['cuadrante']}
- Importancia: {estrategia['importancia']}
- Plan Funcional: {estrategia['plan_asignado']}
- Actividades Clave: {estrategia['actividades']}

INSTRUCCIÓN:
Basándote ÚNICAMENTE en la información anterior (sin pedir datos adicionales), realiza un análisis experto que determine:

1. COLOR DEL SEMÁFORO (🔴🟡🟢):
   - Analiza la coherencia entre la importancia de la estrategia, su cuadrante FODA y el plan asignado
   - Considera: ¿Es una estrategia crítica para la postura {contexto_empresarial['postura']} de la empresa?
   - Evalúa: ¿Las actividades propuestas son suficientes y coherentes?
   - Determina: Dado el contexto PEST, ¿esta estrategia está bien posicionada?

2. JUSTIFICACIÓN DEL COLOR (máximo 150 palabras):
   Explica POR QUÉ cae en ese color considerando:
   - Alineación con la estrategia FODA principal
   - Factores PEST que afectan específicamente esta estrategia
   - Coherencia entre importancia y recursos asignados (plan funcional)
   - Viabilidad de las actividades propuestas
   - Riesgos implícitos en el cuadrante (FO=explotar, FA=defender, DO=reforzar, DA=sobrevivir)

3. DIAGNÓSTICO PROFUNDO:
   - Fortalezas de esta estrategia específica
   - Debilidades o riesgos detectados
   - Oportunidades de mejora inmediata

4. ACCIONES RECOMENDADAS:
   - Acción inmediata (esta semana)
   - Acción corto plazo (este mes)
   - Acción de seguimiento (trimestral)

5. IMPACTO ESTRATÉGICO:
   - ¿Qué pasa si esta estrategia falla?
   - ¿Qué otras estrategias se ven afectadas?
   - ¿Es crítica para el éxito del plan {estrategia['plan_asignado']}?

FORMATO DE RESPUESTA OBLIGATORIO:
COLOR: [🔴 ROJO / 🟡 AMARILLO / 🟢 VERDE]

JUSTIFICACIÓN:
[Texto explicativo coherente y específico]

DIAGNÓSTICO:
- Fortalezas: [lista]
- Debilidades: [lista]
- Oportunidades: [lista]

ACCIONES:
- Inmediata: [acción específica]
- Corto plazo: [acción específica]
- Seguimiento: [acción específica]

IMPACTO: [Alto/Medio/Bajo] - [explicación breve]

Genera el análisis ahora:"""

                    # Llamar a la IA
                    respuesta_ia = generar_analisis(prompt_analisis)
                    
                    # Parsear respuesta
                    color_detectado = '🟡'  # default
                    if 'COLOR:' in respuesta_ia or '🔴' in respuesta_ia or '🟢' in respuesta_ia or '🟡' in respuesta_ia:
                        if '🔴' in respuesta_ia or 'ROJO' in respuesta_ia.upper():
                            color_detectado = '🔴'
                        elif '🟢' in respuesta_ia or 'VERDE' in respuesta_ia.upper():
                            color_detectado = '🟢'
                        else:
                            color_detectado = '🟡'
                    
                    resultados_semaforo.append({
                        'estrategia_id': estrategia.get('id', idx),
                        'cuadrante': estrategia['cuadrante'],
                        'estrategia_nombre': estrategia['estrategia'],
                        'plan_asignado': estrategia['plan_asignado'],
                        'importancia': estrategia['importancia'],
                        'color': color_detectado,
                        'analisis_completo': respuesta_ia
                    })
                
                # Guardar en session state
                st.session_state['resultados_semaforo'] = resultados_semaforo
                st.success(f"✅ Análisis completado para {len(resultados_semaforo)} estrategias")
                st.rerun()
        
        # Mostrar resultados si existen
        if 'resultados_semaforo' in st.session_state:
            resultados = st.session_state['resultados_semaforo']
            
            # Dashboard resumen
            st.subheader("📊 Dashboard de Semaforización")
            
            conteo_colores = {'🔴': 0, '🟡': 0, '🟢': 0}
            for r in resultados:
                conteo_colores[r['color']] = conteo_colores.get(r['color'], 0) + 1
            
            total = len(resultados)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🟢 Óptimas", f"{conteo_colores['🟢']} ({conteo_colores['🟢']/total*100:.0f}%)")
            with col2:
                st.metric("🟡 Atención", f"{conteo_colores['🟡']} ({conteo_colores['🟡']/total*100:.0f}%)")
            with col3:
                st.metric("🔴 Críticas", f"{conteo_colores['🔴']} ({conteo_colores['🔴']/total*100:.0f}%)")
            with col4:
                riesgo = "ALTO" if conteo_colores['🔴'] > total*0.3 else "MEDIO" if conteo_colores['🔴'] > total*0.1 else "BAJO"
                st.metric("Nivel de Riesgo", riesgo)
            
            # Gráfico de distribución
            fig_colores = go.Figure(data=[go.Pie(
                labels=['Óptimas', 'Atención', 'Críticas'],
                values=[conteo_colores['🟢'], conteo_colores['🟡'], conteo_colores['🔴']],
                marker_colors=['#2ecc71', '#f1c40f', '#e74c3c'],
                hole=0.4
            )])
            fig_colores.update_layout(title="Distribución de Estrategias por Estado")
            st.plotly_chart(fig_colores, use_container_width=True)
            
            st.divider()
            
            # Detalle por estrategia
            st.subheader("📋 Análisis Detallado por Estrategia")
            
            # Filtros
            col_filtro1, col_filtro2 = st.columns(2)
            with col_filtro1:
                filtro_color = st.multiselect("Filtrar por color", ['🔴', '🟡', '🟢'], default=['🔴', '🟡', '🟢'])
            with col_filtro2:
                filtro_plan = st.multiselect("Filtrar por plan", 
                    df_cmi['plan_asignado'].unique().tolist() if not df_cmi.empty else [],
                    default=df_cmi['plan_asignado'].unique().tolist() if not df_cmi.empty else [])
            
            # Mostrar estrategias filtradas
            for resultado in resultados:
                if resultado['color'] not in filtro_color:
                    continue
                if resultado['plan_asignado'] not in filtro_plan:
                    continue
                
                with st.container():
                    # Encabezado con color
                    color_bg = {'🔴': '#ffebee', '🟡': '#fffde7', '🟢': '#e8f5e9'}[resultado['color']]
                    
                    st.markdown(f"""
                    <div style='background-color: {color_bg}; padding: 15px; border-radius: 10px; border-left: 5px solid {"#e74c3c" if resultado["color"]=="🔴" else "#f1c40f" if resultado["color"]=="🟡" else "#2ecc71"}; margin-bottom: 10px;'>
                        <h4>{resultado['color']} {resultado['cuadrante']} | {resultado['estrategia_nombre'][:60]}...</h4>
                        <p><strong>Plan:</strong> {resultado['plan_asignado']} | <strong>Importancia:</strong> {resultado['importancia']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander("Ver análisis completo de IA"):
                        st.markdown(resultado['analisis_completo'])
                        
                        # Botón para regenerar análisis específico
                        if st.button("🔄 Regenerar análisis", key=f"regen_{resultado['estrategia_id']}"):
                            # Eliminar este resultado específico y regenerar
                            st.session_state['regenerar_estrategia'] = resultado['estrategia_id']
                            st.rerun()
                    
                    st.divider()
            
            # Análisis ejecutivo general
            with st.expander("📄 Ver Análisis Ejecutivo General"):
                prompt_resumen = f"""Como Director Estratégico, genera un resumen ejecutivo de máximo 400 palabras basado en este análisis de semaforización:

DISTRIBUCIÓN DE ESTRATEGIAS:
- 🟢 Óptimas: {conteo_colores['🟢']} de {total}
- 🟡 Atención: {conteo_colores['🟡']} de {total}  
- 🔴 Críticas: {conteo_colores['🔴']} de {total}

CONTEXTO: {contexto_empresarial['nombre']} con postura {contexto_empresarial['postura']}

Incluye:
1. Diagnóstico general del portafolio de estrategias
2. Patrones detectados (¿algún plan funcional con problemas?)
3. Prioridades de acción inmediatas
4. Recomendación estratégica final

Lenguaje ejecutivo y directo."""
                
                if st.button("📊 Generar Resumen Ejecutivo con IA"):
                    with st.spinner("Generando..."):
                        resumen_ejecutivo = generar_analisis(prompt_resumen)
                        st.markdown("### 📋 Análisis Generado:")
                        st.info(resumen_ejecutivo)
                        
                        # Botón para guardar en BD
                        if st.button("💾 Guardar Resumen en Empresa"):
                            try:
                                supabase.table('empresas').update({
                                    'analisis_semaforo_resumen': resumen_ejecutivo
                                }).eq('id', empresa_id).execute()
                                st.success("Resumen guardado")
                            except Exception as e:
                                st.error(f"Error al guardar: {e}")
        
        else:
            # Vista previa/informativa antes de generar
            st.info("""
            ### 🎯 ¿Qué analizará la IA automáticamente?
            
            **Sin que tengas que ingresar nada más**, el sistema evaluará cada estrategia considerando:
            
            1. **🎯 Alineación FODA**: ¿La estrategia apoya la postura estratégica general?
            
            2. **🌍 Contexto PEST**: ¿El entorno externo favorece o dificulta esta estrategia?
            
            3. **⚖️ Coherencia**: ¿Hay coherencia entre la importancia declarada y el plan asignado?
            
            4. **📋 Viabilidad**: ¿Las actividades propuestas son suficientes y realistas?
            
            5. **⚠️ Riesgos implícitos**: Cada cuadrante FODA tiene riesgos característicos
            
            ### 📊 Output del análisis:
            - **Color del semáforo** para cada estrategia
            - **Justificación detallada** del por qué ese color
            - **Diagnóstico** de fortalezas/debilidades
            - **Acciones recomendadas** inmediatas
            - **Impacto estratégico** si falla
            
            Haz clic en **"Generar Análisis Completo"** arriba para comenzar.
            """)
            
            # Mostrar preview de estrategias a analizar
            if not df_cmi.empty:
                st.subheader("Estrategias que se analizarán:")
                preview_df = df_cmi[['cuadrante', 'estrategia', 'plan_asignado', 'importancia']].copy()
                preview_df.columns = ['Cuadrante', 'Estrategia', 'Plan', 'Importancia']
                st.dataframe(preview_df, use_container_width=True, hide_index=True)
    
    # --- PESTAÑA 6: OPERATIVIZACIÓN/PRESUPUESTO ---
    with tab6:
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

    
    # --- PESTAÑA DASHBOARD: BUSINESS INTELLIGENCE INTEGRADO ---
    with tab_dash:
        st.header("📊 Dashboard Ejecutivo - Business Intelligence")
        st.markdown("*Análisis interactivo tipo Power BI con filtros dinámicos y visualizaciones en tiempo real*")
        
        # ============================================================
        # 1. CARGA DE TODOS LOS DATOS DISPONIBLES
        # ============================================================
        
        @st.cache_data(ttl=300)
        def cargar_todos_los_datos(empresa_id):
            datos = {}
            datos['empresa'] = get_datos_empresa(empresa_id)
            datos['estrategias'] = get_datos_tabla('estrategias_generadas', empresa_id)
            datos['foda'] = get_datos_tabla('foda_cruzado', empresa_id)
            datos['pest'] = get_datos_tabla('matrices', empresa_id, tipo_matriz_filter='PEST')
            datos['operativizacion'] = get_datos_tabla('operativizacion', empresa_id)
            datos['pg'] = get_datos_tabla('perdida_ganancia', empresa_id)
            datos['proyeccion'] = get_datos_tabla('proyeccion_financiera', empresa_id)
            datos['cmi'] = get_datos_tabla('estrategias_generadas', empresa_id)
            return datos
        
        # Verificar que empresa_id existe
        if not empresa_id:
            st.error("No se ha seleccionado una empresa")
            st.stop()
            
        datos = cargar_todos_los_datos(empresa_id)
        
        # ============================================================
        # 2. PANEL DE FILTROS GLOBALES (Tipo Power BI)
        # ============================================================
        
        st.subheader("🎛️ Filtros Globales")
        
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        
        with col_f1:
            # Filtro por Cuadrante FODA
            if not datos['estrategias'].empty and 'cuadrante' in datos['estrategias'].columns:
                cuadrantes = ['Todos'] + datos['estrategias']['cuadrante'].unique().tolist()
            else:
                cuadrantes = ['Todos']
            filtro_cuadrante = st.selectbox("📍 Cuadrante FODA", cuadrantes, key="dash_cuadrante")
        
        with col_f2:
            # Filtro por Plan Funcional
            if not datos['estrategias'].empty and 'plan_asignado' in datos['estrategias'].columns:
                planes = ['Todos'] + datos['estrategias']['plan_asignado'].unique().tolist()
            else:
                planes = ['Todos']
            filtro_plan = st.selectbox("📋 Plan Funcional", planes, key="dash_plan")
        
        with col_f3:
            # Filtro por Importancia
            if not datos['estrategias'].empty and 'importancia' in datos['estrategias'].columns:
                importancias = ['Todas'] + datos['estrategias']['importancia'].unique().tolist()
            else:
                importancias = ['Todas']
            filtro_importancia = st.selectbox("⚡ Importancia", importancias, key="dash_importancia")
        
        with col_f4:
            # Filtro por Categoría PEST
            if not datos['pest'].empty and 'categoria' in datos['pest'].columns:
                categorias_pest = ['Todas'] + datos['pest']['categoria'].unique().tolist()
            else:
                categorias_pest = ['Todas']
            filtro_pest = st.selectbox("🌍 Categoría PEST", categorias_pest, key="dash_pest")
        
        # Filtros adicionales expandibles
        with st.expander("🔍 Filtros Avanzados"):
            col_f5, col_f6 = st.columns(2)
            with col_f5:
                # Rango de impacto FODA
                if not datos['foda'].empty and 'impacto' in datos['foda'].columns:
                    impacto_max_val = int(datos['foda']['impacto'].max()) if not datos['foda']['impacto'].isna().all() else 10
                    impacto_min_val = int(datos['foda']['impacto'].min()) if not datos['foda']['impacto'].isna().all() else 0
                    impacto_min, impacto_max = st.slider(
                        "Rango de Impacto FODA", 
                        min_value=impacto_min_val, 
                        max_value=max(impacto_max_val, 10), 
                        value=(impacto_min_val, impacto_max_val),
                        key="dash_impacto"
                    )
                else:
                    impacto_min, impacto_max = 0, 10
                    st.slider("Rango de Impacto FODA", 0, 10, (0, 10), key="dash_impacto_disabled", disabled=True)
            
            with col_f6:
                # Filtro por texto
                filtro_texto = st.text_input("🔎 Buscar en estrategias", placeholder="Escribe palabra clave...", key="dash_texto")
        
        # Botón para aplicar filtros (simula refresh de Power BI)
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        with col_btn1:
            aplicar_filtros = st.button("🔄 Aplicar Filtros", type="primary", key="dash_aplicar")
        with col_btn2:
            if st.button("❌ Limpiar Filtros", key="dash_limpiar"):
                st.rerun()
        
        st.divider()
        
        # ============================================================
        # 3. APLICACIÓN DE FILTROS Y CÁLCULO DE MÉTRICAS
        # ============================================================
        
        # Filtrar estrategias
        df_estrategias_filtrado = datos['estrategias'].copy() if not datos['estrategias'].empty else pd.DataFrame()
        
        if not df_estrategias_filtrado.empty:
            if filtro_cuadrante != 'Todos' and 'cuadrante' in df_estrategias_filtrado.columns:
                df_estrategias_filtrado = df_estrategias_filtrado[df_estrategias_filtrado['cuadrante'] == filtro_cuadrante]
            
            if filtro_plan != 'Todos' and 'plan_asignado' in df_estrategias_filtrado.columns:
                df_estrategias_filtrado = df_estrategias_filtrado[df_estrategias_filtrado['plan_asignado'] == filtro_plan]
            
            if filtro_importancia != 'Todas' and 'importancia' in df_estrategias_filtrado.columns:
                df_estrategias_filtrado = df_estrategias_filtrado[df_estrategias_filtrado['importancia'] == filtro_importancia]
            
            if filtro_texto and 'estrategia' in df_estrategias_filtrado.columns:
                mask = df_estrategias_filtrado['estrategia'].str.contains(filtro_texto, case=False, na=False)
                df_estrategias_filtrado = df_estrategias_filtrado[mask]
        
        # Filtrar PEST
        df_pest_filtrado = datos['pest'].copy() if not datos['pest'].empty else pd.DataFrame()
        
        if not df_pest_filtrado.empty:
            if filtro_pest != 'Todas' and 'categoria' in df_pest_filtrado.columns:
                df_pest_filtrado = df_pest_filtrado[df_pest_filtrado['categoria'] == filtro_pest]
        
        # ============================================================
        # 4. KPIs PRINCIPALES (Tarjetas tipo Power BI)
        # ============================================================
        
        st.subheader("📈 Indicadores Clave de Desempeño (KPIs)")
        
        col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
        
        # KPI 1: Total Estrategias Filtradas
        with col_kpi1:
            total_est = len(df_estrategias_filtrado) if not df_estrategias_filtrado.empty else 0
            total_est_original = len(datos['estrategias']) if not datos['estrategias'].empty else 0
            delta_est = total_est_original - total_est
            st.metric(
                label="🎯 Estrategias",
                value=total_est,
                delta=f"-{delta_est} filtradas" if delta_est > 0 else "Todas",
                delta_color="off"
            )
        
        # KPI 2: Inversión Total Operativizada
        with col_kpi2:
            inversion_total = 0
            if not datos['operativizacion'].empty and 'costo' in datos['operativizacion'].columns:
                df_op = datos['operativizacion'].copy()
                if filtro_plan != 'Todos' and 'plan_asignado' in df_op.columns:
                    df_op = df_op[df_op['plan_asignado'] == filtro_plan]
                inversion_total = pd.to_numeric(df_op['costo'], errors='coerce').sum()
            st.metric(
                label="💰 Inversión Total",
                value=f"${inversion_total:,.0f}",
                delta="Presupuesto" if inversion_total > 0 else "Sin datos"
            )
        
        # KPI 3: Score PEST Promedio
        with col_kpi3:
            score_pest = 0
            if not df_pest_filtrado.empty and 'valor_ponderado' in df_pest_filtrado.columns:
                score_pest = pd.to_numeric(df_pest_filtrado['valor_ponderado'], errors='coerce').sum()
            st.metric(
                label="🌍 Score PEST",
                value=f"{score_pest:.2f}",
                delta="Favorable" if score_pest > 2.5 else "Desafiante",
                delta_color="normal" if score_pest > 2.5 else "inverse"
            )
        
        # KPI 4: Estrategias de Alta Importancia
        with col_kpi4:
            altas = 0
            if not df_estrategias_filtrado.empty and 'importancia' in df_estrategias_filtrado.columns:
                altas = len(df_estrategias_filtrado[df_estrategias_filtrado['importancia'] == 'Alta'])
            st.metric(
                label="⚡ Alta Prioridad",
                value=altas,
                delta="Requieren atención" if altas > 0 else "Sin alertas",
                delta_color="inverse" if altas > 5 else "normal"
            )
        
        # KPI 5: Rentabilidad Esperada
        with col_kpi5:
            utilidad_total = 0
            if not datos['proyeccion'].empty and 'utilidad_neta_proyectada' in datos['proyeccion'].columns:
                utilidad_total = pd.to_numeric(datos['proyeccion']['utilidad_neta_proyectada'], errors='coerce').sum()
            st.metric(
                label="📈 Utilidad Proy.",
                value=f"${utilidad_total:,.0f}",
                delta="5 años" if utilidad_total > 0 else "Sin proyección"
            )
        
        st.divider()
        
        # ============================================================
        # 5. GRÁFICOS PRINCIPALES (Layout tipo Power BI)
        # ============================================================
        
        # Fila 1: Gráficos grandes
        col_graf1, col_graf2 = st.columns([2, 1])
        
        with col_graf1:
            st.subheader("🎯 Distribución de Estrategias")
            
            if not df_estrategias_filtrado.empty and 'cuadrante' in df_estrategias_filtrado.columns and 'plan_asignado' in df_estrategias_filtrado.columns:
                try:
                    fig_burbuja = px.scatter(
                        df_estrategias_filtrado,
                        x='cuadrante',
                        y='plan_asignado',
                        color='cuadrante',
                        hover_data=['estrategia'] if 'estrategia' in df_estrategias_filtrado.columns else None,
                        size_max=60,
                        title="Mapa de Estrategias por Cuadrante y Plan"
                    )
                    fig_burbuja.update_layout(height=400)
                    st.plotly_chart(fig_burbuja, use_container_width=True)
                except Exception as e:
                    st.error(f"Error al generar gráfico: {e}")
            else:
                st.info("No hay datos suficientes de estrategias")
        
        with col_graf2:
            st.subheader("📊 Matriz de Importancia")
            
            if not df_estrategias_filtrado.empty and 'importancia' in df_estrategias_filtrado.columns:
                try:
                    imp_count = df_estrategias_filtrado['importancia'].value_counts()
                    fig_pastel = px.pie(
                        values=imp_count.values,
                        names=imp_count.index,
                        title="Distribución por Prioridad",
                        hole=0.4
                    )
                    fig_pastel.update_layout(height=400)
                    st.plotly_chart(fig_pastel, use_container_width=True)
                except Exception as e:
                    st.error(f"Error al generar gráfico: {e}")
            else:
                st.info("No hay datos de importancia")
        
        st.divider()
        
        # Fila 2: Análisis PEST y FODA
        col_graf3, col_graf4 = st.columns(2)
        
        with col_graf3:
            st.subheader("🌍 Análisis PEST Interactivo")
            
            if not df_pest_filtrado.empty and 'categoria' in df_pest_filtrado.columns and 'valor_ponderado' in df_pest_filtrado.columns:
                try:
                    pest_agrupado = df_pest_filtrado.groupby('categoria')['valor_ponderado'].sum().reset_index()
                    fig_pest = px.bar(
                        pest_agrupado,
                        x='categoria',
                        y='valor_ponderado',
                        color='categoria',
                        title="Impacto por Categoría PEST"
                    )
                    fig_pest.update_layout(height=350, showlegend=False)
                    st.plotly_chart(fig_pest, use_container_width=True)
                except Exception as e:
                    st.error(f"Error al generar gráfico PEST: {e}")
            else:
                st.info("No hay datos PEST disponibles")
        
        with col_graf4:
            st.subheader("⚔️ Análisis FODA Cruzado")
            
            if not datos['foda'].empty and 'cuadrante' in datos['foda'].columns and 'impacto' in datos['foda'].columns:
                try:
                    foda_pivot = datos['foda'].groupby('cuadrante')['impacto'].sum().reset_index()
                    
                    colores_foda = {'FO': '#2ecc71', 'FA': '#e74c3c', 'DO': '#3498db', 'DA': '#f39c12'}
                    colores_barras = [colores_foda.get(c, '#95a5a6') for c in foda_pivot['cuadrante']]
                    
                    fig_foda = go.Figure(data=go.Bar(
                        x=foda_pivot['cuadrante'],
                        y=foda_pivot['impacto'],
                        marker_color=colores_barras,
                        text=foda_pivot['impacto'],
                        textposition='auto'
                    ))
                    fig_foda.update_layout(
                        title="Puntaje por Cuadrante FODA",
                        height=350
                    )
                    st.plotly_chart(fig_foda, use_container_width=True)
                except Exception as e:
                    st.error(f"Error al generar gráfico FODA: {e}")
            else:
                st.info("No hay datos FODA disponibles")
        
        st.divider()
        
        # ============================================================
        # 6. TABLA DINÁMICA TIPO EXCEL/POWER BI
        # ============================================================
        
        st.subheader("📋 Tabla Dinámica de Estrategias")
        
        if not df_estrategias_filtrado.empty:
            # Seleccionar columnas disponibles
            columnas_disponibles = []
            for col in ['cuadrante', 'estrategia', 'plan_asignado', 'importancia', 'actividades']:
                if col in df_estrategias_filtrado.columns:
                    columnas_disponibles.append(col)
            
            if columnas_disponibles:
                st.dataframe(
                    df_estrategias_filtrado[columnas_disponibles],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Botones de exportación
                col_exp1, col_exp2 = st.columns(2)
                with col_exp1:
                    try:
                        csv = df_estrategias_filtrado.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Descargar CSV",
                            data=csv,
                            file_name=f"estrategias_{empresa_id}.csv",
                            mime="text/csv",
                            key="dash_csv"
                        )
                    except Exception as e:
                        st.error(f"Error al generar CSV: {e}")
                
                with col_exp2:
                    try:
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            df_estrategias_filtrado.to_excel(writer, sheet_name='Estrategias', index=False)
                        
                        st.download_button(
                            label="📊 Descargar Excel",
                            data=buffer.getvalue(),
                            file_name=f"estrategias_{empresa_id}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dash_excel"
                        )
                    except Exception as e:
                        st.warning("Instala 'openpyxl' para exportar a Excel: pip install openpyxl")
            else:
                st.warning("No hay columnas disponibles para mostrar")
        else:
            st.warning("No hay estrategias que coincidan con los filtros")
        
        st.divider()
        
        # ============================================================
        # 7. ANÁLISIS DE PRESUPUESTO Y COSTOS
        # ============================================================
        
        if not datos['operativizacion'].empty and 'costo' in datos['operativizacion'].columns:
            st.subheader("💰 Análisis de Presupuesto")
            
            col_pres1, col_pres2 = st.columns(2)
            
            with col_pres1:
                if 'plan_asignado' in datos['operativizacion'].columns:
                    try:
                        presupuesto_plan = datos['operativizacion'].groupby('plan_asignado')['costo'].sum().reset_index()
                        fig_pres = px.bar(
                            presupuesto_plan,
                            x='plan_asignado',
                            y='costo',
                            color='plan_asignado',
                            title="Inversión por Plan Funcional"
                        )
                        fig_pres.update_layout(height=350, showlegend=False)
                        st.plotly_chart(fig_pres, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error: {e}")
            
            with col_pres2:
                if 'descripcion_actividad' in datos['operativizacion'].columns:
                    try:
                        top_actividades = datos['operativizacion'].nlargest(10, 'costo')
                        if 'plan_asignado' in top_actividades.columns:
                            fig_top = px.bar(
                                top_actividades,
                                y='descripcion_actividad',
                                x='costo',
                                orientation='h',
                                color='plan_asignado',
                                title="Top 10 Actividades más Costosas"
                            )
                            fig_top.update_layout(height=350)
                            st.plotly_chart(fig_top, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # ============================================================
        # 8. PROYECCIÓN FINANCIERA
        # ============================================================
        
        if not datos['proyeccion'].empty:
            cols_necesarios = ['anio', 'ingresos_proyectados', 'costos_proyectados', 'utilidad_neta_proyectada']
            if all(col in datos['proyeccion'].columns for col in cols_necesarios):
                st.subheader("📈 Proyección Financiera")
                
                try:
                    fig_proy = go.Figure()
                    
                    fig_proy.add_trace(go.Scatter(
                        x=datos['proyeccion']['anio'],
                        y=datos['proyeccion']['ingresos_proyectados'],
                        mode='lines+markers',
                        name='Ingresos',
                        line=dict(color='#2ecc71', width=3)
                    ))
                    
                    fig_proy.add_trace(go.Scatter(
                        x=datos['proyeccion']['anio'],
                        y=datos['proyeccion']['costos_proyectados'],
                        mode='lines+markers',
                        name='Costos',
                        line=dict(color='#e74c3c', width=3)
                    ))
                    
                    fig_proy.add_trace(go.Scatter(
                        x=datos['proyeccion']['anio'],
                        y=datos['proyeccion']['utilidad_neta_proyectada'],
                        mode='lines+markers',
                        name='Utilidad Neta',
                        line=dict(color='#3498db', width=4)
                    ))
                    
                    fig_proy.update_layout(
                        title="Proyección a 5 Años",
                        xaxis_title="Año",
                        yaxis_title="Monto ($)",
                        height=450,
                        hovermode='x unified'
                    )
                    
                    st.plotly_chart(fig_proy, use_container_width=True)
                except Exception as e:
                    st.error(f"Error en proyección: {e}")
        
        # ============================================================
        # 9. INSIGHTS CON IA
        # ============================================================
        
        st.divider()
        st.subheader("🤖 Insights y Recomendaciones")
        
        if st.button("💡 Generar Análisis con IA", key="dash_ia"):
            with st.spinner("Analizando datos..."):
                # Preparar resumen
                resumen_datos = f"""
Estrategias: {total_est}
Inversión: ${inversion_total:,.0f}
Score PEST: {score_pest:.2f}
Alta prioridad: {altas}
"""
                
                prompt_insights = f"""Como Director Ejecutivo, analiza estos datos y genera:
1. INSIGHT PRINCIPAL (hallazgo clave)
2. ALERTAS (máximo 2)
3. OPORTUNIDADES (máximo 2)
4. RECOMENDACIÓN PRIORITARIA

Datos: {resumen_datos}

Sé directo y accionable. Máximo 200 palabras."""
                
                try:
                    insights = generar_analisis(prompt_insights)
                    st.markdown("### 📋 Análisis Generado:")
                    st.info(insights)
                except Exception as e:
                    st.error(f"Error al generar análisis: {e}")    

# --- PESTAÑA 9: RESUMEN Y CONCLUSIONES ---
    with tab7:
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
            
            st.info(
                "**Estructura del documento generado:**\n\n"
                "- **Resumen Ejecutivo** "
                "- **Plan Estratégico** "
                "- **Anexos** "
            )
            
            submitted_pdf = st.form_submit_button("🚀 Generar PDF Profesional")
        
        # El procesamiento va FUERA del with st.form()
        if submitted_pdf:
            with st.spinner("Generando documento con formato APA. Esto puede tomar un momento..."):
                # Generar PDF con formato profesional
                pdf_buffer = generar_pdf_completo_mejorado(
                    empresa_id, 
                    pdf_version, 
                    pdf_elaborado, 
                    pdf_revisado, 
                    pdf_aprobado
                )

                if pdf_buffer:
                    # Guardar PDF
                    st.session_state['pdf_bytes'] = pdf_buffer.getvalue()
                    st.session_state['pdf_nombre'] = f"Plan_Estrategico_{empresa_data.get('nombre', 'Empresa')}_V{pdf_version}.pdf"

                    st.session_state['pdf_generado'] = True
                    st.success("✅ Documento PDF generado correctamente.")
        
        # Mostrar botones de descarga si el documento fue generado
        if st.session_state.get('pdf_generado', False) and 'pdf_bytes' in st.session_state:
            col1, col2 = st.columns([1, 3])
            with col1:
                # Botón descargar PDF
                download_buffer = BytesIO(st.session_state['pdf_bytes'])
                st.download_button(
                    label="⬇️ Descargar PDF", 
                    data=download_buffer, 
                    file_name=st.session_state.get('pdf_nombre', 'plan_estrategico.pdf'), 
                    mime="application/pdf",
                    type="primary"
                )
            with col2:
                st.success(f"Documento listo: {st.session_state.get('pdf_nombre', 'plan_estrategico.pdf')}")
                st.caption("Formato profesional APA con encabezado, pie de página y todas las secciones.")

            # Botón para generar nuevo documento
            if st.button("🔄 Generar Nuevo", type="secondary"):
                if 'pdf_bytes' in st.session_state:
                    del st.session_state['pdf_bytes']
                if 'pdf_nombre' in st.session_state:
                    del st.session_state['pdf_nombre']
                st.session_state['pdf_generado'] = False
                st.rerun()            
def pantalla_acceso():
    st.sidebar.title("Estratega Pro UG-UCE")
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


















