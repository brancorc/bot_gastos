# ==============================================================================
# ARCHIVO: bot_server.py
# PROPÓSITO: Este archivo es la "cara pública" y el "recepcionista" de
# nuestro bot. Su trabajo es convertirse en un servidor web usando Flask,
# escuchar las peticiones de Twilio que llegan de WhatsApp, y delegar
# el trabajo pesado a nuestro "motor" (main.py).
# ==============================================================================


# --- 1. IMPORTACIONES ---
# Herramientas necesarias para nuestro servidor y comunicación.

from flask import Flask, request  # Flask es el framework para crear el servidor web.
                                  # 'request' nos da acceso a la información que envía Twilio.
from twilio.twiml.messaging_response import MessagingResponse # Para construir respuestas simples de WhatsApp.
from twilio.rest import Client  # Para poder ENVIAR mensajes a través de la API de Twilio.
import requests  # Para descargar la imagen desde la URL que nos da Twilio.
import os        # Para interactuar con el sistema operativo (leer variables, borrar archivos).
import threading # Para ejecutar nuestro proceso largo en segundo plano y no hacer esperar a Twilio.
import time      # Para manejar tiempos y pausas si es necesario.

# Importamos las funciones "jefe" de nuestro motor. Es como si el recepcionista
# tuviera una línea directa con el jefe de la fábrica.
from main import procesar_gasto_completo, configurar_servicios


# --- 2. CONFIGURACIÓN E INICIALIZACIÓN ---
# Preparamos todo lo que necesita el servidor para arrancar.

# Primero, intentamos configurar todos los servicios externos (Gemini, etc.).
# Si esto falla, el programa se detiene aquí con un error claro.
try:
    configurar_servicios()
except Exception as e:
    print(f"ERROR FATAL AL INICIAR: El servidor no puede arrancar. Causa: {e}")
    exit() # Detiene la ejecución del script.

# Creamos la aplicación web Flask. 'app' es el objeto principal de nuestro servidor.
app = Flask(__name__)

# Cargamos las credenciales de Twilio desde las variables de entorno (.env).
# Es más seguro que escribirlas directamente en el código.
ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_NUMBER = 'whatsapp:+14155238886' # El número oficial del sandbox de Twilio.

# Verificación de seguridad: nos aseguramos de que las credenciales existan.
if not ACCOUNT_SID or not AUTH_TOKEN:
    raise ValueError("Las credenciales de Twilio (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) no se encontraron en el .env")

# Creamos un "cliente" de Twilio. Este objeto es nuestro "teléfono" para
# poder hacer llamadas a la API de Twilio y enviar mensajes.
twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)


# --- 3. FUNCIONES DE LÓGICA DEL BOT ---

