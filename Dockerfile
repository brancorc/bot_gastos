# Dockerfile

# 1. Base: Empezamos con una imagen oficial de Python 3.11.
FROM python:3.11-slim

# 2. Directorio de Trabajo: Creamos una carpeta /app y nos movemos dentro.
WORKDIR /app

# 3. Instalación de Dependencias del Sistema: Aquí instalamos Tesseract.
# El comando 'apt-get' es el 'pip' de los sistemas Linux (Debian/Ubuntu).
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 4. Copiamos solo el archivo de requerimientos de Python.
COPY requirements.txt .

# 5. Instalamos las librerías de Python.
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiamos el resto del código de nuestra aplicación.
COPY . .

# 7. Comando para arrancar el servidor.
# Gunicorn arrancará nuestro 'bot_server.py' y escuchará en el puerto 10000,
# que es el que Render espera por defecto.
CMD ["gunicorn", "bot_server:app", "--bind", "0.0.0.0:10000"]