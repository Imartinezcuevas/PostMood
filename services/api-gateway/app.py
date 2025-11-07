import os
import uuid
import httpx
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from asyncio import sleep
from redis import asyncio as aioredis
import json
import time

# ----------------------
# Configuration
# ----------------------
load_dotenv()
logging.basicConfig(level=logging.INFO)
REDDIT_WORKER_URL = os.getenv("REDDIT_WORKER_URL", "http://reddit-worker:8001")
SENTIMENT_ANALYZER_URL = os.getenv("SENTIMENT_ANALYZER_URL", "http://sentiment-analyzer:8002")

app = FastAPI(title="API Gateway")

# ------------------
# Redis setup
# -----------------
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_TTL = int(os.getenv("REDIS_TTL", 600))
redis = None

# ------------------
# Events
# -----------------
@app.on_event("startup")
async def startup():
    global redis
    try:
        redis = await aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", encoding="utf-8", decode_responses=True)
        logging.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        logging.error(f"Failed to connect to Redis: {e}")
        raise

@app.on_event("shutdown")
async def shutdown():
    if redis:
        await redis.close()
        logging.info("Redis connection closed.")

# ----------------------
# Models
# ----------------------
class SearchRequest(BaseModel):
    keyword: str

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
    logging.info(f"[{search_id}] New search: {request.keyword}")

    cache_key = f"reddit:{request.keyword}"
    if redis:
        cached_data = await redis.get(cache_key)
        if cached_data:
            logging.info(f"Cache hit for '{request.keyword}'")
            cached = json.loads(cached_data)
            return {
                "search_id": search_id,
                "keyword": request.keyword,
                **cached
            }

    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        # 1️. Llamada al reddit-worker
        try:
            reddit_resp = await client.post(f"{REDDIT_WORKER_URL}/search", json=request.dict())
            reddit_resp.raise_for_status()
            posts = reddit_resp.json()["posts"]
        except Exception as e:
            logging.error(f"[{search_id}] Reddit worker failed: {e}")
            raise HTTPException(status_code=502, detail="Reddit worker unavailable")

        # 2️. Llamada al sentiment-analyzer
        try: 
            texts = [f"{p['title']} {p['text']}" for p in posts]
            sentiment_resp = await client.post(f"{SENTIMENT_ANALYZER_URL}/analyze", json={"posts": texts})
            sentiment_resp.raise_for_status()
            sentiments = sentiment_resp.json()["results"]
        except Exception as e:
            logging.error(f"[{search_id}] Sentiment analyzer failed: {e}")
            raise HTTPException(status_code=502, detail="Sentiment analyzer unavailble")

    # 3️ Agregar sentimiento al resultado
    for post, sent in zip(posts, sentiments):
        post.update(sent)

    if redis and posts:
        payload = {
            "results": post,
            "cached_at": time.time()
        }
        await redis.set(cache_key, json.dumps(payload), ex=REDIS_TTL)
        logging.info(f"Stored '{request.keyword}' results in cache ({REDIS_TTL}s TTL).")

    return {
        "search_id": search_id,
        "keyword": request.keyword,
        "results": posts,
    }