import streamlit as st
import os
import base64
from database import registrar_mantenimiento
from datetime import date
from fpdf import FPDF, enums
from fpdf.enums import XPos, YPos

class PDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'Informe Técnico (Electrico) - Depósito Castelar', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(5)


# --- Configuración de la página ---
st.set_page_config(page_title="Informe Castelar", page_icon="assets/logo.png", layout="wide")
st.title("⚡ Carga de Informe Técnico (Electrico) - Depósito Castelar")

# --- Inicialización del estado de la sesión ---
# Es una buena práctica inicializar todas las claves del estado de sesión al principio.
if 'lista_tareas' not in st.session_state:
    st.session_state.lista_tareas = []
if 'pdf_bytes' not in st.session_state:
    st.session_state.pdf_bytes = None
if 'tareas_multi_temp' not in st.session_state:
    st.session_state.tareas_multi_temp = {}

# --- Sidebar ---
with st.sidebar:
    st.header("Datos del Informe")
    fecha_trabajo = st.date_input("Fecha", value=date.today())
    tipo_informe = st.selectbox("Tipo de Informe", ["Bimestral", "Quincenal"])
    tren = st.selectbox("Tren", [f"{i:02d}" for i in range(1, 26)])
    km = st.number_input("Kilometraje", min_value=0)
    st.divider()

# --- Función auxiliar para agregar tareas ---
def agregar_tarea(sistema, datos):
    """Añade una tarea a la lista en el estado de la sesión y limpia el PDF previo."""
    st.session_state.lista_tareas.append({"sistema": sistema, "datos": datos})
    st.session_state.pdf_bytes = None # Invalida el PDF previo al agregar nueva tarea

# --- Configuración de Tareas (Refactorización) ---
COCHES = ["TC1", "M1-1", "M2-1", "T3", "M1-2", "M2-2", "M4", "M3", "TC2"]

TAREAS_CONFIG = [
    {"nombre": "FUSIBLES (PATÍN)", "tipo_entrada": "multiple", "campos": [
        {"label": "Boguie", "tipo": "selectbox", "opciones": ["Boguie 1", "Boguie 2"]},
        {"label": "Lado", "tipo": "selectbox", "opciones": ["Norte", "Sur"]},
        {"label": "Causa", "tipo": "selectbox", "opciones": ["Quemado", "Cortocircuito", "Intermitente"]},
    ]},
    {"nombre": "TRENCITAS", "tipo_entrada": "simple", "campos": [
        {"label": "Coche", "tipo": "selectbox", "opciones": COCHES},
        {"label": "Ubicación", "tipo": "selectbox", "opciones": ["Caja Auxiliar", "Caja Principal"]},
        {"label": "Causa", "tipo": "selectbox", "opciones": ["Corte", "Desgaste"]},
    ]},
    {"nombre": "LUCES DE PODER", "tipo_entrada": "simple", "campos": [
        {"label": "Sentido", "tipo": "selectbox", "opciones": ["Norte", "Sur"]},
        {"label": "Tipo", "tipo": "selectbox", "opciones": ["Alta", "Baja"]},
        {"label": "Causa", "tipo": "selectbox", "opciones": ["Balasto", "Lámpara"]},
    ]},
    {"nombre": "ILUMINACIÓN INTERNA", "tipo_entrada": "multiple", "campos": [
        {"label": "Componente", "tipo": "selectbox", "opciones": ["Tubo LED", "Tubo LED con Puente", "Fluo 36w"]},
        {"label": "Causa", "tipo": "selectbox", "opciones": ["Balasto", "Zócalo", "Quemado"]},
        {"label": "Cantidad", "tipo": "number_input", "default": 1, "min_value": 1},
    ]},
    {"nombre": "PRECINTOS NUMÉRICOS", "tipo_entrada": "simple", "visible_en": ["Bimestral", "Quincenal"], "campos": [
        {"label": "Coche", "tipo": "selectbox", "opciones": ["TC1", "TC2"]},
        {"label": "N° ATS", "tipo": "text_input"},
        {"label": "N° ATP", "tipo": "text_input"},
        {"label": "N° SKEMP", "tipo": "text_input"},
    ]},
    {"nombre": "LIMPIEZA SIV (BIMESTRAL)", "tipo_entrada": "simple", "visible_en": ["Bimestral"], "campos": [
        {"label": "Coche", "tipo": "selectbox", "opciones": ["TC1", "TC2", "T3"]},
        {"label": "Estado", "tipo": "selectbox", "opciones": ["Realizado"]},
    ]},
    {"nombre": "LIMPIEZA COMPRESORES (QUINCENAL)", "tipo_entrada": "simple", "visible_en": ["Quincenal"], "campos": [
        {"label": "Coche", "tipo": "selectbox", "opciones": ["TC1", "TC2"]},
        {"label": "Estado", "tipo": "selectbox", "opciones": ["Realizado"]},
    ]},
]

