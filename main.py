# main.py - VERSIÓN CORREGIDA CON TOKEN DE AUTENTICACIÓN

import os
import json
import pytesseract
import cv2
import google.generativeai as genai
import requests
from datetime import date
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

# --- CONFIGURACIÓN CENTRALIZADA ---
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
COMANDA_CENTRAL_API_URL = os.getenv("COMANDA_CENTRAL_API_URL")
# NUEVA VARIABLE PARA EL TOKEN
COMANDA_CENTRAL_API_TOKEN = os.getenv("COMANDA_CENTRAL_API_TOKEN") 
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# --- FUNCIONES ---

def configurar_servicios():
    """Chequeo de calidad inicial."""
    print("Iniciando configuración de servicios...")
    if not GEMINI_API_KEY: raise ValueError("GEMINI_API_KEY no encontrada.")
    if not COMANDA_CENTRAL_API_URL: raise ValueError("COMANDA_CENTRAL_API_URL no encontrada.")
    # NUEVO CHEQUEO PARA EL TOKEN
    if not COMANDA_CENTRAL_API_TOKEN: raise ValueError("COMANDA_CENTRAL_API_TOKEN no encontrado.")
    if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
        raise ValueError("Credenciales de Cloudinary no encontradas en .env")
    
    genai.configure(api_key=GEMINI_API_KEY)
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )
    print("-> Servicios configurados con éxito.")

def extraer_texto_de_imagen(ruta_imagen: str) -> str:
    """ESTACIÓN 1: El Digitalizador (OCR)."""
    if not os.path.exists(ruta_imagen): raise FileNotFoundError(f"Imagen no encontrada: {ruta_imagen}")
    imagen_cv = cv2.imread(ruta_imagen)
    gris = cv2.cvtColor(imagen_cv, cv2.COLOR_BGR2GRAY)
    return pytesseract.image_to_string(gris, lang='spa', config=r'--oem 3 --psm 4')

def analizar_texto_con_gemini(texto_ticket: str) -> dict | None:
    """ESTACIÓN 2: El Analista (IA)."""
    generation_config = {"temperature": 0.0}
    model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)
    prompt = f"""
    Tu única función es analizar el texto de un ticket y extraer dos datos en formato JSON.
    Tu respuesta DEBE SER solo el JSON. Estructura: {{ "total": float, "categoria": "string" }}
    Reglas de categoría: Elige EXCLUSIVAMENTE una de estas categorias, NO incluyas otras: ["Materia Prima", "Descartables", "Servicios", "Gastos Fijos", "Gastos Operativos", "Gastos de Mantenimiento", "Otros Gastos"]. y el precio total de la compra.
    Texto a procesar: {texto_ticket}
    Salida JSON:
    """
    try:
        response = model.generate_content(prompt)
        # Limpieza de la respuesta de la IA mejorada
        texto_json_crudo = response.text.strip()
        # Encuentra el inicio y fin del JSON para evitar texto extra
        inicio_json = texto_json_crudo.find('{')
        fin_json = texto_json_crudo.rfind('}') + 1
        if inicio_json == -1 or fin_json == 0:
            print(f"Respuesta de la IA no contiene un JSON válido: {texto_json_crudo}")
            return None
        texto_json = texto_json_crudo[inicio_json:fin_json]
        return json.loads(texto_json)
    except Exception as e:
        print(f"Error en Gemini o al parsear JSON: {e}")
        return None

def subir_imagen_a_cloudinary(ruta_imagen: str) -> str | None:
    """ESTACIÓN 3: Sube la imagen a Cloudinary y devuelve una URL segura."""
    try:
        print("Subiendo imagen a Cloudinary...")
        upload_result = cloudinary.uploader.upload(ruta_imagen, folder="tickets_gastos")
        print(f"-> Imagen subida con éxito. URL: {upload_result['secure_url']}")
        return upload_result['secure_url']
    except Exception as e:
        print(f"Error al subir imagen a Cloudinary: {e}")
        return None

def guardar_gasto_en_api(datos_gasto: dict) -> bool:
    """ESTACIÓN 4: El Registrador de Gastos (MODIFICADO para enviar el token)."""
    try:
        url_endpoint = f"{COMANDA_CENTRAL_API_URL}/api/gastos"
        
        # Preparamos la cabecera de autenticación
        headers = {
            "Authorization": f"Bearer {COMANDA_CENTRAL_API_TOKEN}"
        }
        
        # Hacemos la petición POST incluyendo la cabecera
        response = requests.post(url_endpoint, json=datos_gasto, headers=headers)
        
        # Lanza un error si el status no es 2xx (ej. 401, 403, 500)
        response.raise_for_status() 
        
        print(f"-> Gasto registrado con éxito en Comanda Central. Status: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error al contactar la API: {e}")
        # Este bloque ahora imprimirá el error exacto que devuelve Comanda Central
        if e.response is not None: 
            print(f"Respuesta del servidor ({e.response.status_code}): {e.response.text}")
        return False

# --- FUNCIÓN PRINCIPAL (ORQUESTACIÓN) ---
# (Sin cambios en esta función)
def procesar_gasto_completo(ruta_imagen: str) -> bool:
    try:
        print("-" * 50)
        print(f"Iniciando procesamiento para: {ruta_imagen}")

        texto_crudo = extraer_texto_de_imagen(ruta_imagen)
        if not texto_crudo.strip(): 
            print("-> Fallo: No se pudo extraer texto.")
            return False
        
        url_imagen_publica = subir_imagen_a_cloudinary(ruta_imagen)
        if not url_imagen_publica: 
            print("-> Fallo: No se pudo subir la imagen.")
            return False
        
        datos_ia = analizar_texto_con_gemini(texto_crudo)
        if not datos_ia or 'total' not in datos_ia or 'categoria' not in datos_ia: 
            print("-> Fallo: El análisis de la IA no produjo resultados válidos.")
            return False
        
        datos_finales = {
            "fecha": date.today().isoformat(),
            "concepto": url_imagen_publica,
            "categoria": datos_ia['categoria'],
            "monto": datos_ia['total']
        }
        
        return guardar_gasto_en_api(datos_finales)

    except Exception as e:
        print(f"[ERROR CRÍTICO] Proceso falló: {e}")
        return False

# --- PUNTO DE ENTRADA DEL SCRIPT (PARA PRUEBAS LOCALES) ---
if __name__ == "__main__":
    try:
        configurar_servicios()
        IMAGEN_A_PROCESAR = "ticket1.jpg" 
        
        if os.path.exists(IMAGEN_A_PROCESAR):
            exito = procesar_gasto_completo(IMAGEN_A_PROCESAR)
            if exito:
                print("\n========================================")
                print("   PROCESO DE PRUEBA COMPLETADO CON ÉXITO")
                print("========================================")
            else:
                print("\n----------------------------------------")
                print("   EL PROCESO DE PRUEBA FALLÓ")
                print("----------------------------------------")
        else:
            print(f"\n[ATENCIÓN] No se encontró la imagen de prueba '{IMAGEN_A_PROCESAR}'.")
            print("El motor está listo, pero no se pudo ejecutar la prueba local.")

    except Exception as e:
        print(f"El programa no pudo iniciar debido a un error de configuración: {e}")