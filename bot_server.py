# bot_server.py - VERSIÓN ACTUALIZADA PARA MÚLTIPLES IMÁGENES

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import requests
import os
import threading
import time
from main import procesar_gasto_completo, configurar_servicios

# --- CONFIGURACIÓN E INICIALIZACIÓN ---
try:
    configurar_servicios()
except Exception as e:
    print(f"ERROR FATAL AL INICIAR: {e}")
    exit()

app = Flask(__name__)

ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_NUMBER = 'whatsapp:+14155238886'

if not ACCOUNT_SID or not AUTH_TOKEN:
    raise ValueError("Credenciales de Twilio no encontradas en .env")

twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)

# --- LÓGICA DEL BOT ---
# (La función procesar_en_segundo_plano no necesita cambios)
def procesar_en_segundo_plano(media_url: str, sender_number: str):
    """Se ejecuta en un hilo separado para no bloquear a Twilio."""
    print(f"Iniciando procesamiento en segundo plano para: {sender_number}")
    
    id_usuario = sender_number.split(':')[-1]
    timestamp = int(time.time() * 1000)
    # Añadimos un identificador único basado en la URL para evitar colisiones de nombres
    url_hash = hash(media_url) & 0xffffffff 
    ruta_temporal_imagen = f"temp_{id_usuario}_{timestamp}_{url_hash}.jpg"

    try:
        twilio_client.messages.create(
            body="📸 Procesando uno de tus tickets...",  
            from_=TWILIO_NUMBER, to=sender_number
        )

        response = requests.get(media_url, auth=(ACCOUNT_SID, AUTH_TOKEN))
        if response.status_code == 200:
            with open(ruta_temporal_imagen, 'wb') as f:
                f.write(response.content)
            print(f"-> Imagen descargada como: {ruta_temporal_imagen}")

            exito_del_proceso = procesar_gasto_completo(ruta_temporal_imagen)
            
            if exito_del_proceso:
                mensaje_final = "✅ ¡Gasto registrado con éxito en Comanda Central!"
            else:
                mensaje_final = "⚠️ Hubo un error al procesar este ticket. Revisa los logs del bot."
            twilio_client.messages.create(body=mensaje_final, from_=TWILIO_NUMBER, to=sender_number)
            
            try:
                os.remove(ruta_temporal_imagen)
                print(f"-> Archivo temporal {ruta_temporal_imagen} borrado.")
            except OSError as e:
                print(f"Error borrando archivo temporal: {e}")
        else:
            print(f"-> Fallo al descargar imagen. Status: {response.status_code}")
            twilio_client.messages.create(body="❌ Error: No pude descargar una de las imágenes.", from_=TWILIO_NUMBER, to=sender_number)
    
    except Exception as e:
        print(f"Error en el hilo de procesamiento para {ruta_temporal_imagen}: {e}")
        import traceback
        traceback.print_exc()
        twilio_client.messages.create(body="❌ Ocurrió un error general e inesperado con uno de los tickets.", from_=TWILIO_NUMBER, to=sender_number)

# --- RUTAS DEL SERVIDOR WEB ---
@app.route("/")
def index():
    return "Bot de Gastos para Comanda Central - Funcionando.", 200

# --- RUTA PRINCIPAL MODIFICADA ---
@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    """Ruta principal del bot, webhook para Twilio."""
    num_media = int(request.values.get("NumMedia", 0))
    sender_number = request.values.get("From")

    if num_media > 0:
        # 1. Envía una confirmación inicial al usuario.
        plural = "imágenes" if num_media > 1 else "imagen"
        resp = MessagingResponse()
        resp.message(f"¡Recibí {num_media} {plural}! Voy a procesarlas una por una. Te enviaré un mensaje por cada una.")
        
        # 2. Inicia un hilo de procesamiento para CADA imagen.
        for i in range(num_media):
            media_url = request.values.get(f"MediaUrl{i}")
            if media_url:
                thread = threading.Thread(target=procesar_en_segundo_plano, args=(media_url, sender_number))
                thread.start()
        
        return str(resp) # Devuelve la confirmación inicial
    else:
        # Mensaje de instrucciones si no hay imágenes
        resp = MessagingResponse()
        resp.message("Hola! Soy el bot de Comanda Central. Para registrar un gasto, solo envíame una o más fotos de tus tickets. 🧾")
        return str(resp)
    
    return '', 204

# --- PUNTO DE ENTRADA (para pruebas locales) ---
if __name__ == "__main__":
    app.run(port=5000, debug=False)