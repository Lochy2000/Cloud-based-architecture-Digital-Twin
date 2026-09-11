"""Create an auditable JSON summary for one completed experiment run."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from influxdb_client import InfluxDBClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from twin.query import (
    fetch_point_count,
    fetch_series_cardinality,
    fetch_time_bounds,
)


def run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=True)


def compose(env_file: str, *args: str) -> subprocess.CompletedProcess:
    return run(["docker", "compose", "--env-file", env_file, *args])


def structured_logs(env_file: str, service: str) -> list[dict]:
    """Read JSON application events from the current Compose container."""
    result = compose(env_file, "logs", "--no-log-prefix", service)
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


def latest_completed_run(entries: list[dict]) -> tuple[dict, dict]:
    """Return the latest matched publisher started/stopping event pair."""
    started = None
    completed = None
    for entry in entries:
        if entry.get("event") == "started":
            started = entry
        elif entry.get("event") == "stopping" and started is not None:
            completed = (started, entry)
            started = None
    if completed is None:
        raise RuntimeError("publisher logs contain no completed run")
    return completed


def database_volume_bytes(env_file: str) -> int:
    """Measure the allocated InfluxDB data directory in KiB, returned as bytes."""
    result = compose(env_file, "exec", "-T", "influxdb", "du", "-sk", "/var/lib/influxdb2")
    kibibytes = int(result.stdout.split()[0])
    return kibibytes * 1024


def required_setting(values: dict, name: str) -> str:
    value = os.environ.get(name) or values.get(name)
    if not value:
        raise RuntimeError(f"environment file is missing {name}")
    return str(value)


def create_summary(configuration: str, env_file: str) -> dict:
    started, stopped = latest_completed_run(structured_logs(env_file, "publisher"))
    started_at = datetime.fromisoformat(started["timestamp"])
    stopped_at = datetime.fromisoformat(stopped["timestamp"])
    if started_at.tzinfo is None or stopped_at.tzinfo is None:
        raise RuntimeError("publisher log timestamps must be timezone-aware")

    values = dotenv_values(env_file)
    url = os.environ.get("INFLUX_QUERY_URL", "http://localhost:8086")
    token = required_setting(values, "INFLUX_TOKEN")
    org = required_setting(values, "INFLUX_ORG")
    bucket = required_setting(values, "INFLUX_BUCKET")
    asset_id = str(os.environ.get("ASSET_ID") or values.get("ASSET_ID", "boiler_01"))

    with InfluxDBClient(url=url, token=token, org=org) as client:
        query_api = client.query_api()
        message_count = fetch_point_count(
            query_api, bucket, asset_id, started_at, stopped_at
        )
        first_stored, last_stored = fetch_time_bounds(
            query_api, bucket, asset_id, started_at, stopped_at
        )
        cardinality = fetch_series_cardinality(
            query_api, bucket, started_at, stopped_at
        )

    return {
        "configuration": configuration,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "asset_id": asset_id,
        "publisher_started_at": started_at.isoformat(),
        "publisher_stopped_at": stopped_at.isoformat(),
        "run_duration_seconds": round((stopped_at - started_at).total_seconds(), 3),
        "publish_interval_seconds": float(started["interval_seconds"]),
        "stored_message_count": message_count,
        "first_stored_at": first_stored.isoformat() if first_stored else None,
        "last_stored_at": last_stored.isoformat() if last_stored else None,
        "series_cardinality": cardinality,
        "database_volume_bytes": database_volume_bytes(env_file),
        "publisher_messages_accepted": int(stopped["messages_accepted"]),
        "publisher_messages_deferred": int(stopped["messages_deferred"]),
        "publisher_tick_overruns": int(stopped["tick_overruns"]),
    }


def default_output(configuration: str, summary: dict) -> Path:
    timestamp = datetime.fromisoformat(summary["publisher_started_at"]).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    return PROJECT_ROOT / "experiments" / "run_summaries" / f"{configuration}_{timestamp}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarise one completed digital-twin run.")
    parser.add_argument("--configuration", required=True, choices=["c1", "c2a", "c2b"])
    parser.add_argument("--env-file", help="Compose environment file")
    parser.add_argument("--output", type=Path, help="JSON output path")
    args = parser.parse_args()

    env_file = args.env_file or f"../config/env/{args.configuration}.env"
    summary = create_summary(args.configuration, env_file)
    output = args.output or default_output(args.configuration, summary)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
