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

from twin.asset import load_asset
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