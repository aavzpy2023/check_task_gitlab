# /backend/Dockerfile
FROM python:3.11-slim-bookworm

WORKDIR /app

# SSS: Instalar la dependencia de sistema 'pandoc' requerida por 'pypandoc'.
# Esto es esencial para la generación de PDFs.
RUN apt-get update && apt-get install -y pandoc weasyprint && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the application will run on
EXPOSE 8001

# The command to run the FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]