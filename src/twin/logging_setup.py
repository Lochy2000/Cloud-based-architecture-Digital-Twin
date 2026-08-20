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