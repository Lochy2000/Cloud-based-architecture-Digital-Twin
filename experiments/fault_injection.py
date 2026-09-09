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

ENV_FILE = os.environ.get("COMPOSE_ENV_FILE", "../config/env/c1.env")
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
DEFAULT_OUTAGE_SECONDS = 150.0

MANUAL_RECOVERY_ACTIONS = {
    ("c1", "broker"): 1,   # restart the self-hosted broker
    ("c2a", "broker"): 0,  # managed broker and client recover automatically
    ("c2b", "broker"): 0,
    ("c1", "network"): 1,  # restore publisher connectivity
    ("c2a", "network"): 1,
    ("c2b", "network"): 1,
    ("c1", "storage"): 1,  # restart InfluxDB
    ("c2a", "storage"): 1,
    ("c2b", "storage"): 1,
}

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

def total_missing(entries: list[dict]) -> int:
    return sum(e.get("messages_missing", 0) for e in entries if e.get("event") == "sequence_gap")

def manual_actions_for(configuration: str, mode: str) -> int:
    """Return operator recovery actions, excluding fault injection actions."""
    return MANUAL_RECOVERY_ACTIONS[(configuration, mode)]


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


#----- run script --------------------------------------------------

def run_trial(configuration: str, mode: str, trial: int, outage: float, settle: float) -> dict:
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

    manual_actions = manual_actions_for(configuration, mode)

    time.sleep(outage)

    if mode == "broker" and configuration == "c1":
        start_service(BROKER_SERVICE)
    elif mode in ("broker", "network"):
        restore_network(*severed_connection)
    elif mode == "storage":
        start_service(INFLUX_SERVICE)

    time.sleep(settle)

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

    storage_entries = logs_since(STORAGE_SERVICE, since)

    return {
        "configuration": configuration,
        "mode": mode,
        "trial": trial,
        "started_at": since,
        "outage_seconds": outage,
        "detection_seconds": round(detection_seconds, 3) if detection_seconds is not None else "",
        "recovery_seconds": round(recovery_seconds, 3) if recovery_seconds is not None else "",
        "messages_lost": total_missing(storage_entries),
        "manual_actions": manual_actions,
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
