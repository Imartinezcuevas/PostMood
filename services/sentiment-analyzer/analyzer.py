import os
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline
from dotenv import load_dotenv

# -------------------
# Config
# -----------------
load_dotenv()
logging.basicConfig(level=logging.INFO)

MODEL_NAME = os.getenv("MODEL_NAME", "tabularisai/multilingual-sentiment-analysis")

logging.info(f"Loading sentiment model: {MODEL_NAME}")
analyzer = pipeline("sentiment-analysis", model=MODEL_NAME)

app = FastAPI(title="Sentiment analyzer")

# -------------
# Models
# -------------
class AnalyzeRequest(BaseModel):
    posts: list[str]

# ---------------------
# Endpoints
# -----------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/analyze")
async def analyze_sentiment(request: AnalyzeRequest):
    results = []
    for text in request.posts:
        if not text.strip():
            results.append({'text': text, "label": "neutral", "score": 0.0})
        try:
            result = analyzer(text[:512])[0]
            results.append({
                "text": text[:512],
                "label": result["label"].lower(),
                "score": result["score"]
            })
        except Exception as e:
            logging.error(f"Error analyzing text: {e}")
            results.append({"text": text, "label": "error", "score": 0.0})
    return {"results": results}