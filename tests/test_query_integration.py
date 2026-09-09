"""Opt-in integration tests for the shared InfluxDB query functions."""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from twin.query import (
    fetch_point_count,
    fetch_sequences,
    fetch_series_cardinality,
    fetch_time_bounds,
)


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_INFLUX_INTEGRATION") != "1",
        reason="set RUN_INFLUX_INTEGRATION=1 to run against InfluxDB",
    ),
]


@pytest.fixture
def temporary_bucket():
    url = os.environ.get("INFLUX_TEST_URL", "http://localhost:8086")
    token = os.environ["INFLUX_TOKEN"]
    org = os.environ["INFLUX_ORG"]
    client = InfluxDBClient(url=url, token=token, org=org)
    bucket = client.buckets_api().create_bucket(
        bucket_name=f"query-test-{uuid4().hex}", org=org
    )
    try:
        yield client, bucket.name, org
    finally:
        client.buckets_api().delete_bucket(bucket)
        client.close()


def test_queries_known_points_and_empty_window(temporary_bucket):
    client, bucket, org = temporary_bucket
    write_api = client.write_api(write_options=SYNCHRONOUS)
    start = datetime.now(timezone.utc).replace(microsecond=0)
    times = [start + timedelta(seconds=index) for index in range(3)]

    records = [
        Point("telemetry")
        .tag("asset_id", "boiler_test")
        .field("sequence", sequence)
        .time(timestamp, WritePrecision.S)
        for sequence, timestamp in zip((2, 4, 5), times)
    ]
    records.append(
        Point("telemetry")
        .tag("asset_id", "second_asset")
        .field("sequence", 0)
        .time(times[0], WritePrecision.S)
    )
    write_api.write(bucket=bucket, org=org, record=records)

    stop = start + timedelta(minutes=1)
    query_api = client.query_api()
    assert fetch_sequences(query_api, bucket, "boiler_test", start, stop) == {2, 4, 5}
    assert fetch_point_count(query_api, bucket, "boiler_test", start, stop) == 3
    assert fetch_time_bounds(query_api, bucket, "boiler_test", start, stop) == (
        times[0], times[-1]
    )
    assert fetch_series_cardinality(query_api, bucket, start, stop) == 2

    empty_start = start + timedelta(days=1)
    empty_stop = empty_start + timedelta(minutes=1)
    assert fetch_sequences(
        query_api, bucket, "boiler_test", empty_start, empty_stop
    ) == set()
    assert fetch_time_bounds(
        query_api, bucket, "boiler_test", empty_start, empty_stop
    ) == (None, None)
