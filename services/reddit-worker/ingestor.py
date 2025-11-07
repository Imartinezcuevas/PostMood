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
import psycopg2
from psycopg2.extras import RealDictCursor

# --------------------
# General config
# -------------------
logging.basicConfig(level=logging.INFO)
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
LIMIT = int(os.getenv("LIMIT", 50))

app = FastAPI(title="Reddit Worker")

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
# Routs
# -----------------
@app.get("/health")
def health_check():
    return {"status": "Ok"}

@app.post("/search")
async def search_posts(request: KeywordRequest):
    logging.info(f"Received request: {request}")
    try:
        posts = []
        subreddit = await reddit.subreddit("all")

        async for submission in subreddit.search(request.keyword, limit=LIMIT):
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

        return {
            "from_cache": False,
            "posts": posts
        }

    except Exception as e:
        logging.exception("Error searching Reddit")
        return {"error": str(e)}
