# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy & install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy your entire project (including db/, agents/, dashboard/, etc.)
COPY . .

# Ensure Python will look in /app for modules
ENV PYTHONPATH=/app

# Default Redis connection via env vars
ENV REDIS_HOST=redis
ENV REDIS_PORT=6379

# Run Streamlit
CMD ["streamlit", "run", "dashboard/streamlit_app.py", \
     "--server.port", "8501", "--server.address", "0.0.0.0"]