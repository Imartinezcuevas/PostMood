import os
import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
import asyncpraw
from dotenv import load_dotenv
from pathlib import Path
import logging

# Configuración básica de logs
logging.basicConfig(level=logging.INFO)

# Cargar variables de entorno desde la raíz del proyecto
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Inicializar FastAPI
app = FastAPI(title="Reddit Worker")

# Configurar cliente de Reddit
reddit = asyncpraw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent="sentiment_analyzer_worker"
)

# Modelo de entrada
class KeywordRequest(BaseModel):
    keyword: str
    limit: int = 5

@app.get("/health")
def health_check():
    return {"status": "Ok"}

@app.post("/search")
async def search_posts(request: KeywordRequest):
    logging.info(f"Received request: {request}")
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

        return {"posts": posts}

    except Exception as e:
        logging.exception("Error searching Reddit")
        return {"error": str(e)}
