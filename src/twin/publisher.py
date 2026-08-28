"""
Publisher entrypoint.
simulates one asset and publishes an aggregated telemetry message on a fixed
interval. Deliberately thin; simulation, schema and connection logic all live
in their own modules.

scheduling is monotonic: each tick's target is computed from a fixed start
point rather than by sleeping a fixed duration, so message count over 24 hours
does not drift below nominal. Message count is a cost-model input, so drift is
a measurement error rather than an inconvenience.
"""

import os
import signal
import sys
import time
from datetime import datetime, timezone

from twin.assets import load_asset
from twin.config import load_broker_config, load_workload_config
from twin.logging_setup import setup_logging
from twin.mqtt_client import build_client, connect, disconnect
from twin.payload import build_payload, serialize
from twin.simulator import simulate

COMPONENT = "publisher"

# external air temperature. Held constant in the base case: the framework
# states cost and complexity measures are insensitive to telemetry realism,
# and a varying ambient would add a second source of variation between runs.
AMBIENT_TEMPERATURE_C = 12.0

_shutdown_requested = False

def _handle_shutdown(signum, frame):
    """
    without this the process is killed
    outright, the client never sends DISCONNECT, and the broker records an
    unexpected drop; indistinguishable from the failures fault injection is
    meant to produce.
    """
    global _shutdown_requested
    _shutdown_requested = True

def topic_for(asset_id: str) -> str:
    return f"twin/{asset_id}/telemetry"

def next_tick_delay(start: float, sequence: int, interval: float, now: float) -> float:
    """
    seconds to wait before publishing message number `sequence`.

    targets are absolute offsets from a fixed origin, so per-tick work never
    accumulates into drift
    negative result means the tick was missed;
    the nominal message count was not met, which matters because message
    count is a cost-model input
    """
    return start + (sequence * interval) - now

def run() -> int:
    logger = setup_logging(COMPONENT)

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

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
    published = 0
    start = time.monotonic()

    while not _shutdown_requested:
        timestamp = datetime.now(timezone.utc)

        readings = simulate(asset, timestamp, AMBIENT_TEMPERATURE_C)
        payload = build_payload(asset_id, sequence, timestamp, readings)

        result = client.publish(topic, serialize(payload), qos=broker_config.qos)

        if result.rc != 0:
            logger.error(
                "publish failed",
                extra={
                    "event": "publish_failed",
                    "sequence": sequence,
                    "reason_code": int(result.rc),
                },
            )
        else:
            published += 1

        sequence += 1

        # next tick is measured from the fixed start point, not from now
        # next_tick = start + (sequence * interval)
        # remaining = next_tick - time.monotonic()
        remaining = next_tick_delay(start, sequence, interval, time.monotonic())

        if remaining < 0:
            #  tick was missed entirely; record it rather than silently
            # skipping, since it means the nominal message count was not met.
            logger.warning(
                "tick overran interval",
                extra={"event": "tick_overrun", "sequence": sequence, "late_by_seconds": -remaining},
            )
            continue

        # sleep in short slices so a shutdown signal is acted on promptly
        # rather than after a full interval
        deadline = time.monotonic() + remaining
        while time.monotonic() < deadline and not _shutdown_requested:
            time.sleep(min(0.5, deadline - time.monotonic()))

    logger.info(
        "publisher stopping",
        extra={
            "event": "stopping",
            "messages_published": published,
            "final_sequence": sequence - 1 if sequence else None,
        },
    )

    disconnect(client)
    return 0


if __name__ == "__main__":
    sys.exit(run())