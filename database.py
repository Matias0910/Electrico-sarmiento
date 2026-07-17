from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure, ConfigurationError
import os
from dotenv import load_dotenv
import pandas as pd
import streamlit as st

from datetime import datetime

# Cargar variables de entorno desde un archivo .env
load_dotenv()

# Usa variables de entorno para la URI de conexión para mayor seguridad.
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "app_castelar" 
COLLECTION_NAME = "informes_mantenimiento"

# --- Cliente de base de datos centralizado ---
# Usamos cache_resource para crear una única conexión que persiste.
@st.cache_resource
def init_connection():
    """Inicializa la conexión a MongoDB y muestra errores en la UI si falla."""
    if not MONGO_URI:
        st.error("Error Crítico: La variable de entorno MONGO_URI no está definida. Revisa tu archivo `.env`.")
        return None
    try:
        # Usamos un timeout para no esperar indefinidamente si el servidor no responde.
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        client.admin.command('ping')
        print("✅ Conexión a MongoDB establecida con éxito.")
        return client
    except (ConnectionFailure, ConfigurationError) as e:
        st.error(f"❌ No se pudo conectar a la base de datos. Error: {e}")
        st.warning("Asegúrate de que la MONGO_URI en tu archivo `.env` es correcta y que el servidor de MongoDB está funcionando.")
        return None

# --- Inicialización de la conexión ---
client = init_connection()

# Las colecciones serán None si la conexión falla, y las funciones lo manejarán.
db = client[DB_NAME] if client is not None else None
collection = db[COLLECTION_NAME] if db is not None else None
documentos_collection = db["documentos_importantes"] if db is not None else None

def registrar_mantenimiento(registro):
    if collection is None:
        raise ConnectionFailure("No hay conexión a la base de datos. Revisa la consola o la URI de conexión.")
    try:
        resultado = collection.insert_one(registro)
        print(f"Éxito: Documento insertado con ID {resultado.inserted_id}")
        return resultado.inserted_id
    except OperationFailure as e:
        print(f"ERROR AL GUARDAR EN MONGODB: {e}")
        raise e # Re-lanzamos la excepción para que la app principal la maneje

def buscar_informes(query={}):
    if collection is None:
        raise ConnectionFailure("No hay conexión a la base de datos. Revisa la consola o la URI de conexión.")
    # Ordena por fecha descendente para mostrar los más recientes primero
    return collection.find(query).sort("fecha", -1) 

def obtener_todos_los_informes():
    """Obtiene todos los informes de la base de datos como una lista."""
    if collection is None:
        raise ConnectionFailure("No hay conexión a la base de datos. Revisa la consola o la URI de conexión.")
    return list(collection.find({}).sort("fecha", -1))

def eliminar_informe(informe_id):
    if collection is None:
        raise ConnectionFailure("No hay conexión a la base de datos. Revisa la consola o la URI de conexión.")
    resultado = collection.delete_one({"_id": informe_id})
    return resultado.deleted_count

def eliminar_tarea_de_informe(informe_id, tarea_a_eliminar):
    """Elimina una tarea específica de la lista de tareas de un informe."""
    if collection is None:
        raise ConnectionFailure("No hay conexión a la base de datos.")
    
    resultado = collection.update_one(
        {"_id": informe_id},
        {"$pull": {"tareas": tarea_a_eliminar}}
    )
    return resultado.modified_count

def agregar_tarea_a_informe(informe_id, nueva_tarea):
    """Agrega una nueva tarea a la lista de tareas de un informe existente."""
    if collection is None:
        raise ConnectionFailure("No hay conexión a la base de datos.")
    
    resultado = collection.update_one(
        {"_id": informe_id},
        {"$push": {"tareas": nueva_tarea}}
    )
    return resultado.modified_count

