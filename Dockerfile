# Dockerfile (Versión Final Robusta)

# 1. Base: Python 3.11-slim, una base ligera y eficiente.
FROM python:3.11-slim

# 2. Directorio de Trabajo
WORKDIR /app

# 3. Instalación de Tesseract y dependencias del sistema.
# El '-y' confirma automáticamente. '--no-install-recommends' evita paquetes innecesarios.
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 4. Copiamos y instalamos requerimientos de Python.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiamos el resto del código de la aplicación.
COPY . .

# 6. Comando de Inicio.
# En lugar de Gunicorn, crearemos un script de inicio para tener más control.
# Esto es una práctica común y muy robusta.
# Por ahora lo dejamos así, pero la clave está en el Start Command de Render.
# El CMD original está bien, pero lo sobreescribiremos en Render para más seguridad.
CMD ["gunicorn", "bot_server:app", "--bind", "0.0.0.0:10000"]