# 1. Imagen base de Python
FROM python:3.11-slim

# 2. Instalar dependencias del sistema operativo (VERSIÓN CORREGIDA Y MÁS ROBUSTA)
# Se separa 'update' de 'install' para mejorar la fiabilidad.
RUN apt-get update
RUN apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1-mesa-glx \
    libglib2.0-0 \
# Se añaden comandos de limpieza para reducir el tamaño final de la imagen.
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*

# 3. Configurar el entorno de la aplicación (Sin cambios)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# 4. Comando para iniciar el servidor (Sin cambios)
# Render nos dará el puerto a usar en la variable de entorno $PORT
CMD gunicorn --bind 0.0.0.0:${PORT} bot_server:app