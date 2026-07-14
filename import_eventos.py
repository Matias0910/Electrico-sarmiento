from pymongo import MongoClient, UpdateOne, errors
from dotenv import load_dotenv
import os
import pdfplumber

# Cargar variables de entorno
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "app_castelar"
COLLECTION_NAME = "eventos_fallas" # Corregido: Apuntar a la colección de eventos

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    client.admin.command('ping')
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
except (errors.ConnectionFailure, errors.ConfigurationError, errors.ServerSelectionTimeoutError) as e:
    print(f"❌ Error de conexión a MongoDB: {e}")
    print("Asegúrate de que MONGO_URI en tu archivo .env es correcta y que el servidor está activo.")
    exit()
    
def importar_eventos_pdf(ruta_pdf, categoria):
    """
    Lee un PDF usando pdfplumber, maneja celdas combinadas (rowspan) y carga los datos en MongoDB.
    """
    # --- Plantillas de Mapeo de Columnas por Categoría ---
    # Define las palabras clave para encontrar cada columna, adaptado a cada tipo de PDF.
    MAPEO_COLUMNAS = {
        "TCMS": {
            'num_evento': ['n°', 'evento'], 'evento': ['evento', 'tcms'], 'codigo_sistema': [],
            'codigo_tcms': ['código', 'tcms'], 'descripcion': ['descrip', 'descrip'], 'resolucion': ['resolución'], 'plano': ['plano']
        },
        "DCU": {
            'num_evento': ['n°', 'evento'], 'evento': ['evento', 'dcu'], 'codigo_sistema': ['código', 'dcu'],
            'codigo_tcms': ['código', 'tcms'], 'descripcion': ['descrip', 'descrip'], 'resolucion': ['resolución'], 'plano': ['plano']
        },
        "SIV": {
            'num_evento': ['n°', 'evento'], 'evento': ['siv'], 'codigo_sistema': ['cód', 'siv'],
            'codigo_tcms': ['cód', 'tcms'], 'descripcion': ['descrip', 'descrip'], 'resolucion': ['resolución'], 'plano': ['plano']
        },
        "EBCU": {
            'num_evento': ['n°', 'evento'], 'evento': ['evento', 'knorr'], 'codigo_sistema': ['cód', 'ebcu'],
            'codigo_tcms': ['cód', 'tcms'], 'descripcion': ['descrip', 'descrip'], 'resolucion': ['resolución'], 'plano': ['plano']
        },
        "HVAC": {
            'num_evento': ['n°', 'evento'], 'evento': ['eventos', 'tcms', 'havc'], 'codigo_sistema': [], # Se deja vacío para ignorar la 3ra columna si no tiene un título útil
            'codigo_tcms': ['cód', 'tcms'], 'descripcion': ['descrip', 'descrip'], 'resolucion': ['resolución'], 'plano': ['plano'] # Buscará 'cód. tcms' donde lo encuentre
        },
        "EDCU": {
            'num_evento': ['n°', 'evento'], 'evento': ['evento', 'edcu'], 'codigo_sistema': [],
            'codigo_tcms': ['código', 'tcms'], 'descripcion': ['descrip', 'descrip'], 'resolucion': ['resolución'], 'plano': ['plano']
        },
        "PIDS": {
            'num_evento': ['n°', 'evento'], 'evento': ['eventos', 'tcms', 'pids'], 'codigo_sistema': [],
            'codigo_tcms': ['cód', 'tcms'], 'descripcion': ['descrip', 'descrip'], 'resolucion': ['resolución'], 'plano': ['plano']
        },
        "DEFAULT": { # Plantilla por defecto si la categoría no coincide
            'num_evento': ['n°', 'evento'], 'evento': ['evento'], 'codigo_sistema': ['código', 'sistema'],
            'codigo_tcms': ['código', 'tcms'], 'descripcion': ['descripción', 'descripición'], 'resolucion': ['resolución'], 'plano': ['plano']
        }
    }

    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            operaciones = []
            eventos_acumulados = {} # Diccionario para manejar eventos que se extienden por varias filas

            for page in pdf.pages:
                table = page.extract_table()
                if not table: continue

                # --- Lógica de mapeo dinámico de columnas (mejorada) ---
                # Normalizamos el encabezado para hacerlo más robusto: quitamos espacios, puntos y saltos de línea.
                header_raw = [str(h).lower().replace('\n', ' ').strip() if h else '' for h in table[0]]
                header_normalized = [''.join(filter(str.isalnum, h)) for h in header_raw]
                
                # Función para encontrar el índice de una columna de forma flexible (mejorada)
                def find_col_index(keywords):
                    if not keywords: return -1 # Si no hay keywords, no se busca
                    for i, h in enumerate(header_raw):
                        if all(keyword in h for keyword in keywords):
                            return i
                    return -1 # No encontrado

                try:
                    # Selecciona la plantilla correcta según la categoría del archivo
                    plantilla = MAPEO_COLUMNAS.get(categoria, MAPEO_COLUMNAS["DEFAULT"])
                    idx_map = {campo: find_col_index(keywords) for campo, keywords in plantilla.items()}

                    # Validar que se encontraron las columnas esenciales
                    if idx_map['num_evento'] == -1 or idx_map['descripcion'] == -1:
                        raise ValueError("No se encontraron las columnas esenciales 'N° Evento' o 'Descripción'.")

                except ValueError as e:
                    print(f"⚠️  Omitiendo página en '{os.path.basename(ruta_pdf)}': {e}. Encabezado encontrado: {header_raw}")
                    continue

                for fila in table[1:]: # Iterar sobre las filas de datos
                    fila_limpia = [str(c).replace('\n', ' ').strip() if c is not None else "" for c in fila]

                    # Función auxiliar para obtener datos de forma segura
                    def get_data(field_name):
                        return fila_limpia[idx_map[field_name]] if field_name in idx_map and idx_map[field_name] != -1 and idx_map[field_name] < len(fila_limpia) else ""

                    num_evento = get_data('num_evento')

                    # Si la fila define un nuevo evento (tiene "N° Evento")
                    if num_evento:
                        # El código TCMS es la clave única para agrupar filas
                        # Usamos el código TCMS si existe, si no, el código de sistema, si no, el número de evento como fallback.
                        codigo_tcms = get_data('codigo_tcms') or get_data('codigo_sistema') or num_evento

                        if not codigo_tcms: continue # Si no hay código, no podemos procesar el evento

                        eventos_acumulados[codigo_tcms] = {
                            "numero_evento": num_evento,
                            "evento": get_data('evento'),
                            "codigo_sistema": get_data('codigo_sistema'),
                            "codigo_tcms": codigo_tcms,
                            "descripcion": [get_data('descripcion')] if get_data('descripcion') else [],
                            "resolucion": [get_data('resolucion')] if get_data('resolucion') else [],
                            "plano": get_data('plano'),
                            "categoria": categoria
                        }
                    # Si es una fila de continuación (sin "N° Evento"), la agregamos al último evento que tenga código
                    elif eventos_acumulados:
                        ultimo_codigo = list(eventos_acumulados.keys())[-1]
                        if get_data('descripcion'): eventos_acumulados[ultimo_codigo]["descripcion"].append(get_data('descripcion'))
                        if get_data('resolucion'): eventos_acumulados[ultimo_codigo]["resolucion"].append(get_data('resolucion'))

            # --- Guardado en Base de Datos ---
            for evento_data in eventos_acumulados.values():
                operaciones.append(UpdateOne(
                    {"codigo_tcms": evento_data["codigo_tcms"], "categoria": categoria},
                    {"$set": evento_data},
                    upsert=True
                ))
                
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