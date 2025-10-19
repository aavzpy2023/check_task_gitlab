# /frontend/Dockerfile
FROM python:3.11-slim-bookworm

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and static assets
COPY . .

# Expose the default Streamlit port
EXPOSE 8501

# The command to run the Streamlit application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]