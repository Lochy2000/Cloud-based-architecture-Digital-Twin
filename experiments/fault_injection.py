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

def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return run(["docker", "compose", *args], check=check)

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


# --- create the different failuer modes ----------------------------------------------------

def sever_network(service: str) -> None:
    """
    Drop outbound traffic from a container. Requires NET_ADMIN, which is
    granted to the publisher in compose
    """
    run(["docker", "exec", "--privileged", container_id(service),
        "iptables", "-A", "OUTPUT", "-p", "tcp", "--dport", "8883", "-j", "DROP"])

def restore_network(service: str) -> None:
    run(["docker", "exec", "--privileged", container_id(service),
        "iptables", "-D", "OUTPUT", "-p", "tcp", "--dport", "8883", "-j", "DROP"])

def stop_service(service: str) -> None:
    compose("stop", service)

def start_service(service: str) -> None:
    compose("start", service)


#----- run script --------------------------------------------------

def run_trial(configuration: str, mode: str, trial: int, outage: float, settle: float) -> dict:
    started_at = datetime.now(timezone.utc)
    since = started_at.isoformat()

    if mode == "broker":
        if configuration == "c1":
            stop_service(BROKER_SERVICE)
            manual_actions = 2  # stop and start
        else:
            sever_network(PUBLISHER_SERVICE)
            manual_actions = 2
    elif mode == "network":
        sever_network(PUBLISHER_SERVICE)
        manual_actions = 2
    elif mode == "storage":
        stop_service(INFLUX_SERVICE)
        manual_actions = 2
    else:
        raise ValueError(f"unknown mode {mode!r}")

    time.sleep(outage)

    if mode == "broker" and configuration == "c1":
        start_service(BROKER_SERVICE)
    elif mode in ("broker", "network"):
        restore_network(PUBLISHER_SERVICE)
    elif mode == "storage":
        start_service(INFLUX_SERVICE)

    time.sleep(settle)

    watched = STORAGE_SERVICE if mode == "storage" else PUBLISHER_SERVICE
    entries = logs_since(watched, since)

    detected = first_event_time(entries, {"disconnected", "write_failed", "publish_failed"})
    detection_seconds = (detected - started_at).total_seconds() if detected else None

    resumed = None
    for entry in entries:
        if entry.get("event") not in {"connected", "started"}:
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
    parser.add_argument("--outage", type=float, default=60.0,
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