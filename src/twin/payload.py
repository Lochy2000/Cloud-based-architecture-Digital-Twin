"""
Message schema for the digital twin pipelinethe single source of
truth for what a telemetry message contains 

mean payload size over 1,000 messages, and message loss detected by gap analysis on
the sequence number, which is why it is present from the first commit
rather than added later

No MQTT, no file I/O, no network build_payload() and parse() are
pure functions over plain Python values and bytes.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime

SCHEMA_VERSION = "1.0"

# The fixed base-case channel set. One
# non-temperature channel (power draw) so the payload is not
# homogeneous. This tuple is the single place that set is defined 
# simulator.py and tests both import it rather than re-listing it.
CHANNELS = (
    "supply_temperature_c",
    "return_temperature_c",
    "ambient_temperature_c",
    "power_draw_kw",
    "setpoint_c",
)

_NON_CHANNEL_FIELDS = ("asset_id", "timestamp", "sequence", "schema_version")
_ALL_FIELDS = frozenset(_NON_CHANNEL_FIELDS + CHANNELS)

class PayloadError(Exception):
    """Raised when a payload cannot be built, or a received payload is malformed."""

@dataclass(frozen=True)
class TelemetryPayload:
    asset_id: str
    timestamp: str  # ISO-8601, UTC, millisecond precision — matches logging_setup.py
    sequence: int
    schema_version: str
    supply_temperature_c: float
    return_temperature_c: float
    ambient_temperature_c: float
    power_draw_kw: float
    setpoint_c: float

def build_payload(asset_id: str, sequence: int, timestamp: datetime, readings: dict) -> TelemetryPayload:
    """
    Called by publisher.py once per tick, with the reading set
    simulator.py's pure function returned. timestamp is a required,
    explicit argument, not generated here, so the simulator's output
    and the payload's timestamp always come from the same clock read
    rather than two datetime.now() calls microseconds apart.
    """
    if not asset_id or not isinstance(asset_id, str):
        raise PayloadError(f"asset_id must be a non-empty string, got {asset_id!r}")

    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise PayloadError(f"sequence must be a non-negative integer, got {sequence!r}")

    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
        raise PayloadError(f"timestamp must be a timezone-aware datetime, got {timestamp!r}")
    if timestamp.utcoffset().total_seconds() != 0:
        raise PayloadError(f"timestamp must be UTC (offset 0), got offset {timestamp.utcoffset()}")

    _validate_channels(readings)

    return TelemetryPayload(
        asset_id=asset_id,
        timestamp=timestamp.isoformat(timespec="milliseconds"),
        sequence=sequence,
        schema_version=SCHEMA_VERSION,
        **{channel: float(readings[channel]) for channel in CHANNELS},
    )

def _validate_channels(readings: dict) -> None:
    if not isinstance(readings, dict):
        raise PayloadError(f"readings must be a dict, got {type(readings).__name__}")

    missing = set(CHANNELS) - readings.keys()
    if missing:
        raise PayloadError(f"readings missing channel(s): {sorted(missing)}")

    extra = readings.keys() - set(CHANNELS)
    if extra:
        raise PayloadError(f"readings has unexpected channel(s): {sorted(extra)}")

    for channel in CHANNELS:
        value = readings[channel]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PayloadError(f"readings[{channel!r}] must be a number, got {value!r}")
