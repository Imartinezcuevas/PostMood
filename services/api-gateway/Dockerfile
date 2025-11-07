# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY services/api-gateway/requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy service code
COPY services/api-gateway/ ./

# Copy shared modules
COPY common /app/common
COPY monitoring /app/monitoring

# Set Python path so common modules can be imported
ENV PYTHONPATH=/app

# Expose service port
EXPOSE 8000

# Command to run the app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
