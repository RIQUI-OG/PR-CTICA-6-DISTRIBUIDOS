# Usar una imagen base de Python ligera
FROM python:3.10-slim

# Instalar dependencias del sistema con el NUEVO nombre del paquete
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar e instalar requerimientos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del servidor modificado para Docker
COPY chat_servidor_v2.py ./chat_servidor.py

# Exponer el puerto de la API de Flask
EXPOSE 9000

# Ejecutar el servidor
CMD ["python", "chat_servidor.py"]
