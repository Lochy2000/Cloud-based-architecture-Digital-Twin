"""Simulate one asset and publish its telemetry on a fixed interval.

The scheduler follows https://docs.python.org/3/library/time.html#time.monotonic.
AI prompt used: "Implement a
stoppable telemetry publisher whose tick deadlines are
  calculated from one monotonic start time rather than repeated fixed sleeps."
"""

import os
import signal
import sys
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from twin.assets import load_asset
from twin.config import load_broker_config, load_workload_config
from twin.logging_setup import setup_logging
from twin.mqtt_client import build_client, connect, disconnect
from twin.payload import build_payload, serialize
from twin.simulator import simulate

COMPONENT = "publisher"
PROGRESS_EVERY_MESSAGES = 20

# Fixed so runs stay comparable.
AMBIENT_TEMPERATURE_C = 12.0

_shutdown_requested = False
_snapshot_requested = False

def _handle_shutdown(signum, frame):
    """Leave enough time for MQTT to send a clean disconnect."""
    global _shutdown_requested
    _shutdown_requested = True

def _handle_snapshot(signum, frame):
    global _snapshot_requested
    _snapshot_requested = True

def topic_for(asset_id: str) -> str:
    return f"twin/{asset_id}/telemetry"

def next_tick_delay(start: float, sequence: int, interval: float, now: float) -> float:
    """Return the delay to an absolute tick, or a negative value if it was missed."""
    # AI prompt used: "Calculate deadlines
    # from the original monotonic start so earlier
    # work cannot accumulate scheduling drift."
    return start + (sequence * interval) - now

def sleep_duration(deadline: float, now: float) -> float:
    """Return a non-negative, shutdown-responsive scheduler sleep duration."""
    return max(0.0, min(0.5, deadline - now))

def publish_outcome(qos: int, reason_code: int) -> str:
    """Classify whether Paho accepted, deferred, or rejected a publish."""
    if reason_code == mqtt.MQTT_ERR_SUCCESS:
        return "accepted"
    if qos > 0 and reason_code == mqtt.MQTT_ERR_NO_CONN:
        return "deferred"
    return "failed"

def should_log_progress(sequence: int) -> bool:
    """Return True after each group of twenty zero-based message sequences."""
    return (sequence + 1) % PROGRESS_EVERY_MESSAGES == 0

def run() -> int:
    global _snapshot_requested
    logger = setup_logging(COMPONENT)

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    if hasattr(signal, "SIGUSR1"):
        signal.signal(signal.SIGUSR1, _handle_snapshot)

    broker_config = load_broker_config()
    workload_config = load_workload_config()
    asset = load_asset(workload_config.asset_config_path)

    asset_id = asset["asset_id"]
    topic = topic_for(asset_id)
    interval = workload_config.publish_interval_seconds

    client_id = os.environ.get("MQTT_CLIENT_ID", f"twin-publisher-{asset_id}")
    client = build_client(broker_config, client_id, COMPONENT)
    connect(client, broker_config)

    logger.info(
        "publisher started",
        extra={
            "event": "started",
            "asset_id": asset_id,
            "topic": topic,
            "interval_seconds": interval,
            "qos": broker_config.qos,
        },
    )

    sequence = 0
    accepted = 0
    deferred = 0
    overruns = 0
    start = time.monotonic()

    while not _shutdown_requested:
        timestamp = datetime.now(timezone.utc)

        readings = simulate(asset, timestamp, AMBIENT_TEMPERATURE_C)
        payload = build_payload(asset_id, sequence, timestamp, readings)

        result = client.publish(topic, serialize(payload), qos=broker_config.qos)
        outcome = publish_outcome(broker_config.qos, result.rc)

        if outcome == "deferred":
            accepted += 1
            deferred += 1
            logger.warning(
                "publish queued until reconnect",
                extra={
                    "event": "publish_deferred",
                    "sequence": sequence,
                    "reason_code": int(result.rc),
                },
            )
        elif outcome == "failed":
            logger.error(
                "publish failed",
                extra={
                    "event": "publish_failed",
                    "sequence": sequence,
                    "reason_code": int(result.rc),
                },
            )
        else:
            accepted += 1

        sequence += 1

        # Always schedule from the original start so slow ticks do not add drift.
        remaining = next_tick_delay(start, sequence, interval, time.monotonic())

        overran = remaining < 0
        if overran:
            overruns += 1
            # Keep overruns visible in the experiment results.
            logger.warning(
                "tick overran interval",
                extra={"event": "tick_overrun", "sequence": sequence, "late_by_seconds": -remaining},
            )

        current_sequence = sequence - 1
        if should_log_progress(current_sequence):
            logger.info(
                "publisher progress",
                extra={
                    "event": "publish_progress",
                    "sequence": current_sequence,
                    "messages_accepted": accepted,
                    "messages_deferred": deferred,
                    "tick_overruns": overruns,
                },
            )

        if _snapshot_requested:
            logger.info(
                "publisher snapshot",
                extra={
                    "event": "publisher_snapshot",
                    "sequence": current_sequence,
                    "messages_accepted": accepted,
                    "messages_deferred": deferred,
                    "tick_overruns": overruns,
                },
            )
            _snapshot_requested = False

        if overran:
            continue

        # Short sleeps keep shutdown responsive even with a long interval.
        deadline = time.monotonic() + remaining
        while time.monotonic() < deadline and not _shutdown_requested:
            time.sleep(sleep_duration(deadline, time.monotonic()))

    logger.info(
        "publisher stopping",
        extra={
            "event": "stopping",
            "messages_accepted": accepted,
            "messages_deferred": deferred,
            "tick_overruns": overruns,
            "final_sequence": sequence - 1 if sequence else None,
        },
    )

    disconnect(client)
    return 0


if __name__ == "__main__":
    sys.exit(run())
