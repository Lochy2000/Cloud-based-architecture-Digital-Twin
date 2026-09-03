# Operations

## Services and startup

Compose starts InfluxDB, Grafana, publisher, and storage writer. Profile `c1`
also starts Mosquitto. Health checks prevent application startup before the
local broker and database are ready.

Use [run.md](run.md) for local operation. Validate configuration first:

```powershell
Set-Location deploy
docker compose --env-file ../config/env/c1.env --profile c1 config --quiet
```

For the published runtime, merge `docker-compose.registry.yml` after the main
file and use `up --no-build`. The override changes only the publisher and
storage-writer image source; supporting services and runtime behaviour remain
unchanged.

## TLS and broker credentials

C1 requires a private CA, a server certificate for `mosquitto`, and a Mosquitto
password database. Use an organisational PKI where available; OpenSSL is
adequate for local experimental use.

The server certificate must be signed by the CA supplied to clients and include
`DNS:mosquitto` in its SAN. `DNS:localhost` is also appropriate for host-side
testing. Verify the chain with `openssl verify` before startup.

Generate `deploy/mosquitto/passwd` with `mosquitto_passwd`. It must be a
non-empty file readable by the container's `mosquitto` user. Private keys, the
password database, and real environment files must remain outside version
control.

## Observability

Application logs are structured JSON on standard output. Important events
include `connected`, `disconnected`, `connect_refused`, `publish_failed`,
`tick_overrun`, `sequence_gap`, `payload_rejected`, and `write_failed`.

```powershell
docker compose --env-file ../config/env/c1.env --profile c1 ps
docker compose --env-file ../config/env/c1.env --profile c1 logs -f publisher storage-writer
```

Grafana provisions its data source from `deploy/grafana/provisioning/datasources`
and dashboard provider from `deploy/grafana/provisioning/dashboards`. Dashboard
JSON is stored in `deploy/grafana/dashboards` and treated as configuration as
code.

## Payload sampling

With broker variables available to the process, run:

```powershell
python -m twin.capture_sample
```

It waits for 1,000 valid messages and writes `payload_sample.json` with captured
messages and mean, minimum, and maximum serialized sizes. The output is ignored
by Git.

## Troubleshooting

`Unable to open pwfile` means the password mount is absent, is a directory, or
is unreadable. Confirm it is a non-empty file and inspect permissions inside the
broker image.

Missing `DOCKER_INFLUXDB_INIT_*` values mean Compose did not receive the selected
environment file. Use `--env-file`; service `env_file` does not perform Compose
substitution.

`CERTIFICATE_VERIFY_FAILED` means the signing CA was not loaded or the
certificate identity differs from `BROKER_HOST`. Check `BROKER_CA_CERT`, mounts,
chain verification, and SAN entries.

Name-resolution errors for `mosquitto` commonly follow broker startup failure.
Fix the broker's first error before treating DNS as the primary fault.

If Grafana does not show the dashboard, confirm the plural `dashboards`
provisioning directory, JSON mount, and provisioning logs.

`docker compose down` is a recoverable stop. Adding `--volumes` deletes persisted
service data and is appropriate only for an intentional reset.
