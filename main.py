# --- 1. IMPORTACIONES ---
# Importamos todas las librerías que nuestro programa necesita para funcionar.
import os
import json
import pytesseract
import cv2
import gspread
import google.generativeai as genai
from dotenv import load_dotenv

# --- 2. CONFIGURACIÓN CENTRALIZADA ---
# Centralizamos todas las variables de configuración aquí para que sean fáciles de modificar.

# Carga las variables de entorno (como nuestras claves secretas) desde el archivo .env
load_dotenv()

# Configuración de la ruta de Tesseract OCR (ajustar si es necesario)
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Configuración de la API de Google Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configuración de Google Sheets
GOOGLE_SHEETS_CREDENTIALS_FILE = 'credentials.json'
GOOGLE_SHEETS_NAME = "Registros de gastos"


# --- 3. FUNCIONES AUXILIARES ---
# Dividimos el programa en funciones pequeñas y específicas. Cada una hace una sola cosa.

def configurar_servicios():
    """
    Configura y valida las APIs y herramientas externas al inicio del programa.
    Si algo falla aquí, el programa se detiene con un error claro.
    """
    print("Iniciando configuración de servicios...")
    # Configuración de Tesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    if not os.path.exists(TESSERACT_PATH):
        raise FileNotFoundError(f"Tesseract no se encontró en la ruta: {TESSERACT_PATH}")

    # Configuración de Gemini
    if not GEMINI_API_KEY:
        raise ValueError("No se encontró la GEMINI_API_KEY en el archivo .env")
    genai.configure(api_key=GEMINI_API_KEY)
    print("-> Servicios configurados con éxito.")


def extraer_texto_de_imagen(ruta_imagen: str) -> str:
    """
    Recibe la ruta de una imagen, la procesa con OpenCV y extrae el texto usando Tesseract.
    
    Args:
        ruta_imagen (str): La ruta al archivo de imagen.

    Returns:
        str: El texto extraído de la imagen.
    """
    if not os.path.exists(ruta_imagen):
        raise FileNotFoundError(f"La imagen no se encontró en la ruta: {ruta_imagen}")

    # Leemos la imagen con OpenCV y la convertimos a escala de grises.
    imagen_cv = cv2.imread(ruta_imagen)
    gris = cv2.cvtColor(imagen_cv, cv2.COLOR_BGR2GRAY)
    
    # Configuramos Tesseract para que espere un bloque de texto uniforme.
    config = r'--oem 3 --psm 4' 
    texto = pytesseract.image_to_string(gris, lang='spa', config=config)
    return texto


def analizar_texto_con_gemini(texto_ticket: str) -> dict | None:
    """
    Envía el texto extraído a la IA de Gemini para que lo estructure en un formato JSON.

    Args:
        texto_ticket (str): El bloque de texto obtenido del OCR.

    Returns:
        dict | None: Un diccionario con los datos estructurados, o None si falla el análisis.
    """
    # Configuración del modelo para que sea determinista (poca "creatividad").
    generation_config = {"temperature": 0.0}
    model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)

    # El "prompt" es la instrucción clave. Es muy específico para evitar respuestas inesperadas.
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
        response = model.generate_content(prompt)
        # Limpiamos la respuesta para asegurarnos de que solo tenemos el JSON.
        texto_json = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(texto_json)
    except Exception as e:
        print(f"Error durante el análisis con Gemini: {e}")
        print(f"Respuesta recibida que causó el error: {response.text if 'response' in locals() else 'No response'}")
        return None