@st.cache_data
def obtener_estadisticas_fallas(filtro_tren=None, filtro_coche=None):
    """
    Obtiene y procesa estadísticas de fallas desde MongoDB usando un pipeline de agregación.
    """
    if collection is None:
        raise ConnectionFailure("No hay conexión a la base de datos.")

    pipeline = []

    # Paso 1: Filtrar por tren si se especifica
    if filtro_tren:
        pipeline.append({"$match": {"tren": filtro_tren}})

    # Paso 2: Desenrollar el array de tareas para procesar cada una individualmente
    pipeline.append({"$unwind": "$tareas"})

    # Paso 3: Excluir tareas que no son consideradas fallas
    tareas_a_excluir = [
        "PRECINTOS NUMÉRICOS",
        "LIMPIEZA SIV (BIMESTRAL)",
        "LIMPIEZA COMPRESORES (QUINCENAL)"
    ]
    pipeline.append({
        "$match": {
            "tareas.sistema": {"$nin": tareas_a_excluir}
        }
    })

    # Paso 4: Filtrar por coche si se especifica
    if filtro_coche:
        pipeline.append({"$match": {"tareas.datos.Coche": filtro_coche}})

    # Paso 5: Agrupar por sistema (nombre de la tarea) y causa
    # Se usa $ifNull para manejar tareas que no tienen 'Causa' (ej. Notas, Limpieza)
    pipeline.append({
        "$group": {
            "_id": {
                "sistema": "$tareas.sistema",
                "causa": {"$ifNull": ["$tareas.datos.Causa", "N/A"]},
                "coche": {"$ifNull": ["$tareas.datos.Coche", "N/A"]},
                "tren": "$tren"
            },
            "cantidad": {"$sum": 1}
        }
    })

    # Paso 6: Ordenar por cantidad de forma descendente
    pipeline.append({"$sort": {"cantidad": -1}})

    # Paso 7: Proyectar para un formato de salida más limpio y legible
    pipeline.append({
        "$project": {
            "_id": 0,
            "Tren": "$_id.tren",
            "Coche": "$_id.coche",
            "Componente / Tarea": "$_id.sistema",
            "Causa de la Falla": "$_id.causa",
            "Cantidad": "$cantidad"
        }
    })

    resultados = list(collection.aggregate(pipeline))
    
    return pd.DataFrame(resultados)

def guardar_documento(titulo, descripcion, nombre_archivo, categoria, codigo_falla=None):
    """Guarda la metadata de un nuevo documento en la base de datos."""
    if documentos_collection is None:
        raise ConnectionFailure("No hay conexión a la base de datos.")
    documento = {
        "titulo": titulo,
        "descripcion": descripcion,
        "categoria": categoria,
        "codigo_falla": str(codigo_falla) if codigo_falla else None,
        "nombre_archivo": nombre_archivo,
        "fecha_carga": datetime.now()
    }
    return documentos_collection.insert_one(documento)

def obtener_documentos(texto_busqueda=None, categoria=None, codigo_falla=None):
    """
    Obtiene documentos de la base de datos, con filtros opcionales.
    - texto_busqueda: Busca en el título y la descripción.
    - categoria: Filtra por una categoría específica.
    """
    if documentos_collection is None:
        raise ConnectionFailure("No hay conexión a la base de datos.")
    
    # Lista de condiciones que deben cumplirse todas (AND)
    query_conditions = []
    
    if codigo_falla and codigo_falla.strip():
        regex_codigo = {"$regex": codigo_falla.strip(), "$options": "i"}
        query_conditions.append({"codigo_falla": regex_codigo})

    if texto_busqueda and texto_busqueda.strip():
        regex_texto = {"$regex": texto_busqueda, "$options": "i"}
        query_conditions.append({"$or": [{"titulo": regex_texto}, {"descripcion": regex_texto}]})

    if categoria and categoria != "Todos":
        query_conditions.append({"categoria": categoria})

    # Construimos la consulta final. Si hay condiciones, las unimos con AND.
    query = {"$and": query_conditions} if query_conditions else {}
    
    return documentos_collection.find(query).sort("fecha_carga", -1)

def buscar_evento(codigo=None, texto=None, categoria=None):
    """
    Busca eventos por código, texto libre y/o categoría.
    """
    if db is None:
        raise ConnectionFailure("No hay conexión a la base de datos.")

    eventos_collection = db["eventos_fallas"]

    query_conditions = []
    if codigo and codigo.strip():
        query_conditions.append({"codigo_tcms": {"$regex": codigo, "$options": "i"}})
    
    if texto and texto.strip():
        regex_texto = {"$regex": texto, "$options": "i"}
        query_conditions.append({
            "$or": [
                {"evento": regex_texto},
                {"descripcion": regex_texto}
            ]
        })
    
    if categoria and categoria != "Todas":
        query_conditions.append({"categoria": categoria})

    query = {"$and": query_conditions} if query_conditions else {}
    return list(eventos_collection.find(query))