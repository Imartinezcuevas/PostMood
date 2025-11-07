import os
import httpx
import logging
import json
import time
from dotenv import load_dotenv
from redis import Redis

load_dotenv()
logging.basicConfig(level=logging.INFO)

REDDIT_WORKER_URL = os.getenv("REDDIT_WORKER_URL", "http://reddit-worker:8001")
SENTIMENT_ANALYZER_URL = os.getenv("SENTIMENT_ANALYZER_URL", "http://sentiment-analyzer:8002")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_TTL = int(os.getenv("REDIS_TTL", 600))


def process_search(keyword: str):
    """Tarea ejecutada en background (por el worker)."""
    redis = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    cache_key = f"reddit:{keyword}"

    try:
        start = time.time()

        # 1️. Llamada al reddit-worker
        with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
            reddit_resp = client.post(f"{REDDIT_WORKER_URL}/search", json={"keyword": keyword})
            reddit_resp.raise_for_status()
            posts = reddit_resp.json()["posts"]

        # 2️. Llamada al sentiment-analyzer
            texts = [f"{p['title']} {p['text']}" for p in posts]
            sentiment_resp = client.post(f"{SENTIMENT_ANALYZER_URL}/analyze", json={"posts": texts})
            sentiment_resp.raise_for_status()
            sentiments = sentiment_resp.json()["results"]

        # 3️. Merge de resultados
        for post, sent in zip(posts, sentiments):
            post.update(sent)

        payload = {"results": posts, "cached_at": time.time()}

        redis.setex(cache_key, REDIS_TTL, json.dumps(payload))
        elapsed = time.time() - start
        logging.info(f"[TASK] Finished '{keyword}' | {len(posts)} posts | {elapsed:.2f}s")
        return payload

    except Exception as e:
        logging.error(f"[TASK] Failed '{keyword}': {e}")
        raise

    finally:
        redis.close()
