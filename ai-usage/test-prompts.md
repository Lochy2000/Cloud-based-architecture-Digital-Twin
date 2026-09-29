# Reconstructed prompts for complex tests

These prompts record plausible AI-assisted test specifications for the more
complex parts of the project. They describe intended behaviour; the final tests
may have been adjusted manually as the implementation and conventions developed.
Simpler direct return-value and missing-field tests are not included.

## 1. MQTT connection waits for CONNACK and restores the callback

Related test: `tests/test_mqtt_client.py::TestConnect::test_successful_connack_returns_and_restores_callback`

```text
Write one pytest unit test for connect() in twin.mqtt_client.

The test must verify that connect() returns after a successful MQTT CONNACK and
restores the client's original on_connect callback after temporarily using its
own callback while waiting for the acknowledgement.

Structure the test using Arrange-Act-Assert:
- Arrange: build a client with the existing password configuration helper and
  save its original on_connect callback. Patch mqtt.Client.connect so no network
  connection is made. Patch mqtt.Client.loop_start with a side effect that calls
  the client's current on_connect callback using a successful Paho MQTT v2
  CONNACK ReasonCode. Patch loop_stop as well.
- Act: call connect() with the client, configuration, and a fixed timeout.
- Assert: connect() does not raise and client.on_connect is the same callback
  object that was saved before the call.

Do not connect to a real broker and do not sleep. Use unittest.mock with pytest,
follow the existing helper and import style, and return only the proposed test
code.
```

## 2. Storage writer logs one recovery after repeated failures

Related test: `tests/test_storage_writer.py::TestHandleMessage::test_first_success_after_failures_logs_one_recovery`

```text
Write one pytest unit test for handle_message() and WriteFailureState in
twin.storage_writer.

The test must verify that two consecutive InfluxDB write failures followed by
two successful writes produce exactly one recovery log on the first success.
The recovery metadata must identify sequence 2 and report two failures since the
last success; the later successful write must not produce another recovery log.

Structure the test using Arrange-Act-Assert:
- Arrange: use the existing _raw() helper to create messages with sequences 0
  through 3. Create one shared SequenceTracker and WriteFailureState. Configure a
  mocked write API with side effects of two exceptions followed by two successful
  returns, and use a mocked logger.
- Act: call handle_message() once for each message while reusing the same tracker,
  failure state, write API, and logger.
- Assert: logger.info was called exactly once and its extra dictionary is exactly
  {"event": "write_recovered", "sequence": 2,
  "failures_since_last_success": 2}.

Do not use a live InfluxDB instance. Preserve state across all four calls and
return only the proposed test code.
```

## 3. Interrupted fault injection always restores the affected service

Related test: `tests/test_fault_injection.py::test_interrupted_outage_restores_target`

```text
Write one parameterized pytest unit test for run_trial() in
experiments.fault_injection.

The test must verify that cleanup restores the affected target when a
KeyboardInterrupt occurs during an outage. Cover storage, broker, and network
outage modes.

Structure the test using Arrange-Act-Assert:
- Arrange: parameterize mode over "storage", "broker", and "network". Patch the
  publisher snapshot with a fixed UTC timestamp and sequence, patch container and
  network discovery with stable values, and patch command execution and service
  control so no Docker operations occur. Make the outage sleep raise
  KeyboardInterrupt. Spy on start_service and restore_network.
- Act: call run_trial("c1", mode, 1, 10, 10) and assert that KeyboardInterrupt is
  propagated.
- Assert: for network mode, restore_network is called once with the discovered
  network and publisher container ID. For storage mode, start_service is called
  once with "influxdb". For broker mode, it is called once with "mosquitto".

Use descriptive parameter IDs. Return only the proposed pytest code.
```

## 4. Fault trial includes its final timestamp and records recovery

Related test: `tests/test_fault_injection.py::test_trial_includes_final_timestamp_and_records_recovery_action`

```text
Write one pytest unit test for run_trial() in experiments.fault_injection.

The test must verify that a storage-outage trial includes the final publisher
timestamp in its delivery query, reports no loss when all expected sequences are
stored, records the recovery duration, and records the automatic recovery action.

Structure the test using Arrange-Act-Assert:
- Arrange: provide two publisher snapshots with the same fixed timezone-aware
  timestamp and sequences 0 and 2. Patch container lookup, service stop/start,
  sleep, recovery confirmation, delivery polling, and log inspection. Make
  confirmed_recovery return 3.5 and wait_for_delivery return {1, 2}.
- Act: call run_trial("c1", "storage", 1, 10, 10).
- Assert: the stop bound passed to wait_for_delivery is the final snapshot
  timestamp plus one millisecond, messages_lost is 0, recovery_seconds is 3.5,
  and recovery_actions is the JSON string ["compose start influxdb"].

Use fixed values and patched collaborators; do not invoke Docker, InfluxDB, or
real sleeps. Return only the proposed pytest code.
```

