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