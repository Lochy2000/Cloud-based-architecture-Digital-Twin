"""
ests for src/twin/storage_writer.py.

covers the three pieces that are testable without a live broker or database:
payload-to-point mapping, sequence gap detection, and the guarantee
that a bad message or a failed write never escapes the MQTT callback.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from twin.payload import build_payload, serialize
from twin.storage_writer import (
    SequenceTracker,
    attach_subscription_callback,
    handle_message,
    to_point,
    topic_for,
)

def _readings():
    return {
        "supply_temperature_c": 62.3,
        "return_temperature_c": 54.1,
        "ambient_temperature_c": 19.7,
        "power_draw_kw": 4.85,
        "setpoint_c": 60.0,
    }


def _payload(sequence=0, asset_id="boiler_01"):
    ts = datetime(2026, 8, 20, 14, 3, 22, 123000, tzinfo=timezone.utc)
    return build_payload(asset_id, sequence, ts, _readings())


def _raw(sequence=0, asset_id="boiler_01"):
    return serialize(_payload(sequence, asset_id))

class TestTopic:

    def test_matches_publisher_topic(self):
        # Must agree with publisher.topic_for or nothing is ever received.
        assert topic_for("boiler_01") == "twin/boiler_01/telemetry"

class TestSubscription:

    def test_subscribes_after_initial_connect_and_reconnect(self):
        client = MagicMock()
        lifecycle_callback = MagicMock()
        client.on_connect = lifecycle_callback
        attach_subscription_callback(client, "twin/boiler_01/telemetry", qos=0)

        success = MagicMock(value=0)
        success.__eq__.side_effect = lambda other: success.value == other
        client.on_connect(client, None, {}, success, None)
        client.on_connect(client, None, {}, success, None)

        assert lifecycle_callback.call_count == 2
        assert client.subscribe.call_count == 2
        client.subscribe.assert_called_with("twin/boiler_01/telemetry", qos=0)

class TestToPoint:

    def test_asset_id_is_a_tag(self):
        line = to_point(_payload()).to_line_protocol()
        assert "asset_id=boiler_01" in line

    def test_all_five_channels_are_fields(self):
        line = to_point(_payload()).to_line_protocol()
        for channel in ("supply_temperature_c", "return_temperature_c",
                        "ambient_temperature_c", "power_draw_kw", "setpoint_c"):
            assert channel in line

    def test_sequence_is_a_field_not_a_tag(self):
        # As a tag, sequence would give unbounded cardinality.
        line = to_point(_payload(sequence=4821)).to_line_protocol()
        assert "sequence=4821" in line
        assert ",sequence=" not in line.split(" ")[0]

    def test_timestamp_comes_from_payload_not_arrival(self):
        # 2026-08-20T14:03:22.123Z in milliseconds.
        line = to_point(_payload()).to_line_protocol()
        assert line.endswith("1787234602123")

class TestSequenceTracker:

    def test_first_message_is_never_a_gap(self):
        assert SequenceTracker().check("boiler_01", 0) == 0

    def test_contiguous_messages_report_no_gap(self):
        tracker = SequenceTracker()
        tracker.check("boiler_01", 0)
        assert tracker.check("boiler_01", 1) == 0

    def test_single_missing_message_reported(self):
        tracker = SequenceTracker()
        tracker.check("boiler_01", 0)
        assert tracker.check("boiler_01", 2) == 1

    def test_multiple_missing_messages_counted(self):
        tracker = SequenceTracker()
        tracker.check("boiler_01", 10)
        assert tracker.check("boiler_01", 25) == 14

    def test_publisher_restart_is_not_counted_as_a_gap(self):
        # Sequence restarts at 0 when the publisher process restarts.
        tracker = SequenceTracker()
        tracker.check("boiler_01", 500)
        assert tracker.check("boiler_01", 0) == 0

    def test_redelivered_message_is_not_a_gap(self):
        # QoS 1 can redeliver a message already seen.
        tracker = SequenceTracker()
        tracker.check("boiler_01", 5)
        assert tracker.check("boiler_01", 5) == 0

    def test_assets_are_tracked_independently(self):
        tracker = SequenceTracker()
        tracker.check("boiler_01", 100)
        assert tracker.check("chiller_02", 0) == 0


class TestHandleMessage:

    def test_valid_message_is_written(self):
        write_api = MagicMock()
        stored = handle_message(_raw(), write_api, "telemetry", SequenceTracker(), MagicMock())

        assert stored is True
        write_api.write.assert_called_once()
        assert write_api.write.call_args.kwargs["bucket"] == "telemetry"

    def test_malformed_payload_is_discarded_without_raising(self):
        write_api = MagicMock()
        logger = MagicMock()

        stored = handle_message(b"not json", write_api, "telemetry", SequenceTracker(), logger)

        assert stored is False
        write_api.write.assert_not_called()
        logger.error.assert_called_once()

    def test_wrong_schema_version_is_discarded(self):
        write_api = MagicMock()
        raw = _raw().replace(b'"1.0"', b'"2.0"')

        stored = handle_message(raw, write_api, "telemetry", SequenceTracker(), MagicMock())

        assert stored is False
        write_api.write.assert_not_called()

    def test_influx_failure_does_not_raise(self):
        # An exception escaping the MQTT callback kills the network loop thread,
        # which during a trial would be indistinguishable from broker failure.
        write_api = MagicMock()
        write_api.write.side_effect = Exception("connection refused")
        logger = MagicMock()

        stored = handle_message(_raw(), write_api, "telemetry", SequenceTracker(), logger)

        assert stored is False
        logger.error.assert_called_once()

    def test_sequence_gap_is_logged(self):
        write_api = MagicMock()
        logger = MagicMock()
        tracker = SequenceTracker()

        handle_message(_raw(sequence=0), write_api, "telemetry", tracker, logger)
        handle_message(_raw(sequence=5), write_api, "telemetry", tracker, logger)

        logger.warning.assert_called_once()
        assert logger.warning.call_args.kwargs["extra"]["messages_missing"] == 4

    def test_gap_does_not_prevent_storage(self):
        # A gap is a finding, not a reason to discard the message that revealed it.
        write_api = MagicMock()
        tracker = SequenceTracker()

        handle_message(_raw(sequence=0), write_api, "telemetry", tracker, MagicMock())
        stored = handle_message(_raw(sequence=9), write_api, "telemetry", tracker, MagicMock())

        assert stored is True
        assert write_api.write.call_count == 2