def generar_formularios_tareas(tipo_informe_seleccionado):
    """Genera dinámicamente los expanders y formularios para cada tipo de tarea."""
    for i, config in enumerate(TAREAS_CONFIG):
        # Lógica para mostrar tareas condicionalmente
        if "visible_en" in config and tipo_informe_seleccionado not in config["visible_en"]:
            continue # Si la tarea no corresponde al tipo de informe, no la muestra

        with st.expander(config["nombre"]):
            # Usamos un prefijo único para las claves de los widgets
            key_prefix = f"task_{i}_"
            datos_capturados = {}
            tipo_entrada = config.get("tipo_entrada", "simple") # 'simple' por defecto

            if tipo_entrada == "multiple":
                # Inicializar la lista temporal para esta tarea si no existe
                if i not in st.session_state.tareas_multi_temp:
                    st.session_state.tareas_multi_temp[i] = []

                # Formulario para agregar una tarea a la vez
                st.write("**Paso 1: Añadir tarea por coche**")
                form_cols = st.columns(len(config["campos"]) + 2) # +2 para Coche y botón
                
                with form_cols[0]:
                    coche_seleccionado = st.selectbox("Coche", COCHES, key=f"{key_prefix}coche_select")
                
                for j, campo in enumerate(config["campos"]):
                    with form_cols[j+1]:
                        key = f"{key_prefix}{j}_{campo['label'].lower().replace(' ', '_')}"
                        if campo["tipo"] == "selectbox":
                            datos_capturados[campo['label']] = st.selectbox(campo['label'], campo['opciones'], key=key)
                        elif campo["tipo"] == "number_input":
                            datos_capturados[campo['label']] = st.number_input(campo['label'], min_value=campo.get("min_value", 1), value=campo.get('default', 1), key=key)
                
                with form_cols[-1]:
                    st.write("‎") # Espacio para alinear el botón
                    if st.button("➕", key=f"{key_prefix}btn_add_temp", help=f"Añadir esta tarea a la lista para {config['nombre']}"):
                        datos_completos = {"Coche": coche_seleccionado, **datos_capturados}
                        st.session_state.tareas_multi_temp[i].append(datos_completos)
                        st.rerun()

                # Mostrar la lista de tareas temporales
                if st.session_state.tareas_multi_temp[i]:
                    st.divider()
                    st.write("**Paso 2: Revisar y confirmar tareas**")
                    for idx, tarea_temp in enumerate(st.session_state.tareas_multi_temp[i]):
                        col1, col2 = st.columns([0.9, 0.1])
                        datos_str = " | ".join([f"{k}: {v}" for k, v in tarea_temp.items()])
                        col1.markdown(f"- {datos_str}")
                        if col2.button("🗑️", key=f"{key_prefix}del_temp_{idx}", help="Quitar esta tarea de la lista"):
                            st.session_state.tareas_multi_temp[i].pop(idx)
                            st.rerun()
                    
                    if st.button(f"✅ Confirmar y Agregar {len(st.session_state.tareas_multi_temp[i])} Tarea(s) al Informe", key=f"{key_prefix}btn_confirm_multiple", type="primary"):
                        for tarea_datos in st.session_state.tareas_multi_temp[i]:
                            agregar_tarea(config['nombre'], tarea_datos)
                        # Limpiar la lista temporal después de agregar
                        st.session_state.tareas_multi_temp[i] = []
                        st.rerun()

            else: # tipo_entrada 'simple'
                num_campos = len(config["campos"])
                cols = st.columns(num_campos)
                for j, campo in enumerate(config["campos"]):
                    with cols[j]:
                        key = f"{key_prefix}{j}_{campo['label'].lower().replace(' ', '_')}"
                        if campo["tipo"] == "selectbox":
                            datos_capturados[campo['label']] = st.selectbox(campo['label'], campo['opciones'], key=key)
                        elif campo["tipo"] == "number_input":
                            datos_capturados[campo['label']] = st.number_input(campo['label'], min_value=campo.get("min_value", 1), value=campo.get('default', 1), key=key)
                        elif campo["tipo"] == "text_input":
                            datos_capturados[campo['label']] = st.text_input(campo['label'], key=key)
                
                if st.button(f"➕ Agregar {config['nombre']}", key=f"{key_prefix}btn"):
                    if config['nombre'] == "PRECINTOS NUMÉRICOS" and not any(v for k, v in datos_capturados.items() if k.startswith('N°')):
                        pass # No agregar si no hay número de precinto
                    else:
                        agregar_tarea(config['nombre'], datos_capturados)
                    st.rerun()

# --- Carga de Tareas (UI) ---
st.subheader("Agregar Tareas al Informe")
generar_formularios_tareas(tipo_informe)

