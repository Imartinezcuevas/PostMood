import os
import json
import re
import time
import logging
from fastapi import FastAPI
from pydantic import BaseModel
import asyncpraw
from dotenv import load_dotenv
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from common.logging_setup import setup_logging

# --------------------
# Configuración general
# -------------------
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = setup_logging()
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.handlers = []
uvicorn_logger.propagate = True

fastapi_logger = logging.getLogger("fastapi")
fastapi_logger.handlers = []
fastapi_logger.propagate = True

SERVICE_NAME = "reddit-ingestor"
LIMIT = int(os.getenv("LIMIT", 50))

logger.info(json.dumps({
    "event": "service_start",
    "service": SERVICE_NAME,
    "limit": LIMIT
}))

app = FastAPI(title="Reddit Ingestor")

# ------------------
# Reddit setup
# -----------------
try:
    reddit = asyncpraw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent="sentiment_analyzer_worker"
    )
    logger.info(json.dumps({
        "event": "reddit_client_initialized",
        "service": SERVICE_NAME
    }))
except Exception as e:
    logger.error(json.dumps({
        "event": "reddit_client_failed",
        "error": str(e),
        "service": SERVICE_NAME
    }))
    raise

# ------------------
# PostgreSQL setup
# -----------------
def get_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            dbname=os.getenv("POSTGRES_DB", "postmood"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        logger.error(json.dumps({
            "event": "db_connection_failed",
            "error": str(e),
            "service": SERVICE_NAME
        }))
        raise

def insert_post(conn, post):
    try:
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
    except Exception as e:
        logger.error(json.dumps({
            "event": "db_insert_failed",
            "error": str(e),
            "post_id": post.get("id"),
            "service": SERVICE_NAME
        }))

# ------------------
# Modelos
# -----------------
class KeywordRequest(BaseModel):
    keyword: str

# -------------------
# Limpieza de texto
# -------------------
def clean_text(text: str):
    if not text:
        return ""
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"@\w+", "<USER>", text)
    text = re.sub(r"[\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()

# ------------------
# Endpoints
# -----------------
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/search")
async def search_posts(request: KeywordRequest):
    start = time.time()
    keyword = request.keyword.strip()

    logger.info(json.dumps({
        "event": "search_start",
        "keyword": keyword,
        "limit": LIMIT,
        "service": SERVICE_NAME
    }))

    try:
        posts = []
        subreddit = await reddit.subreddit("all")

        async for submission in subreddit.search(keyword, limit=LIMIT):
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
            posts.append({
                "title": post["title"],
                "text": post["selftext"]
            })
            # Optional: store in DB
            # conn = get_connection()
            # insert_post(conn, post)

        elapsed = round(time.time() - start, 2)
        logger.info(json.dumps({
            "event": "search_complete",
            "keyword": keyword,
            "count": len(posts),
            "elapsed": elapsed,
            "service": SERVICE_NAME
        }))

        return {"from_cache": False, "posts": posts}

    except Exception as e:
        logger.error(json.dumps({
            "event": "search_failed",
            "error": str(e),
            "keyword": keyword,
            "service": SERVICE_NAME
        }))
        return {"error": str(e)}
