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

class SequenceTracker:
    """
    tracks the last sequence number seen per asset and reports gaps.

    A gap means messages were lost in transit. Under QoS 1 this should be rare
    and is itself a finding; under QoS 0 it is the expected outcome of a broker
    outage and is the measurement.
    """

    def __init__(self):
        self._last = {}

    def check(self, asset_id: str, sequence: int) -> int:
        """
        returns the number of messages missing before this one. Zero means
        contiguous, or that this is the first message seen for the asset.
        """
        previous = self._last.get(asset_id)
        self._last[asset_id] = sequence

        if previous is None or sequence <= previous:
            # A lower or repeated sequence means the publisher restarted, or
            # the broker redelivered. Neither is a gap.
            return 0
        return sequence - previous - 1

ef run() -> int:
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
    client_id = os.environ.get("MQTT_CLIENT_ID", f"twin-storage-{asset_id}")
    client = build_client(broker_config, client_id, COMPONENT)

    def on_message(client, userdata, message):
        handle_message(message.payload, write_api, influx_config.bucket, tracker, logger)

    client.on_message = on_message

    connect(client, broker_config)
    client.subscribe(topic, qos=broker_config.qos)

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
