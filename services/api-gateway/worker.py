import logging
import time
import os
from dotenv import load_dotenv
from redis import Redis
from rq import Worker, Queue

# ----------------------
# Config
# ----------------------
load_dotenv()
redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = int(os.getenv("REDIS_PORT", 6379))
queue_name = os.getenv("QUEUE_NAME", "analysis")

logging.basicConfig(level=logging.INFO, format="[WORKER] %(asctime)s | %(message)s")

# ----------------------
# Esperar a que Redis esté listo
# ----------------------
def wait_for_redis(host, port, retries=10, delay=3):
    for i in range(retries):
        try:
            conn = Redis(host=host, port=port)
            conn.ping()
            logging.info(f"Connected to Redis at {host}:{port}")
            return conn
        except Exception as e:
            logging.warning(f"Redis not ready ({e}), retrying {i+1}/{retries}...")
            time.sleep(delay)
    raise ConnectionError(f"Failed to connect to Redis after {retries} retries")

# ----------------------
# Arranque del worker
# ----------------------
if __name__ == "__main__":
    redis_conn = wait_for_redis(redis_host, redis_port)
    listen = [queue_name]

    queues = [Queue(name, connection=redis_conn) for name in listen]
    worker = Worker(queues=queues, connection=redis_conn)

    logging.info(f"Starting RQ worker listening on queues: {listen}")
    worker.work(with_scheduler=True)
