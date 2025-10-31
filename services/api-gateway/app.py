from fastapi import FastAPI

app = FastAPI(title="API Gateway")

@app.get("/")
def read_root():
    return {"message": "Hello from API Gateway!"}

@app.get("/health")
def health_check():
    return {"status": "Ok"}