## 5. Completed-run summary uses one consistent measurement window

Related test: `tests/test_run_summary.py::test_create_summary_uses_one_completed_publisher_window`

```text
Write one pytest unit test for create_summary() in experiments.run_summary.

The test must verify that the summary is built from one completed publisher run
and that its InfluxDB query uses that run's exact start and stop timestamps.

Structure the test using Arrange-Act-Assert:
- Arrange: use fixed UTC start and stop datetimes exactly 60 seconds apart. Mock
  structured_logs with matching started and stopping events, including interval,
  accepted, deferred, and overrun fields. Mock dotenv_values with the required
  InfluxDB and asset values. Mock InfluxDBClient as a context manager whose query
  API is a MagicMock. Patch point count to 3, time bounds to the same start and
  stop, series cardinality to 1, and database volume to 4096. Supply a network
  capture for the same run with counters 1000 and 1600.
- Act: call create_summary("c1", "c1.env", network_capture).
- Assert: the summary reports a 60.0-second duration, 3 stored messages, 3
  accepted messages, 1 deferred message, 4096 database bytes, and 600 publisher
  network bytes. Also assert that the point-count query receives the mocked query
  API, bucket, asset ID, start, and stop exactly once.

Patch dependencies where experiments.run_summary imports them. Do not read a
real environment file or contact InfluxDB or Docker. Return only the proposed
test code.
```

## 6. Deployment timing cleans up after measurement failure

Related test: `tests/test_deployment_timer.py::test_trial_cleans_after_measurement_failure`

```text
Write one pytest unit test for measure_trial() in
experiments.deployment_timer.

The test must verify that both pre-trial and final cleanup occur when waiting for
the first database point raises TimeoutError, and that TimeoutError is not
swallowed.

Structure the test using Arrange-Act-Assert:
- Arrange: patch clean_stack and compose, make wait_for_first_point raise
  TimeoutError, and give time.monotonic the fixed values 10.0 and 11.0.
- Act: call measure_trial() for configuration "c1", Path("c1.env"), project
  "timing-c1", an empty environment, timeout 60, and poll interval 0.25.
- Assert: pytest.raises observes TimeoutError and clean_stack has been called
  exactly twice.

Do not invoke Docker, query InfluxDB, or use real time. Patch dependencies at the
module-under-test boundary and return only the proposed pytest code.
```

## 7. Network checkpoint preserves a single run's counters

Related test: `tests/test_run_summary.py::test_network_checkpoint_records_start_and_end_for_one_run`

```text
Write one pytest unit test for capture_network_counter() and
network_measurements() in experiments.run_summary.

The test must verify that start and end network counters are recorded for the
same publisher run and that transmitted bytes are calculated as end minus start.

Structure the test using Arrange-Act-Assert:
- Arrange: use tmp_path for the checkpoint JSON file and a fixed timezone-aware
  UTC publisher start. Patch structured_logs to return the matching started
  event. Patch publisher_network_tx_bytes to return ("publisher-id", 1000) for
  the start capture and ("publisher-id", 1450) for the end capture.
- Act: call capture_network_counter() first with action "start" and then with
  action "end", using configuration "c1" and environment file "c1.env". Pass
  the resulting capture and fixed publisher start to network_measurements().
- Assert: the capture contains counters 1000 and 1450, and the calculated
  publisher_network_tx_bytes value is exactly 450.

Use only tmp_path and patched command-facing functions; do not invoke Docker.
Return only the proposed pytest code.
```

## 8. InfluxDB query helpers agree on known and empty windows

Related test: `tests/test_query_integration.py::test_queries_known_points_and_empty_window`

```text
Write one pytest integration test for fetch_sequences(), fetch_point_count(),
fetch_time_bounds(), and fetch_series_cardinality() in twin.query.

The test must verify that all four query helpers agree after writing a small,
known dataset to a temporary InfluxDB bucket, and that sequence and time-bound
queries return their documented empty results for a future window.

Structure the test using Arrange-Act-Assert:
- Arrange: use the existing temporary_bucket fixture. Create three telemetry
  points for asset "boiler_test" with sequences 2, 4, and 5 at consecutive
  one-second timestamps. Add one point for "second_asset" so cardinality can be
  checked. Write synchronously and use UTC timestamps.
- Act: query a one-minute window containing the points, then query a future
  one-minute window containing none of them.
- Assert: the populated window returns sequence set {2, 4, 5}, point count 3,
  first and last inserted timestamps as its bounds, and series cardinality 2.
  The empty window returns an empty sequence set and (None, None) time bounds.

Mark the test as integration or rely on the module-level integration marker and
environment-controlled skip already used by the module. Isolate the second asset
from the boiler-specific results. Return only the proposed pytest code.
```
