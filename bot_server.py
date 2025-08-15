# bot_server.py - VERSIÓN FINAL CON MENSAJE DE RESUMEN

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import requests
import os
import threading
import time
from main import procesar_gasto_completo, configurar_servicios
from collections import defaultdict

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

# --- LÓGICA DEL BOT MEJORADA ---

# Objeto global para llevar la cuenta de los resultados por usuario
resultados_por_usuario = defaultdict(lambda: {'exitos': 0, 'fallos': 0, 'total': 0})
lock = threading.Lock() # Para manejar el acceso concurrente al diccionario de resultados

def procesar_y_contar(media_url: str, sender_number: str):
    """
    Función que se ejecuta en cada hilo. Procesa una imagen y actualiza
    el contador de resultados para ese usuario.
    """
    id_usuario = sender_number.split(':')[-1]
    timestamp = int(time.time() * 1000)
    url_hash = hash(media_url) & 0xffffffff
    ruta_temporal_imagen = f"temp_{id_usuario}_{timestamp}_{url_hash}.jpg"
    
    exito_final = False
    try:
        response = requests.get(media_url, auth=(ACCOUNT_SID, AUTH_TOKEN))
        if response.status_code == 200:
            with open(ruta_temporal_imagen, 'wb') as f:
                f.write(response.content)
            
            # La función principal ahora hace todo el trabajo
            if procesar_gasto_completo(ruta_temporal_imagen):
                exito_final = True
            
            try:
                os.remove(ruta_temporal_imagen)
            except OSError as e:
                print(f"Error borrando archivo temporal: {e}")
        else:
            print(f"Fallo al descargar imagen. Status: {response.status_code}")
    except Exception as e:
        print(f"Error crítico en el hilo de procesamiento: {e}")

    # --- SECCIÓN CRÍTICA: Actualizar resultados y enviar resumen si es el último ---
    with lock:
        if exito_final:
            resultados_por_usuario[sender_number]['exitos'] += 1
        else:
            resultados_por_usuario[sender_number]['fallos'] += 1
        
        # Comprobar si este es el último ticket del lote
        procesados = resultados_por_usuario[sender_number]['exitos'] + resultados_por_usuario[sender_number]['fallos']
        total_a_procesar = resultados_por_usuario[sender_number]['total']

        if procesados == total_a_procesar:
            print(f"-> Todos los tickets procesados para {sender_number}. Enviando resumen.")
            # Construir y enviar el mensaje de resumen
            exitos = resultados_por_usuario[sender_number]['exitos']
            fallos = resultados_por_usuario[sender_number]['fallos']
            
            mensaje_resumen = f"🧾 *Resumen de tickets procesados:*\n\n"
            if exitos > 0:
                mensaje_resumen += f"✅ {exitos} gasto{'s' if exitos > 1 else ''} registrado{'s' if exitos > 1 else ''} con éxito.\n"
            if fallos > 0:
                mensaje_resumen += f"⚠️ {fallos} gasto{'s' if fallos > 1 else ''} no se pudieron registrar. Revisa los logs del bot para más detalles."

            try:
                twilio_client.messages.create(body=mensaje_resumen, from_=TWILIO_NUMBER, to=sender_number)
            except Exception as e:
                print(f"Error al enviar mensaje de resumen a {sender_number}: {e}")

            # Limpiar los resultados para este usuario para el próximo lote
            del resultados_por_usuario[sender_number]


# --- RUTAS DEL SERVIDOR WEB ---
@app.route("/")
def index():
    return "Bot de Gastos para Comanda Central - Funcionando.", 200

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    """Ruta principal del bot. Ahora orquesta el procesamiento y el resumen."""
    num_media = int(request.values.get("NumMedia", 0))
    sender_number = request.values.get("From")

    if num_media > 0:
        with lock:
            # Preparamos el contador para este nuevo lote de imágenes
            resultados_por_usuario[sender_number]['total'] = num_media
            resultados_por_usuario[sender_number]['exitos'] = 0
            resultados_por_usuario[sender_number]['fallos'] = 0

        # Enviamos una única confirmación inicial
        plural = "imágenes" if num_media > 1 else "imagen"
        resp = MessagingResponse()
        resp.message(f"¡Recibí {num_media} {plural}! Cuando termine de procesarlas todas, te enviaré un resumen.")
        
        # Lanzamos los hilos para procesar cada imagen
        for i in range(num_media):
            media_url = request.values.get(f"MediaUrl{i}")
            if media_url:
                thread = threading.Thread(target=procesar_y_contar, args=(media_url, sender_number))
                thread.start()
        
        return str(resp)
    else:
        resp = MessagingResponse()
        resp.message("Hola! Soy el bot de Comanda Central. Para registrar un gasto, solo envíame una o más fotos de tus tickets. 🧾")
        return str(resp)
    
    return '', 204

if __name__ == "__main__":
    app.run(port=5000, debug=False)