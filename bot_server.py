# bot_server.py (Versión Corregida para Procesos Largos)

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import requests
import os
import threading # Importamos la librería para hilos

# Importamos nuestra lógica principal
from main import procesar_gasto_completo, configurar_servicios

# --- Configuración Inicial ---
try:
    configurar_servicios()
except Exception as e:
    print(f"ERROR FATAL AL INICIAR: {e}")
    exit()

app = Flask(__name__)

# Credenciales de Twilio
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
twilio_number = 'whatsapp:+14155238886' # El número del sandbox de Twilio

# Creamos un cliente de Twilio para poder enviar mensajes
client = Client(account_sid, auth_token)

def procesar_en_segundo_plano(media_url, sender_number):
    """
    Esta función se ejecuta en un hilo separado para no bloquear la respuesta a Twilio.
    """
    print(f"Iniciando procesamiento en segundo plano para {sender_number}")
    try:
        # 1. Notificamos al usuario que empezamos a trabajar.
        client.messages.create(
            body="Imagen recibida. Analizando el ticket, banca un toque :v",  
            from_=twilio_number,
            to=sender_number
        )

        # 2. Descargamos la imagen
        ruta_temporal_imagen = f"temp_{sender_number.split(':')[-1]}.jpg"
        response = requests.get(media_url, auth=(account_sid, auth_token)) # Añadimos autenticación a la descarga

        if response.status_code == 200:
            with open(ruta_temporal_imagen, 'wb') as f:
                f.write(response.content)
            print("-> Imagen descargada con éxito.")

            # 3. ¡Llamamos a nuestro motor!
            # Redirigimos la salida a una función para poder capturarla si quisiéramos
            procesar_gasto_completo(ruta_temporal_imagen)
            
            # 4. Enviamos mensaje de éxito
            client.messages.create(
                body="✅ Listo pa, el gasto ha sido registrado en tu Google Sheet.",
                from_=twilio_number,
                to=sender_number
            )
            # Opcional: Borrar la imagen temporal
            os.remove(ruta_temporal_imagen)
        else:
            print(f"-> Fallo al descargar imagen. Status: {response.status_code}, Razón: {response.text}")
            client.messages.create(body="❌ Error: No pude descargar la imagen desde Twilio. Intenta de nuevo.", from_=twilio_number, to=sender_number)
    
    except Exception as e:
        print(f"Error en el hilo de procesamiento: {e}")
        client.messages.create(body="❌ Ocurrió un error inesperado al procesar tu ticket.", from_=twilio_number, to=sender_number)


@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    """Esta función AHORA solo recibe el mensaje y delega el trabajo pesado."""
    
    num_media = int(request.values.get("NumMedia", 0))
    sender_number = request.values.get("From")

    if num_media > 0:
        media_url = request.values.get("MediaUrl0")
        
        # Creamos y arrancamos un hilo para hacer el trabajo en segundo plano
        # Esto permite que respondamos a Twilio inmediatamente.
        thread = threading.Thread(target=procesar_en_segundo_plano, args=(media_url, sender_number))
        thread.start()
    else:
        # Si no hay imagen, respondemos de forma síncrona.
        resp = MessagingResponse()
        resp.message("Me tenes que pasar una foto del ticket, si no me mandas una foto del ticket no se que mierda queres que haga")
        return str(resp)
    
    # Devolvemos una respuesta vacía a Twilio para indicar "OK, recibido".
    # Esto cierra la conexión HTTP inicial inmediatamente.
    return '', 204

# Punto de entrada para ejecutar el servidor Flask
if __name__ == "__main__":
    app.run(port=5000, debug=False) # Es mejor desactivar el debug mode cuando usamos hilos

