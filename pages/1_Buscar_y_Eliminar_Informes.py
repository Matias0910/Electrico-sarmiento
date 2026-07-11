import streamlit as st
from database import buscar_informes, eliminar_informe, eliminar_tarea_de_informe
from datetime import datetime
from bson.objectid import ObjectId

st.set_page_config(page_title="Buscar Informes", layout="wide")
st.title("🔎 Buscar y Eliminar Informes")

st.write("Aquí puedes ver y eliminar los informes de mantenimiento guardados.")

# --- Filtros de Búsqueda ---
st.subheader("Filtrar informes")
col1, col2, col3 = st.columns(3)

filtro_tren = col1.text_input("Buscar por N° de tren")
filtro_fecha = col2.date_input("Buscar por fecha", value=None, help="Busca todos los informes de la fecha seleccionada.")
filtro_tipo = col3.selectbox("Filtrar por tipo", ["Todos", "Bimestral", "Quincenal"])

# Construir la consulta para MongoDB
query = {}
if filtro_tren:
    query["tren"] = filtro_tren
if filtro_fecha:
    # Usamos una expresión regular para buscar todos los informes de un día específico,
    # ya que la fecha se guarda como una cadena ISO (con hora).
    query["fecha"] = {"$regex": f"^{filtro_fecha.strftime('%Y-%m-%d')}"}
if filtro_tipo != "Todos":
    query["tipo_informe"] = filtro_tipo


# --- Lista de Informes ---
st.divider()

try:
    informes = list(buscar_informes(query))

    if not informes:
        st.write("No se encontraron informes con los filtros seleccionados.")
    else:
        st.write(f"Se encontraron {len(informes)} informes.")

        for informe in informes:
            # Usar el ID del informe como clave para el expander
            informe_id_str = str(informe["_id"])
            tipo = informe.get('tipo_informe', 'N/D') # Obtiene el tipo o 'N/D' si no existe (para informes antiguos)
            
            # Formatear la fecha para que sea más legible
            fecha_str = informe.get('fecha', '')
            try:
                fecha_legible = datetime.fromisoformat(fecha_str).strftime('%d/%m/%Y %H:%M')
            except (ValueError, TypeError):
                fecha_legible = fecha_str # Si hay un error, muestra la fecha original
            
            with st.expander(f"**Tren {informe['tren']}** ({tipo}) - Fecha: {fecha_legible}"):
                st.write("**Tareas Realizadas:**")
                
                tareas = informe.get("tareas", [])
                if not tareas:
                    st.write("No hay tareas registradas para este informe.")
                else:
                    for i, tarea in enumerate(tareas):
                        col1, col2 = st.columns([0.9, 0.1])
                        with col1:
                            detalles = ", ".join([f"{k}: {v}" for k, v in tarea.get("datos", {}).items()])
                            st.markdown(f"**{tarea.get('sistema')}**: {detalles}")
                        with col2:
                            if st.button("🗑️", key=f"del_task_{informe_id_str}_{i}", help="Eliminar esta tarea"):
                                eliminar_tarea_de_informe(informe["_id"], tarea)
                                st.success("Tarea eliminada. La página se recargará.")
                                st.rerun()

                st.write("**Observaciones:**")
                st.write(informe.get("obs", "Sin observaciones."))

                st.write("---")
                if st.button("🗑️ Eliminar Informe", key=f"del_{informe_id_str}", type="primary"):
                    eliminar_informe(informe["_id"])
                    st.success(f"Informe del tren {informe['tren']} ({fecha_legible}) eliminado.")
                    st.rerun()
except Exception as e:
    st.error(f"❌ No se pudo conectar a la base de datos: {e}")
    st.info("Por favor, revisa tu cadena de conexión MONGO_URI y la consola para más detalles.")