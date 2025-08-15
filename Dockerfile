# 1. Imagen base de Python (CORREGIDA A UNA VERSIÓN MÁS MODERNA Y ESTABLE)
FROM python:3.11-slim-bullseye

# 2. Instalar dependencias del sistema operativo (usando la versión robusta)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 3. Configurar el entorno de la aplicación (Sin cambios)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# 4. Comando para iniciar el servidor (Sin cambios)
CMD gunicorn --bind 0.0.0.0:${PORT} bot_server:app