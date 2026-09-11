"""Focused tests for the clean deployment timing harness."""

from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.deployment_timer import compose_command, measure_trial


def test_c1_compose_command_includes_profile_before_subcommand():
    command = compose_command("c1", Path("c1.env"), "timing-c1", "up", "--detach")

    assert command == [
        "docker", "compose",
        "--project-name", "timing-c1",
        "--env-file", "c1.env",
        "--profile", "c1",
        "up", "--detach",
    ]


def test_managed_compose_command_has_no_local_broker_profile():
    command = compose_command("c2a", Path("c2a.env"), "timing-c2a", "up")

    assert "--profile" not in command


@patch("experiments.deployment_timer.wait_for_first_point", return_value=4.0)
@patch("experiments.deployment_timer.compose")
@patch("experiments.deployment_timer.clean_stack")
@patch("experiments.deployment_timer.time.monotonic", side_effect=[10.0, 12.0])
def test_trial_times_startup_and_query_and_cleans_both_sides(
    monotonic, clean, compose, wait
):
    result = measure_trial(
        "c1", Path("c1.env"), "timing-c1", {}, timeout=60, poll_interval=0.25
    )

    assert result["seconds_to_first_datapoint"] == 6.0
    assert clean.call_count == 2
    compose.assert_called_once_with(
        "c1", Path("c1.env"), "timing-c1", "up", "--detach", "--no-build"
    )
    wait.assert_called_once()


@patch("experiments.deployment_timer.wait_for_first_point", side_effect=TimeoutError)
@patch("experiments.deployment_timer.compose")
@patch("experiments.deployment_timer.clean_stack")
@patch("experiments.deployment_timer.time.monotonic", side_effect=[10.0, 11.0])
def test_trial_cleans_after_measurement_failure(monotonic, clean, compose, wait):
    with pytest.raises(TimeoutError):
        measure_trial(
            "c1", Path("c1.env"), "timing-c1", {}, timeout=60, poll_interval=0.25
        )

    assert clean.call_count == 2
