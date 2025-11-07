import os
import sys
import json
import logging
import datetime

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "service": os.getenv("SERVICE_NAME", "unknown"),
            "message": record.getMessage(),
        }

        # Añade campos extra
        extras = {}
        for k, v in record.__dict__.items():
            if k not in (
                "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
                "created", "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process"
            ):
                extras[k] = v
        if extras:
            log_record["extras"] = extras

        return json.dumps(log_record, ensure_ascii=False)

def setup_logging(level: str = None):
    level = level or os.getenv("LOG_LEVEL", "INFO")
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = []
    root.addHandler(handler)
    root.setLevel(level)
    return root
