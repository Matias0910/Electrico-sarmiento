from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure, ConfigurationError
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde un archivo .env
load_dotenv()

# Usa variables de entorno para la URI de conexión para mayor seguridad.
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "app_castelar" 
COLLECTION_NAME = "informes_mantenimiento"

# --- Cliente de base de datos centralizado ---
# Se crea una sola instancia del cliente para ser reutilizada en toda la aplicación.
client = None
collection = None

if not MONGO_URI:
    print("❌ Error: La variable de entorno MONGO_URI no está definida.")
    # En una app de Streamlit, st.error() sería más visible, pero esto funciona al inicio.
else:
    try:
        client = MongoClient(MONGO_URI)
        # La siguiente línea verifica que la conexión se estableció correctamente.
        client.admin.command('ping')
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        print("✅ Conexión a MongoDB establecida con éxito.")
    except (ConnectionFailure, ConfigurationError) as e:
        print(f"❌ Error de conexión o configuración de MongoDB: {e}")
        # La colección permanecerá como None, las funciones lo manejarán.

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