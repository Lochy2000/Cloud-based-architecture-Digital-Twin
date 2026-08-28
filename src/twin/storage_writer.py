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