import json
import os
import re
import unicodedata

import google.generativeai as genai
from dotenv import load_dotenv


load_dotenv()

ultimo_error_ia = ""

try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"))
except Exception as e:
    print(f"ADVERTENCIA: No se pudo configurar la API de Google. Error: {e}")
    model = None


def obtener_ultimo_error_ia():
    return ultimo_error_ia


def normalizar_comando_usuario(comando_usuario):
    reemplazos = {
        r"\bbo+g+i+e+\b": "bogie",
        r"\bbo+g+u+i+e?\b": "bogie",
        r"\bbo+ji+e?\b": "bogie",
        r"\bbo+ji+a?\b": "bogie",
        r"\bbu+ji+e?\b": "bogie",
        r"\bbu+ji+a?\b": "bogie",
        r"\bbo+gy+\b": "bogie",
        r"\bbougie\b": "bogie",
    }

    comando_normalizado = comando_usuario or ""
    comando_normalizado = unicodedata.normalize("NFKD", comando_normalizado)
    comando_normalizado = "".join(
        caracter for caracter in comando_normalizado
        if not unicodedata.combining(caracter)
    )

    for patron, reemplazo in reemplazos.items():
        comando_normalizado = re.sub(
            patron,
            reemplazo,
            comando_normalizado,
            flags=re.IGNORECASE,
        )

    return comando_normalizado


def interpretar_comando_con_ia(comando_usuario):
    """
    Usa Gemini para interpretar un comando de lenguaje natural y convertirlo
    en una lista de tareas estructuradas.
    """
    global ultimo_error_ia

    respuesta_texto = ""
    ultimo_error_ia = ""

    if not model:
        ultimo_error_ia = "El modelo de IA no se inicializo. Revisa GOOGLE_API_KEY y GEMINI_MODEL."
        print(ultimo_error_ia)
        return []

    comando_normalizado = normalizar_comando_usuario(comando_usuario)

    prompt = f"""
    Tu tarea es actuar como un asistente para una aplicacion de mantenimiento de trenes.
    Debes analizar el comando del usuario y determinar la intencion: "agregar_tarea" o "buscar_falla".
    Responde SIEMPRE con un unico objeto JSON.

    Si la intencion es "agregar_tarea", el JSON debe tener la forma:
    {{"accion": "agregar_tarea", "tareas": [{{...}}]}}
    Donde "tareas" es una lista de objetos, cada uno con "sistema", "datos", "explicacion_falla" y "solucion_sugerida".

    Si la intencion es "buscar_falla", el JSON debe tener la forma:
    {{"accion": "buscar_falla", "codigo": "XXXX"}}
    Extrae el codigo de la falla del comando del usuario.

    Si no puedes interpretar el comando, devuelve: {{"accion": "error", "detalle": "No se pudo interpretar el comando."}}

    Reglas importantes:
    - Responde SIEMPRE con un unico objeto JSON valido, sin explicaciones ni bloque markdown.
    - Usa exactamente los nombres de sistemas y campos indicados en los ejemplos.
    - Para "agregar_tarea":
        - "explicacion_falla" debe explicar en una o dos oraciones, con palabras simples, que se detecto o que probablemente esta fallando.
        - "solucion_sugerida" debe proponer pasos generales y prudentes para diagnosticar o resolver la falla.
    - Para "buscar_falla":
        - El valor de "accion" debe ser "buscar_falla".
        - El valor de "codigo" debe ser el numero de falla extraido del texto.

    - No inventes mediciones, repuestos, codigos ni procedimientos especificos que el usuario no haya mencionado.
    - Si la tarea puede afectar seguridad, traccion, frenos o alta tension, indica que se debe aislar el equipo segun el procedimiento vigente y escalar a personal habilitado.
    - La solucion debe incluir "Verificar el manual y el procedimiento vigente" cuando no haya suficiente informacion para confirmar la causa.
    - El sistema de fusibles debe llamarse "FUSIBLES (PATÍN)".
    - El campo interno para bogie debe llamarse exactamente "Boguie", aunque el usuario diga "bogie".
    - Interpreta bogie, boji, bujie, bogy, bougie o variantes similares como "Boguie".
    - Si el usuario dice bogie 1, bogie uno, primer bogie o delantero, usa "Boguie": "Boguie 1".
    - Si el usuario dice bogie 2, bogie dos, segundo bogie o trasero, usa "Boguie": "Boguie 2".
    - Si el usuario dice lado norte o norte, usa "Lado": "Norte".
    - Si el usuario dice lado sur o sur, usa "Lado": "Sur".

    Ejemplos de Tareas:

    Comando de usuario: "agrega un fusible quemado en el coche TC1, bogie 1, lado norte"
    Respuesta JSON esperada:
    {{
        "accion": "agregar_tarea",
        "tareas": [
            {{
                "sistema": "FUSIBLES (PATÍN)",
                "datos": {{
                    "Coche": "TC1",
                    "Boguie": "Boguie 1",
                    "Lado": "Norte",
                    "Causa": "Quemado"
                }},
                "explicacion_falla": "El fusible del bogie 1, lado norte, esta quemado y el circuito que protege puede haber quedado sin alimentacion.",
                "solucion_sugerida": "Con el equipo aislado segun el procedimiento, revisar la causa de la sobrecorriente antes de reemplazar el fusible por otro de la especificacion correcta. Verificar el manual y el procedimiento vigente."
            }}
        ]
    }}

    Ejemplos de Busqueda:

    Comando de usuario: "que dice la falla 3101"
    Respuesta JSON esperada:
    {{
        "accion": "buscar_falla",
        "codigo": "3101"
    }}

    Comando de usuario: "dame info del codigo 1234"
    Respuesta JSON esperada:
    {{
        "accion": "buscar_falla",
        "codigo": "1234"
    }}

    Comando de usuario: "fusible quemado en TC2 boji dos lado sur"
    Respuesta JSON esperada:
    {{
        "accion": "agregar_tarea",
        "tareas": [
            {{
                "sistema": "FUSIBLES (PATÍN)",
                "datos": {{
                    "Coche": "TC2",
                    "Boguie": "Boguie 2",
                    "Lado": "Sur",
                    "Causa": "Quemado"
                }},
                "explicacion_falla": "El fusible informado esta quemado en el bogie 2, lado sur.",
                "solucion_sugerida": "Revisar el circuito protegido antes de reemplazar el fusible por uno de la especificacion correcta. Verificar el manual y el procedimiento vigente."
            }}
        ]
    }}

    Comando de usuario: "camara de pupitre en TC2 no funciona"
    Respuesta JSON esperada:
    {{
        "accion": "agregar_tarea",
        "tareas": [
            {{
                "sistema": "CAMARAS",
                "datos": {{
                    "Coche": "TC2",
                    "Ubicacion": "Pupitre",
                    "Causa": "No funciona"
                }},
                "explicacion_falla": "La camara del pupitre de TC2 no esta entregando una imagen funcional.",
                "solucion_sugerida": "Comprobar alimentacion, conexiones y estado de la camara siguiendo el procedimiento de mantenimiento. Verificar el manual y el procedimiento vigente."
            }}
        ]
    }}

    Ahora procesa el siguiente comando.
    Comando de usuario: "{comando_normalizado}"
    """

    try:
        response = model.generate_content(prompt)
        respuesta_texto = getattr(response, "text", "") or ""

        json_text = respuesta_texto.strip().replace("```json", "").replace("```", "").strip()

        if not json_text or not json_text.startswith("{"):
            ultimo_error_ia = "La IA devolvio una respuesta vacia o con un formato no valido."
            print(f"{ultimo_error_ia} Respuesta: {respuesta_texto}")
            return None

        respuesta_json = json.loads(json_text)
        if not isinstance(respuesta_json, dict) or "accion" not in respuesta_json:
            ultimo_error_ia = "La IA devolvio una estructura de respuesta no valida."
            return None

        return respuesta_json
    except Exception as e:
        ultimo_error_ia = f"Error al consultar Gemini: {e}"
        print(ultimo_error_ia)
        if respuesta_texto:
            print(f"Respuesta recibida que causo el error: {respuesta_texto}")
        return None


