import streamlit as st
import pandas as pd
from database import obtener_estadisticas_fallas

st.set_page_config(page_title="Estadísticas y Alertas", layout="wide")

# --- Lógica de Autenticación (copiada en cada página) ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

USUARIOS = {
    "matias": "castelar2026",
    "pablo": "qwerty",
    "diego": "fusible123",
    "richard": "cabinero789"
}

def verificar_credenciales(usuario, password):
    usr = usuario.strip().lower()
    return usr in USUARIOS and USUARIOS[usr] == password

if not st.session_state.logged_in:
    st.title("🔑 Acceso - Depósito Castelar")
    st.info("Por favor, inicia sesión para acceder a esta página.")
    
    with st.form("login_form_page"):
        usuario = st.text_input("Usuario (Nombre)")
        password = st.text_input("Contraseña", type="password")
        boton_ingresar = st.form_submit_button("Iniciar Sesión")
        
        if boton_ingresar:
            if verificar_credenciales(usuario, password):
                st.session_state.logged_in = True
                st.session_state.usuario_activo = usuario.strip().capitalize()
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    st.stop()

# --- Fin de la Lógica de Autenticación ---

st.title("📊 Estadísticas y Alertas de Fallas")
st.write("Analiza las fallas más recurrentes por tren y por coche para un mantenimiento proactivo.")

# --- Barra lateral de Filtros ---
st.sidebar.header("Filtros")

# Buscador por texto para componente
busqueda_componente = st.sidebar.text_input(
    "Buscar componente por nombre",
    placeholder="Ej: Fusible, Luz, Camara..."
)

# Filtros originales de Tren y Coche
trenes_disponibles = ["Todos"] + [f"{i:02d}" for i in range(1, 26)]
filtro_tren = st.sidebar.selectbox("Seleccionar Tren", trenes_disponibles)

COCHES = ["TC1", "M1-1", "M2-1", "T3", "M1-2", "M2-2", "M3", "M4", "TC2"]
coches_disponibles = ["Todos"] + COCHES
filtro_coche = st.sidebar.selectbox("Seleccionar Coche", coches_disponibles)

st.divider()

# --- Lógica para mostrar estadísticas ---
try:
    # Pasamos None si el usuario selecciona "Todos"
    tren_a_buscar = filtro_tren if filtro_tren != "Todos" else None
    coche_a_buscar = filtro_coche if filtro_coche != "Todos" else None

    # Obtenemos el DataFrame con todas las estadísticas desde la base de datos
    df_estadisticas = obtener_estadisticas_fallas(filtro_tren=tren_a_buscar, filtro_coche=coche_a_buscar)

    # Aplicamos el filtro de búsqueda por texto si el usuario escribió algo
    if busqueda_componente:
        # Diccionario de sinónimos para una búsqueda más inteligente
        SINONIMOS = {
            'luces': ['luces', 'luz', 'iluminacion', 'iluminación'],
            'fusibles': ['fusible', 'fusibles'],
            'camaras': ['camara', 'camaras'],
        }
        
        termino_buscado = busqueda_componente.lower()
        patron_busqueda = termino_buscado
        
        for clave, lista_sinonimos in SINONIMOS.items():
            if termino_buscado in lista_sinonimos:
                patron_busqueda = '|'.join(lista_sinonimos) # Crea un patrón regex: 'luces|luz|iluminacion'
                break
        df_estadisticas = df_estadisticas[df_estadisticas['Componente / Tarea'].str.contains(patron_busqueda, case=False, na=False, regex=True)]

    if df_estadisticas.empty:
        st.info("No se encontraron datos de fallas con los filtros seleccionados.")
    else:
        st.subheader("Ranking de Fallas Recurrentes")
        
        # Función para resaltar la cantidad cuando es mayor a 1
        def resaltar_cantidad(val):
            return 'color: red; font-weight: bold;' if isinstance(val, (int, float)) and val > 1 else ''

        # Reordenamos las columnas para que 'Tren' aparezca primero
        columnas_ordenadas = ['Tren', 'Coche', 'Componente / Tarea', 'Causa de la Falla', 'Cantidad']
        # Nos aseguramos de que solo usamos las columnas que existen en el dataframe para evitar errores
        columnas_a_mostrar = [col for col in columnas_ordenadas if col in df_estadisticas.columns]
        df_mostrado = df_estadisticas[columnas_a_mostrar]

        # Mostramos la tabla con el estilo
        st.dataframe(
            df_mostrado.style.map(resaltar_cantidad, subset=['Cantidad']),
            use_container_width=True,
            hide_index=True
        )

except Exception as e:
    st.error(f"❌ Ocurrió un error al obtener las estadísticas: {e}")
    st.info("Asegúrate de que la conexión a la base de datos esté funcionando correctamente.")