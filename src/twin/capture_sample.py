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