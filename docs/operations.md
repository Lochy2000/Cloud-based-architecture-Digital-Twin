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
include `connected`, `disconnected`, `connect_refused`, `publish_progress`,
`publish_deferred`, `publish_failed`,
`write_recovered`,
`tick_overrun`, `sequence_gap`, `payload_rejected`, and `write_failed`.

Fault trials default to a 150-second outage so network isolation remains in
place long enough for a 60-second MQTT keepalive failure to be detected.
Recovery actions are assessed separately in the maintainability matrix by
inspecting each configuration's runbook; they are not presented as measured
trial data.

Network faults use Docker network disconnect and connect operations from the
host. The runtime container therefore needs neither root access nor `NET_ADMIN`.

Each trial requests publisher snapshots immediately before and after the fault
window. Expected sequences are reconciled with the sequence set stored in
InfluxDB, producing auditable `messages_expected`, `messages_stored`, and
`messages_lost` columns. Live `sequence_gap` events remain diagnostic and are
not used as the final loss total because QoS 1 can deliver a missing message
later.

## Completed-run summaries

Capture the publisher's network counter just after starting a measured run:

```powershell
python ../experiments/run_summary.py --configuration c1 --capture-start
```

At the end of the run, capture the counter again immediately before stopping
the publisher, then create the JSON summary:

```powershell
python ../experiments/run_summary.py --configuration c1 --capture-end
docker compose --env-file ../config/env/c1.env --profile c1 stop publisher
python ../experiments/run_summary.py --configuration c1
```

The tool selects the latest completed `started`/`stopping` pair from the
publisher logs. It records the run window, stored message count and time bounds,
series cardinality, InfluxDB data-directory size, publisher accepted, deferred,
and overrun counts, and the difference between the two network transmit
counters. The network figure includes all publisher-container traffic,
including local MQTT, DNS, and TLS traffic. It is a cross-check for provider
billing data rather than a replacement for it. Output is written to
`experiments/run_summaries/`; generated summaries are not committed. Restart
the publisher with the normal Compose `start publisher` command if required.

## Deployment timing

The deployment timer measures wall-clock time from Compose startup until the
first telemetry point is queryable in InfluxDB. Runtime images are prepared
before timing begins. It performs three clean trials by default and reports the
median:

```powershell
python experiments/deployment_timer.py --configuration c1
```

Each trial uses a dedicated Compose project named
`digital-twin-timing-<configuration>`. Its volumes are removed before and after
every measurement so later trials do not inherit an initialised database. This
cleanup does not target the volumes of the normal `digital-twin` project.
Generated timing files are written under `experiments/deployment_timings/` and
are not committed.

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
