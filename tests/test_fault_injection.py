"""Focused tests for fault-injection measurement behavior."""

from unittest.mock import patch

from experiments.fault_injection import (
    DEFAULT_OUTAGE_SECONDS,
    first_event_time,
    manual_actions_for,
    restore_network,
    sever_network,
)

from datetime import datetime, timezone


def test_default_outage_exceeds_two_sixty_second_keepalives():
    assert DEFAULT_OUTAGE_SECONDS > 120


def test_network_commands_run_iptables_as_root():
    with patch("experiments.fault_injection.container_id", return_value="publisher-id"), \
         patch("experiments.fault_injection.run") as command:
        sever_network("publisher")
        restore_network("publisher")

    for call in command.call_args_list:
        arguments = call.args[0]
        assert arguments[:6] == [
            "docker", "exec", "--privileged", "-u", "0", "publisher-id"
        ]
        assert arguments[6] == "iptables"


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
