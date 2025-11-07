FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y curl && pip install --no-cache-dir -r requirements.txt

COPY analyzer.py .

COPY ../../common /app/common
ENV PYTHONPATH=/app

EXPOSE 8002

CMD ["uvicorn", "analyzer:app", "--host", "0.0.0.0", "--port", "8002"]