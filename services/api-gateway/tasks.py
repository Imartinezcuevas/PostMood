import os
import httpx
import json
import time
from dotenv import load_dotenv
from redis import Redis
from common.logging_setup import setup_logging

# -----------------------------------------------------------
# Environment & Logging
# -----------------------------------------------------------
# Load environment variables from .env and initialize structured logging.
load_dotenv()
logger = setup_logging()
logger.info("Initializing tasks worker")

# Service URLs for worker orchestration
REDDIT_WORKER_URL = os.getenv("REDDIT_WORKER_URL", "http://reddit-worker:8001")
SENTIMENT_ANALYZER_URL = os.getenv("SENTIMENT_ANALYZER_URL", "http://sentiment-analyzer:8002")

# Redis configuration for caching task results
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_TTL = int(os.getenv("REDIS_TTL", 600))

# -----------------------------------------------------------
# Background Task
# -----------------------------------------------------------
def process_search(keyword: str):
    """
    Executes a background task for analyzing Reddit posts related to a keyword.
    
    Steps:
    1. Fetch posts from reddit-worker microservice.
    2. Send posts to sentiment-analyzer microservice.
    3. Merge sentiment results into posts.
    4. Cache the combined results in Redis for future requests.
    
    Args:
        keyword (str): Search keyword.
    
    Returns:
        dict: Aggregated posts with sentiment labels and metadata.
    
    Raises:
        Exception: Any network or processing error is logged and re-raised.
    """
    redis = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    cache_key = f"reddit:{keyword}"

    try:
        start = time.time()
        logger.info(json.dumps({"event": "task_started", "keyword": keyword}))

        # 1️. Fetch posts from reddit-worker
        with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
            reddit_resp = client.post(f"{REDDIT_WORKER_URL}/search", json={"keyword": keyword})
            reddit_resp.raise_for_status()
            posts = reddit_resp.json()["posts"]
            logger.info(json.dumps({"event": "reddit_fetched", "keyword": keyword, "posts": len(posts)}))

        # 2️. Analyze sentiment for each post
            texts = [p["full_text"] for p in posts]
            sentiment_resp = client.post(f"{SENTIMENT_ANALYZER_URL}/analyze", json={"posts": texts})
            sentiment_resp.raise_for_status()
            sentiments = sentiment_resp.json()["results"]
            logger.info(json.dumps({"event": "sentiment_done", "keyword": keyword, "results": len(sentiments)}))

        # 3️. Merge sentiment results into original posts
        for post, sent in zip(posts, sentiments):
            post.setdefault("post_id", post.get("id"))
            post.setdefault("source", "reddit")
            post.setdefault("title", post.get("title", ""))
            post.setdefault("text", post.get("text", ""))
            post.setdefault("full_text", post.get("full_text", ""))
            post.setdefault("url", post.get("url", ""))
            post.setdefault("created_at", post.get("created_at", None))
            post.setdefault("reddit_score", post.get("reddit_score", None))

            label = sent.get("label") if isinstance(sent, dict) else None
            score_val = sent.get("score") if isinstance(sent, dict) else None

            post["label"] = label
            post["original_sentiment"] = label
            post["score"] = score_val

            post["keyword"] = keyword

        # 4. Cache results
        payload = {"results": posts, "cached_at": time.time()}
        redis.setex(cache_key, REDIS_TTL, json.dumps(payload))

        elapsed = time.time() - start
        logger.info(json.dumps({
            "event": "task_completed",
            "keyword": keyword,
            "posts": len(posts),
            "elapsed_s": round(elapsed, 2)
        }))
        return payload

    except Exception as e:
        # Log and propagate errors for monitoring & retries
        logger.error(json.dumps({
            "event": "task_failed",
            "keyword": keyword,
            "error": str(e)
        }))
        raise

    finally:
        # Ensure Redis connection is always closed
        redis.close()
