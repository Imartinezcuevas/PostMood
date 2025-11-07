# Base image
FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN apt-get update && apt-get install -y curl && pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

COPY ../../common /app/common
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]