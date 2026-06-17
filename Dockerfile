# Usar una imagen base de Python ligera
FROM python:3.10-slim

# Instalar dependencias del sistema necesarias para ejecutar OpenCV (libglib)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar requerimientos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del servidor modificado
COPY chat_servidor_v2.py ./chat_servidor.py

# Exponer el puerto de la API
EXPOSE 9000

# Ejecutar el servidor
CMD ["python", "chat_servidor.py"]