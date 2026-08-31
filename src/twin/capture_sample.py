"""
this was a payload utility that should have been added prev

it subscribes, records 1,000 consecutive messages to payload_sample.json with
their serialised byte sizes, and reports the mean. this allows the framework to have 
a measure mean
measured mean over 1,000 messages, not a single representative payload.

This is only for configuration 1- self hosted. The figure is a property of the schema, not the broker.
"""

import json
import os
import sys
import threading

from twin.config import load_broker_config
from twin.logging_setup import setup_logging
from twin.mqtt_client import build_client, connect, disconnect
from twin.payload import PayloadError, parse

COMPONENT = "capture_sample"
TARGET_MESSAGES = 1000
OUTPUT_PATH = os.environ.get("PAYLOAD_SAMPLE_PATH", "payload_sample.json")

def summarise(sizes: list[int]) -> dict:
    """Mean, min and max byte size."""
    return {
        "message_count": len(sizes),
        "mean_bytes": round(sum(sizes) / len(sizes), 2),
        "min_bytes": min(sizes),
        "max_bytes": max(sizes),
    }

def run() -> int:
    logger = setup_logging(COMPONENT)
    broker_config = load_broker_config()

    asset_id = os.environ.get("ASSET_ID", "boiler_01")
    topic = f"twin/{asset_id}/telemetry"

    captured = []
    sizes = []
    complete = threading.Event()

    def on_message(client, userdata, message):
        if len(captured) >= TARGET_MESSAGES:
            return
        try:
            payload = parse(message.payload)
        except PayloadError as exc:
            logger.error("malformed payload skipped", extra={"error": str(exc)})
            return

        sizes.append(len(message.payload))
        captured.append(json.loads(message.payload.decode("utf-8")))

        if len(captured) % 100 == 0:
            logger.info("capture progress", extra={"captured": len(captured)})

        if len(captured) >= TARGET_MESSAGES:
            complete.set()

    client = build_client(broker_config, f"twin-capture-{asset_id}", COMPONENT)
    client.on_message = on_message
    connect(client, broker_config)
    client.subscribe(topic, qos=broker_config.qos)

    logger.info("capture started", extra={"topic": topic, "target": TARGET_MESSAGES})
    complete.wait()
    disconnect(client)

    summary = summarise(sizes)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "messages": captured}, handle, indent=2)

    logger.info("capture complete", extra={**summary, "output": OUTPUT_PATH})
    return 0


if __name__ == "__main__":
    sys.exit(run())