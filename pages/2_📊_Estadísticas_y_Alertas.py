import streamlit as st
import pandas as pd
from database import obtener_estadisticas_fallas

st.set_page_config(page_title="Estadísticas y Alertas", layout="wide")

st.title("📊 Estadísticas y Alertas de Fallas")
st.write("Analiza las fallas más recurrentes por tren y por coche para un mantenimiento proactivo.")

# --- Constantes ---
COCHES = ["TC1", "M1-1", "M2-1", "T3", "M1-2", "M2-2", "M4", "M3", "TC2"]

# --- Filtros ---
st.subheader("Filtros de Búsqueda")
col1, col2 = st.columns(2)

with col1:
    # Selector para todos los trenes, incluyendo una opción para ver "Todos"
    trenes_disponibles = ["Todos"] + [f"{i:02d}" for i in range(1, 26)]
    filtro_tren = st.selectbox("Seleccionar Tren", trenes_disponibles)

with col2:
    # Selector para todos los coches, incluyendo una opción para ver "Todos"
    coches_disponibles = ["Todos"] + COCHES
    filtro_coche = st.selectbox("Seleccionar Coche", coches_disponibles)

st.divider()

# --- Lógica para mostrar estadísticas ---
try:
    # Pasamos None si el usuario selecciona "Todos"
    tren_a_buscar = filtro_tren if filtro_tren != "Todos" else None
    coche_a_buscar = filtro_coche if filtro_coche != "Todos" else None

    df_estadisticas = obtener_estadisticas_fallas(filtro_tren=tren_a_buscar, filtro_coche=coche_a_buscar)

    if df_estadisticas.empty:
        st.info("No se encontraron datos de fallas con los filtros seleccionados.")
    else:
        st.subheader("Ranking de Fallas Recurrentes")
        # Usamos st.dataframe para una tabla interactiva y con buen formato
        
        # Función para resaltar solo los números en la columna 'Cantidad'
        def resaltar_cantidad(val):
            return 'color: red; font-weight: bold;' if val > 1 else ''

        st.dataframe(df_estadisticas.style.map(resaltar_cantidad, subset=['Cantidad']), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"❌ Ocurrió un error al obtener las estadísticas: {e}")
    st.info("Asegúrate de que la conexión a la base de datos esté funcionando correctamente.")