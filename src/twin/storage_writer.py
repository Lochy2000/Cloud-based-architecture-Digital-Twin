"""
Storage writer entrypoint

Subscribes to the telemetry topic, validates each message against the payload
schema, and writes it to InfluxDB. Uses the same connection factory as the
publisher, so reconnect behaviour is identical on both sides 

sequence gaps are detected and logged here rather than reconstructed from
stored data afterwards, which is what makes message loss measurable per
trial instead of only in aggregate
"""

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

def to_point(payload: TelemetryPayload) -> Point:
    """
    a validated payload onto an InfluxDB point.

    asset_id is a tag (indexed, used for filtering); the five channels are
    fields (the measured values). sequence is a field rather than a tag: it is
    unique per message, and a tag with unbounded cardinality would degrade
    InfluxDB performance badly.

    The timestamp comes from the payload, not from arrival time, so a message
    redelivered after a broker outage is stored at the instant it was measured.
    """
    point = (
        Point(MEASUREMENT)
        .tag("asset_id", payload.asset_id)
        .field("sequence", payload.sequence)
        .time(payload.timestamp, WritePrecision.MS)
    )
    for channel in CHANNELS:
        point = point.field(channel, float(getattr(payload, channel)))
    return point
