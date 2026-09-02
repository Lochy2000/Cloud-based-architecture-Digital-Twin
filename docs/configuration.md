# Configuration

Configuration is supplied through environment variables. Runtime `.env` files
contain secrets and are ignored by Git; committed `.env.example` files are
templates only.

## Broker variables

| Variable | Purpose |
| --- | --- |
| `BROKER_HOST`, `BROKER_PORT` | MQTT endpoint. |
| `BROKER_TLS` | Enables TLS. |
| `BROKER_AUTH_MODE` | `password` or `cert`. |
| `BROKER_USERNAME`, `BROKER_PASSWORD` | Required for password authentication. |
| `BROKER_CA_CERT` | Optional private CA for password mode; required for certificate mode. |
| `BROKER_CLIENT_CERT`, `BROKER_CLIENT_KEY` | Required for mutual TLS. |
| `BROKER_KEEPALIVE` | MQTT keepalive in seconds; default is 60. |
| `MQTT_QOS` | MQTT QoS 0, 1, or 2. |

For C1, certificate paths are container paths such as `/certs/ca.crt`, not host
paths. C2a normally uses the operating-system CA store. C2b mounts the provider
CA, device certificate, and private key under `/certs`.

## Workload variables

| Variable | Purpose |
| --- | --- |
| `ASSET_ID` | Asset selected by subscribers and utilities. |
| `ASSET_CONFIG_PATH` | Asset YAML path inside the publisher container. |
| `PUBLISH_INTERVAL_SECONDS` | Positive publication interval. |
| `MQTT_CLIENT_ID` | Optional service-specific override. IDs must be unique. |
| `PAYLOAD_SAMPLE_PATH` | Optional capture utility output path. |

## InfluxDB and Grafana variables

| Variable | Purpose |
| --- | --- |
| `INFLUX_URL` | InfluxDB endpoint used by the storage writer. |
| `INFLUX_TOKEN` | API token shared with the writer and Grafana data source. |
| `INFLUX_ORG`, `INFLUX_BUCKET` | InfluxDB organisation and bucket. |
| `INFLUX_INIT_USERNAME`, `INFLUX_INIT_PASSWORD` | Initial local administrator credentials. |
| `GRAFANA_ADMIN_PASSWORD` | Initial Grafana administrator password. |
| `LOG_LEVEL` | Python logging threshold; default is `INFO`. |

The provisioned dashboard currently queries bucket `telemetry`. Keep
`INFLUX_BUCKET=telemetry`, or update the dashboard queries with the deployment.

## Asset YAML

Files under `config/assets` define model inputs rather than live readings.
Required values include supply/return temperatures, ambient baseline, heating
and cooling time constants, operating hours, cycle period, and on fraction.

Add an asset by creating a conforming YAML file, mounting the asset directory,
and setting `ASSET_ID` and `ASSET_CONFIG_PATH`. Update service client IDs when
running multiple assets concurrently.

## Compose substitution

Compose `${VARIABLE}` substitution is separate from a service's `env_file`.
Always pass the selected file explicitly:

```powershell
docker compose --env-file ../config/env/c1.env --profile c1 config --quiet
```

Use `--profile c1` only for local Mosquitto. Managed broker configurations omit
that profile and select their runtime file through `--env-file`; set `ENV_FILE`
if the service-level environment file must differ from its default.
