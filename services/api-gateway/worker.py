import time
import os
from dotenv import load_dotenv
from redis import Redis
from rq import Worker, Queue
from common.logging_setup import setup_logging
import json

# -----------------------------------------------------------
# Environment & Logging Setup
# -----------------------------------------------------------
# Load environment variables and initialize structured logging.
load_dotenv()
logger = setup_logging()

# Redis configuration for task queues
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
QUEUE_NAME = os.getenv("QUEUE_NAME", "analysis")

# Worker service identifier for logging and monitoring
SERVICE_NAME = "analyzer-worker"

logger.info(json.dumps({
    "event": "worker_init",
    "service": SERVICE_NAME,
    "queue": QUEUE_NAME
}))

# -----------------------------------------------------------
# Helper: Wait for Redis
# -----------------------------------------------------------
def wait_for_redis(host, port, retries=10, delay=3):
    """
    Waits for Redis to be available before starting the worker.
    
    This ensures the worker does not crash on startup if Redis is not yet ready.
    
    Args:
        host (str): Redis host.
        port (int): Redis port.
        retries (int): Number of retry attempts before failing.
        delay (int): Delay between retries in seconds.
    
    Returns:
        Redis: Connected Redis instance.
    
    Raises:
        ConnectionError: If Redis is unreachable after all retries.
    """
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

# -----------------------------------------------------------
# Worker Initialization
# -----------------------------------------------------------
if __name__ == "__main__":
    # Ensure Redis is ready before starting the worker
    redis_conn = wait_for_redis(REDIS_HOST, REDIS_PORT)

    # Define the queues the worker will listen to
    listen = [QUEUE_NAME]
    queues = [Queue(name, connection=redis_conn) for name in listen]

    # Initialize the RQ worker
    worker = Worker(queues=queues, connection=redis_conn)

    logger.info(json.dumps({
        "event": "worker_started",
        "queues": listen,
        "service": SERVICE_NAME
    }))

    # Start processing jobs from the queue
    try:
        # with_scheduler=True enables scheduled jobs if any are added
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
