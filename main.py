# ==============================================================================
# ARCHIVO: main.py
# PROPÓSITO: Este archivo es el "motor" principal de nuestro bot. Su única
# responsabilidad es tomar la ruta de una imagen, procesarla paso a paso
# (OCR -> IA -> Google Sheets) y devolver si el proceso fue exitoso.
# Es completamente independiente de WhatsApp; podría ser llamado desde
# cualquier otra aplicación.
# ==============================================================================


# --- 1. IMPORTACIONES ---
import os  # Para interactuar con el sistema operativo, como verificar si un archivo existe.
import json  # Para trabajar con el formato de datos JSON, que es el que nos devuelve la IA.
import pytesseract  # La librería que nos permite hablar con el programa Tesseract OCR.
import cv2  # La librería OpenCV, nuestra navaja suiza para todo lo relacionado con imágenes.
import gspread  # La librería que simplifica enormemente la comunicación con Google Sheets.
import google.generativeai as genai  # La librería oficial de Google para usar la IA Gemini.
from dotenv import load_dotenv  # Una utilidad para cargar "secretos" desde un archivo .env.


# --- 2. CONFIGURACIÓN CENTRALIZADA ---
# Agrupamos todas las variables de configuración en un solo lugar.
# Esto hace que sea muy fácil cambiar cosas en el futuro sin tener que buscar
# por todo el código.

# Ejecuta la función para cargar las variables del archivo .env a la memoria.
load_dotenv()

# Configuración de la API de Google Gemini.
# os.getenv("GEMINI_API_KEY") busca una variable llamada "GEMINI_API_KEY"
# que cargamos desde el archivo .env.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configuración de Google Sheets.
# Guardamos los nombres de los archivos y de la hoja para no tener que escribirlos
# repetidamente en el código (esto se llama "hardcodear" y es una mala práctica).
GOOGLE_SHEETS_CREDENTIALS_FILE = 'credentials.json'
GOOGLE_SHEETS_NAME = "Registros de gastos"


# --- 3. DEFINICIÓN DE FUNCIONES ---
# Aquí definimos nuestras "estaciones de trabajo". Cada función es un obrero
# especializado que realiza una sola tarea y la hace bien.

def configurar_servicios():
    """
    Esta función es un "chequeo de calidad" inicial.
    Verifica que tengamos acceso a los servicios externos (como Gemini)
    antes de empezar el trabajo pesado. Si algo falta, detiene el programa.
    """
    print("Iniciando configuración de servicios...")
    
    # Verificamos que la clave de API de Gemini fue cargada correctamente.
    if not GEMINI_API_KEY:
        # Si no existe, lanzamos un error claro y el programa se detiene.
        raise ValueError("No se encontró la GEMINI_API_KEY en el archivo .env")
    
    # Si la clave existe, la usamos para configurar la librería de Gemini.
    genai.configure(api_key=GEMINI_API_KEY)
    print("-> Servicios configurados con éxito.")


def extraer_texto_de_imagen(ruta_imagen: str) -> str:
    """
    ESTACIÓN DE TRABAJO 1: El Digitalizador (OCR).
    Recibe la ruta de una imagen, la limpia y extrae todo el texto que contiene.
    
    El `: str` y `-> str` son "type hints" (pistas de tipo). Le dicen a otros
    programadores (y a nosotros mismos en el futuro) que esta función espera
    un `string` (texto) como entrada y devuelve otro `string`.
    """
    # Verificación de seguridad: ¿existe realmente el archivo que nos pasaron?
    if not os.path.exists(ruta_imagen):
        raise FileNotFoundError(f"La imagen no se encontró en la ruta: {ruta_imagen}")

    # Paso 3.1: Leer la imagen del disco duro usando OpenCV.
    imagen_cv = cv2.imread(ruta_imagen)
    
    # Paso 3.2: Convertir la imagen a escala de grises.
    # El color puede confundir al OCR, así que lo eliminamos.
    gris = cv2.cvtColor(imagen_cv, cv2.COLOR_BGR2GRAY)
    
    # Paso 3.3: Usar Pytesseract para hacer el OCR sobre la imagen en grises.
    # - 'lang="spa"' le dice a Tesseract que espere texto en español.
    # - 'config' son parámetros avanzados para Tesseract. '--psm 4' asume
    #   que el ticket es un único bloque de texto, lo que suele dar buenos resultados.
    config = r'--oem 3 --psm 4' 
    texto = pytesseract.image_to_string(gris, lang='spa', config=config)
    
    # Devolvemos el texto extraído.
    return texto


