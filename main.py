import streamlit as st
import os
import base64
from database import registrar_mantenimiento
from datetime import date, datetime
from pdf_utils import generar_pdf


# --- Configuración de la página ---
st.set_page_config(page_title="Informe Castelar", page_icon="assets/logo.png", layout="wide")

# --- Estilos CSS para mejorar la visibilidad de los botones ---
st.markdown("""
<style>
    /* Apunta a los botones primarios de Streamlit */
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #FFFFFF; /* Fondo blanco */
        color: #0073B8; /* Color de texto azul (del logo) */
        border: 1px solid #0073B8; /* Borde azul */
    }
</style>
""", unsafe_allow_html=True)
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
    st.session_state.pdf_bytes = None  # Invalida el PDF previo al agregar nueva tarea

# --- Configuración de Tareas (Refactorización) ---
COCHES = ["TC1", "M1-1", "M2-1", "T3", "M1-2", "M2-2", "M3", "M4", "TC2"]

TAREAS_CONFIG = [
    {"nombre": "FUSIBLES (PATÍN)", "tipo_entrada": "fusibles_layout", "campos": [
        {"label": "Causa", "tipo": "selectbox", "opciones": ["Quemado", "Cortocircuito", "Intermitente"]},
    ]},
    {"nombre": "TRENCITAS", "tipo_entrada": "trencitas_layout", "campos": [
        {"label": "Ubicación", "tipo": "selectbox", "opciones": ["Caja Auxiliar", "Caja Principal"]},
        {"label": "Causa", "tipo": "selectbox", "opciones": ["Corte", "Desgaste"]},
    ]},
    {"nombre": "LUCES DE PODER (Cabinas)", "tipo_entrada": "luces_cabina_layout", "campos": [
        {"label": "Tipo", "tipo": "selectbox", "opciones": ["Alta", "Baja"]},
        {"label": "Causa", "tipo": "selectbox", "opciones": ["Balasto", "Lámpara", "Balasto y Lampara"]},
    ]},
    {"nombre": "ILUMINACIÓN INTERNA", "tipo_entrada": "iluminacion_layout", "campos": [
        {"label": "Componente", "tipo": "selectbox", "opciones": ["Tubo LED", "Tubo LED con Puente", "Fluo 36w"]},
        {"label": "Causa", "tipo": "selectbox", "opciones": ["Balasto", "Zócalo", "Quemado"]},
        {"label": "Cantidad", "tipo": "number_input", "default": 1, "min_value": 1},
    ]},
    {"nombre": "PRECINTOS NUMÉRICOS", "tipo_entrada": "precintos_layout", "visible_en": ["Bimestral", "Quincenal"], "campos": [
        {"label": "N° ATS", "tipo": "text_input"},
        {"label": "N° ATP", "tipo": "text_input"},
        {"label": "N° SKEMP", "tipo": "text_input"},
    ]},
    {"nombre": "LIMPIEZA SIV (BIMESTRAL)", "tipo_entrada": "limpieza_layout", "visible_en": ["Bimestral"], "coches": ["TC1", "TC2", "T3"]},
    {"nombre": "LIMPIEZA COMPRESORES (QUINCENAL)", "tipo_entrada": "limpieza_layout", "visible_en": ["Quincenal"], "coches": ["TC1", "TC2"]},
    {"nombre": "BCH", "tipo_entrada": "simple_check_layout", "campos": []},
    {"nombre": "PW", "tipo_entrada": "simple_check_layout", "campos": []},
]

# Lista para recolectar todas las tareas antes de agregarlas
tareas_a_agregar_global = []

