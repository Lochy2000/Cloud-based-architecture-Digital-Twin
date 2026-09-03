# Tools and references

Python runtime versions are pinned in `requirements-runtime.txt`; development
and test additions are in `requirements.txt`. Container image versions are
pinned in `deploy/docker-compose.yml`.

## Runtime and development

- [Python](https://docs.python.org/3/) 3.11 runs the application. Standard
  [`venv`](https://docs.python.org/3/library/venv.html) isolates dependencies.
- [pytest](https://docs.pytest.org/en/stable/) discovers and runs unit tests.
- [PyYAML](https://pyyaml.org/wiki/PyYAMLDocumentation) parses asset YAML. The
  project uses `safe_load` followed by application validation.
- [Eclipse Paho MQTT Python](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html)
  provides MQTT 3.1.1 clients, callback API v2, TLS, background network loops,
  session handling, publishing, subscription, and reconnection.
- [InfluxDB Python client](https://influxdb-client.readthedocs.io/en/stable/)
  performs synchronous writes of validated telemetry points.
- [`python-dotenv`](https://saurabh-kumar.com/python-dotenv/) is pinned but is
  not currently imported by application code. Containers receive configuration
  from Docker Compose.

## Infrastructure

- [Docker](https://docs.docker.com/get-started/) builds non-root service images.
- [Docker Compose](https://docs.docker.com/compose/) defines services, networks,
  volumes, profiles, health checks, dependencies, and environment injection.
- [Eclipse Mosquitto](https://mosquitto.org/documentation/) is the C1 MQTT
  broker. Its clients implement the health check; `mosquitto_passwd` creates the
  credential database.
- [InfluxDB 2](https://docs.influxdata.com/influxdb/v2/) stores timestamped data
  in the `telemetry` bucket and measurement.
- [Grafana](https://grafana.com/docs/grafana/latest/) visualises InfluxDB data.
  Data sources and dashboards use
  [file provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/).
- [OpenSSL](https://docs.openssl.org/master/) creates and verifies local C1 TLS
  certificates. It is a setup tool, not an application runtime dependency.

## Managed brokers

- [HiveMQ Cloud documentation](https://docs.hivemq.com/hivemq-cloud/) applies to
  C2a password-authenticated broker configuration.
- [AWS IoT Core developer guide](https://docs.aws.amazon.com/iot/latest/developerguide/what-is-aws-iot.html)
  applies to C2b endpoints and mutual-TLS device certificates.

External documentation defines tool behaviour. Repository code and environment
templates define how each tool is used by this project.
