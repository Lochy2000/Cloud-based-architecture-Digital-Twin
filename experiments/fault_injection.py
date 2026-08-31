"""
fault injection trials.

runs three failure modes, three trials each, and records timings to
recovery_trials.csv. The pipeline must already be running and flowing data
before this is started.

Failure modes:
  broker      broker unreachable for the outage duration
  network     publisher-to-broker connectivity severed, broker still running
  storage     InfluxDB stopped, messages still arriving

for the self-hosted configuration the broker is stopped directly. For the
managed brokers there is no container to stop, so connectivity is severed
inside the publisher container instead. The same mechanism is used for the
network mode across all three configurations, which keeps the comparison
consistent.
"""

import argparse
import csv
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path("recovery_trials.csv")
FIELDNAMES = [
    "configuration", "mode", "trial", "started_at",
    "outage_seconds", "detection_seconds", "recovery_seconds",
    "messages_lost", "manual_actions", "notes",
]

PUBLISHER_SERVICE = "publisher"
STORAGE_SERVICE = "storage-writer"
INFLUX_SERVICE = "influxdb"
BROKER_SERVICE = "mosquitto"

def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=check)