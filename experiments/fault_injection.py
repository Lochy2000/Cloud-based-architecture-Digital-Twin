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
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sys

from dotenv import dotenv_values
from influxdb_client import InfluxDBClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from twin.query import fetch_sequences

ENV_FILE = os.environ.get("COMPOSE_ENV_FILE", "../config/env/c1.env")
COMPOSE_PROJECT = None
CONFIGURATION = None
OUTPUT_PATH = Path(os.environ.get("TRIAL_OUTPUT_PATH", "recovery_trials.csv"))
FIELDNAMES = [
    "configuration", "compose_project", "mode", "trial", "started_at",
    "outage_seconds", "detection_seconds", "recovery_seconds",
    "messages_expected", "messages_stored", "messages_lost",
    "restored_at", "recovery_actions", "delivery_timeout_seconds", "notes",
]

PUBLISHER_SERVICE = "publisher"
STORAGE_SERVICE = "storage-writer"
INFLUX_SERVICE = "influxdb"
BROKER_SERVICE = "mosquitto"
DEFAULT_OUTAGE_SECONDS = 150.0

def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=check)

def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    if not COMPOSE_PROJECT or not CONFIGURATION:
        raise RuntimeError("select --configuration and --project-name before running trials")
    command = ["docker", "compose", "--project-name", COMPOSE_PROJECT,
               "--file", str(PROJECT_ROOT / "deploy/docker-compose.yml"),
               "--env-file", ENV_FILE]
    if CONFIGURATION == "c1":
        command.extend(["--profile", "c1"])
    return run([*command, *args], check=check)

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
    token = values.get("INFLUX_TOKEN")
    org = values.get("INFLUX_ORG")
    bucket = values.get("INFLUX_BUCKET")
    asset_id = values.get("ASSET_ID", "boiler_01")
    if not all((token, org, bucket, asset_id)):
        raise RuntimeError("trial environment is missing InfluxDB or asset settings")
    with InfluxDBClient(url=url, token=token, org=org) as client:
        return fetch_sequences(
            client.query_api(), bucket, asset_id, start=start, stop=stop
        )


#----- run script --------------------------------------------------

def wait_for_delivery(start: datetime, stop: datetime, expected: set[int],
                      timeout: float) -> set[int]:
    """Wait for a fixed range; an unreadable database is not evidence of loss."""
    deadline = time.monotonic() + timeout
    while True:
        stored = stored_sequences(start, stop)
        if expected <= stored or time.monotonic() >= deadline:
            return stored
        time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))


def confirmed_recovery(restored_at: datetime, timeout: float) -> float | None:
    """Observe delivery of telemetry generated after restoration."""
    began = time.monotonic()
    deadline = began + timeout
    while time.monotonic() < deadline:
        try:
            if stored_sequences(restored_at, datetime.now(timezone.utc) + timedelta(milliseconds=1)):
                return time.monotonic() - began
        except Exception:
            # InfluxDB may still be starting; timeout records unavailable recovery.
            pass
        time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
    return None


