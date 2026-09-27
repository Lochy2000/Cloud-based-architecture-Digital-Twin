"""Build, validate, and parse telemetry payloads."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime

SCHEMA_VERSION = "1.0"

# Keep the channel list in one place; the simulator and tests use it too.
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
    """Build one payload from a simulator reading."""
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

def serialize(payload: TelemetryPayload) -> bytes:

    """UTF-8 JSON, sorted keys — deterministic, so byte size is comparable run to run (M1.6)."""
    return json.dumps(asdict(payload), sort_keys=True).encode("utf-8")

def parse(raw: bytes) -> TelemetryPayload:
    """Parse wire data and reject anything outside the current schema."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PayloadError(f"payload is not valid UTF-8 JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise PayloadError(f"payload must be a JSON object, got {type(data).__name__}")

    missing = _ALL_FIELDS - data.keys()
    if missing:
        raise PayloadError(f"payload missing required field(s): {sorted(missing)}")

    extra = data.keys() - _ALL_FIELDS
    if extra:
        raise PayloadError(f"payload has unexpected field(s): {sorted(extra)}")

    if data["schema_version"] != SCHEMA_VERSION:
        raise PayloadError(
            f"unsupported schema_version {data['schema_version']!r}, expected {SCHEMA_VERSION!r}"
        )

    if not isinstance(data["sequence"], int) or isinstance(data["sequence"], bool) or data["sequence"] < 0:
        raise PayloadError(f"sequence must be a non-negative integer, got {data['sequence']!r}")

    if not isinstance(data["asset_id"], str) or not data["asset_id"]:
        raise PayloadError(f"asset_id must be a non-empty string, got {data['asset_id']!r}")

    for channel in CHANNELS:
        value = data[channel]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PayloadError(f"{channel} must be a number, got {value!r}")

    return TelemetryPayload(**data)
