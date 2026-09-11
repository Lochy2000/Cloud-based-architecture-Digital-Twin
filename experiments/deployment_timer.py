"""Measure clean deployment time from Compose startup to first stored point."""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values
from influxdb_client import InfluxDBClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_DIR = PROJECT_ROOT / "deploy"
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from twin.query import fetch_point_count

DEFAULT_TRIALS = 3
DEFAULT_TIMEOUT_SECONDS = 180.0
DEFAULT_POLL_SECONDS = 0.25


def run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=DEPLOY_DIR,
        capture_output=True,
        text=True,
        check=True,
    )


def compose_command(configuration: str, env_file: Path,
                    project_name: str, *args: str) -> list[str]:
    command = [
        "docker", "compose",
        "--project-name", project_name,
        "--env-file", str(env_file),
    ]
    if configuration == "c1":
        command.extend(["--profile", "c1"])
    return [*command, *args]


def compose(configuration: str, env_file: Path,
            project_name: str, *args: str) -> subprocess.CompletedProcess:
    return run(compose_command(configuration, env_file, project_name, *args))


def required_setting(values: dict, name: str) -> str:
    value = os.environ.get(name) or values.get(name)
    if not value:
        raise RuntimeError(f"environment file is missing {name}")
    return str(value)


def influx_settings(env_file: Path) -> dict[str, str]:
    values = dotenv_values(env_file)
    return {
        "url": os.environ.get("INFLUX_QUERY_URL", "http://localhost:8086"),
        "token": required_setting(values, "INFLUX_TOKEN"),
        "org": required_setting(values, "INFLUX_ORG"),
        "bucket": required_setting(values, "INFLUX_BUCKET"),
        "asset_id": str(os.environ.get("ASSET_ID") or values.get("ASSET_ID", "boiler_01")),
    }


def first_point_exists(settings: dict[str, str], started_at: datetime) -> bool:
    """Return whether this deployment has stored at least one telemetry point."""
    stop = datetime.now(timezone.utc) + timedelta(seconds=1)
    with InfluxDBClient(
        url=settings["url"], token=settings["token"], org=settings["org"]
    ) as client:
        return fetch_point_count(
            client.query_api(),
            settings["bucket"],
            settings["asset_id"],
            started_at,
            stop,
        ) > 0


def wait_for_first_point(settings: dict[str, str], started_at: datetime,
                         timeout: float, poll_interval: float) -> float:
    """Poll until the first point is queryable and return monotonic elapsed time."""
    began = time.monotonic()
    deadline = began + timeout
    while time.monotonic() < deadline:
        try:
            if first_point_exists(settings, started_at):
                return time.monotonic() - began
        except Exception:
            # Connection and query failures are expected while InfluxDB starts.
            pass
        time.sleep(poll_interval)
    raise TimeoutError(f"no telemetry point appeared within {timeout}s")


def clean_stack(configuration: str, env_file: Path, project_name: str) -> None:
    compose(
        configuration,
        env_file,
        project_name,
        "down",
        "--volumes",
        "--remove-orphans",
    )


def prepare_images(configuration: str, env_file: Path, project_name: str) -> None:
    """Resolve supporting images and build the runtime outside measured time."""
    compose(
        configuration, env_file, project_name,
        "pull", "--ignore-buildable",
    )
    compose(
        configuration, env_file, project_name,
        "build", "publisher", "storage-writer",
    )


def measure_trial(configuration: str, env_file: Path, project_name: str,
                  settings: dict[str, str], timeout: float,
                  poll_interval: float) -> dict:
    """Measure one clean deployment and always remove its isolated volumes."""
    clean_stack(configuration, env_file, project_name)
    started_at = datetime.now(timezone.utc)
    began = time.monotonic()
    try:
        compose(configuration, env_file, project_name, "up", "--detach", "--no-build")
        startup_elapsed = time.monotonic() - began
        query_elapsed = wait_for_first_point(
            settings, started_at, timeout - startup_elapsed, poll_interval
        )
        elapsed = startup_elapsed + query_elapsed
        return {
            "started_at": started_at.isoformat(),
            "seconds_to_first_datapoint": round(elapsed, 3),
        }
    finally:
        clean_stack(configuration, env_file, project_name)


def default_output(configuration: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        PROJECT_ROOT / "experiments" / "deployment_timings"
        / f"{configuration}_{timestamp}.json"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure clean Compose deployment time to the first stored point."
    )
    parser.add_argument("--configuration", required=True, choices=["c1", "c2a", "c2b"])
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.trials < 1:
        parser.error("--trials must be at least 1")
    if args.timeout <= 0 or args.poll_interval <= 0:
        parser.error("--timeout and --poll-interval must be positive")

    env_file = (args.env_file or (
        PROJECT_ROOT / "config" / "env" / f"{args.configuration}.env"
    )).resolve()
    project_name = f"digital-twin-timing-{args.configuration}"
    settings = influx_settings(env_file)

    prepare_images(args.configuration, env_file, project_name)
    trials = []
    for number in range(1, args.trials + 1):
        print(f"[{args.configuration}] deployment trial {number}/{args.trials}", flush=True)
        result = measure_trial(
            args.configuration,
            env_file,
            project_name,
            settings,
            args.timeout,
            args.poll_interval,
        )
        result["trial"] = number
        trials.append(result)
        print(f"  first datapoint={result['seconds_to_first_datapoint']}s", flush=True)

    durations = [trial["seconds_to_first_datapoint"] for trial in trials]
    summary = {
        "configuration": args.configuration,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trials": trials,
        "median_seconds_to_first_datapoint": round(statistics.median(durations), 3),
        "poll_interval_seconds": args.poll_interval,
    }
    output = args.output or default_output(args.configuration)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"\nMedian: {summary['median_seconds_to_first_datapoint']}s")
    print(f"Written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