def run_trial(configuration: str, mode: str, trial: int, outage: float,
              settle: float, delivery_timeout: float = 90.0) -> dict:
    if mode not in {"broker", "network", "storage"}:
        raise ValueError(f"unknown mode {mode!r}")
    start_snapshot = publisher_snapshot()
    window_start = datetime.fromisoformat(start_snapshot["timestamp"])
    started_at = datetime.now(timezone.utc)
    since = started_at.isoformat()
    stopped_service = None
    connection = None
    actions = []

    # Resolve recovery targets before mutating Docker state.
    if mode == "storage":
        stopped_service = INFLUX_SERVICE
        container_id(stopped_service)
    elif mode == "broker" and configuration == "c1":
        stopped_service = BROKER_SERVICE
        container_id(stopped_service)
    else:
        container = container_id(PUBLISHER_SERVICE)
        connection = (container_network(container), container)

    try:
        if stopped_service:
            stop_service(stopped_service)
        else:
            run(["docker", "network", "disconnect", *connection])
        time.sleep(outage)
    finally:
        # Also runs on Ctrl+C, sleep errors, or a partially failed injection.
        if stopped_service:
            start_service(stopped_service)
            actions.append(f"compose start {stopped_service}")
        else:
            network, container = connection
            attached = json.loads(run([
                "docker", "inspect", "--format",
                "{{json .NetworkSettings.Networks}}", container
            ]).stdout)
            if network not in attached:
                restore_network(network, container)
                actions.append(f"docker network connect {network} {container}")

    restored_at = datetime.now(timezone.utc)
    recovery_seconds = confirmed_recovery(restored_at, settle)
    end_snapshot = publisher_snapshot()
    # Log and payload timestamps have millisecond precision; Flux stop is exclusive.
    window_stop = datetime.fromisoformat(end_snapshot["timestamp"]) + timedelta(milliseconds=1)
    first = int(start_snapshot["sequence"])
    last = int(end_snapshot["sequence"])
    reconcile_sequences(first, last, set())  # reject a publisher sequence reset
    expected = set(range(first + 1, last + 1))
    stored = wait_for_delivery(window_start, window_stop, expected, delivery_timeout)
    loss = reconcile_sequences(first, last, stored)

    watched = STORAGE_SERVICE if mode == "storage" else PUBLISHER_SERVICE
    entries = [entry for entry in logs_since(watched, since)
               if not entry.get("expected", False)]
    detected = first_event_time(
        entries, {"disconnected", "write_failed", "publish_failed", "publish_deferred"}
    )
    detection_seconds = (detected - started_at).total_seconds() if detected else None
    notes = []
    if detected is None:
        notes.append("no detection event found in logs")
    if recovery_seconds is None:
        notes.append("no post-restoration database delivery before recovery timeout")
    if loss["messages_lost"]:
        notes.append("messages missing at delivery timeout; later delivery remains possible")
    return {
        "configuration": configuration, "compose_project": COMPOSE_PROJECT,
        "mode": mode, "trial": trial,
        "started_at": since, "restored_at": restored_at.isoformat(),
        "outage_seconds": outage,
        "detection_seconds": round(detection_seconds, 3) if detected else "",
        "recovery_seconds": round(recovery_seconds, 3) if recovery_seconds is not None else "",
        "recovery_actions": json.dumps(actions),
        "delivery_timeout_seconds": delivery_timeout,
        **loss, "notes": "; ".join(notes),
    }

def append_row(row: dict) -> None:
    exists = OUTPUT_PATH.exists()
    if exists:
        with OUTPUT_PATH.open(newline="", encoding="utf-8") as handle:
            if next(csv.reader(handle), None) != FIELDNAMES:
                raise ValueError("CSV header differs; select a new --output file")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        if not exists:
            writer.writeheader()
        writer.writerow(row)

def main() -> int:
    global ENV_FILE, COMPOSE_PROJECT, CONFIGURATION, OUTPUT_PATH
    parser = argparse.ArgumentParser(description="Run fault injection trials.")
    parser.add_argument("--configuration", required=True, choices=["c1", "c2a", "c2b"])
    parser.add_argument("--project-name", required=True, help="existing Compose project name")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--delivery-timeout", type=float, default=90.0)
    parser.add_argument("--mode", choices=["broker", "network", "storage", "all"], default="all")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--outage", type=float, default=DEFAULT_OUTAGE_SECONDS,
                        help="seconds the failure is held")
    parser.add_argument("--settle", type=float, default=90.0,
                        help="timeout for confirmed post-restoration database delivery")
    parser.add_argument("--gap", type=float, default=120.0,
                        help="seconds between trials, so one does not affect the next")
    args = parser.parse_args()
    if args.trials < 1 or min(args.outage, args.settle, args.delivery_timeout) <= 0 or args.gap < 0:
        parser.error("trials and timeouts must be positive; gap must be non-negative")
    CONFIGURATION = args.configuration
    COMPOSE_PROJECT = args.project_name
    ENV_FILE = str((args.env_file or PROJECT_ROOT / "config/env" / f"{CONFIGURATION}.env").resolve())
    if not Path(ENV_FILE).is_file():
        parser.error(f"environment file does not exist: {ENV_FILE}")
    # Compose interpolation and service env_file must select the same configuration.
    os.environ["ENV_FILE"] = ENV_FILE
    if args.output:
        OUTPUT_PATH = args.output
    if OUTPUT_PATH.exists():
        with OUTPUT_PATH.open(newline="", encoding="utf-8") as handle:
            if next(csv.reader(handle), None) != FIELDNAMES:
                parser.error("CSV header differs; select a new --output file")
    container_id(PUBLISHER_SERVICE)
    container_id(STORAGE_SERVICE)

    modes = ["broker", "network", "storage"] if args.mode == "all" else [args.mode]

    for mode in modes:
        for trial in range(1, args.trials + 1):
            print(f"[{args.configuration}] {mode} trial {trial}/{args.trials}", flush=True)
            row = run_trial(args.configuration, mode, trial, args.outage, args.settle,
                            args.delivery_timeout)
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
