# Development

## Repository layout

```text
config/assets/       Thermal asset definitions
config/env/          Templates and ignored runtime environments
deploy/              Images, Compose, Mosquitto, and Grafana provisioning
docs/                Developer and operator documentation
src/twin/            Python application package
tests/               Unit tests
```

The project uses Python 3.11 and a `src` layout. `pytest.ini` adds `src` to the
test import path.

## Setup and tests

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
pytest -q
```

The production image installs `requirements-runtime.txt`, which excludes pytest
and other development-only packages.

Run one module or test group while developing:

```powershell
pytest tests/test_simulator.py -v
pytest tests/test_simulator.py::TestNewtonsCooling -v
```

Unit tests require neither a live broker nor InfluxDB. They cover:

- environment and asset validation;
- thermal duty-cycle and cold-start calculations;
- payload construction, parsing, and byte stability;
- MQTT authentication, TLS, sessions, callbacks, and errors;
- scheduling, reconnect subscription, sequence gaps, and point mapping;
- structured logging and capture summary calculations.

Use Compose for integration checks across TLS, broker, database, and dashboard
boundaries.

## Change guidance

When changing telemetry fields, update `TelemetryPayload`, `CHANNELS`, parsing,
simulator output, InfluxDB mapping, dashboard queries, and tests together. Change
`SCHEMA_VERSION` when compatibility is intentionally broken.

When changing timing, retain UTC domain timestamps and monotonic scheduling. Do
not calculate the next delay from the previous sleep because processing time
would accumulate as drift.

When changing MQTT callbacks, use Paho callback API version 2 and preserve the
lifecycle callback chain. Callback exceptions can disrupt the network loop and
invalidate fault measurements.

Do not commit `.env` files, password databases, private keys, generated samples,
or service data. Run the full suite and validate the relevant Compose
configuration before submitting a change.
