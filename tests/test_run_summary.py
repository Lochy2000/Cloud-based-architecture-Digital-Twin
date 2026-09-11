"""Tests for completed-run summary selection and measurement."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from experiments.run_summary import (
    capture_network_counter,
    create_summary,
    database_volume_bytes,
    latest_completed_run,
    network_measurements,
    publisher_network_tx_bytes,
)


def test_latest_completed_run_ignores_current_incomplete_run():
    entries = [
        {"event": "started", "timestamp": "2026-09-10T08:00:00+00:00"},
        {"event": "stopping", "timestamp": "2026-09-10T08:01:00+00:00"},
        {"event": "started", "timestamp": "2026-09-10T09:00:00+00:00"},
    ]

    started, stopped = latest_completed_run(entries)

    assert started["timestamp"] == "2026-09-10T08:00:00+00:00"
    assert stopped["timestamp"] == "2026-09-10T08:01:00+00:00"


def test_latest_completed_run_requires_a_matched_pair():
    with pytest.raises(RuntimeError, match="no completed run"):
        latest_completed_run([{"event": "started"}])


def test_database_volume_converts_kibibytes_to_bytes():
    result = type("Result", (), {"stdout": "123\t/var/lib/influxdb2\n"})()
    with patch("experiments.run_summary.compose", return_value=result):
        assert database_volume_bytes("c1.env") == 123 * 1024


def test_publisher_network_counter_reads_exact_container_value():
    container = type("Result", (), {"stdout": "publisher-id\n"})()
    counter = type("Result", (), {"stdout": "8192\n"})()
    with patch("experiments.run_summary.compose", return_value=container), \
         patch("experiments.run_summary.run", return_value=counter) as command:
        assert publisher_network_tx_bytes("c1.env") == ("publisher-id", 8192)

    assert command.call_args.args[0] == [
        "docker", "exec", "publisher-id",
        "cat", "/sys/class/net/eth0/statistics/tx_bytes",
    ]


def test_network_measurements_reject_a_stale_run():
    capture = {
        "publisher_started_at": "2026-09-10T07:00:00+00:00",
        "tx_start_bytes": 100,
        "tx_end_bytes": 200,
    }
    with pytest.raises(RuntimeError, match="different completed run"):
        network_measurements(
            capture, datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
        )


def test_network_checkpoint_records_start_and_end_for_one_run(tmp_path):
    started_at = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
    started = {"event": "started", "timestamp": started_at.isoformat()}
    capture_file = tmp_path / "network.json"

    with patch("experiments.run_summary.structured_logs", return_value=[started]), \
         patch(
             "experiments.run_summary.publisher_network_tx_bytes",
             side_effect=[("publisher-id", 1000), ("publisher-id", 1450)],
         ):
        capture_network_counter("c1", "c1.env", capture_file, "start")
        capture = capture_network_counter("c1", "c1.env", capture_file, "end")

    assert capture["tx_start_bytes"] == 1000
    assert capture["tx_end_bytes"] == 1450
    assert network_measurements(capture, started_at)["publisher_network_tx_bytes"] == 450


@patch("experiments.run_summary.database_volume_bytes", return_value=4096)
@patch("experiments.run_summary.fetch_series_cardinality", return_value=1)
@patch("experiments.run_summary.fetch_time_bounds")
@patch("experiments.run_summary.fetch_point_count", return_value=3)
@patch("experiments.run_summary.InfluxDBClient")
@patch("experiments.run_summary.dotenv_values")
@patch("experiments.run_summary.structured_logs")
def test_create_summary_uses_one_completed_publisher_window(
    logs, env_values, client_class, point_count, time_bounds, cardinality, volume
):
    start = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
    stop = datetime(2026, 9, 10, 8, 1, tzinfo=timezone.utc)
    logs.return_value = [
        {
            "event": "started",
            "timestamp": start.isoformat(),
            "interval_seconds": 30,
        },
        {
            "event": "stopping",
            "timestamp": stop.isoformat(),
            "messages_accepted": 3,
            "messages_deferred": 1,
            "tick_overruns": 0,
        },
    ]
    env_values.return_value = {
        "INFLUX_TOKEN": "test-token",
        "INFLUX_ORG": "test-org",
        "INFLUX_BUCKET": "test-bucket",
        "ASSET_ID": "boiler_test",
    }
    query_api = MagicMock()
    client_class.return_value.__enter__.return_value.query_api.return_value = query_api
    time_bounds.return_value = (start, stop)

    network_capture = {
        "publisher_started_at": start.isoformat(),
        "start_captured_at": "2026-09-10T08:00:01+00:00",
        "end_captured_at": "2026-09-10T08:00:59+00:00",
        "tx_start_bytes": 1000,
        "tx_end_bytes": 1600,
    }
    summary = create_summary("c1", "c1.env", network_capture)

    assert summary["run_duration_seconds"] == 60.0
    assert summary["stored_message_count"] == 3
    assert summary["publisher_messages_accepted"] == 3
    assert summary["publisher_messages_deferred"] == 1
    assert summary["database_volume_bytes"] == 4096
    assert summary["publisher_network_tx_bytes"] == 600
    point_count.assert_called_once_with(
        query_api, "test-bucket", "boiler_test", start, stop
    )