def generar_formularios_tareas(tipo_informe_seleccionado):
    """Genera dinámicamente los expanders y formularios para cada tipo de tarea."""
    for i, config in enumerate(TAREAS_CONFIG):
        # Lógica para mostrar tareas condicionalmente
        if "visible_en" in config and tipo_informe_seleccionado not in config["visible_en"]:
            continue # Si la tarea no corresponde al tipo de informe, no la muestra

        with st.expander(config["nombre"]):
            # Usamos un prefijo único para las claves de los widgets
            # Usamos un prefijo único para las claves de los widgets para evitar colisiones
            key_prefix = f"task_{i}_"
            datos_capturados = {}
            tipo_entrada = config.get("tipo_entrada", "simple")  # 'simple' por defecto

            if tipo_entrada == "multiple":
                st.write("**Paso 1: Selecciona los coches a intervenir**")
                cols_coches = st.columns(len(COCHES))
                coches_seleccionados = {}
                for idx, coche in enumerate(COCHES):
                    coches_seleccionados[coche] = cols_coches[idx].toggle(coche, key=f"{key_prefix}toggle_{coche}")

                st.divider()

                # --- Lógica dinámica: Mostrar formularios solo para los seleccionados ---
                for coche, activo in coches_seleccionados.items():
                    if activo:
                        with st.container(border=True):
                            st.subheader(f"Tareas para: {coche}")
                            datos_coche_actual = {}

                            num_campos_form = len(config["campos"]) + 1 # +1 para el botón
                            form_cols = st.columns(len(config["campos"]))

                            for j, campo in enumerate(config["campos"]):
                                with form_cols[j]:
                                    # Clave única para cada campo y coche para no mezclar valores
                                    key = f"{key_prefix}{coche}_{j}_{campo['label'].lower().replace(' ', '_')}"
                                    if campo["tipo"] == "selectbox":
                                        datos_coche_actual[campo['label']] = st.selectbox(campo['label'], campo['opciones'], key=key)
                                    elif campo["tipo"] == "number_input":
                                        datos_coche_actual[campo['label']] = st.number_input(campo['label'], min_value=campo.get("min_value", 1), value=campo.get('default', 1), key=key)
                            # Guardamos los datos del formulario para este coche
                            tareas_a_agregar_global.append({"nombre_tarea": config['nombre'], "datos_completos": {"Coche": coche, **datos_coche_actual}})

            elif tipo_entrada == "simple": # Para tareas genéricas de un solo formulario
                # Añadimos un toggle para que el usuario decida si quiere agregar esta tarea
                col_toggle, col_form = st.columns([0.2, 0.8])
                
                with col_toggle:
                    activar_tarea = st.toggle("Activar Tarea", key=f"{key_prefix}activar")

                cols = col_form.columns(len(config["campos"]))
                for j, campo in enumerate(config["campos"]):
                    with cols[j]:
                        key = f"{key_prefix}{j}_{campo['label'].lower().replace(' ', '_')}"
                        if campo["tipo"] == "selectbox":
                            datos_capturados[campo['label']] = st.selectbox(campo['label'], campo['opciones'], key=key)
                        elif campo["tipo"] == "number_input":
                            datos_capturados[campo['label']] = st.number_input(campo['label'], min_value=campo.get("min_value", 1), value=campo.get('default', 1), key=key, step=1)
                        elif campo["tipo"] == "text_input":
                            datos_capturados[campo['label']] = st.text_input(campo['label'], key=key)
                
                if activar_tarea:
                    # Solo recolectamos los datos si la tarea fue activada explícitamente
                    tareas_a_agregar_global.append({"nombre_tarea": config['nombre'], "datos_completos": datos_capturados})
            
            elif tipo_entrada == "limpieza_layout":
                tarea_realizada = st.checkbox("Tarea Realizada", key=f"{key_prefix}realizada")
                if tarea_realizada:
                    # Si se marca, se agrega la tarea para cada coche definido en la configuración
                    for coche in config["coches"]:
                        datos = {"Coche": coche, "Estado": "Realizado"}
                        tareas_a_agregar_global.append({"nombre_tarea": config['nombre'], "datos_completos": datos})

            
            elif tipo_entrada == "precintos_layout":
                col_tc1, col_tc2 = st.columns(2)
                datos_tc1 = {}
                datos_tc2 = {}

                with col_tc1:
                    st.subheader("TC1")
                    for campo in config["campos"]:
                        datos_tc1[campo['label']] = st.text_input(campo['label'], key=f"{key_prefix}tc1_{campo['label']}")
                
                with col_tc2:
                    st.subheader("TC2")
                    for campo in config["campos"]:
                        datos_tc2[campo['label']] = st.text_input(campo['label'], key=f"{key_prefix}tc2_{campo['label']}")

                # Recolectar si hay datos
                if any(datos_tc1.values()):
                    tareas_a_agregar_global.append({"nombre_tarea": config['nombre'], "datos_completos": {"Coche": "TC1", **datos_tc1}})
                if any(datos_tc2.values()):
                    tareas_a_agregar_global.append({"nombre_tarea": config['nombre'], "datos_completos": {"Coche": "TC2", **datos_tc2}})

            elif tipo_entrada == "fusibles_layout":
                st.write("**Paso 1: Selecciona los coches a intervenir**")
                cols_coches = st.columns(len(COCHES))
                coches_seleccionados = {}
                for idx, coche in enumerate(COCHES):
                    coches_seleccionados[coche] = cols_coches[idx].toggle(coche, key=f"{key_prefix}toggle_{coche}")

                st.divider()

                for coche, activo in coches_seleccionados.items():
                    if activo:
                        with st.container(border=True):
                            st.subheader(f"Fusibles para: {coche}")
                            opciones_causa = ["-"] + config["campos"][0]["opciones"]
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown("**Bogie 1**")
                                causa_b1_n = st.selectbox("Lado Norte", opciones_causa, key=f"{key_prefix}{coche}_b1_n")
                                causa_b1_s = st.selectbox("Lado Sur", opciones_causa, key=f"{key_prefix}{coche}_b1_s")
                            with col2:
                                st.markdown("**Bogie 2**")
                                causa_b2_n = st.selectbox("Lado Norte", opciones_causa, key=f"{key_prefix}{coche}_b2_n")
                                causa_b2_s = st.selectbox("Lado Sur", opciones_causa, key=f"{key_prefix}{coche}_b2_s")

                            # Recolectar tareas si se seleccionó una causa
                            if causa_b1_n != "-": tareas_a_agregar_global.append({"nombre_tarea": config['nombre'], "datos_completos": {"Coche": coche, "Boguie": "Boguie 1", "Lado": "Norte", "Causa": causa_b1_n}})
                            if causa_b1_s != "-": tareas_a_agregar_global.append({"nombre_tarea": config['nombre'], "datos_completos": {"Coche": coche, "Boguie": "Boguie 1", "Lado": "Sur", "Causa": causa_b1_s}})
                            if causa_b2_n != "-": tareas_a_agregar_global.append({"nombre_tarea": config['nombre'], "datos_completos": {"Coche": coche, "Boguie": "Boguie 2", "Lado": "Norte", "Causa": causa_b2_n}})
                            if causa_b2_s != "-": tareas_a_agregar_global.append({"nombre_tarea": config['nombre'], "datos_completos": {"Coche": coche, "Boguie": "Boguie 2", "Lado": "Sur", "Causa": causa_b2_s}})

            elif tipo_entrada == "trencitas_layout":
                st.write("**Paso 1: Selecciona los coches a intervenir**")
                cols_coches = st.columns(len(COCHES))
                coches_seleccionados = {}
                for idx, coche in enumerate(COCHES):
                    coches_seleccionados[coche] = cols_coches[idx].toggle(coche, key=f"{key_prefix}toggle_{coche}")

                st.divider()

                for coche, activo in coches_seleccionados.items():
                    if activo:
                        with st.container(border=True):
                            st.subheader(f"Trencitas para: {coche}")
                            opciones_causa = ["-"] + config["campos"][1]["opciones"]
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                causa_aux = st.selectbox("Caja Auxiliar", opciones_causa, key=f"{key_prefix}{coche}_aux")
                            with col2:
                                causa_ppal = st.selectbox("Caja Principal", opciones_causa, key=f"{key_prefix}{coche}_ppal")

                            # Recolectar tareas si se seleccionó una causa
                            if causa_aux != "-": tareas_a_agregar_global.append({"nombre_tarea": config['nombre'], "datos_completos": {"Coche": coche, "Ubicación": "Caja Auxiliar", "Causa": causa_aux}})
                            if causa_ppal != "-": tareas_a_agregar_global.append({"nombre_tarea": config['nombre'], "datos_completos": {"Coche": coche, "Ubicación": "Caja Principal", "Causa": causa_ppal}})

            elif tipo_entrada == "luces_cabina_layout":
                for coche_cabina in ["TC1", "TC2"]:
                    with st.container(border=True):
                        st.subheader(f"Luces de Poder para: {coche_cabina}")
                        opciones_tipo = ["-"] + config["campos"][0]["opciones"]
                        opciones_causa = ["-"] + config["campos"][1]["opciones"]

                        st.markdown("**Lado Norte**")
                        col_n1, col_n2 = st.columns(2)
                        tipo_n = col_n1.selectbox("Tipo", opciones_tipo, key=f"{key_prefix}{coche_cabina}_n_tipo")
                        causa_n = col_n2.selectbox("Causa", opciones_causa, key=f"{key_prefix}{coche_cabina}_n_causa")

                        st.markdown("**Lado Sur**")
                        col_s1, col_s2 = st.columns(2)
                        tipo_s = col_s1.selectbox("Tipo", opciones_tipo, key=f"{key_prefix}{coche_cabina}_s_tipo")
                        causa_s = col_s2.selectbox("Causa", opciones_causa, key=f"{key_prefix}{coche_cabina}_s_causa")

                        if tipo_n != "-" and causa_n != "-":
                            tareas_a_agregar_global.append({"nombre_tarea": "LUCES DE PODER", "datos_completos": {"Coche": coche_cabina, "Sentido": "Norte", "Tipo": tipo_n, "Causa": causa_n}})
                        if tipo_s != "-" and causa_s != "-":
                            tareas_a_agregar_global.append({"nombre_tarea": "LUCES DE PODER", "datos_completos": {"Coche": coche_cabina, "Sentido": "Sur", "Tipo": tipo_s, "Causa": causa_s}})

            elif tipo_entrada == "iluminacion_layout":
                st.write("**Paso 1: Selecciona los coches a intervenir**")
                cols_coches = st.columns(len(COCHES))
                coches_seleccionados = {}
                for idx, coche in enumerate(COCHES):
                    coches_seleccionados[coche] = cols_coches[idx].toggle(coche, key=f"{key_prefix}toggle_{coche}")

                st.divider()

                for coche, activo in coches_seleccionados.items():
                    if activo:
                        with st.container(border=True):
                            st.subheader(f"Iluminación para: {coche}")
                            
                            componentes = config["campos"][0]["opciones"]
                            opciones_causa = ["-"] + config["campos"][1]["opciones"]

                            for comp in componentes:
                                st.markdown(f"**{comp}**")
                                col1, col2 = st.columns(2)
                                causa = col1.selectbox("Causa", opciones_causa, key=f"{key_prefix}{coche}_{comp}_causa")
                                cantidad = col2.number_input("Cantidad", min_value=0, value=0, step=1, key=f"{key_prefix}{coche}_{comp}_cant")

                                if causa != "-" and cantidad > 0:
                                    tareas_a_agregar_global.append({
                                        "nombre_tarea": config['nombre'],
                                        "datos_completos": {
                                            "Coche": coche,
                                            "Componente": comp,
                                            "Causa": causa,
                                            "Cantidad": cantidad
                                        }
                                    })

            elif tipo_entrada == "simple_check_layout":
                st.write("**Selecciona los coches donde se realizó el cambio:**")
                cols_coches = st.columns(len(COCHES))
                for idx, coche in enumerate(COCHES):
                    realizado = cols_coches[idx].checkbox(coche, key=f"{key_prefix}check_{coche}")
                    if realizado:
                        # Si se marca, se agrega la tarea para ese coche
                        datos = {"Coche": coche, "Estado": "Cambiado"}
                        tareas_a_agregar_global.append({"nombre_tarea": config['nombre'], "datos_completos": datos})

# --- Carga de Tareas (UI) ---
st.subheader("Agregar Tareas al Informe")
generar_formularios_tareas(tipo_informe)

# --- Botón Global para Agregar Tareas ---
if st.button(f"✅ Agregar Tareas al Informe", key="add_all_global", type="primary"):
    if tareas_a_agregar_global:
        for tarea in tareas_a_agregar_global:
            agregar_tarea(tarea['nombre_tarea'], tarea['datos_completos'])
        st.rerun()

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

    # --- Botones de Acción ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Confirmar y Guardar", type="primary", use_container_width=True):
            try:
                datos_informe = {
                    "fecha": fecha_trabajo.isoformat(),
                    "tipo_informe": tipo_informe,
                    "tren": tren, 
                    "km": km, 
                    "tareas": st.session_state.lista_tareas, 
                    "obs": "" # Las observaciones ahora se manejan en la sección de Notas
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
        if st.button("👁️ Previsualizar PDF", use_container_width=True):
            pdf_bytes = generar_pdf(fecha_trabajo, tren, km, st.session_state.lista_tareas, "")
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
