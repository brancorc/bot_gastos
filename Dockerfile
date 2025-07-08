# Dockerfile (Versión Final con la dependencia de OpenCV)

# 1. Base: Python 3.11-slim
FROM python:3.11-slim

# 2. Directorio de Trabajo
WORKDIR /app

# 3. Instalación de Dependencias del Sistema
# ¡AÑADIMOS libgl1 A LA LISTA!
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 4. Copiamos y instalamos requerimientos de Python.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiamos el resto del código de nuestra aplicación.
COPY . .

# 6. Comando para arrancar el servidor.
CMD ["gunicorn", "bot_server:app", "--bind", "0.0.0.0:10000", "--timeout", "120"]