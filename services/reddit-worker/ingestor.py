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
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from common.logging_setup import setup_logging
from monitoring.prometheus_middleware import PrometheusMiddleware, metrics_endpoint

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
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics_endpoint)

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
            text_content = submission.selftext
            if hasattr(submission, "crosspost_parent_list") and submission.crosspost_parent_list:
                text_content = submission.crosspost_parent_list[0].get("selftext", text_content)
            
            post_test = clean_text(text_content)
            post_full_text = clean_text(f"{submission.title} {text_content}".strip())
            post = {
                "id": submission.id,
                "post_id": submission.id,
                "source": "reddit",
                "title": clean_text(submission.title),
                "text": post_test,
                "full_text": post_full_text,
                "subreddit": str(submission.subreddit),
                "author": str(submission.author) if submission.author else "unknown",
                "reddit_score": submission.score,
                "created_at": datetime.utcfromtimestamp(submission.created_utc).isoformat() + "Z",
                "url": f"https://www.reddit.com{submission.permalink}"
            }
            posts.append({
                "id": post["id"],
                "post_id": post["post_id"],
                "source": post["source"],
                "title": post["title"],
                "text": post["text"],
                "full_text": post["full_text"],
                "url": post["url"],
                "created_at": post["created_at"],
                "reddit_score": post["reddit_score"],
            })

        posts = [p for p in posts if p.get("full_text", "").strip()]
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
