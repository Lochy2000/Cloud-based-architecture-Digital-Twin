"""
Tests for src/twin/logging_setup.py.

Evidence for Stage 1's acceptance test: a log line is valid JSON with an
ISO-8601, millisecond-precision, UTC timestamp — a precondition for
M3.1-M3.3 (detection/recovery time measurements). Also covers the
handler-duplication guard and the LOG_LEVEL environment fallback (D-18).
"""

import json

from twin.logging_setup import setup_logging


def _read_json_lines(capsys):
    """Parse every line pytest captured on stdout as a JSON object."""
    captured = capsys.readouterr()
    return [json.loads(line) for line in captured.out.splitlines() if line.strip()]


class TestSetupLogging:

    def test_log_line_is_valid_json_with_required_fields(self, capsys):
        logger = setup_logging("test.basic_fields")
        logger.info("connected to broker")

        [record] = _read_json_lines(capsys)

        assert record["level"] == "INFO"
        assert record["component"] == "test.basic_fields"
        assert record["message"] == "connected to broker"
        assert "timestamp" in record

    def test_timestamp_is_iso8601_utc_with_millisecond_precision(self, capsys):
        logger = setup_logging("test.timestamp_format")
        logger.info("tick")

        [record] = _read_json_lines(capsys)
        timestamp = record["timestamp"]

        assert timestamp.endswith("+00:00")  # UTC offset explicit, not assumed

        fractional = timestamp.split(".")[1].split("+")[0]
        assert len(fractional) == 3  # milliseconds, e.g. ...22.123+00:00

    def test_extra_fields_are_merged_into_payload(self, capsys):
        logger = setup_logging("test.extra_fields")
        logger.info("reconnect attempt", extra={"asset_id": "boiler_01", "attempt": 3})

        [record] = _read_json_lines(capsys)

        assert record["asset_id"] == "boiler_01"
        assert record["attempt"] == 3

    def test_exception_info_is_captured(self, capsys):
        logger = setup_logging("test.exception_info")
        try:
            raise ValueError("broker connection refused")
        except ValueError:
            logger.exception("connect failed")

        [record] = _read_json_lines(capsys)

        assert "exception" in record
        assert "ValueError" in record["exception"]
        assert "broker connection refused" in record["exception"]

    def test_repeated_setup_does_not_duplicate_handlers(self, capsys):
        setup_logging("test.no_duplicates")
        logger = setup_logging("test.no_duplicates")  # called again, same component
        logger.info("single line expected")

        assert len(_read_json_lines(capsys)) == 1

    def test_explicit_level_overrides_default(self, capsys):
        logger = setup_logging("test.explicit_level", level="WARNING")
        logger.info("should be suppressed")
        logger.warning("should appear")

        records = _read_json_lines(capsys)
        assert len(records) == 1
        assert records[0]["message"] == "should appear"

    def test_log_level_env_var_used_when_no_explicit_level(self, monkeypatch, capsys):
        monkeypatch.setenv("LOG_LEVEL", "ERROR")

        logger = setup_logging("test.env_level")
        logger.warning("should be suppressed")
        logger.error("should appear")

        records = _read_json_lines(capsys)
        assert len(records) == 1
        assert records[0]["message"] == "should appear"

    def test_default_level_is_info_when_nothing_specified(self, capsys):
        logger = setup_logging("test.default_level")
        logger.debug("should be suppressed")
        logger.info("should appear")

        records = _read_json_lines(capsys)
        assert len(records) == 1
        assert records[0]["message"] == "should appear"

    def test_does_not_propagate_to_root_logger(self):
        logger = setup_logging("test.no_propagate")
        assert logger.propagate is False