def analizar_texto_con_gemini(texto_ticket: str) -> dict | None:
    """
    ESTACIÓN DE TRABAJO 2: El Analista (IA).
    Recibe el texto crudo y desordenado y lo convierte en datos limpios y estructurados.
    Devuelve un diccionario (como un objeto JSON) o None si algo sale mal.
    """
    # Configuración del modelo de IA.
    # 'temperature=0.0' le pide a la IA que sea lo más lógica y menos "creativa" posible.
    generation_config = {"temperature": 0.0}
    model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)

    # El "Prompt": Es el corazón de la IA. Son las instrucciones exactas que le damos.
    # Un buen prompt es la diferencia entre el éxito y el fracaso.
    # Usamos f-strings (la 'f' antes de las comillas) para poder insertar el
    # {texto_ticket} dentro de un bloque de texto grande.
    prompt = f"""
    Tu única función es convertir el texto de un ticket de compra en un objeto JSON estructurado.
    No debes dar explicaciones, resúmenes ni análisis. Tu respuesta DEBE SER solo el JSON y nada más.

    Sigue esta estructura y estas reglas:
    {{
      "comercio": "string",
      "fecha": "string con formato YYYY-MM-DD",
      "items": [
        {{ "descripcion": "string", "precio": float }}
      ],
      "subtotal": float,
      "descuento": float,
      "total": float,
      "categoria": "string"
    }}
    
    Reglas de la categoría: Debes elegir OBLIGATORIAMENTE una de las siguientes opciones: ["Materia prima", "Bebidas", "Limpieza y Descartables", "Mantenimiento", "Administrativo", "Otro"].

    --- TAREA REAL ---
    Texto a procesar:
    {texto_ticket}
    
    Salida JSON:
    """
    try:
        # Hacemos la llamada a la API de Gemini.
        response = model.generate_content(prompt)
        
        # A veces la IA devuelve el JSON rodeado de ```json ... ```.
        # Estas líneas limpian cualquier texto extra para quedarnos solo con el JSON.
        texto_json = response.text.strip().replace("```json", "").replace("```", "").strip()
        
        # Convertimos el texto JSON a un diccionario de Python. Si el texto no es
        # un JSON válido, esta línea dará un error que será capturado por el 'except'.
        return json.loads(texto_json)
    except Exception as e:
        # Si algo falla (la IA no responde, devuelve texto inválido, etc.),
        # lo imprimimos en la consola para depurar y devolvemos None.
        print(f"Error durante el análisis con Gemini: {e}")
        print(f"Respuesta recibida que causó el error: {response.text if 'response' in locals() else 'No response'}")
        return None


def guardar_en_google_sheets(datos_gasto: dict) -> bool:
    """
    ESTACIÓN DE TRABAJO 3: El Archivista.
    Recibe los datos estructurados y los guarda como una nueva fila en Google Sheets.
    Devuelve True si tiene éxito, False si no.
    """
    try:
        # Definimos los "permisos" que nuestra cuenta de servicio necesita.
        # Necesita poder ver los archivos de Drive y editar las Hojas de Cálculo.
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        # Nos autenticamos con Google usando nuestro archivo de credenciales.
        gc = gspread.service_account(filename=GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=scopes)
        
        # Abrimos la hoja de cálculo por su nombre.
        spreadsheet = gc.open(GOOGLE_SHEETS_NAME)
        worksheet = spreadsheet.sheet1 # Seleccionamos la primera hoja.
        
        # Preparamos la columna 'items'. Como es una lista de productos, la convertimos
        # en un solo texto, separando cada producto con una coma.
        # Esto es una "list comprehension", una forma compacta y eficiente de crear listas en Python.
        items_lista = datos_gasto.get('items', [])
        items_texto = ", ".join([f"{item.get('descripcion', '')} (${item.get('precio', 0.0):.2f})" for item in items_lista])
        
        # Creamos la lista de valores que vamos a insertar.
        # El orden DEBE coincidir con el orden de las columnas en tu Google Sheet.
        # .get('clave', 'valor_por_defecto') es una forma segura de acceder a un diccionario.
        # Si la clave no existe, no da error, sino que usa el valor por defecto.
        fila_para_insertar = [
            datos_gasto.get('fecha', 'N/A'),
            datos_gasto.get('comercio', 'N/A'),
            datos_gasto.get('categoria', 'N/A'),
            datos_gasto.get('total', 0.0),
            items_texto
        ]
        
        # El comando mágico que añade la fila al final de la hoja.
        worksheet.append_row(fila_para_insertar)
        return True # Si llegamos hasta aquí, todo salió bien.

    except gspread.exceptions.SpreadsheetNotFound:
        # Un 'except' específico para el error más común: no encontrar la hoja.
        print(f"ERROR: No se encontró la hoja de cálculo llamada '{GOOGLE_SHEETS_NAME}'.")
        return False
    except Exception as e:
        # Un 'except' genérico para cualquier otro problema (falta de permisos, etc.).
        print(f"Ocurrió un error al guardar en Google Sheets: {e}")
        return False


