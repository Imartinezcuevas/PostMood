from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx
import os

load_dotenv()

app = FastAPI(title="API Gateway")

REDDIT_WORKER_URL = os.getenv("REDDIT_WORKER_URL", "http://localhost:8001")

class SearchRequest(BaseModel):
    keyword: str
    limit: int = 5

@app.get("/")
def read_root():
    return {"message": "Hello from API Gateway!"}

@app.get("/health")
def health_check():
    return {"status": "Ok"}

@app.post("/search")
async def search_posts(request: SearchRequest):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{REDDIT_WORKER_URL}/search", json=request.dict())
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Connection error: {str(e)}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=response.status_code, detail=response.text)