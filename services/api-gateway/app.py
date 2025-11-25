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
# Init
# ----------------------
load_dotenv()
logger = setup_logging()

app = FastAPI(title="API Gateway")
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics_endpoint)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------
# Env Vars
# ----------------------
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_TTL = int(os.getenv("REDIS_TTL", "600"))
QUEUE_NAME = os.getenv("QUEUE_NAME", "analysis")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "postmood")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postmood")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postmood")

redis_cache = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
redis_rq = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
queue = Queue(QUEUE_NAME, connection=redis_rq)

# ----------------------
# DB Connection
# ----------------------
def get_db_conn():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        cursor_factory=RealDictCursor
    )

# ----------------------
# Models
# ----------------------
class SearchRequest(BaseModel):
    keyword: str

class Correction(BaseModel):
    post_id: str
    keyword: str
    original_sentiment: str
    corrected_sentiment: str
    text: str
    score: float | None = None

ALLOWED_LABELS = {"very negative", "negative", "positive", "very positive"}


# ----------------------
# Helpers
# ----------------------
def process_posts_to_sentiment(posts):
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

    for p in posts:
        label = p.get("label", "")
        bucket_key = label_to_bucket.get(label, None)
        if bucket_key:
            buckets[bucket_key].append(p)
        else:
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
# Endpoints
# ----------------------
@app.post("/search")
def search_posts(request: SearchRequest):
    keyword = request.keyword.strip().lower()
    cache_key = f"analyzed:{keyword}"
    job_key = f"job:{keyword}"

    # Check cached processed results
    cached = redis_cache.get(cache_key)
    if cached:
        logger.info(f"[CACHE HIT] {keyword}")
        payload = json.loads(cached)
        return payload

    # Check if a job already exists
    existing_job = redis_cache.get(job_key)
    if existing_job:
        logger.info(f"[QUEUE] Already queued {keyword}")
        return {"status": "queued", "job_id": existing_job, "keyword": keyword}

    # Enqueue new job
    job = queue.enqueue(process_search, keyword)
    redis_cache.setex(job_key, REDIS_TTL, job.id)

    logger.info(f"Enqueued {job.id} for {keyword}")
    return {"status": "queued", "job_id": job.id, "keyword": keyword}


@app.get("/status/{job_id}")
def get_status(job_id: str):
    try:
        job = Job.fetch(job_id, connection=redis_rq)

        if job.is_finished:
            raw = job.result

            if "results" in raw:
                processed = process_posts_to_sentiment(raw["results"])
                keyword = job.args[0]

                response = {
                    "status": "done",
                    "keyword": keyword,
                    "data": processed
                }

                redis_cache.setex(f"analyzed:{keyword}", REDIS_TTL, json.dumps(response))
                return response

            return {"status": "done", "data": raw}

        if job.is_failed:
            return {"status": "failed", "error": str(job.exc_info)}

        return {"status": job.get_status()}

    except Exception:
        raise HTTPException(404, f"Job {job_id} not found")


@app.post("/correction")
def store_correction(c: Correction):
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
    return {"message": "API Gateway running"}


@app.get("/health")
def health():
    return {"status": "ok"}
