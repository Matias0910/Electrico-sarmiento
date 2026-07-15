import io
import importlib
import wave

import speech_recognition as sr
import streamlit as st
from streamlit_mic_recorder import mic_recorder

import ai_utils


ai_utils = importlib.reload(ai_utils)
interpretar_comando_con_ia = ai_utils.interpretar_comando_con_ia


st.set_page_config(page_title="Asistente IA", layout="wide")

st.title("Asistente de Carga por Voz y Texto")
st.write("Graba o escribe tu comando. La IA intentara rellenar las tareas por vos.")
st.info("Ejemplo: 'Agrega un fusible quemado en el coche TC1, bogie 1, lado norte.'")


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
        tareas = interpretar_comando_con_ia(texto)

    if not tareas:
        st.warning("La IA no pudo interpretar el comando.")
        return

    if "lista_tareas" not in st.session_state:
        st.session_state.lista_tareas = []

    for tarea in tareas:
        st.session_state.lista_tareas.append(tarea)
        st.markdown(
            f"**{tarea['sistema']}** -> "
            + ", ".join(
                f"{k}: {v}"
                for k, v in tarea["datos"].items()
            )
        )

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
