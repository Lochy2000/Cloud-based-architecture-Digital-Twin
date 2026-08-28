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