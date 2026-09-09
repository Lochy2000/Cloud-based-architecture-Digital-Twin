"""Shared read queries for telemetry stored in InfluxDB."""

import json
from datetime import datetime, timezone


MEASUREMENT = "telemetry"
SEQUENCE_FIELD = "sequence"


def _flux_string(value: str) -> str:
    return json.dumps(value)


def _flux_time(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("query timestamps must be timezone-aware")
    timestamp = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return f"time(v: {_flux_string(timestamp)})"


def _sequence_query(bucket: str, asset_id: str, start: datetime, stop: datetime) -> str:
    return f'''from(bucket: {_flux_string(bucket)})
  |> range(start: {_flux_time(start)}, stop: {_flux_time(stop)})
  |> filter(fn: (r) => r._measurement == {_flux_string(MEASUREMENT)})
  |> filter(fn: (r) => r.asset_id == {_flux_string(asset_id)})
  |> filter(fn: (r) => r._field == {_flux_string(SEQUENCE_FIELD)})'''


def _records(tables):
    for table in tables:
        yield from table.records


def fetch_sequences(query_api, bucket: str, asset_id: str,
                    start: datetime, stop: datetime) -> set[int]:
    """Return stored sequence numbers for an asset in a time window."""
    tables = query_api.query(_sequence_query(bucket, asset_id, start, stop))
    return {int(record.get_value()) for record in _records(tables)}


def fetch_time_bounds(query_api, bucket: str, asset_id: str,
                      start: datetime, stop: datetime) -> tuple[datetime | None, datetime | None]:
    """Return the earliest and latest stored telemetry timestamps in a window."""
    base = _sequence_query(bucket, asset_id, start, stop)
    first = list(_records(query_api.query(f"{base}\n  |> first()")))
    last = list(_records(query_api.query(f"{base}\n  |> last()")))
    return (
        first[0].get_time() if first else None,
        last[0].get_time() if last else None,
    )


def fetch_point_count(query_api, bucket: str, asset_id: str,
                      start: datetime, stop: datetime) -> int:
    """Count telemetry messages through their single sequence field."""
    query = f"{_sequence_query(bucket, asset_id, start, stop)}\n  |> count()"
    return sum(int(record.get_value()) for record in _records(query_api.query(query)))


def fetch_series_cardinality(query_api, bucket: str,
                             start: datetime, stop: datetime) -> int:
    """Count distinct asset series; asset_id is the schema's only tag."""
    query = f'''from(bucket: {_flux_string(bucket)})
  |> range(start: {_flux_time(start)}, stop: {_flux_time(stop)})
  |> filter(fn: (r) => r._measurement == {_flux_string(MEASUREMENT)})
  |> filter(fn: (r) => r._field == {_flux_string(SEQUENCE_FIELD)})
  |> group()
  |> distinct(column: "asset_id")
  |> count()'''
    return sum(int(record.get_value()) for record in _records(query_api.query(query)))
