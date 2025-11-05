import os
import asyncio
import json
import re
from fastapi import FastAPI
from pydantic import BaseModel
import asyncpraw
from dotenv import load_dotenv
from pathlib import Path
import logging
from redis import asyncio as aioredis
import psycopg2
from psycopg2.extras import RealDictCursor

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
# Postgres setup
# -----------------
def get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        dbname=os.getenv("POSTGRES_DB", "postmood"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        cursor_factory=RealDictCursor
    )

def insert_post(conn, post):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO reddit_posts (id, title, selftext, subreddit, author, score, created_utc, url)
            VALUES (%s,%s,%s,%s,%s,%s,to_timestamp(%s),%s)
            ON CONFLICT (id) DO NOTHING;
        """, (
            post["id"], post["title"], post["selftext"], post["subreddit"],
            post["author"], post["score"], post["created_utc"], post["url"]
        ))
    conn.commit()

# ------------------
# Models
# -----------------
class KeywordRequest(BaseModel):
    keyword: str
    limit: int = 20

# -------------------
# Cleaning
# -------------------
def clean_text(text: str):
    if not text:
        return ""
    text = re.sub(r"http\S+", "",  text)
    text = re.sub(r"@\w+", "<USER>", text)
    text = re.sub(r"[\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()

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
        conn = get_connection()
        subreddit = await reddit.subreddit("all")

        async for submission in subreddit.search(request.keyword, limit=request.limit):
            post = {
                "id": submission.id,
                "title": clean_text(submission.title),
                "selftext": clean_text(submission.selftext),
                "subreddit": str(submission.subreddit),
                "author": str(submission.author) if submission.author else "unknown",
                "score": submission.score,
                "created_utc": submission.created_utc,
                "url": f"https://www.reddit.com{submission.permalink}"
            }

            insert_post(conn, post)
            posts.append({
                "title": post["title"],
                "text": post["selftext"]
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
