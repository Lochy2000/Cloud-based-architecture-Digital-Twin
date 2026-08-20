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