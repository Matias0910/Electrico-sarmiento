import streamlit as st
import pandas as pd
import auth
from database import obtener_estadisticas_fallas

st.set_page_config(page_title="Estadísticas y Alertas", layout="wide")

if not auth.check_authentication(): # Si no está autenticado
    auth.login() # Muestra el formulario de login
    st.stop()

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

# Ordenamos los coches para que aparezcan de forma lógica en el filtro
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

        # --- Lógica de Ordenamiento Personalizado ---
        # 1. Convertimos la columna 'Coche' a un tipo categórico con el orden correcto,
        # asegurándonos de que los valores no presentes en COCHES (como 'N/A') se manejen correctamente.
        coches_con_na = COCHES + [c for c in df_mostrado['Coche'].unique() if c not in COCHES]
        df_mostrado['Coche'] = pd.Categorical(df_mostrado['Coche'], categories=coches_con_na, ordered=True)
        
        # 2. Ordenamos el DataFrame: primero por Tren, luego por el orden de Coche, y finalmente por Cantidad descendente.
        df_mostrado = df_mostrado.sort_values(
            by=['Tren', 'Coche', 'Cantidad'], 
            ascending=[True, True, False]
        )

        # Mostramos la tabla con el estilo
        st.dataframe(
            df_mostrado.style.map(resaltar_cantidad, subset=['Cantidad']),
            use_container_width=True,
            hide_index=True
        )

except Exception as e:
    st.error(f"❌ Ocurrió un error al obtener las estadísticas: {e}")
    st.info("Asegúrate de que la conexión a la base de datos esté funcionando correctamente.")