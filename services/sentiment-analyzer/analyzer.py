import os
import json
import time
import logging
import re
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline
from dotenv import load_dotenv
from common.logging_setup import setup_logging
from monitoring.prometheus_middleware import PrometheusMiddleware, metrics_endpoint

# ----------------------
# Application initialization
# ----------------------
# Loads environment variables from .env and sets up structured loggins.
load_dotenv()
logger = setup_logging()
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.handlers = []
uvicorn_logger.propagate = True

fastapi_logger = logging.getLogger("fastapi")
fastapi_logger.handlers = []
fastapi_logger.propagate = True

# Service constants
MODEL_NAME = os.getenv("MODEL_NAME", "tabularisai/multilingual-sentiment-analysis")
SERVICE_NAME = "sentiment-analyzer"

# Load and initialize the sentiment analysis model
logger.info(json.dumps({
    "event": "model_loading",
    "model": MODEL_NAME,
    "service": SERVICE_NAME
}))
try:
    analyzer = pipeline("sentiment-analysis", model=MODEL_NAME)
    logger.info(json.dumps({
        "event": "model_loaded",
        "model": MODEL_NAME,
        "service": SERVICE_NAME,
        "device": "cpu"
    }))
except Exception as e:
    logger.error(json.dumps({
        "event": "model_load_failed",
        "error": str(e),
        "service": SERVICE_NAME
    }))
    raise

# Initialize FastAPI application and Prometheus monitoring
app = FastAPI(title="Sentiment Analyzer")
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics_endpoint)

# -------------------
# Data Models
# -------------------
class AnalyzeRequest(BaseModel):
    """
    Model for sentiment analysis requests.

    Attributes:
        posts (list[str]): List of text strings to analyze.
    """
    posts: list[str]


def normalize_label(raw_label: str) -> str:
    """
    Normalize raw sentiment labels returned by the model into a consistent set:
    'very positive', 'positive', 'negative', 'very negative'.

    Args:
        raw_label (str): Raw label from the model output.

    Returns:
        str: Normalized sentiment label.
    """
    if not raw_label:
        return "positive"
    s = raw_label.lower().strip().replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    if "very" in s and "positive" in s:
        return "very positive"
    if "very" in s and "negative" in s:
        return "very negative"
    if "positive" in s:
        return "positive"
    if "negative" in s:
        return "negative"
    return "positive"

# -------------------
# API Endpoints
# -------------------
@app.get("/health")
def health_check():
    """
    Health check endpoint for the sentiment analyzer service.
    """
    return {"status": "ok"}


@app.post("/analyze")
async def analyze_sentiment(request: AnalyzeRequest):
    """
    Analyze a batch of posts for sentiment.

    Steps:
        1. Preprocess and truncate text to 512 characters.
        2. Use the Hugging Face pipeline to predict sentiment.
        3. Normalize model labels to consistent format.
        4. Return text, sentiment label, and score.

    Args:
        request (AnalyzeRequest): Request payload containing list of posts.

    Returns:
        dict: Analysis results for each post.
    """
    start = time.time()
    results = []

    for text in request.posts:
        text_clean = text.strip()[:512]

        # Skip empty or whitespace-only text
        if not text_clean:
            results.append({"text": text, "label": "neutral", "score": 0.0})
            continue

        try:
            res = analyzer(text_clean)[0]
            label = normalize_label(res.get("label", ""))
            score = float(res.get("score", 0.0))
            results.append({
                "text": text_clean,
                "label": label,
                "score": score
            })
        except Exception as e:
            logger.error(json.dumps({
                "event": "analyze_error",
                "error": str(e),
                "text_sample": text_clean[:50],
                "service": SERVICE_NAME
            }))
            results.append({"text": text_clean, "label": "error", "score": 0.0})

    elapsed = round(time.time() - start, 2)
    logger.info(json.dumps({
        "event": "analyze_done",
        "count": len(request.posts),
        "elapsed": elapsed,
        "service": SERVICE_NAME
    }))
    return {"results": results}
