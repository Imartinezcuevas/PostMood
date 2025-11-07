import time
import os
from dotenv import load_dotenv
from redis import Redis
from rq import Worker, Queue
from common.logging_setup import setup_logging
import json

# ----------------------
# Config
# ----------------------
load_dotenv()
logger = setup_logging()

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
QUEUE_NAME = os.getenv("QUEUE_NAME", "analysis")
SERVICE_NAME = "analyzer-worker"

logger.info(json.dumps({
    "event": "worker_init",
    "service": SERVICE_NAME,
    "queue": QUEUE_NAME
}))

# ----------------------
# Esperar a que Redis esté listo
# ----------------------
def wait_for_redis(host, port, retries=10, delay=3):
    for i in range(retries):
        try:
            conn = Redis(host=host, port=port)
            conn.ping()
            logger.info(json.dumps({
                "event": "redis_connected",
                "host": host,
                "port": port
            }))
            return conn
        except Exception as e:
            logger.warning(json.dumps({
                "event": "redis_retry",
                "attempt": i + 1,
                "error": str(e)
            }))
            time.sleep(delay)
    raise ConnectionError(f"Failed to connect to Redis after {retries} retries")

# ----------------------
# Arranque del worker
# ----------------------
if __name__ == "__main__":
    redis_conn = wait_for_redis(REDIS_HOST, REDIS_PORT)
    listen = [QUEUE_NAME]

    queues = [Queue(name, connection=redis_conn) for name in listen]
    worker = Worker(queues=queues, connection=redis_conn)

    logger.info(json.dumps({
        "event": "worker_started",
        "queues": listen,
        "service": SERVICE_NAME
    }))

    try:
        worker.work(with_scheduler=True)
    except KeyboardInterrupt:
        logger.warning(json.dumps({
            "event": "worker_stopped",
            "service": SERVICE_NAME
        }))
    except Exception as e:
        logger.error(json.dumps({
            "event": "worker_crashed",
            "service": SERVICE_NAME,
            "error": str(e)
        }))
        raise
