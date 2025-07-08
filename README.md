# Bot de Gestión de Gastos con IA para WhatsApp

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python) ![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white) ![Google Cloud](https://img.shields.io/badge/Google_Cloud-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white) ![Twilio](https://img.shields.io/badge/Twilio-F22F46?style=for-the-badge&logo=twilio&logoColor=white)

Este proyecto es un bot de WhatsApp completamente funcional, diseñado para automatizar el registro de gastos. El bot utiliza tecnologías de Visión por Computadora (OCR) e Inteligencia Artificial (IA) para leer, entender y archivar tickets de compra enviados como imágenes a través de WhatsApp.

La aplicación está desplegada en la nube y operativa 24/7, proporcionando una solución eficiente y a medida para la gestión de finanzas personales o de pequeños negocios.

---

## 🚀 Funcionalidades Principales

-   **Interfaz Conversacional:** Interacción directa y sencilla a través de WhatsApp.
-   **Procesamiento Inteligente de Imágenes:**
    -   Utiliza **Tesseract** para una digitalización precisa del texto de los tickets.
    -   Emplea la **API de Google Gemini** para analizar el texto y extraer de forma estructurada:
        -   Nombre del Comercio
        -   Fecha de la Compra
        -   Lista detallada de Ítems y sus precios
        -   Subtotal, Descuento y Total del gasto.
    -   **Categorización Automática** del gasto (ej: "Materia prima", "Bebidas", "Limpieza", etc.).
-   **Almacenamiento Centralizado:** Guarda todos los datos extraídos en una nueva fila de una hoja de cálculo de **Google Sheets**, creando una base de datos de gastos fácil de consultar.
-   **Arquitectura Asíncrona:** Usa un sistema de cola de tareas para procesar las imágenes de forma secuencial, asegurando la estabilidad en entornos con recursos limitados y notificando al usuario en tiempo real sobre el estado del proceso.

---

## 🛠️ Arquitectura y Stack Tecnológico

El sistema está diseñado con una arquitectura robusta y modular, separando la lógica de negocio del servidor web.

-   **Backend & Lógica (`main.py`):**
    -   **Python:** Lenguaje principal de programación.
    -   **OpenCV:** Para el pre-procesamiento de imágenes (conversión a escala de grises).
    -   **Tesseract (pytesseract):** Motor de OCR.
    -   **Google Gemini API:** Para la extracción de entidades y estructuración de datos.
    -   **Gspread:** Librería para la interacción con la API de Google Sheets.

-   **Servidor Web y API (`bot_server.py`):**
    -   **Flask:** Micro-framework web para recibir los webhooks de Twilio.
    -   **Twilio API:** Gateway oficial para la comunicación con la API de WhatsApp.
    -   **Queue & Threading:** Implementación de una cola de tareas y un worker en segundo plano para un procesamiento asíncrono y eficiente.

-   **Infraestructura y Despliegue:**
    -   **Docker:** La aplicación está "conteneirizada" en un `Dockerfile` que define un entorno Linux con todas las dependencias de sistema (Tesseract, `libgl1`) y de Python (`requirements.txt`).
    -   **Render.com:** Plataforma en la nube (PaaS) que hostea el contenedor Docker.
    -   **Gunicorn:** Servidor WSGI de producción para ejecutar la aplicación Flask.
    -   **GitHub:** Para el control de versiones y el despliegue continuo (CI/CD) en Render.

---

## ⚙️ Flujo de Operación

1.  Un usuario envía una imagen a un número de WhatsApp gestionado por el **Sandbox de Twilio**.
2.  Twilio dispara un **webhook `POST`** a un endpoint público hosteado en **Render**.
3.  La aplicación **Flask** recibe la petición, pone la tarea (URL de la imagen y número del remitente) en una **cola (`Queue`)** y responde inmediatamente a Twilio.
4.  Un **hilo de trabajo (`worker thread`)** toma la tarea de la cola.
5.  El worker descarga la imagen, la procesa con **Tesseract y Gemini**, y guarda los datos en **Google Sheets**.
6.  Durante el proceso, el worker utiliza la **API REST de Twilio** para enviar mensajes de estado ("Procesando...", "¡Completado!") al usuario.