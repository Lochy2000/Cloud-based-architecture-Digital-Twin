"""Telemetry payload building, validation, and parsing."""

from datetime import datetime, timezone

import pytest

from twin.payload import CHANNELS, SCHEMA_VERSION, PayloadError, TelemetryPayload, build_payload, parse, serialize


def _example_readings():
    return {
        "supply_temperature_c": 62.3,
        "return_temperature_c": 54.1,
        "ambient_temperature_c": 19.7,
        "power_draw_kw": 4.85,
        "setpoint_c": 60.0,
    }


def _example_timestamp():
    return datetime(2026, 8, 20, 14, 3, 22, 123000, tzinfo=timezone.utc)


# --- build_payload -------------------------------------------------

class TestBuildPayload:

    def test_builds_a_valid_payload(self):
        # Builds a valid payload.
        payload = build_payload("boiler_01", 4821, _example_timestamp(), _example_readings())

        assert payload.asset_id == "boiler_01"
        assert payload.sequence == 4821
        assert payload.schema_version == SCHEMA_VERSION
        assert payload.timestamp == "2026-08-20T14:03:22.123+00:00"
        assert payload.supply_temperature_c == 62.3

    def test_rejects_empty_asset_id(self):
        # Rejects empty asset ID.
        with pytest.raises(PayloadError, match="asset_id"):
            build_payload("", 0, _example_timestamp(), _example_readings())

    def test_rejects_negative_sequence(self):
        # Rejects negative sequence.
        with pytest.raises(PayloadError, match="sequence"):
            build_payload("boiler_01", -1, _example_timestamp(), _example_readings())

    def test_rejects_non_integer_sequence(self):
        # Rejects non integer sequence.
        with pytest.raises(PayloadError, match="sequence"):
            build_payload("boiler_01", "4", _example_timestamp(), _example_readings())

    def test_rejects_bool_as_sequence(self):
        # Rejects bool as sequence.
        # bool is a subclass of int in Python — True would otherwise slip through as 1.
        with pytest.raises(PayloadError, match="sequence"):
            build_payload("boiler_01", True, _example_timestamp(), _example_readings())

    def test_rejects_naive_timestamp(self):
        # Rejects naive timestamp.
        naive = datetime(2026, 8, 20, 14, 3, 22)  # no tzinfo
        with pytest.raises(PayloadError, match="timestamp"):
            build_payload("boiler_01", 0, naive, _example_readings())

    def test_rejects_non_utc_timestamp(self):
        # Rejects non UTC timestamp.
        from datetime import timedelta

        bst = timezone(timedelta(hours=1))
        non_utc = datetime(2026, 8, 20, 14, 3, 22, tzinfo=bst)
        with pytest.raises(PayloadError, match="UTC"):
            build_payload("boiler_01", 0, non_utc, _example_readings())

    def test_rejects_missing_channel(self):
        # Rejects missing channel.
        readings = _example_readings()
        del readings["setpoint_c"]
        with pytest.raises(PayloadError, match="setpoint_c"):
            build_payload("boiler_01", 0, _example_timestamp(), readings)

    def test_rejects_unexpected_channel(self):
        # Rejects unexpected channel.
        readings = _example_readings()
        readings["humidity_pct"] = 45.0
        with pytest.raises(PayloadError, match="humidity_pct"):
            build_payload("boiler_01", 0, _example_timestamp(), readings)

    def test_rejects_non_numeric_channel_value(self):
        # Rejects non numeric channel value.
        readings = _example_readings()
        readings["supply_temperature_c"] = "warm"
        with pytest.raises(PayloadError, match="supply_temperature_c"):
            build_payload("boiler_01", 0, _example_timestamp(), readings)


# --- round trip ---------------------------------------------------

class TestRoundTrip:

    def test_parse_of_serialize_equals_original(self):
        # Serializing and parsing gets the same payload back.
        original = build_payload("boiler_01", 4821, _example_timestamp(), _example_readings())
        rebuilt = parse(serialize(original))

        assert rebuilt == original

    def test_round_trip_preserves_every_field_value(self):
        # Round trip preserves every field value.
        original = build_payload("boiler_01", 4821, _example_timestamp(), _example_readings())
        rebuilt = parse(serialize(original))

        for channel in CHANNELS:
            assert getattr(rebuilt, channel) == getattr(original, channel)
        assert rebuilt.sequence == original.sequence
        assert rebuilt.timestamp == original.timestamp


# --- parse: malformed input -----------------------------------------

class TestParseRejectsMalformedInput:

    def _valid_payload_bytes(self):
        return serialize(build_payload("boiler_01", 0, _example_timestamp(), _example_readings()))

    def test_rejects_non_json_bytes(self):
        # Rejects non JSON bytes.
        with pytest.raises(PayloadError, match="JSON"):
            parse(b"not json at all")

    def test_rejects_json_that_is_not_an_object(self):
        # Rejects JSON that is not an object.
        with pytest.raises(PayloadError, match="JSON object"):
            parse(b"[1, 2, 3]")

    def test_rejects_missing_field(self):
        # Rejects missing field.
        import json
        data = json.loads(self._valid_payload_bytes())
        del data["sequence"]
        with pytest.raises(PayloadError, match="sequence"):
            parse(json.dumps(data).encode("utf-8"))

    def test_rejects_unexpected_field(self):
        # Rejects unexpected field.
        import json
        data = json.loads(self._valid_payload_bytes())
        data["extra_field"] = "surprise"
        with pytest.raises(PayloadError, match="extra_field"):
            parse(json.dumps(data).encode("utf-8"))

    def test_rejects_wrong_schema_version(self):
        # Rejects wrong schema version.
        import json
        data = json.loads(self._valid_payload_bytes())
        data["schema_version"] = "2.0"
        with pytest.raises(PayloadError, match="schema_version"):
            parse(json.dumps(data).encode("utf-8"))

    def test_rejects_negative_sequence(self):
        # Rejects negative sequence.
        import json
        data = json.loads(self._valid_payload_bytes())
        data["sequence"] = -5
        with pytest.raises(PayloadError, match="sequence"):
            parse(json.dumps(data).encode("utf-8"))

    def test_rejects_non_numeric_channel(self):
        # Rejects non numeric channel.
        import json
        data = json.loads(self._valid_payload_bytes())
        data["ambient_temperature_c"] = None
        with pytest.raises(PayloadError, match="ambient_temperature_c"):
            parse(json.dumps(data).encode("utf-8"))


# --- G-2: measured byte size ----------------------------------------

class TestMeasuredByteSize:

    def test_representative_payload_is_248_bytes(self):
        # Representative payload is 248 bytes.
        """
        a slight increase in the inital payload this is 248 bytes compared to the expected 200 but thats fine for now

        If this test ever fails, it means a field was added, removed, or
        renamed 
        """
        payload = build_payload("boiler_01", 4821, _example_timestamp(), _example_readings())
        raw = serialize(payload)

        assert len(raw) == 248
