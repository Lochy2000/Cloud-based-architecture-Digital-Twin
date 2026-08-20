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