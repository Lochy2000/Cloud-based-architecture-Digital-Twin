"""Validate MQTT telemetry and write it to InfluxDB."""

import os
import signal
import sys
import threading

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from twin.config import load_broker_config, load_influx_config
from twin.logging_setup import setup_logging
from twin.mqtt_client import build_client, connect, disconnect
from twin.payload import CHANNELS, PayloadError, TelemetryPayload, parse

COMPONENT = "storage_writer"
MEASUREMENT = "telemetry"

_shutdown_requested = threading.Event()


def _handle_shutdown(signum, frame):
    _shutdown_requested.set()


def topic_for(asset_id: str) -> str:
    return f"twin/{asset_id}/telemetry"

def attach_subscription_callback(client, topic: str, qos: int) -> None:
    """Subscribe after every successful connection, including reconnects."""
    lifecycle_on_connect = client.on_connect

    def on_connect(client, userdata, flags, reason_code, properties):
        lifecycle_on_connect(client, userdata, flags, reason_code, properties)
        if reason_code == 0:
            client.subscribe(topic, qos=qos)

    client.on_connect = on_connect

def to_point(payload: TelemetryPayload) -> Point:
    """Turn a validated payload into an InfluxDB point."""
    # Sequence stays a field; using it as a tag would create unbounded cardinality.
    point = (
        Point(MEASUREMENT)
        .tag("asset_id", payload.asset_id)
        .field("sequence", payload.sequence)
        .time(payload.timestamp, WritePrecision.MS)
    )
    for channel in CHANNELS:
        point = point.field(channel, float(getattr(payload, channel)))
    return point

class SequenceTracker:
    """Track the last sequence per asset and report gaps."""

    def __init__(self):
        self._last = {}

    def check(self, asset_id: str, sequence: int) -> int:
        """Return how many messages are missing before this one."""
        previous = self._last.get(asset_id)
        self._last[asset_id] = sequence

        if previous is None or sequence <= previous:
            # A lower or repeated sequence means the publisher restarted, or
            # the broker redelivered. Neither is a gap.
            return 0
        return sequence - previous - 1

class WriteFailureState:
    """Track consecutive database write failures until storage recovers."""

    def __init__(self):
        self.failures = 0

    def record_failure(self) -> None:
        self.failures += 1

    def record_success(self) -> int:
        failures = self.failures
        self.failures = 0
        return failures

def run() -> int:
    logger = setup_logging(COMPONENT)

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    broker_config = load_broker_config()
    influx_config = load_influx_config()

    asset_id = os.environ.get("ASSET_ID", "boiler_01")
    topic = topic_for(asset_id)

    influx = InfluxDBClient(
        url=influx_config.url, token=influx_config.token, org=influx_config.org
    )
    write_api = influx.write_api(write_options=SYNCHRONOUS)

    tracker = SequenceTracker()
    write_failure_state = WriteFailureState()
    client_id = os.environ.get("MQTT_CLIENT_ID", f"twin-storage-{asset_id}")
    client = build_client(broker_config, client_id, COMPONENT)

    def on_message(client, userdata, message):
        handle_message(
            message.payload,
            write_api,
            influx_config.bucket,
            tracker,
            logger,
            write_failure_state,
        )

    client.on_message = on_message
    attach_subscription_callback(client, topic, broker_config.qos)

    connect(client, broker_config)

    logger.info(
        "storage writer started",
        extra={"event": "started", "topic": topic, "bucket": influx_config.bucket,
               "qos": broker_config.qos},
    )

    _shutdown_requested.wait()

    logger.info("storage writer stopping", extra={"event": "stopping"})
    disconnect(client)
    influx.close()
    return 0

def handle_message(
    raw: bytes,
    write_api,
    bucket: str,
    tracker: SequenceTracker,
    logger,
    write_failure_state: WriteFailureState | None = None,
) -> bool:
    """Process one message and return whether it reached InfluxDB."""
    try:
        payload = parse(raw)
    except PayloadError as exc:
        logger.error("malformed payload discarded", extra={"event": "payload_rejected", "error": str(exc)})
        return False

    missing = tracker.check(payload.asset_id, payload.sequence)
    if missing:
        logger.warning(
            "sequence gap detected",
            extra={"event": "sequence_gap", "asset_id": payload.asset_id,
                   "sequence": payload.sequence, "messages_missing": missing},
        )

    try:
        write_api.write(bucket=bucket, record=to_point(payload))
    except Exception as exc:
        if write_failure_state is not None:
            write_failure_state.record_failure()
        # Keep the callback alive so a storage recovery can still be observed.
        logger.error(
            "influx write failed",
            extra={"event": "write_failed", "sequence": payload.sequence, "error": str(exc)},
        )
        return False

    failures = write_failure_state.record_success() if write_failure_state else 0
    if failures:
        logger.info(
            "influx write recovered",
            extra={
                "event": "write_recovered",
                "sequence": payload.sequence,
                "failures_since_last_success": failures,
            },
        )

    return True


if __name__ == "__main__":
    sys.exit(run())
