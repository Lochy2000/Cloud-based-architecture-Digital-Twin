"""
Structured JSON logging for the digital twin pipeline.

Serves tp config from environment, fail loudly so errors are
logged, not swallowed, and directly enables costs evalulation framework, which measure
detection and recovery times in seconds: that's only possible if every
log line carries a parseable, millisecond-precision timestamp.

One JSON object per line, to stdout only process doesn't manage
log files, Docker does (twelve-factor). Every line carries: timestamp
(UTC, ISO-8601, millisecond precision), level, component (which module
emitted it), message, plus any extra structured fields the caller adds.
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
    "processName", "process", "taskName",
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
    """
    Call once, at process startup, in each entrypoint (publisher.py,
    storage_writer.py). The logger is named after the component so log
    lines are attributable when several services' output is read
    together during fault-injection trials.

    level falls back to the LOG_LEVEL environment variable, then to
    INFO, keeping this consistent without adding a whole
    LoggingConfig loader in config.py for one string.
    """
    resolved_level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()

    logger = logging.getLogger(component)
    logger.setLevel(resolved_level)
    logger.propagate = False

    if logger.handlers:
        # Guards against duplicate log lines if setup_logging is called
        # more than once for the same component (happens in tests).
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    return logger