def procesar_en_segundo_plano(media_url: str, sender_number: str):
    """
    Esta función se ejecuta en un hilo separado para no bloquear la respuesta a Twilio.
    """
    print(f"Iniciando procesamiento en segundo plano para el número: {sender_number}")
    
    # --- 2. GENERAMOS UN NOMBRE DE ARCHIVO ÚNICO ---
    id_usuario = sender_number.split(':')[-1]
    # Usamos la marca de tiempo actual (timestamp) para asegurar la unicidad.
    timestamp = int(time.time() * 1000) # Tiempo en milisegundos
    ruta_temporal_imagen = f"temp_{id_usuario}_{timestamp}.jpg"
    # --- FIN DEL CAMBIO ---

    try:
        # Notificamos al usuario...
        twilio_client.messages.create(
            body="📸👁️ Imagen recibida. Analizando el ticket...",  
            from_=TWILIO_NUMBER,
            to=sender_number
        )

        # Descargamos la imagen...
        response = requests.get(media_url, auth=(ACCOUNT_SID, AUTH_TOKEN))

        if response.status_code == 200:
            with open(ruta_temporal_imagen, 'wb') as f:
                f.write(response.content)
            print(f"-> Imagen descargada con éxito como: {ruta_temporal_imagen}")

            # Llamamos a nuestro motor...
            exito_del_proceso = procesar_gasto_completo(ruta_temporal_imagen)
            
            # Enviamos el mensaje final...
            if exito_del_proceso:
                mensaje_final = "✅ ¡Listo! El gasto de este ticket ha sido registrado."
            else:
                mensaje_final = "⚠️ Atención: Hubo un error al procesar este ticket. Revisa los logs."

            twilio_client.messages.create(body=mensaje_final, from_=TWILIO_NUMBER, to=sender_number)
            
            # Limpieza: Borramos el archivo temporal específico de este proceso.
            # Usamos un try-except por si el archivo ya fue borrado por otro motivo.
            try:
                os.remove(ruta_temporal_imagen)
                print(f"-> Archivo temporal {ruta_temporal_imagen} borrado.")
            except OSError as e:
                print(f"Error borrando archivo temporal: {e}")
        else:
            # Si la descarga falla...
            print(f"-> Fallo al descargar imagen. Status: {response.status_code}")
            twilio_client.messages.create(body="❌ Error: No pude descargar la imagen desde Twilio.", from_=TWILIO_NUMBER, to=sender_number)
    
    except Exception as e:
        # Si ocurre cualquier otro error...
        print(f"Error en el hilo de procesamiento para {ruta_temporal_imagen}: {e}")
        import traceback
        traceback.print_exc() # Imprime el error completo en los logs para depurar
        twilio_client.messages.create(body="❌ Ocurrió un error general e inesperado al procesar tu ticket.", from_=TWILIO_NUMBER, to=sender_number)


# --- 4. RUTAS DEL SERVIDOR WEB (ENDPOINTS) ---
# Aquí definimos las "puertas" de nuestro servidor y qué hacer cuando alguien toca el timbre.

@app.route("/")
def index():
    """
    Esta es la ruta raíz. Sirve para verificar que el bot está vivo.
    Si visitas la URL principal (ej: https://bot-gastos.onrender.com/), verás este mensaje.
    También es usada por Render para sus "Health Checks".
    """
    return "¡Hola! Soy el Bot de Gastos y estoy funcionando correctamente.", 200

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    """
    Esta es la ruta principal del bot, la que ponemos en Twilio.
    Solo acepta peticiones POST y su única misión es recibir el mensaje y delegar el trabajo.
    """
    
    # Extraemos información de la petición de Twilio.
    num_media = int(request.values.get("NumMedia", 0)) # ¿Cuántas imágenes hay?
    sender_number = request.values.get("From") # ¿Quién envía el mensaje?

    if num_media > 0:
        # Si el mensaje contiene al menos una imagen...
        media_url = request.values.get("MediaUrl0") # Obtenemos la URL de la primera imagen.
        
        # Creamos y arrancamos un "hilo" para hacer el trabajo pesado en segundo plano.
        # 'target' es la función que se ejecutará en el hilo.
        # 'args' son los argumentos que le pasamos a esa función.
        thread = threading.Thread(target=procesar_en_segundo_plano, args=(media_url, sender_number))
        thread.start() # Iniciamos el hilo. El programa principal no espera a que termine.
    else:
        # Si el mensaje no tiene imagen, respondemos directamente con instrucciones.
        resp = MessagingResponse()
        resp.message("Hola Branco, para registrar un gasto, envía una imagen del ticket de compra. 😉 ")
        return str(resp)
    
    # Si se inició un hilo, devolvemos una respuesta vacía con código 204.
    # Esto le dice a Twilio "OK, recibí tu petición, gracias", y cierra la conexión
    # inmediatamente para que no se quede esperando.
    return '', 204


# --- 5. PUNTO DE ENTRADA (SOLO PARA PRUEBAS LOCALES) ---
# Este bloque solo se ejecuta si corres `python bot_server.py` en tu propia PC.
# Gunicorn (en Render) ignora esta parte.
if __name__ == "__main__":
    # app.run() inicia el servidor de desarrollo de Flask.
    # Es mejor desactivar el 'debug mode' cuando usamos hilos para evitar reinicios extraños.
    app.run(port=5000, debug=False)