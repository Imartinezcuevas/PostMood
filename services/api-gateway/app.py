import os
import json
import logging
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
# Configuration
# ----------------------
load_dotenv()
logger = setup_logging()
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.handlers = []
uvicorn_logger.propagate = True

fastapi_logger = logging.getLogger("fastapi")
fastapi_logger.handlers = []
fastapi_logger.propagate = True
logger.info("Initializing API Gateway")
app = FastAPI(title="API Gateway")

app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics_endpoint)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_TTL = int(os.getenv("REDIS_TTL", "600").strip())
QUEUE_NAME = os.getenv("QUEUE_NAME", "analysis")

redis_cache = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
redis_rq = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
queue = Queue(QUEUE_NAME, connection=redis_rq)

# ----------------------
# Models
# ----------------------
class SearchRequest(BaseModel):
    keyword: str

# ----------------------
# Helper Functions
# ----------------------
def process_posts_to_sentiment(posts):
    """
    Procesa un array de posts con labels y los convierte en la estructura
    de sentimientos agrupados que espera el frontend.
    """
    sentiment_buckets = {
        "veryNegative": [],
        "negative": [],
        "positive": [],
        "veryPositive": [],
    }

    for post in posts:
        if post["label"] == "very negative":
            sentiment_buckets["veryNegative"].append(post)
        elif post["label"] == "negative":
            sentiment_buckets["negative"].append(post)
        elif post["label"] == "positive":
            sentiment_buckets["positive"].append(post)
        elif post["label"] == "very positive":
            sentiment_buckets["veryPositive"].append(post)

    total = sum(len(v) for v in sentiment_buckets.values()) or 1
    
    processed_data = {}
    for k, v in sentiment_buckets.items():
        processed_data[k] = {
            "percentage": round(len(v) / total * 100, 2),
            "examples": [p["text"] for p in v[:5]]
        }

    return processed_data

# ----------------------
# Endpoints
# ----------------------
@app.get("/")
def read_root():
    return {"message": "Hello from API Gateway!"}

@app.get("/health")
def health_check():
    return {"status": "Ok"}

@app.post("/search")
def search_posts(request: SearchRequest):
    keyword = request.keyword.strip().lower()
    cache_key = f"analyzed:{keyword}"
    job_key = f"job:{keyword}"

    cached_data = redis_cache.get(cache_key)
    if cached_data:
        logger.info(f"[CACHE HIT] Returning cached analyzed results for '{keyword}'")
        cached_result = json.loads(cached_data)
        return {
            "status": "done",
            "keyword": keyword,
            "data": cached_result["data"]
        }
    
    existing_job_id = redis_cache.get(job_key)
    if existing_job_id:
        logger.info(f"[QUEUE] Job already enqueued for '{keyword}' ({existing_job_id})")
        return {
            "status": "queued",
            "job_id": existing_job_id,
            "keyword": keyword
        }
    
    job = queue.enqueue(process_search, keyword)
    redis_cache.setex(job_key, REDIS_TTL, job.id)

    logger.info(f"Enqueued job {job.id} for keyword '{keyword}'")
    return {"status": "queued", "job_id": job.id, "keyword": keyword}

@app.get("/status/{job_id}")
def get_status(job_id: str):
    try:
        job = Job.fetch(job_id, connection=redis_rq)

        if job.is_finished:
            raw_result = job.result
            
            if "results" in raw_result:
                processed_data = process_posts_to_sentiment(raw_result["results"])
                
                keyword = job.kwargs.get('keyword', job.args[0] if job.args else 'unknown')
                
                result = {
                    "status": "done",
                    "keyword": keyword,
                    "data": processed_data
                }
                
                cache_key = f"analyzed:{keyword}"
                redis_cache.setex(cache_key, REDIS_TTL, json.dumps(result))
                logger.info(f"[CACHE SAVE] Saved analyzed results for '{keyword}'")
                
                return {
                    "status": "done",
                    "result": result
                }
            else:
                return {"status": "done", "result": raw_result}
                
        elif job.is_failed:
            return {"status": "failed", "error": str(job.exc_info)}
        else:
            return {"status": job.get_status()}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Job not found: {e}")
    
@app.post("/analyze")
def analyze_keyword(request: SearchRequest):
    keyword = request.keyword.strip().lower()
    cache_key = f"analyzed:{keyword}"
    job_key = f"job:{keyword}"
    
    cached_analyzed = redis_cache.get(cache_key)
    if cached_analyzed:
        logger.info(f"[CACHE HIT] Returning cached analyzed results for '{keyword}'")
        return json.loads(cached_analyzed)
    
    existing_job_id = redis_cache.get(job_key)
    if existing_job_id:
        logger.info(f"[QUEUE] Job already enqueued for '{keyword}' ({existing_job_id})")
        return {
            "status": "queued",
            "job_id": existing_job_id,
            "keyword": keyword
        }
    
    # No hay nada en caché, encolar el job
    job = queue.enqueue(process_search, keyword)
    redis_cache.setex(job_key, REDIS_TTL, job.id)
    
    logger.info(f"Enqueued job {job.id} for keyword '{keyword}'")
    return {"status": "queued", "job_id": job.id, "keyword": keyword}