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
    """Encola la tarea y devuelve el ID."""
    keyword = request.keyword.strip().lower()
    cache_key = f"reddit:{keyword}"
    job_key = f"job:{keyword}"

    # Check if results are already cached
    cached_data = redis_cache.get(cache_key)
    if cached_data:
        logger.info(f"[CACHE HIT] Returning cached results for '{keyword}'")
        return {
            "status": "done",
            "keyword": keyword,
            "results": json.loads(cached_data)["results"]
        }
    
    # Check if there's already a job running for this keyword
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
    """Consulta el estado de una tarea."""
    try:
        job = Job.fetch(job_id, connection=redis_rq)

        if job.is_finished:
            return {"status": "done", "result": job.result}
        elif job.is_failed:
            return {"status": "failed", "error": str(job.exc_info)}
        else:
            return {"status": job.get_status()}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Job not found: {e}")
