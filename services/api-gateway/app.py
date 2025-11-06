import os
import uuid
import httpx
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from asyncio import sleep

# ----------------------
# Configuration
# ----------------------
load_dotenv()
logging.basicConfig(level=logging.INFO)
REDDIT_WORKER_URL = os.getenv("REDDIT_WORKER_URL", "http://reddit-worker:8001")
SENTIMENT_ANALYZER_URL = os.getenv("SENTIMENT_ANALYZER_URL", "http://sentiment-analyzer:8002")

app = FastAPI(title="API Gateway")

# ----------------------
# Models
# ----------------------
class SearchRequest(BaseModel):
    keyword: str
    limit: int = 25

# ----------------------
# Endpoints
# ----------------------

@app.get("/")
def read_root():
    return {"message": "Hello from API Gateway!"}

@app.get("/health")
def health_check():
    return {"status": "Ok"}

@app.post("/search")
async def search_posts(request: SearchRequest):
    search_id = str(uuid.uuid4())
    logging.info(f"[{search_id}] New search: {request.keyword} (limit={request.limit})")

    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        # 1️⃣ Llamada al reddit-worker
        reddit_resp = await client.post(f"{REDDIT_WORKER_URL}/search", json=request.dict())
        reddit_resp.raise_for_status()
        posts = reddit_resp.json()["posts"]

        # 2️⃣ Llamada al sentiment-analyzer
        texts = [f"{p['title']} {p['text']}" for p in posts]
        sentiment_resp = await client.post(f"{SENTIMENT_ANALYZER_URL}/analyze", json={"posts": texts})
        sentiment_resp.raise_for_status()
        sentiments = sentiment_resp.json()["results"]

        # 3️⃣ Agregar sentimiento al resultado
        for post, sent in zip(posts, sentiments):
            post.update(sent)

        return {
            "search_id": search_id,
            "keyword": request.keyword,
            "results": posts,
        }