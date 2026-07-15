import json
import os
import re
import unicodedata

import google.generativeai as genai


try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
except Exception as e:
    print(f"ADVERTENCIA: No se pudo configurar la API de Google. Error: {e}")
    model = None


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
    respuesta_texto = ""

    if not model:
        print("El modelo de IA no esta inicializado. Revisa tu GOOGLE_API_KEY.")
        return []

    comando_normalizado = normalizar_comando_usuario(comando_usuario)

    prompt = f"""
    Tu tarea es actuar como un asistente para una aplicacion de mantenimiento de trenes.
    Debes analizar el comando del usuario y convertirlo en una lista de objetos JSON que representen tareas.
    Cada objeto debe tener las claves "sistema" y "datos".
    Si el comando del usuario no parece ser una tarea de mantenimiento valida o no puedes interpretarlo, devuelve [].

    Reglas importantes:
    - Responde unicamente con JSON valido, sin explicaciones ni bloque markdown.
    - Usa exactamente los nombres de sistemas y campos indicados en los ejemplos.
    - El sistema de fusibles debe llamarse "FUSIBLES (PATÍN)".
    - El campo interno para bogie debe llamarse exactamente "Boguie", aunque el usuario diga "bogie".
    - Interpreta bogie, boji, bujie, bogy, bougie o variantes similares como "Boguie".
    - Si el usuario dice bogie 1, bogie uno, primer bogie o delantero, usa "Boguie": "Boguie 1".
    - Si el usuario dice bogie 2, bogie dos, segundo bogie o trasero, usa "Boguie": "Boguie 2".
    - Si el usuario dice lado norte o norte, usa "Lado": "Norte".
    - Si el usuario dice lado sur o sur, usa "Lado": "Sur".

    Ejemplos:

    Comando de usuario: "agrega un fusible quemado en el coche TC1, bogie 1, lado norte"
    Respuesta JSON esperada:
    [
        {{
            "sistema": "FUSIBLES (PATÍN)",
            "datos": {{
                "Coche": "TC1",
                "Boguie": "Boguie 1",
                "Lado": "Norte",
                "Causa": "Quemado"
            }}
        }}
    ]

    Comando de usuario: "fusible quemado en TC2 boji dos lado sur"
    Respuesta JSON esperada:
    [
        {{
            "sistema": "FUSIBLES (PATÍN)",
            "datos": {{
                "Coche": "TC2",
                "Boguie": "Boguie 2",
                "Lado": "Sur",
                "Causa": "Quemado"
            }}
        }}
    ]

    Comando de usuario: "camara de pupitre en TC2 no funciona"
    Respuesta JSON esperada:
    [
        {{
            "sistema": "CAMARAS",
            "datos": {{
                "Coche": "TC2",
                "Ubicacion": "Pupitre",
                "Causa": "No funciona"
            }}
        }}
    ]

    Ahora procesa el siguiente comando.
    Comando de usuario: "{comando_normalizado}"
    """

    try:
        response = model.generate_content(prompt)
        respuesta_texto = getattr(response, "text", "") or ""

        json_text = respuesta_texto.strip().replace("```json", "").replace("```", "").strip()

        if not json_text or not json_text.startswith("["):
            print(f"La IA devolvio una respuesta no valida o vacia: {respuesta_texto}")
            return []

        tareas = json.loads(json_text)
        return tareas if isinstance(tareas, list) else []
    except Exception as e:
        print(f"Error al interpretar la respuesta de la IA: {e}")
        if respuesta_texto:
            print(f"Respuesta recibida que causo el error: {respuesta_texto}")
        return []
