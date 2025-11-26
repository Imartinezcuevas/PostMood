FROM python:3.11-slim

WORKDIR /app

COPY services/dataset-generator/ ./

COPY services/dataset-generator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]