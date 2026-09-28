"""Write structured JSON logs to stdout for Docker to collect.

This follows https://docs.python.org/3/library/logging.html. AI prompt used:
"Create a Python logging formatter that writes one JSON object per
  line, preserves extra fields, and formats timestamps in UTC milliseconds."
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

_RESERVED_LOGRECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "asctime",
}

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }

        # Extra structured fields, e.g.
        # logger.info("reconnect attempt", extra={"asset_id": "boiler_01", "attempt": 3})
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOGRECORD_ATTRS:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)

def setup_logging(component: str, level: str | None = None) -> logging.Logger:
    """Set up one component logger without adding duplicate handlers."""
    resolved_level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()

    logger = logging.getLogger(component)
    logger.setLevel(resolved_level)
    logger.propagate = False

    if logger.handlers:
        # Reusing a component should not double every log line.
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    return logger