def generar_solucion_practica_con_ia(descripcion_tecnica, resolucion_tecnica):
    """
    Usa Gemini para generar una guía de resolución práctica a partir de datos técnicos.
    """
    global ultimo_error_ia

    if not model:
        ultimo_error_ia = "El modelo de IA no se inicializó."
        return "El modelo de IA no está disponible para generar una sugerencia."

    prompt = f"""
    Tu tarea es actuar como un asistente experto en mantenimiento de trenes.
    Recibirás la descripción técnica y la resolución de una falla.
    Tu objetivo es generar una guía práctica, paso a paso, para un técnico.

    Reglas:
    - Usa un lenguaje claro, directo y fácil de entender.
    - Enfócate en los pasos prácticos y verificaciones que el técnico debe realizar.
    - Si la resolución técnica menciona herramientas o mediciones, inclúyelas.
    - Si la falla es de seguridad (frenos, alta tensión, etc.), SIEMPRE debes empezar indicando que se debe consignar el equipo y seguir los procedimientos de seguridad vigentes.
    - No inventes información que no esté implícita en los datos proporcionados.
    - El resultado debe ser una lista de pasos o un párrafo conciso.

    Descripción Técnica de la Falla:
    {descripcion_tecnica}

    Resolución Técnica de la Base de Datos:
    {resolucion_tecnica}

    Ahora, genera la guía de resolución práctica:
    """
    try:
        response = model.generate_content(prompt)
        return getattr(response, "text", "") or "No se pudo generar una sugerencia."
    except Exception as e:
        ultimo_error_ia = f"Error al generar la solución práctica: {e}"
        return f"Error al contactar a la IA para generar la sugerencia: {e}"
