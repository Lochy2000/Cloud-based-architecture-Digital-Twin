"""
Tests for src/twin/publisher.py.

Covers the two pieces that are unit-testable without a broker: topic
construction, and the monotonic scheduling arithmetic. Drift in the latter
would understate message count, which feeds M1.1 and M1.3 directly.

The publish loop itself is exercised at Stage 7 against a live broker.
"""

from twin.publisher import next_tick_delay, topic_for

class TestTopic:

    def test_topic_includes_asset_id(self):
        assert topic_for("boiler_01") == "twin/boiler_01/telemetry"
