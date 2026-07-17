import base64
import io
import importlib
import wave
import os
import re

import speech_recognition as sr
import streamlit as st
from streamlit_mic_recorder import mic_recorder
import auth # Importamos el módulo completo
import ai_utils
from database import buscar_evento

# Recargamos los módulos para asegurar que los cambios se apliquen
auth = importlib.reload(auth)
ai_utils = importlib.reload(ai_utils)

st.set_page_config(page_title="Asistente IA", layout="wide")

if not auth.check_authentication(): # Si no está autenticado
    auth.login() # Muestra el formulario de login
    st.stop()

# --- Inicialización del estado de la sesión ---
# Nos aseguramos de que la lista de tareas exista.
if "lista_tareas" not in st.session_state:
    st.session_state.lista_tareas = []

st.title("Asistente de Carga por Voz y Texto")
st.write("Graba o escribe tu comando. La IA intentara rellenar las tareas por vos.")
st.info("Ejemplo: 'Agrega un fusible quemado en el coche TC1, bogie 1, lado norte.'")
st.info("También puedes preguntar por fallas: '¿Qué dice la falla 3101?'")

# --- Estilos CSS para mejorar la legibilidad ---
st.markdown("""
<style>
    /* Aplicar estilo a todos los botones de Streamlit */
    div[data-testid="stButton"] > button {
        background-color: #0073B8 !important;
        color: white !important;
        border: 1px solid #005a8d !important;
    }
    
    /* Asegurar que el texto dentro del botón sea blanco y legible */
    div[data-testid="stButton"] > button p {
        color: white !important;
        font-weight: bold;
    }
    
    /* Atacamos todas las variantes de cajas de alerta (st.info, st.success, etc.) */
    div[data-testid="stAlert"], 
    div[data-testid="stNotification"],
    div[role="alert"] {
        background-color: #0073B8 !important;
    }

    /* Forzamos absolutamente todo el texto, títulos y viñetas dentro de la alerta a ser blanco */
    div[data-testid="stAlert"] *, 
    div[data-testid="stNotification"] *,
    div[role="alert"] * {
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def get_pdf_as_base64(file_path):
    """
    Abre un archivo PDF, lo codifica en Base64 y lo cachea.
    Esto evita tener que leer y codificar el archivo en cada re-ejecución.
    """
    try:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
        return base64.b64encode(pdf_bytes).decode('utf-8')
    except FileNotFoundError:
        return None

def normalizar_audio_a_wav(audio):
    audio_bytes = audio.get("bytes", b"")

    if audio_bytes.startswith((b"RIFF", b"FORM", b"fLaC")):
        return audio_bytes

    sample_rate = int(audio.get("sample_rate") or audio.get("sampleRate") or 44100)
    sample_width = int(audio.get("sample_width") or audio.get("sampleWidth") or 2)
    channels = int(audio.get("channels") or audio.get("channel_count") or 1)

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_bytes)

    wav_buffer.seek(0)
    return wav_buffer.read()

def agregar_tareas_desde_texto(texto):
    texto = (texto or "").strip()
    if not texto:
        st.warning("Escribi o graba un comando para procesar.")
        return

    st.write(f"**Comando detectado:** {texto}")

    with st.spinner("Procesando con IA..."):
        respuesta_ia = ai_utils.interpretar_comando_con_ia(texto)

    if not respuesta_ia:
        st.warning("La IA no pudo interpretar el comando.")
        detalle_error = ai_utils.obtener_ultimo_error_ia()
        if detalle_error:
            st.error(detalle_error)
        return

    accion = respuesta_ia.get("accion")

    if accion == "agregar_tarea":
        agregar_tareas_a_session(respuesta_ia.get("tareas", []))
    elif accion == "buscar_falla":
        codigo_falla = respuesta_ia.get("codigo")
        buscar_y_mostrar_falla(codigo_falla)
    else:
        st.warning("La IA no pudo determinar una acción clara (agregar tarea o buscar falla).")
        detalle_error = ai_utils.obtener_ultimo_error_ia() or respuesta_ia.get("detalle")
        if detalle_error:
            st.error(detalle_error)

@st.cache_data(show_spinner=False)
def obtener_sugerencia_ia_cacheada(descripcion, resolucion):
    """
    Función wrapper para cachear los resultados de la IA.
    Si los mismos argumentos (descripción y resolución) se usan de nuevo,
    Streamlit devolverá el resultado cacheado en lugar de llamar a la IA.
    """
    return ai_utils.generar_solucion_practica_con_ia(descripcion, resolucion)

def buscar_y_mostrar_falla(codigo):
    st.subheader(f"Resultado de la búsqueda para la falla '{codigo}':")
    resultados = buscar_evento(codigo=codigo)
    if not resultados:
        st.warning(f"No se encontró información para el código de falla '{codigo}'.")
        return

    for r in resultados:
        with st.container(border=True):
            def format_field(data):
                if isinstance(data, list):
                    items_validos = [item.strip() for item in data if item and item.strip()]
                    if not items_validos: return "N/A"
                    return "\n".join(f"- {item}" for item in items_validos)
                return str(data) if data else "N/A"

            descripcion_tecnica = format_field(r.get('descripcion'))
            resolucion_tecnica = format_field(r.get('resolucion'))

            st.write(f"**Evento:** {r.get('evento', 'N/A')}")
            st.markdown("**Descripción:**")
            st.markdown(descripcion_tecnica)
            st.markdown("**Resolución:**")
            st.markdown(resolucion_tecnica)

            try:
                # --- Generación de sugerencia práctica con IA ---
                with st.spinner("Generando sugerencia práctica con IA..."):
                    # Usamos la función cacheada en lugar de la llamada directa
                    sugerencia_ia = obtener_sugerencia_ia_cacheada(
                        descripcion=descripcion_tecnica,
                        resolucion=resolucion_tecnica
                    )
                    st.info(f"**Sugerencia Práctica de la IA:**\n\n{sugerencia_ia}")
            except Exception as e:
                st.warning(f"⚠️ No se pudo generar la sugerencia práctica de la IA. Error: {e}")
                st.info("La información de la base de datos se muestra a continuación.")

            nombre_plano = r.get("plano")
            if nombre_plano and nombre_plano.strip():
                st.write(f"**Plano asociado:** {nombre_plano}")
                numeros_plano = re.findall(r'\d+', nombre_plano)
                for num in numeros_plano:
                    nombre_archivo_plano = f"SFM{int(num):02d}.pdf"
                    ruta_plano = os.path.join("Planos", nombre_archivo_plano)
                    base64_pdf = get_pdf_as_base64(ruta_plano)
                    if base64_pdf:
                        st.markdown(f"##### Mostrando plano: {nombre_archivo_plano}")
                        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                        st.markdown(pdf_display, unsafe_allow_html=True)
                    else:
                        st.warning(f"⚠️ El PDF del plano '{nombre_archivo_plano}' no se encontró en la carpeta 'Planos'.")

def agregar_tareas_a_session(tareas):
    for tarea in tareas:
        tarea_informe = {
            "sistema": tarea["sistema"],
            "datos": tarea["datos"],
        }
        st.session_state.lista_tareas.append(tarea_informe)
        st.markdown(
            f"**{tarea['sistema']}** -> "
            + ", ".join(
                f"{k}: {v}"
                for k, v in tarea["datos"].items()
            )
        )

        explicacion_falla = tarea.get("explicacion_falla", "").strip()
        solucion_sugerida = tarea.get("solucion_sugerida", "").strip()
        if explicacion_falla:
            st.markdown(f"**Que indica la falla:** {explicacion_falla}")
        if solucion_sugerida:
            st.info(f"**Sugerencia de resolucion:** {solucion_sugerida}")

    st.success("Tareas agregadas correctamente.")
    st.balloons()

def procesar_audio(audio):
    audio_bytes = normalizar_audio_a_wav(audio)
    st.audio(audio_bytes, format="audio/wav")

    recognizer = sr.Recognizer()

    with st.spinner("Transcribiendo tu voz..."):
        audio_file = io.BytesIO(audio_bytes)

        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)

        texto = recognizer.recognize_google(
            audio_data,
            language="es-ES",
        )

    agregar_tareas_desde_texto(texto)

st.subheader("Escribir comando")
comando_escrito = st.text_area(
    "Comando",
    placeholder="Agrega un fusible quemado en el coche TC1, bogie 1, lado norte.",
    key="comando_ia_texto",
)

if st.button("Procesar texto", type="primary"):
    agregar_tareas_desde_texto(comando_escrito)

st.divider()
st.subheader("Grabar comando")

audio = mic_recorder(
    start_prompt="Grabar comando",
    stop_prompt="Detener",
    format="wav",
    key="mic",
)

if audio is not None:
    try:
        procesar_audio(audio)
    except sr.UnknownValueError:
        st.error("No se pudo entender el audio.")
    except sr.RequestError as e:
        st.error(f"Error del servicio de reconocimiento: {e}")
    except Exception as e:
        st.error(f"Error: {e}")
