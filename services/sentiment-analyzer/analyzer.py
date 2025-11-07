import os
import json
import time
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline
from dotenv import load_dotenv
from common.logging_setup import setup_logging

# -------------------
# Config
# -----------------
load_dotenv()
logger = setup_logging()
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.handlers = []
uvicorn_logger.propagate = True

fastapi_logger = logging.getLogger("fastapi")
fastapi_logger.handlers = []
fastapi_logger.propagate = True

MODEL_NAME = os.getenv("MODEL_NAME", "tabularisai/multilingual-sentiment-analysis")
SERVICE_NAME = "sentiment-analyzer"

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

app = FastAPI(title="Sentiment Analyzer")

# -------------------
# Modelos
# -------------------
class AnalyzeRequest(BaseModel):
    posts: list[str]

# -------------------
# Endpoints
# -------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze_sentiment(request: AnalyzeRequest):
    start = time.time()
    results = []

    for text in request.posts:
        text_clean = text.strip()[:512]

        if not text_clean:
            results.append({"text": text, "label": "neutral", "score": 0.0})
            continue

        try:
            res = analyzer(text_clean)[0]
            results.append({
                "text": text_clean,
                "label": res["label"].lower(),
                "score": res["score"]
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
