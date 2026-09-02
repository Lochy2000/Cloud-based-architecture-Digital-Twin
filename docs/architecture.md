# Architecture

## Purpose

The project is an experimental digital-twin pipeline for an SME thermal asset.
It generates deterministic boiler telemetry and supports comparison of broker
cost, delivery, failure detection, and recovery behaviour.

## Data flow

```text
Asset YAML -> simulator -> payload -> publisher -> MQTT broker -> storage writer -> InfluxDB -> Grafana
```

## Components

`assets.py` loads and validates asset YAML. Required sections describe steady
state, thermal dynamics, and duty cycle. Invalid files fail during startup.

`simulator.py` is a pure function of asset configuration, UTC timestamp, and
ambient input. Each operating day starts at the configured baseline. Heating
and cooling use exponential response, and residual heat carries between cycles
within the day.

`payload.py` is the telemetry contract. It validates identity, UTC timestamp,
sequence, schema version, and exactly five numeric channels. JSON serialization
uses sorted keys for stable byte-size measurement.

`publisher.py` publishes to `twin/{asset_id}/telemetry`. Sequence numbers begin
at zero for each process run. Scheduling uses a monotonic clock and absolute
tick targets to avoid cumulative drift.

`mqtt_client.py` centralises MQTT 3.1.1, authentication, TLS, reconnect delays,
session selection, lifecycle logging, and clean shutdown. QoS greater than zero
uses a persistent session; QoS zero uses a clean session.

`storage_writer.py` validates incoming payloads, detects sequence gaps, maps
telemetry to an InfluxDB point, and writes synchronously. It subscribes after
every successful connection so clean-session reconnects continue receiving.
Malformed messages and database write failures are logged without escaping the
MQTT callback thread.

`capture_sample.py` captures 1,000 valid MQTT messages and records serialized
sizes for payload-size analysis. It is an experiment utility, not a long-running
service in the Compose stack.

`logging_setup.py` emits one JSON object per line to standard output. Each event
contains a UTC timestamp, severity, component, message, and structured fields.
Docker owns log collection.

## Telemetry schema

Each payload contains:

- `asset_id`, `timestamp`, `sequence`, and `schema_version`;
- `supply_temperature_c` and `return_temperature_c`;
- `ambient_temperature_c`, `power_draw_kw`, and `setpoint_c`.

InfluxDB stores data in measurement `telemetry`. `asset_id` is an indexed tag;
the sequence and five channels are fields. The payload timestamp is retained as
the point timestamp so delayed delivery does not change measurement time.

## Recovery and measurement

Paho maintains the network loop and retries connections using a 1–32 second
backoff. Connection and disconnection callbacks provide timestamps for recovery
measurement. Sequence gaps quantify loss. QoS 1 may redeliver messages, so a
repeated sequence is not treated as a gap.

The Grafana dashboard presents temperature, power, stored-message rate, and the
latest sequence. It reads data only; it does not generate telemetry.
