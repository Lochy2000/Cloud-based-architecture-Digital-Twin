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
managed brokers there is no container to stop, so Docker disconnects the
publisher container from its network instead. The same mechanism is used for
the network mode across all three configurations, which keeps the comparison
consistent.
"""

import argparse
import csv
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import os
import sys

from dotenv import dotenv_values
from influxdb_client import InfluxDBClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from twin.query import fetch_sequences

ENV_FILE = os.environ.get("COMPOSE_ENV_FILE", "../config/env/c1.env")
OUTPUT_PATH = Path(os.environ.get("TRIAL_OUTPUT_PATH", "recovery_trials.csv"))
FIELDNAMES = [
    "configuration", "mode", "trial", "started_at",
    "outage_seconds", "detection_seconds", "recovery_seconds",
    "messages_expected", "messages_stored", "messages_lost",
    "notes",
]

PUBLISHER_SERVICE = "publisher"
STORAGE_SERVICE = "storage-writer"
INFLUX_SERVICE = "influxdb"
BROKER_SERVICE = "mosquitto"
DEFAULT_OUTAGE_SECONDS = 150.0

def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=check)

def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return run(["docker", "compose", "--env-file", ENV_FILE, *args], check=check)

def container_id(service: str) -> str:
    result = compose("ps", "-q", service)
    cid = result.stdout.strip()
    if not cid:
        raise RuntimeError(f"service {service!r} is not running")
    return cid

def logs_since(service: str, since: str) -> list[dict]:
    """Structured log lines emitted by a service since a timestamp."""
    result = compose("logs", "--since", since, "--no-log-prefix", service, check=False)
    entries = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries

def first_event_time(entries: list[dict], events: set[str]) -> datetime | None:
    for entry in entries:
        if entry.get("event") in events:
            return datetime.fromisoformat(entry["timestamp"])
    return None

def reconcile_sequences(start_sequence: int, end_sequence: int,
                        stored_sequences: set[int]) -> dict[str, int]:
    """Reconcile sequences attempted after start through the inclusive end."""
    if end_sequence < start_sequence:
        raise ValueError("publisher sequence restarted during the trial")
    expected = set(range(start_sequence + 1, end_sequence + 1))
    stored = expected & stored_sequences
    return {
        "messages_expected": len(expected),
        "messages_stored": len(stored),
        "messages_lost": len(expected - stored),
    }

# --- create the different failuer modes ----------------------------------------------------

def container_network(container: str) -> str:
    """Return the single Docker network attached to a trial container."""
    result = run([
        "docker", "inspect", "--format", "{{json .NetworkSettings.Networks}}", container
    ])
    networks = list(json.loads(result.stdout))
    if len(networks) != 1:
        raise RuntimeError(
            f"expected container {container!r} to have one network, found {networks}"
        )
    return networks[0]

def sever_network(service: str) -> tuple[str, str]:
    """Disconnect a service container from its Compose network."""
    container = container_id(service)
    network = container_network(container)
    run(["docker", "network", "disconnect", network, container])
    return network, container

def restore_network(network: str, container: str) -> None:
    """Reconnect a service container to its original Compose network."""
    run(["docker", "network", "connect", network, container])

def stop_service(service: str) -> None:
    compose("stop", service)

def start_service(service: str) -> None:
    compose("start", service)

def publisher_snapshot(timeout: float = 45.0) -> dict:
    """Request and return a fresh publisher snapshot event."""
    requested_at = datetime.now(timezone.utc).isoformat()
    run(["docker", "kill", "--signal=USR1", container_id(PUBLISHER_SERVICE)])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        entries = logs_since(PUBLISHER_SERVICE, requested_at)
        for entry in entries:
            if entry.get("event") == "publisher_snapshot":
                return entry
        time.sleep(0.25)
    raise RuntimeError(f"publisher did not emit a snapshot within {timeout}s")

def stored_sequences(start: datetime, stop: datetime) -> set[int]:
    """Query sequences stored during a trial using its environment file."""
    values = dotenv_values(ENV_FILE)
    url = os.environ.get("INFLUX_QUERY_URL", "http://localhost:8086")
    token = os.environ.get("INFLUX_TOKEN") or values.get("INFLUX_TOKEN")
    org = os.environ.get("INFLUX_ORG") or values.get("INFLUX_ORG")
    bucket = os.environ.get("INFLUX_BUCKET") or values.get("INFLUX_BUCKET")
    asset_id = os.environ.get("ASSET_ID") or values.get("ASSET_ID", "boiler_01")
    if not all((token, org, bucket, asset_id)):
        raise RuntimeError("trial environment is missing InfluxDB or asset settings")
    with InfluxDBClient(url=url, token=token, org=org) as client:
        return fetch_sequences(
            client.query_api(), bucket, asset_id, start=start, stop=stop
        )


#----- run script --------------------------------------------------

def run_trial(configuration: str, mode: str, trial: int, outage: float, settle: float) -> dict:
    start_snapshot = publisher_snapshot()
    window_start = datetime.fromisoformat(start_snapshot["timestamp"])
    started_at = datetime.now(timezone.utc)
    since = started_at.isoformat()
    severed_connection = None

    if mode == "broker":
        if configuration == "c1":
            stop_service(BROKER_SERVICE)
        else:
            severed_connection = sever_network(PUBLISHER_SERVICE)
    elif mode == "network":
        severed_connection = sever_network(PUBLISHER_SERVICE)
    elif mode == "storage":
        stop_service(INFLUX_SERVICE)
    else:
        raise ValueError(f"unknown mode {mode!r}")

    time.sleep(outage)

    if mode == "broker" and configuration == "c1":
        start_service(BROKER_SERVICE)
    elif mode in ("broker", "network"):
        restore_network(*severed_connection)
    elif mode == "storage":
        start_service(INFLUX_SERVICE)

    time.sleep(settle)

    end_snapshot = publisher_snapshot()
    window_stop = datetime.fromisoformat(end_snapshot["timestamp"])

    watched = STORAGE_SERVICE if mode == "storage" else PUBLISHER_SERVICE
    entries = logs_since(watched, since)

    detected = first_event_time(
        entries,
        {"disconnected", "write_failed", "publish_failed", "publish_deferred"},
    )
    detection_seconds = (detected - started_at).total_seconds() if detected else None

    resumed = None
    for entry in entries:
        if entry.get("event") not in {"connected", "started", "write_recovered"}:
            continue
        moment = datetime.fromisoformat(entry["timestamp"])
        if detected and moment > detected:
            resumed = moment
            break

    recovery_seconds = None
    if resumed:
        recovery_seconds = (resumed - started_at).total_seconds() - outage

    loss = reconcile_sequences(
        int(start_snapshot["sequence"]),
        int(end_snapshot["sequence"]),
        stored_sequences(window_start, window_stop),
    )

    return {
        "configuration": configuration,
        "mode": mode,
        "trial": trial,
        "started_at": since,
        "outage_seconds": outage,
        "detection_seconds": round(detection_seconds, 3) if detection_seconds is not None else "",
        "recovery_seconds": round(recovery_seconds, 3) if recovery_seconds is not None else "",
        **loss,
        "notes": "" if detected else "no detection event found in logs",
    }

def append_row(row: dict) -> None:
    exists = OUTPUT_PATH.exists()
    with OUTPUT_PATH.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        if not exists:
            writer.writeheader()
        writer.writerow(row)

def main() -> int:
    parser = argparse.ArgumentParser(description="Run fault injection trials.")
    parser.add_argument("--configuration", required=True, choices=["c1", "c2a", "c2b"])
    parser.add_argument("--mode", choices=["broker", "network", "storage", "all"], default="all")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--outage", type=float, default=DEFAULT_OUTAGE_SECONDS,
                        help="seconds the failure is held")
    parser.add_argument("--settle", type=float, default=90.0,
                        help="seconds to wait after restoring before reading logs")
    parser.add_argument("--gap", type=float, default=120.0,
                        help="seconds between trials, so one does not affect the next")
    args = parser.parse_args()

    modes = ["broker", "network", "storage"] if args.mode == "all" else [args.mode]

    for mode in modes:
        for trial in range(1, args.trials + 1):
            print(f"[{args.configuration}] {mode} trial {trial}/{args.trials}", flush=True)
            row = run_trial(args.configuration, mode, trial, args.outage, args.settle)
            append_row(row)
            print(f"  detection={row['detection_seconds']}s "
                f"recovery={row['recovery_seconds']}s "
                f"lost={row['messages_lost']}", flush=True)

            if not (mode == modes[-1] and trial == args.trials):
                time.sleep(args.gap)

    print(f"\nWritten to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
