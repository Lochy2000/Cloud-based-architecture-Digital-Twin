"""Focused tests for fault-injection measurement behavior."""

from unittest.mock import patch

from experiments.fault_injection import (
    DEFAULT_OUTAGE_SECONDS,
    container_network,
    first_event_time,
    manual_actions_for,
    restore_network,
    sever_network,
)

from datetime import datetime, timezone


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


def test_manual_actions_measure_recovery_not_fault_injection():
    assert manual_actions_for("c1", "broker") == 1
    assert manual_actions_for("c2a", "broker") == 0
    assert manual_actions_for("c2b", "broker") == 0
    assert manual_actions_for("c1", "network") == 1
    assert manual_actions_for("c1", "storage") == 1


def test_write_recovered_can_mark_trial_resumption():
    recovered_at = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    entries = [
        {"event": "write_recovered", "timestamp": recovered_at.isoformat()},
    ]

    assert first_event_time(entries, {"write_recovered"}) == recovered_at
