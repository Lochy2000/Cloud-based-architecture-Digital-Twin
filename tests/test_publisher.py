"""
Tests for src/twin/publisher.py.

Covers the two pieces that are unit-testable without a broker: topic
construction, and the monotonic scheduling arithmetic. Drift in the latter
would understate message count, which would directly effect the costs

The publish loop itself is teste against a live broker.
"""

import paho.mqtt.client as mqtt

from twin.publisher import (
    next_tick_delay,
    publish_outcome,
    should_log_progress,
    sleep_duration,
    topic_for,
)

class TestTopic:

    def test_topic_includes_asset_id(self):
        assert topic_for("boiler_01") == "twin/boiler_01/telemetry"

class TestMonotonicScheduling:

    def test_first_interval_when_work_is_instant(self):
        assert next_tick_delay(start=1000.0, sequence=1, interval=30.0, now=1000.0) == 30.0

    def test_work_time_is_subtracted_not_added(self):
        # Two seconds spent simulating and publishing could mean 28 not 30
        assert next_tick_delay(start=1000.0, sequence=1, interval=30.0, now=1002.0) == 28.0

    def test_targets_do_not_drift_over_many_ticks(self):
        # Tick 100's target is 3000s after the origin regardless of how long
        # earlier ticks took. A sleep-fixed-duration loop would be late by the
        # accumulated per-tick work by this point.
        start = 1000.0
        delay = next_tick_delay(start=start, sequence=100, interval=30.0, now=start + 2999.0)
        assert delay == 1.0

    def test_overrun_returns_negative(self):
        # Tick took longer than the interval — the caller logs this rather than
        # silently skipping, since the nominal message count was not met.
        assert next_tick_delay(start=1000.0, sequence=1, interval=30.0, now=1035.0) == -5.0

    def test_sub_second_interval_supported(self):
        # Load testing may use intervals below one second.
        assert next_tick_delay(start=0.0, sequence=4, interval=0.25, now=0.5) == 0.5

    def test_elapsed_deadline_never_produces_negative_sleep(self):
        # The clock can pass the deadline between the loop condition and sleep.
        assert sleep_duration(deadline=1000.0, now=1000.001) == 0.0

    def test_sleep_slice_is_limited_for_prompt_shutdown(self):
        assert sleep_duration(deadline=1010.0, now=1000.0) == 0.5


class TestPublishOutcome:

    def test_success_is_accepted(self):
        assert publish_outcome(1, mqtt.MQTT_ERR_SUCCESS) == "accepted"

    def test_qos_1_no_connection_is_deferred(self):
        assert publish_outcome(1, mqtt.MQTT_ERR_NO_CONN) == "deferred"

    def test_qos_0_no_connection_is_failed(self):
        assert publish_outcome(0, mqtt.MQTT_ERR_NO_CONN) == "failed"


class TestProgressCadence:

    def test_logs_every_twentieth_message(self):
        assert should_log_progress(19) is True
        assert should_log_progress(39) is True

    def test_does_not_log_between_cadence_boundaries(self):
        assert should_log_progress(0) is False
        assert should_log_progress(18) is False
        assert should_log_progress(20) is False
