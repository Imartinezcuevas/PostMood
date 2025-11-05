import os
import uuid
import httpx
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from asyncio import sleep

# ----------------------
# Configuration
# ----------------------
load_dotenv()
logging.basicConfig(level=logging.INFO)
REDDIT_WORKER_URL = os.getenv("REDDIT_WORKER_URL", "http://reddit-worker:8001")

app = FastAPI(title="API Gateway")

# ----------------------
# Models
# ----------------------
class SearchRequest(BaseModel):
    keyword: str
    limit: int = 5

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
async def search_posts(request: SearchRequest):
    search_id = str(uuid.uuid4())
    logging.info(f"[{search_id} New search: {request.keyword} (limit={request.limit})]")

    max_retries = 3
    delay = 1

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        for attempt in range(1, max_retries + 1):
            try:
                response = await client.post(f"{REDDIT_WORKER_URL}/search", json=request.dict())
                response.raise_for_status()
                logging.info(f"[{search_id}] Success on attemp {attempt}")
                return {
                    "search_id": search_id,
                    "keyword": request.keyword,
                    "data": response.json(),
                }
            except httpx.RequestError as e:
                logging.warning(f"[{search_id}] Network error (attempt {attempt}): {e}")
            except httpx.HTTPStatusError as e:
                logging.warning(f"[{search_id}] Reddit worker returned {e.response.status_code}: {e.response.text}")
            
            if attempt < max_retries:
                await sleep(delay)
                delay *= 2
    raise HTTPException(status_code=502, detail=f"[{search_id}] Reddit worker unavaliable after {max_retries} attemps.")