def guardar_en_google_sheets(datos_gasto: dict) -> bool:
    """
    Se conecta a Google Sheets y añade una nueva fila con los datos del gasto.

    Args:
        datos_gasto (dict): El diccionario con la información del gasto.

    Returns:
        bool: True si se guardó con éxito, False en caso contrario.
    """
    try:
        # Definimos los permisos que nuestro bot necesita.
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        gc = gspread.service_account(filename=GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=scopes)
        
        # Abrimos la hoja de cálculo por su nombre (configurado al inicio).
        spreadsheet = gc.open(GOOGLE_SHEETS_NAME)
        worksheet = spreadsheet.sheet1 # Seleccionamos la primera hoja.
        
        # Formateamos la lista de items para que sea un texto legible en una sola celda.
        items_lista = datos_gasto.get('items', [])
        items_texto = ", ".join([f"{item.get('descripcion', '')} (${item.get('precio', 0.0):.2f})" for item in items_lista])
        
        # Creamos la fila que vamos a insertar, asegurándonos de que el orden
        # coincida con las columnas de nuestro Google Sheet.
        fila_para_insertar = [
            datos_gasto.get('fecha', 'N/A'),
            datos_gasto.get('comercio', 'N/A'),
            datos_gasto.get('categoria', 'N/A'),
            datos_gasto.get('total', 0.0),
            items_texto
        ]
        
        # Añadimos la fila al final de la hoja.
        worksheet.append_row(fila_para_insertar)
        return True

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"ERROR: No se encontró la hoja de cálculo llamada '{GOOGLE_SHEETS_NAME}'.")
        print("Verifica que el nombre en el script y en Google Drive sea idéntico.")
        return False
    except Exception as e:
        print(f"Ocurrió un error al guardar en Google Sheets: {e}")
        return False


# --- 4. FUNCIÓN PRINCIPAL DE ORQUESTACIÓN ---
# Esta es la función "maestra" que llama a todas las demás en el orden correcto.

def procesar_gasto_completo(ruta_imagen: str):
    """
    Orquesta todo el proceso: OCR -> IA -> Guardado en Google Sheets.
    Esta es la función que tu bot de WhatsApp llamará en el futuro.

    Args:
        ruta_imagen (str): La ruta a la imagen del ticket a procesar.
    """
    try:
        print("-" * 50)
        print(f"Iniciando procesamiento para la imagen: {ruta_imagen}")

        # Paso 1: Extraer texto de la imagen.
        print("Paso 1: Extrayendo texto de la imagen (OCR)...")
        texto_crudo = extraer_texto_de_imagen(ruta_imagen)
        if not texto_crudo.strip():
            print("-> Fallo: No se pudo extraer texto. La imagen podría estar en blanco o ser ilegible.")
            return
        print("-> Éxito: Texto extraído.\n")
        
        # Paso 2: Analizar el texto con la IA.
        print("Paso 2: Analizando texto con Gemini para estructurar datos...")
        datos_del_gasto = analizar_texto_con_gemini(texto_crudo)
        if not datos_del_gasto:
            print("-> Fallo: El análisis de la IA no produjo resultados válidos.")
            return
        print("-> Éxito: Análisis completado.\n")
        
        # Paso 3: Guardar los datos en la nube.
        print("Paso 3: Guardando datos en Google Sheets...")
        exito_al_guardar = guardar_en_google_sheets(datos_del_gasto)
        
        if exito_al_guardar:
            print("-> Éxito: ¡Gasto guardado en Google Sheets!")
            print("\n==========================")
            print("   PROCESO COMPLETADO")
            print("==========================")
        else:
            print("-> Fallo: No se pudo guardar la información.")
            print("\n--------------------------")
            print("   EL PROCESO FALLÓ EN EL PASO FINAL")
            print("--------------------------")

    except FileNotFoundError as e:
        print(f"[ERROR CRÍTICO] Archivo no encontrado: {e}")
    except Exception as e:
        print(f"[ERROR CRÍTICO] Ocurrió un error inesperado en el proceso: {e}")


# --- 5. PUNTO DE ENTRADA DEL SCRIPT ---
# Esta parte solo se ejecuta cuando corres el archivo directamente (python main.py).
# Es nuestro campo de pruebas.
if __name__ == "__main__":
    try:
        # Primero, validamos que todas nuestras APIs y herramientas estén bien configuradas.
        configurar_servicios()
        
        # Definimos la imagen que queremos procesar para esta prueba.
        IMAGEN_A_PROCESAR = "tickets/t1.jpg" 
        
        # Llamamos a nuestra función orquestadora para que haga todo el trabajo.
        procesar_gasto_completo(IMAGEN_A_PROCESAR)

    except Exception as e:
        print(f"El programa no pudo iniciar debido a un error de configuración: {e}")