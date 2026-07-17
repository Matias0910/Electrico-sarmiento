import streamlit as st
import os
import base64
from database import buscar_evento
import auth
import re

st.set_page_config(page_title="Buscador de Fallas", layout="wide")

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
        st.warning(f"El archivo PDF no se encontró en la ruta: {file_path}")
        return None

if not auth.check_authentication(): # Si no está autenticado
    auth.login() # Muestra el formulario de login
    st.stop()

st.title("🔎 Buscador de Fallas por Código, Texto o Categoría")
st.write("Usa los filtros para encontrar rápidamente la descripción, resolución y plano asociado a un evento.")

col1, col2, col3 = st.columns(3)
with col1:
    codigo_falla = st.text_input("Código TCMS/DCU/SIV/EBCU/HVAC/EDCU/PIDS:", placeholder="Ej: 3101")
with col2:
    texto_busqueda = st.text_input("Buscar por Título/Descripción:", placeholder="Ej: Compresor")
with col3:
    categoria_busqueda = st.selectbox(
        "Filtrar por Categoría:",
        ["Todas", "TCMS", "DCU", "SIV", "EBCU", "HVAC", "EDCU", "PIDS"]
    )

if codigo_falla or texto_busqueda or categoria_busqueda != "Todas":
    try:
        resultados = buscar_evento(codigo=codigo_falla, texto=texto_busqueda, categoria=categoria_busqueda)
        if resultados:
            for r in resultados:
                with st.container(border=True):
                    # --- Lógica de visualización mejorada para listas ---
                    def format_field(data):
                        """Formatea un campo como lista de viñetas si es una lista, o como texto normal si no lo es."""
                        if isinstance(data, list):
                            items_validos = [item.strip() for item in data if item and item.strip()]
                            if not items_validos: return "N/A"
                            return "\n".join(f"- {item}" for item in items_validos)
                        return str(data) if data else "N/A"

                    st.write(f"**Evento:** {r.get('evento', 'N/A')}")
                    st.markdown("**Descripción:**")
                    st.markdown(format_field(r.get('descripcion')))
                    st.markdown("**Resolución:**")
                    st.markdown(format_field(r.get('resolucion')))
                    
                    nombre_plano = r.get("plano")
                    if nombre_plano and nombre_plano.strip():
                        st.write(f"**Plano asociado:** {nombre_plano}")

                        # Lógica para manejar múltiples planos en un solo campo (ej: "9 y 10")
                        numeros_plano = re.findall(r'\d+', nombre_plano)
                        planos_encontrados = 0

                        for num in numeros_plano:
                            # Construye el nombre del archivo con el formato SFMXX.pdf
                            nombre_archivo_plano = f"SFM{int(num):02d}.pdf"
                            ruta_plano = os.path.join("Planos", nombre_archivo_plano)

                            if os.path.exists(ruta_plano):
                                st.markdown(f"##### Mostrando plano: {nombre_archivo_plano}")
                                base64_pdf = get_pdf_as_base64(ruta_plano)
                                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                                st.markdown(pdf_display, unsafe_allow_html=True)
                                planos_encontrados += 1
                            else:
                                # Muestra una advertencia si un plano específico no se encuentra
                                st.warning(f"⚠️ El PDF del plano '{nombre_archivo_plano}' no se encontró en la carpeta 'Planos'.")
                        
                        if planos_encontrados == 0 and numeros_plano:
                            st.error("No se encontró ninguno de los archivos PDF para los planos asociados.")

        else:
            st.warning("No se encontró información con los filtros seleccionados.", icon="🤔")
            st.info("Posibles causas: La base de datos de eventos está vacía (ejecuta `import_eventos.py`) o los filtros son muy específicos.")

    except Exception as e:
        st.error(f"Ocurrió un error durante la búsqueda: {e}")