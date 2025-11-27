import os
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from redis import Redis
from rq import Queue
from rq.job import Job
from tasks import process_search
from common.logging_setup import setup_logging
from monitoring.prometheus_middleware import PrometheusMiddleware, metrics_endpoint
from fastapi.middleware.cors import CORSMiddleware

# ----------------------
# Application initialization
# ----------------------
# Loadas environment variables from .env and sets up structured loggins.
load_dotenv()
logger = setup_logging()

# Create the FastAPI application and attach Prometheus metrics middleware.
app = FastAPI(title="API Gateway")
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics_endpoint)

# Configure CORS  to allow browser access from the frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------
# Environment configuration
# ----------------------------------
# Redis environment defaults support containerized deployment.
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_TTL = int(os.getenv("REDIS_TTL", "600"))
QUEUE_NAME = os.getenv("QUEUE_NAME", "analysis")

# Postgress environment configuration.
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "postmood")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postmood")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postmood")

# Redis clients: one for cache (string responses), one for RQ.
redis_cache = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
redis_rq = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
queue = Queue(QUEUE_NAME, connection=redis_rq)

# ----------------------
# DB Connection
# ----------------------
def get_db_conn():
    """
    Establishes a new PostgreSQL connection using RealDictCursor to return rows as dicts.
    Caller is responsible for closing the connection.
    """
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        cursor_factory=RealDictCursor
    )

# ----------------------
# Request/response models
# ----------------------
class SearchRequest(BaseModel):
    """Incoming paiload for keyword search request."""
    keyword: str

class Correction(BaseModel):
    """
    Model for user-provided sentiment corrections.
    Score is optional as manual corrections may omit confidence.
    """
    post_id: str
    keyword: str
    original_sentiment: str
    corrected_sentiment: str
    text: str
    score: float | None = None

# Allowed sentiment labels coming from the classifier.
ALLOWED_LABELS = {"very negative", "negative", "positive", "very positive"}


# ----------------------
# Helper functions
# ----------------------
def process_posts_to_sentiment(posts):
    """
    Aggregates sentiment-labeled posts into predefined buckets and computes percentage distribution.
    Returns both distribution and sample examples (up to 10 per bucket).
    """
    buckets = {
        "veryNegative": [],
        "negative": [],
        "positive": [],
        "veryPositive": [],
    }

    label_to_bucket = {
        "very negative": "veryNegative",
        "negative": "negative",
        "positive": "positive",
        "very positive": "veryPositive",
    }

    # Assign posts into buckets; defaults to positive if label is unknown.
    for p in posts:
        label = p.get("label", "")
        bucket_key = label_to_bucket.get(label, None)
        if bucket_key:
            buckets[bucket_key].append(p)
        else:
            #Fallback: unknown labels are treated as positive.
            buckets["positive"].append(p)

    total = sum(len(v) for v in buckets.values()) or 1

    return {
        k: {
            "percentage": round(len(v) / total * 100, 2),
            "examples": v[:10],
        }
        for k, v in buckets.items()
    }


# ----------------------
# API endpoints
# ----------------------
@app.post("/search")
def search_posts(request: SearchRequest):
    """
    Initiates a sentiment analysis job for the given keyword.
    - Returns cached results if available.
    - Prevents duplicate jobs by storing job IDs in Redis.
    - Enqueues a new job when necessary.
    """
    keyword = request.keyword.strip().lower()
    cache_key = f"analyzed:{keyword}"
    job_key = f"job:{keyword}"

    # 1. Serve cached result if available.
    cached = redis_cache.get(cache_key)
    if cached:
        logger.info(f"[CACHE HIT] {keyword}")
        payload = json.loads(cached)
        return payload

    # 2. Avoid duplicate jobs via Redis lock.
    existing_job = redis_cache.get(job_key)
    if existing_job:
        logger.info(f"[QUEUE] Already queued {keyword}")
        return {"status": "queued", "job_id": existing_job, "keyword": keyword}

    # 3. Enqueue new job
    job = queue.enqueue(process_search, keyword)
    redis_cache.setex(job_key, REDIS_TTL, job.id)

    logger.info(f"Enqueued {job.id} for {keyword}")
    return {"status": "queued", "job_id": job.id, "keyword": keyword}


@app.get("/status/{job_id}")
def get_status(job_id: str):
    """
    Retrieves the execution status of an RQ job and post.processes resutls:
    - On success: transforms raw classifier output into sentiment buckets.
    - On failure: exposes error information.
    - On unknown ID: returns HTTP 404.
    """
    try:
        job = Job.fetch(job_id, connection=redis_rq)

        if job.is_finished:
            raw = job.result

            #If results follow the expected structure, post-process them.
            if "results" in raw:
                processed = process_posts_to_sentiment(raw["results"])
                keyword = job.args[0]

                response = {
                    "status": "done",
                    "keyword": keyword,
                    "data": processed
                }

                # Cache processed payload for future requests.
                redis_cache.setex(f"analyzed:{keyword}", REDIS_TTL, json.dumps(response))
                return response
            # Fallback: return raw output untouched.
            return {"status": "done", "data": raw}

        if job.is_failed:
            return {"status": "failed", "error": str(job.exc_info)}

        return {"status": job.get_status()}

    except Exception:
        # Invalid job IDs
        raise HTTPException(404, f"Job {job_id} not found")


@app.post("/correction")
def store_correction(c: Correction):
    """
    Stores a user-submitted sentiment correction.
    Validates labels and inserts the record into PostgreSQL.
    """
    # Input validation against allowed labels.
    if c.original_sentiment not in ALLOWED_LABELS:
        raise HTTPException(400, "Invalid original_sentiment")
    if c.corrected_sentiment not in ALLOWED_LABELS:
        raise HTTPException(400, "Invalid corrected_sentiment")

    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sentiment_corrections
                (post_id, keyword, text, original_sentiment, corrected_sentiment, score, source, approved)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (c.post_id, c.keyword, c.text, c.original_sentiment,
                  c.corrected_sentiment, c.score, "manual", True))
        conn.commit()
        conn.close()
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"[DB ERROR] {e}")
        raise HTTPException(500, "Insert failed")


@app.get("/")
def root():
    """Root endpoint used for availability checks."""
    return {"message": "API Gateway running"}


@app.get("/health")
def health():
    """Simple liveness probe used for container orchetration."""
    return {"status": "ok"}
