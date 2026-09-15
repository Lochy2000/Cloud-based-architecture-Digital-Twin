"""Focused tests for fault-injection measurement behavior."""

from unittest.mock import patch

from experiments.fault_injection import (
    DEFAULT_OUTAGE_SECONDS,
    FIELDNAMES,
    container_network,
    first_event_time,
    reconcile_sequences,
    restore_network,
    sever_network,
)

from datetime import datetime, timezone
from datetime import timedelta
import pytest
from experiments import fault_injection as fi


def test_delivery_waits_for_final_sequence_without_moving_bounds():
    start = datetime(2026, 9, 15, tzinfo=timezone.utc)
    stop = start + timedelta(seconds=30)
    with patch.object(fi, "stored_sequences", side_effect=[{1}, {1, 2}]) as query, \
         patch.object(fi.time, "sleep"):
        assert fi.wait_for_delivery(start, stop, {1, 2}, 10) == {1, 2}
    assert query.call_count == 2
    assert all(call.args == (start, stop) for call in query.call_args_list)


def test_delivery_timeout_reports_only_observed_sequences():
    start = datetime(2026, 9, 15, tzinfo=timezone.utc)
    with patch.object(fi, "stored_sequences", return_value={1}), \
         patch.object(fi.time, "monotonic", side_effect=[0, 10]):
        assert fi.wait_for_delivery(start, start, {1, 2}, 10) == {1}


def test_database_error_is_not_reported_as_message_loss():
    with patch.object(fi, "stored_sequences", side_effect=RuntimeError("unavailable")):
        with pytest.raises(RuntimeError, match="unavailable"):
            fi.wait_for_delivery(None, None, {1}, 10)


def test_recovery_requires_database_delivery_after_restore():
    restored = datetime(2026, 9, 15, tzinfo=timezone.utc)
    with patch.object(fi, "stored_sequences", side_effect=[set(), {5}]) as query, \
         patch.object(fi.time, "sleep"), \
         patch.object(fi.time, "monotonic", side_effect=[10, 10, 11, 12, 12]):
        assert fi.confirmed_recovery(restored, 10) == 2
    assert all(call.args[0] == restored for call in query.call_args_list)


@pytest.mark.parametrize("mode", ["storage", "broker", "network"])
def test_interrupted_outage_restores_target(mode):
    snapshot = {"timestamp": "2026-09-15T00:00:00+00:00", "sequence": 0}
    with patch.object(fi, "publisher_snapshot", return_value=snapshot), \
         patch.object(fi, "container_id", return_value="publisher-id"), \
         patch.object(fi, "container_network", return_value="network"), \
         patch.object(fi, "run", return_value=type("Result", (), {"stdout": "{}"})()), \
         patch.object(fi, "stop_service"), \
         patch.object(fi, "start_service") as start, \
         patch.object(fi, "restore_network") as connect, \
         patch.object(fi.time, "sleep", side_effect=KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            fi.run_trial("c1", mode, 1, 10, 10)
    if mode == "network":
        connect.assert_called_once_with("network", "publisher-id")
    else:
        start.assert_called_once_with("influxdb" if mode == "storage" else "mosquitto")


def test_trial_includes_final_timestamp_and_records_recovery_action():
    stamp = "2026-09-15T00:00:00+00:00"
    snapshots = [{"timestamp": stamp, "sequence": n} for n in (0, 2)]
    with patch.object(fi, "publisher_snapshot", side_effect=snapshots), \
         patch.object(fi, "container_id", return_value="id"), \
         patch.object(fi, "stop_service"), patch.object(fi, "start_service"), \
         patch.object(fi.time, "sleep"), \
         patch.object(fi, "confirmed_recovery", return_value=3.5), \
         patch.object(fi, "wait_for_delivery", return_value={1, 2}) as delivery, \
         patch.object(fi, "logs_since", return_value=[]):
        row = fi.run_trial("c1", "storage", 1, 10, 10)
    assert delivery.call_args.args[1] == datetime.fromisoformat(stamp) + timedelta(milliseconds=1)
    assert row["messages_lost"] == 0
    assert row["recovery_seconds"] == 3.5
    assert row["recovery_actions"] == '["compose start influxdb"]'


@pytest.mark.parametrize("configuration", ["c1", "c2a", "c2b"])
def test_compose_explicitly_targets_project_and_configuration(configuration):
    with patch.object(fi, "CONFIGURATION", configuration), \
         patch.object(fi, "COMPOSE_PROJECT", "cloud-run"), \
         patch.object(fi, "ENV_FILE", "selected.env"), patch.object(fi, "run") as run:
        fi.compose("ps")
    command = run.call_args.args[0]
    assert command[command.index("--project-name") + 1] == "cloud-run"
    assert command[command.index("--env-file") + 1] == "selected.env"
    assert ("--profile" in command) == (configuration == "c1")


def test_default_outage_exceeds_two_sixty_second_keepalives():
    assert DEFAULT_OUTAGE_SECONDS > 120


def test_container_network_reads_the_attached_network():
    result = type("Result", (), {"stdout": '{"digital-twin_default": {}}'})()
    with patch("experiments.fault_injection.run", return_value=result):
        assert container_network("publisher-id") == "digital-twin_default"


def test_network_commands_disconnect_and_connect_the_container():
    with patch("experiments.fault_injection.container_id", return_value="publisher-id"), \
         patch("experiments.fault_injection.container_network", return_value="twin-network"), \
         patch("experiments.fault_injection.run") as command:
        connection = sever_network("publisher")
        restore_network(*connection)

    assert connection == ("twin-network", "publisher-id")
    assert command.call_args_list[0].args[0] == [
        "docker", "network", "disconnect", "twin-network", "publisher-id"
    ]
    assert command.call_args_list[1].args[0] == [
        "docker", "network", "connect", "twin-network", "publisher-id"
    ]


def test_trial_columns_exclude_inspected_recovery_actions():
    assert "manual_actions" not in FIELDNAMES


def test_write_recovered_can_mark_trial_resumption():
    recovered_at = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    entries = [
        {"event": "write_recovered", "timestamp": recovered_at.isoformat()},
    ]

    assert first_event_time(entries, {"write_recovered"}) == recovered_at


def test_sequence_reconciliation_counts_genuine_loss():
    assert reconcile_sequences(99, 104, {100, 101, 103, 104}) == {
        "messages_expected": 5,
        "messages_stored": 4,
        "messages_lost": 1,
    }


def test_sequence_reconciliation_ignores_order_and_duplicates():
    stored = {104, 102, 101, 100}
    assert reconcile_sequences(99, 104, stored) == {
        "messages_expected": 5,
        "messages_stored": 4,
        "messages_lost": 1,
    }


def test_sequence_reconciliation_counts_late_redelivery_as_stored():
    assert reconcile_sequences(99, 102, {100, 102, 101}) == {
        "messages_expected": 3,
        "messages_stored": 3,
        "messages_lost": 0,
    }
