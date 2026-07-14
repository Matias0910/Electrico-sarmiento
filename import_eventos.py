from pymongo import MongoClient, UpdateOne, errors
from dotenv import load_dotenv
import os
import pdfplumber

# Cargar variables de entorno
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "app_castelar"
COLLECTION_NAME = "documentos_importantes"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    client.admin.command('ping')
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
except (errors.ConnectionFailure, errors.ConfigurationError) as e:
    print(f"❌ Error de conexión a MongoDB: {e}")
    print("Asegúrate de que MONGO_URI en tu archivo .env es correcta y que el servidor está activo.")
    exit()
    
def importar_eventos_pdf(ruta_pdf, categoria):
    """
    Lee un PDF usando pdfplumber, maneja celdas combinadas (rowspan) y carga los datos en MongoDB.
    """
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            current_evento_data = {}
            operaciones = []

            def guardar_evento_anterior():
                if current_evento_data and current_evento_data.get("codigo_tcms"):
                    operaciones.append(UpdateOne(
                        {"codigo_tcms": current_evento_data["codigo_tcms"], "categoria": categoria},
                        {"$set": current_evento_data},
                        upsert=True
                    ))

            for page in pdf.pages:
                table = page.extract_table()
                if not table: continue

                for fila in table[1:]: # Saltar encabezado
                    # Limpiar saltos de línea dentro de las celdas
                    fila_limpia = [str(cell).replace('\n', ' ').strip() if cell is not None else "" for cell in fila]
                    
                    # Asignar a variables para mayor claridad
                    num_evento, nombre_evento, codigo_sistema, codigo_tcms, descripcion, resolucion, plano = (fila_limpia + [''] * 7)[:7]

                    # Si la fila define un nuevo evento (tiene número de evento)
                    if num_evento:
                        guardar_evento_anterior() # Guarda el evento que veníamos acumulando
                        
                        # Inicia un nuevo evento
                        current_evento_data = {
                            "numero_evento": num_evento,
                            "evento": nombre_evento,
                            "codigo_sistema": codigo_sistema,
                            "codigo_tcms": codigo_tcms,
                            "descripcion": [descripcion] if descripcion else [],
                            "resolucion": [resolucion] if resolucion else [],
                            "plano": plano,
                            "categoria": categoria
                        }
                    # Si es una fila de continuación (sin número de evento)
                    elif current_evento_data:
                        if descripcion: current_evento_data["descripcion"].append(descripcion)
                        if resolucion: current_evento_data["resolucion"].append(resolucion)
            
            guardar_evento_anterior() # Guarda el último evento procesado al final del PDF

            if operaciones:
                resultado = collection.bulk_write(operaciones)
                print(f"✅ {os.path.basename(ruta_pdf)}: {resultado.inserted_count} insertados, {resultado.modified_count} actualizados.")
            else:
                print(f"❌ No se pudo extraer ninguna fila de datos de '{os.path.basename(ruta_pdf)}'.")

    except Exception as e:
        print(f"❌ Error procesando {os.path.basename(ruta_pdf)}: {e}")

if __name__ == '__main__':
    print("--- Iniciando importación de eventos a MongoDB ---")
    
    # Mapeo de palabras clave a categorías. El script buscará estas palabras en los nombres de archivo.
    # Se pone "EDCU" antes que "DCU" para evitar que la coincidencia más corta ("DCU") se active primero
    # en un nombre de archivo que contiene "EDCU".
    CATEGORIAS_KEYWORD = ["TCMS", "EDCU", "DCU", "SIV", "EBCU", "HVAC", "PIDS"]

    script_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_folder_name = "_PDFs_para_importar"
    pdf_folder_path = os.path.join(script_dir, pdf_folder_name)

    if not os.path.exists(pdf_folder_path):
        os.makedirs(pdf_folder_path)
        print(f"\n📂 Se creó la carpeta '{pdf_folder_name}'.")
        print(f"👉 Por favor, mové todos tus PDFs de eventos a esta nueva carpeta y volvé a ejecutar el script.")
        exit()

    print(f"🔎 Buscando PDFs en la carpeta: {pdf_folder_path}\n")

    # --- Lógica de escaneo de archivos ---
    archivos_en_carpeta = os.listdir(pdf_folder_path)
    pdfs_encontrados = [f for f in archivos_en_carpeta if f.lower().endswith('.pdf')]

    if not pdfs_encontrados:
        print("No se encontraron archivos PDF en la carpeta. Nada para importar.")
    else:
        print(f"Se encontraron {len(pdfs_encontrados)} archivos PDF. Procesando...")
        for pdf_filename in pdfs_encontrados:
            categoria_encontrada = None
            # Intenta adivinar la categoría a partir del nombre del archivo
            for cat_keyword in CATEGORIAS_KEYWORD:
                if cat_keyword.lower() in pdf_filename.lower():
                    categoria_encontrada = cat_keyword
                    break
            
            if categoria_encontrada:
                ruta_completa_pdf = os.path.join(pdf_folder_path, pdf_filename)
                print(f"\n--- Importando '{pdf_filename}' como categoría '{categoria_encontrada}' ---")
                importar_eventos_pdf(ruta_completa_pdf, categoria_encontrada)
            else:
                print(f"\n⚠️ Omitiendo '{pdf_filename}': No se pudo determinar la categoría (TCMS, DCU, etc.) a partir del nombre.")
    
    # Verificación final
    total_eventos = collection.count_documents({"categoria": {"$in": CATEGORIAS_KEYWORD}}) 
    if total_eventos > 0: 
        print(f"\n--- ¡Éxito! Hay {total_eventos} eventos cargados en la base de datos. El buscador ya debería funcionar. ---") 
    else: 
        print("\n--- ⚠️ ¡Atención! No se cargaron eventos. El buscador mostrará 'No se encontró información'. ---") 
        print(f"--- Revisa que los PDFs estén en la carpeta '{pdf_folder_name}' y que el script no muestre errores. ---")