with st.expander("Otras Tareas / Notas"):
    # Callback para limpiar los campos de texto de las notas
    def agregar_y_limpiar_nota():
        # Primero, lee los valores del estado de la sesión
        sistema = st.session_state.otro_sistema
        detalle = st.session_state.otro_detalle
        
        if sistema and detalle:
            agregar_tarea(sistema, {'Detalle': detalle})
            # Luego, limpia los campos
            st.session_state.otro_sistema = ""
            st.session_state.otro_detalle = ""
        else:
            st.warning("Por favor, complete el sistema y la descripción.")

    sistema_otro = st.text_input("Sistema / Componente", key="otro_sistema")
    detalle_otro = st.text_area("Descripción de la tarea o nota", key="otro_detalle")
    st.button("➕ Agregar Nota", on_click=agregar_y_limpiar_nota)


# --- Funciones de ayuda ---
def generar_pdf(fecha, tren, km, tareas, observaciones):
    """Genera un PDF con diseño profesional y lo devuelve como bytes."""
    pdf = PDF()
    pdf.add_page()

    # --- Datos Generales ---
    trenes_argentinos_blue = (0, 115, 184)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_fill_color(*trenes_argentinos_blue)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, f"Informe del Tren {tren}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L', fill=True)
    pdf.set_text_color(0, 0, 0) # Restaurar color de texto a negro
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, text=f"Fecha: {fecha.strftime('%d/%m/%Y')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, text=f"Kilometraje: {km} km", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)

    # --- Tabla de Tareas ---
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, "Tareas Realizadas", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

    # Encabezado de la tabla
    pdf.set_font("Helvetica", 'B', 10)
    pdf.set_fill_color(50, 50, 50) # Gris oscuro
    pdf.set_text_color(255, 255, 255)
    pdf.cell(pdf.epw, 8, "Tareas", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Contenido de la tabla
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(0, 0, 0)

    for item in tareas:
        sistema = item['sistema']
        datos_legibles = " | ".join([f"{k}: {v}" for k, v in item['datos'].items()])
        texto_linea = f"- {sistema}: {datos_legibles}"
        pdf.multi_cell(pdf.epw, 8, txt=texto_linea, border="LR", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

    # Línea final de la tabla
    pdf.cell(pdf.epw, 0, '', 'T', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # --- Observaciones ---
    if observaciones:
        pdf.ln(10)
        pdf.set_font("Helvetica", 'B', 12)
        pdf.set_fill_color(*trenes_argentinos_blue)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 10, "Observaciones", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(pdf.epw, 8, text=observaciones, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())

# --- Revisión, Vista Previa y Guardado ---
st.divider()
st.subheader("📋 Vista Previa")
if st.session_state.lista_tareas:
    st.write("Tareas agregadas al informe:")
    # Iteramos sobre una copia de la lista para poder eliminar elementos de forma segura
    for i, tarea in enumerate(st.session_state.lista_tareas):
        col1, col2 = st.columns([0.9, 0.1]) # 90% para el texto, 10% para el botón
        
        with col1:
            sistema = tarea.get("sistema", "N/A")
            datos = " | ".join([f"{k}: {v}" for k, v in tarea.get("datos", {}).items()])
            st.markdown(f"**{sistema}:** {datos}")
        
        with col2:
            if st.button("🗑️", key=f"delete_task_{i}", help="Eliminar esta tarea"):
                st.session_state.lista_tareas.pop(i)
                st.rerun()
    st.write("---")

    observaciones = st.text_area("Observaciones")

    # --- Botones de Acción ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Confirmar y Guardar", type="primary"):
            try:
                datos_informe = {
                    "fecha": fecha_trabajo.isoformat(),
                    "tipo_informe": tipo_informe,
                    "tren": tren, 
                    "km": km, 
                    "tareas": st.session_state.lista_tareas, 
                    "obs": observaciones
                }
                inserted_id = registrar_mantenimiento(datos_informe)
                st.success(f"✅ ¡Informe guardado con éxito! ID: {inserted_id}")
                st.balloons()
                st.session_state.lista_tareas = []
                st.session_state.pdf_bytes = None
                st.rerun()
            except Exception as e:
                st.error(f"❌ Hubo un error al guardar el informe: {e}")

    with col2:
        if st.button("👁️ Previsualizar PDF"):
            pdf_bytes = generar_pdf(fecha_trabajo, tren, km, st.session_state.lista_tareas, observaciones)
            st.session_state.pdf_bytes = pdf_bytes # Guardar en el estado de la sesión

    if 'pdf_bytes' in st.session_state and st.session_state.pdf_bytes:
        # Mostrar el PDF
        base64_pdf = base64.b64encode(st.session_state.pdf_bytes).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)

        # Botón de descarga
        st.download_button(
            label="📥 Descargar PDF",
            data=st.session_state.pdf_bytes,
            file_name=f"informe_tren_{tren}_{fecha_trabajo}.pdf",
            mime="application/pdf",
        )
