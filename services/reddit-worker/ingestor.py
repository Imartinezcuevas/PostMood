import os
import asyncio
import json
from fastapi import FastAPI
from pydantic import BaseModel
import asyncpraw
from dotenv import load_dotenv
from pathlib import Path
import logging
from redis import asyncio as aioredis

# --------------------
# General config
# -------------------
logging.basicConfig(level=logging.INFO)
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="Reddit Worker")

# ------------------
# Redis setup
# -----------------
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_TTL = int(os.getenv("REDIS_TTL", 600))
redis = None

# ------------------
# Reddit setup
# -----------------
reddit = asyncpraw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent="sentiment_analyzer_worker"
)

# ------------------
# Models
# -----------------
class KeywordRequest(BaseModel):
    keyword: str
    limit: int = 20

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

# ------------------
# Routs
# -----------------
@app.get("/health")
def health_check():
    return {"status": "Ok"}

@app.post("/search")
async def search_posts(request: KeywordRequest):
    logging.info(f"Received request: {request}")

    # 1. Search in cache
    cache_key = f"reddit:{request.keyword}:{request.limit}"
    if redis:
        cached_data = await redis.get(cache_key)
        if cached_data:
            logging.info(f"Cache hit for '{request.keyword}'")
            return {
                "from_cache": True,
                "posts": json.loads(cached_data)
            }
    # 2. Search in reddit
    try:
        posts = []
        subreddit = await reddit.subreddit("all")

        async for submission in subreddit.search(request.keyword, limit=request.limit):
            reddit_url = f"https://www.reddit.com{submission.permalink}"
            external_url = (
                submission.url
                if not submission.url.startswith("https://www.reddit.com")
                else None
            )

            posts.append({
                "title": submission.title,
                "text": submission.selftext,
                "reddit_url": reddit_url,
                "external_url": external_url,
                "score": submission.score,
                "created_utc": submission.created_utc
            })
    
    # 3. Save in cache
        if redis and posts:
            await redis.set(cache_key, json.dumps(posts), ex=REDIS_TTL)
            logging.info(f"Stored '{request.keyword}' results in cache ({REDIS_TTL}s TTL).")
        
        return {
            "from_cache": False,
            "posts": posts
        }

    except Exception as e:
        logging.exception("Error searching Reddit")
        return {"error": str(e)}
