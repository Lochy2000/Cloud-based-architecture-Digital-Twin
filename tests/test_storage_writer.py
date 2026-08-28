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
from twin.storage_writer import SequenceTracker, handle_message, to_point, topic_for

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