# --- 4. FUNCIÓN PRINCIPAL DE ORQUESTACIÓN ---
# Esta función es como el "jefe de planta". No hace el trabajo directamente,
# pero se asegura de que el producto (el ticket) pase por todas las estaciones
# en el orden correcto.

def procesar_gasto_completo(ruta_imagen: str) -> bool:
    """
    Orquesta todo el proceso: OCR -> IA -> Guardado.
    Devuelve True si todo el proceso es exitoso, False si cualquier paso falla.
    """
    try:
        print("-" * 50)
        print(f"Iniciando procesamiento para la imagen: {ruta_imagen}")

        # --- Inicia la cadena de montaje ---
        print("Paso 1: Extrayendo texto de la imagen (OCR)...")
        texto_crudo = extraer_texto_de_imagen(ruta_imagen)
        if not texto_crudo.strip(): # .strip() elimina espacios en blanco al inicio y final.
            print("-> Fallo: No se pudo extraer texto.")
            return False # Si no hay texto, detenemos todo.
        print("-> Éxito: Texto extraído.\n")
        
        print("Paso 2: Analizando texto con Gemini para estructurar datos...")
        datos_del_gasto = analizar_texto_con_gemini(texto_crudo)
        if not datos_del_gasto:
            print("-> Fallo: El análisis de la IA no produjo resultados válidos.")
            return False # Si la IA falla, detenemos todo.
        print("-> Éxito: Análisis completado.\n")
        
        print("Paso 3: Guardando datos en Google Sheets...")
        exito_al_guardar = guardar_en_google_sheets(datos_del_gasto)
        
        return exito_al_guardar # Devolvemos el resultado del último paso.

    except FileNotFoundError as e:
        print(f"[ERROR CRÍTICO] Archivo de imagen no encontrado: {e}")
        return False
    except Exception as e:
        print(f"[ERROR CRÍTICO] Ocurrió un error inesperado en el proceso: {e}")
        return False


# --- 5. PUNTO DE ENTRADA DEL SCRIPT ---
# Este bloque de código especial `if __name__ == "__main__":` solo se ejecuta
# cuando corres este archivo directamente (`python main.py`).
# No se ejecuta si este archivo es importado desde otro (como desde `bot_server.py`).
# Lo usamos como nuestro "banco de pruebas" para testear el motor de forma aislada.

if __name__ == "__main__":
    try:
        # Primero, hacemos el chequeo de calidad.
        configurar_servicios()
        
        # Definimos la imagen que vamos a usar para la prueba.
        IMAGEN_A_PROCESAR = "tickets/t1.jpg" 
        
        # Llamamos a nuestra función "jefe de planta".
        exito = procesar_gasto_completo(IMAGEN_A_PROCESAR)
        
        # Imprimimos un resumen final basado en el resultado.
        if exito:
            print("\n==========================")
            print("   PROCESO DE PRUEBA COMPLETADO CON ÉXITO")
            print("==========================")
        else:
            print("\n--------------------------")
            print("   EL PROCESO DE PRUEBA FALLÓ EN ALGÚN PUNTO")
            print("--------------------------")

    except Exception as e:
        print(f"El programa no pudo iniciar debido a un error de configuración: {e}")