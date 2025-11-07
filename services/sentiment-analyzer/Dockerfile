# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY services/sentiment-analyzer/requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy service code
COPY services/sentiment-analyzer/ ./

# Copy shared modules
COPY common /app/common
COPY monitoring /app/monitoring

# Set Python path so common modules can be imported
ENV PYTHONPATH=/app

# Expose service port
EXPOSE 8002

# Command to run the app
CMD ["uvicorn", "analyzer:app", "--host", "0.0.0.0", "--port", "8002"]
