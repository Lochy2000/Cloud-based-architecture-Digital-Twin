# Ubuntu experiment runbook

This runbook operates C1, C2a, and C2b separately on one Ubuntu server. Run
commands from the repository root unless a section explicitly changes to
`deploy`.

Only one configuration may run at a time because all configurations publish
InfluxDB and Grafana on host ports 8086 and 3000. Each configuration uses a
separate Compose project name so its volumes are not mixed with another
configuration's data.

## Server preparation

Install Git, Python, OpenSSL, and `jq`. Install Docker Engine with the Compose
plugin using Docker's official Ubuntu instructions.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip openssl jq
docker --version
docker compose version
```

Clone the repository and install the dependencies used by the experiment
scripts and tests:

```bash
cd ~
git clone https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin.git
cd Cloud-based-architecture-Digital-Twin
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If Docker requires `sudo`, add the server user to the Docker group according to
the Docker post-installation instructions, then reconnect the SSH session.

## Configuration files

Create one ignored runtime file for each configuration being tested:

```bash
cp config/env/c1.env.example config/env/c1.env
cp config/env/c2a.env.example config/env/c2a.env
cp config/env/c2b.env.example config/env/c2b.env
chmod 600 config/env/c1.env config/env/c2a.env config/env/c2b.env
```

Edit the files and replace every blank or placeholder credential. Generate
independent values for the InfluxDB token, InfluxDB administrator password, and
Grafana administrator password. Do not commit these files.

```bash
openssl rand -hex 32
nano config/env/c1.env
nano config/env/c2a.env
nano config/env/c2b.env
```

Run `openssl rand -hex 32` separately for each generated secret. Broker
passwords and managed-provider credentials must remain distinct from these
local service credentials.

C1 requires `deploy/mosquitto/certs/ca.crt`, `server.crt`, `server.key`, and a
non-empty `deploy/mosquitto/passwd`. Follow [tls-setup.md](tls-setup.md). Create
the password file from `deploy/mosquitto` and use the same password for
`BROKER_PASSWORD` in `c1.env`:

```bash
cd deploy/mosquitto
docker run --rm -it -v "$PWD:/work" eclipse-mosquitto:2.1.2-alpine \
  mosquitto_passwd -c /work/passwd twin
test -s passwd
openssl verify -CAfile certs/ca.crt certs/server.crt
cd ../..
```

Do not commit the generated password database, certificates, or private keys.

C2a requires the HiveMQ Cloud hostname, username, and password in `c2a.env`.
The broker credentials must be permitted to publish and subscribe on
`twin/boiler_01/telemetry`.

C2b requires the AWS IoT endpoint in `c2b.env`, an IoT policy that permits the
publisher and subscriber operations on the same topic, and these files under
`deploy/mosquitto/certs`, matching the configured container paths:

```text
AmazonRootCA1.pem
device-certificate.pem.crt
device-private.pem.key
```

Allow the non-root runtime group (GID 10001) to read the private key without
making it world-readable:

```bash
sudo chgrp 10001 deploy/mosquitto/certs/device-private.pem.key
chmod 640 deploy/mosquitto/certs/device-private.pem.key
chmod 644 deploy/mosquitto/certs/AmazonRootCA1.pem
chmod 644 deploy/mosquitto/certs/device-certificate.pem.crt
```

## Tests

Run the suite before starting an experiment:

```bash
source .venv/bin/activate
python -m pytest -q
```

At the time this runbook was updated, the expected result was:

```text
137 passed, 1 skipped
```

The skipped test is the opt-in InfluxDB integration test. Unit-test counts may
increase as the project changes; failures are not expected.

## Select one configuration

Run exactly one of the following blocks in every new shell or SSH session.
The exported `ENV_FILE` is also used by Compose to inject the correct runtime
file into publisher and storage-writer containers.

### C1: self-hosted Mosquitto

```bash
cd ~/Cloud-based-architecture-Digital-Twin/deploy
export CONFIGURATION=c1
export ENV_FILE=../config/env/c1.env
export COMPOSE_ENV_FILE="$ENV_FILE"
export COMPOSE_PROJECT_NAME=digital-twin-c1
COMPOSE_ARGS=(--env-file "$ENV_FILE" --profile c1)
docker compose "${COMPOSE_ARGS[@]}" config --quiet
```

C1 starts Mosquitto, InfluxDB, Grafana, publisher, and storage-writer.

### C2a: HiveMQ Cloud

```bash
cd ~/Cloud-based-architecture-Digital-Twin/deploy
export CONFIGURATION=c2a
export ENV_FILE=../config/env/c2a.env
export COMPOSE_ENV_FILE="$ENV_FILE"
export COMPOSE_PROJECT_NAME=digital-twin-c2a
COMPOSE_ARGS=(--env-file "$ENV_FILE")
docker compose "${COMPOSE_ARGS[@]}" config --quiet
```

C2a starts InfluxDB, Grafana, publisher, and storage-writer. It does not start
the C1 Mosquitto profile; both Python roles connect to HiveMQ Cloud.

### C2b: AWS IoT Core

```bash
cd ~/Cloud-based-architecture-Digital-Twin/deploy
export CONFIGURATION=c2b
export ENV_FILE=../config/env/c2b.env
export COMPOSE_ENV_FILE="$ENV_FILE"
export COMPOSE_PROJECT_NAME=digital-twin-c2b
COMPOSE_ARGS=(--env-file "$ENV_FILE")
docker compose "${COMPOSE_ARGS[@]}" config --quiet
```

C2b starts InfluxDB, Grafana, publisher, and storage-writer. It uses the AWS IoT
Core endpoint and mutual-TLS files mounted from `deploy/mosquitto/certs`.

No output from `docker compose config --quiet` means the Compose configuration
is valid.

## Deployment-timing experiment

Run deployment timing before the 24-hour baseline, while the normal stack is
stopped. From `deploy`, run:

```bash
docker compose "${COMPOSE_ARGS[@]}" stop
cd ..
python experiments/deployment_timer.py --configuration "$CONFIGURATION"
cd deploy
```

The harness performs three clean deployments using isolated temporary volumes.
Expected console output has this form:

```text
[c1] deployment trial 1/3
  first datapoint=38.61s
[c1] deployment trial 2/3
  first datapoint=38.187s
[c1] deployment trial 3/3
  first datapoint=38.015s

Median: 38.187s
Written to .../experiments/deployment_timings/c1_<timestamp>.json
```

Those numbers are the observed C1 development-machine result, not an Ubuntu
server target. Server and managed-broker times will differ. The output file is:

```text
experiments/deployment_timings/<configuration>_<UTC timestamp>.json
```

## Start a clean 24-hour baseline

Before deleting volumes, copy any results needed from an earlier run. The next
command deletes only the selected configuration's Compose volumes and is
required to prevent stored data from contaminating the new measurement:

```bash
docker compose "${COMPOSE_ARGS[@]}" down --volumes
docker compose "${COMPOSE_ARGS[@]}" up --detach --build
docker compose "${COMPOSE_ARGS[@]}" ps
docker compose "${COMPOSE_ARGS[@]}" logs --tail 20 publisher storage-writer
```

Expected application events include:

```text
"event": "connected"
"event": "started"
```

All containers should be running, and InfluxDB and C1 Mosquitto should report
`healthy`. C2a and C2b have no local Mosquitto container.

Immediately after startup, capture the publisher's initial network counter:

```bash
python ../experiments/run_summary.py \
  --configuration "$CONFIGURATION" \
  --capture-start
date --utc --iso-8601=seconds
```

Expected output is:

```text
Network start checkpoint written to .../.<configuration>_network_capture.json
```

Leave the detached containers running for 24 uninterrupted hours. Docker
continues running if the SSH session closes. Do not suspend or reboot the
server, restart containers, or run fault injection during this baseline.
Publisher progress is logged every 20 messages, approximately every ten
minutes with the default 30-second interval:

```bash
docker compose "${COMPOSE_ARGS[@]}" logs --follow publisher storage-writer
```

Grafana is available at `http://<server-address>:3000`. Prefer an SSH tunnel or
restricted firewall rule rather than exposing Grafana, InfluxDB, or Mosquitto
to the public internet.

## Finish and summarise the 24-hour baseline

After 24 hours, capture the final network counter immediately before stopping
the publisher:

```bash
python ../experiments/run_summary.py \
  --configuration "$CONFIGURATION" \
  --capture-end

docker compose "${COMPOSE_ARGS[@]}" stop publisher

python ../experiments/run_summary.py \
  --configuration "$CONFIGURATION"
```

Expected output identifies the generated file:

```text
Network end checkpoint written to .../.<configuration>_network_capture.json
Written to .../experiments/run_summaries/<configuration>_<timestamp>.json
```

Inspect the result:

```bash
jq . ../experiments/run_summaries/${CONFIGURATION}_*.json
```

The JSON records:

- run duration and publication interval;
- stored message count and first/last stored timestamps;
- series cardinality and InfluxDB data-directory size;
- accepted, deferred, and overrun counts;
- publisher network transmit counters and their byte difference.

At a 30-second interval, an uninterrupted 24-hour run should contain
approximately 2,880 messages. The precise count may differ by one depending on
the stop boundary. A large difference indicates downtime, server suspension,
or failed delivery and must be investigated before using the run.

## Fault-injection experiment

Run faults only after the clean baseline summary has been generated. Restart
the publisher and allow normal telemetry to resume:

```bash
docker compose "${COMPOSE_ARGS[@]}" start publisher
docker compose "${COMPOSE_ARGS[@]}" logs --tail 10 publisher storage-writer
mkdir -p ../experiments/results
export TRIAL_OUTPUT_PATH="../experiments/results/${CONFIGURATION}_recovery_trials.csv"
```

Run three trials for each broker, network, and storage failure mode:

```bash
python ../experiments/fault_injection.py \
  --configuration "$CONFIGURATION" \
  --mode all \
  --trials 3
```

Default timing is a 150-second outage, 90-second recovery-settle period, and
120-second gap between trials. Nine trials therefore take approximately 52
minutes. Expected progress has this form:

```text
[c1] network trial 1/3
  detection=81.707s recovery=19.743s lost=0
...
Written to ../experiments/results/c1_recovery_trials.csv
```

Actual detection, recovery, and loss values will vary. Blank timing fields or
`no detection event found in logs` require investigation. The CSV contains
configuration, mode, timestamps, detection and recovery times, and reconciled
expected, stored, and lost message counts.

For C1, broker mode stops the local Mosquitto container. For C2a and C2b, a
managed broker cannot be stopped by this server, so broker mode simulates
unreachability by disconnecting the publisher container from its Docker
network. Network mode uses the same Docker-network mechanism for all three
configurations.

## Optional payload-size capture

The payload schema is identical across configurations, so capture it once with
C1 rather than repeating it for C2a and C2b. With C1 running, execute from
`deploy`:

```bash
docker compose "${COMPOSE_ARGS[@]}" run --rm \
  --user "$(id -u):$(id -g)" \
  -e PAYLOAD_SAMPLE_PATH=/output/payload_sample.json \
  -v "$PWD/..:/output" \
  publisher python -m twin.capture_sample
```

Progress is logged every 100 messages. At a 30-second publishing interval,
1,000 messages require approximately 8 hours 20 minutes. Completion writes:

```text
payload_sample.json
```

The JSON contains all captured payloads plus mean, minimum, and maximum byte
sizes.

## Use the published runtime image instead of a local build

The default commands above build the Python runtime from local source. To use
the GHCR package, pull and start the same selected configuration with the
registry override:

```bash
export TWIN_IMAGE=ghcr.io/lochy2000/cloud-based-architecture-digital-twin:v0.1.0
docker compose "${COMPOSE_ARGS[@]}" \
  -f docker-compose.yml \
  -f docker-compose.registry.yml \
  pull
docker compose "${COMPOSE_ARGS[@]}" \
  -f docker-compose.yml \
  -f docker-compose.registry.yml \
  up --detach --no-build
```

For reproducible comparisons, set `TWIN_IMAGE` to the same digest for C1, C2a,
and C2b:

```bash
export TWIN_IMAGE='ghcr.io/lochy2000/cloud-based-architecture-digital-twin@sha256:<digest>'
```

## Stop and preserve data

Stop the selected stack while retaining its volumes:

```bash
docker compose "${COMPOSE_ARGS[@]}" down
```

Use `down --volumes` only when intentionally starting a new clean measurement.
Generated experiment JSON and CSV files are ignored by Git; copy them to the
experiment evidence location before cleaning or replacing the server.


## References

### Project sources

- Repository: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin
- Docker Compose configuration: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/deploy/docker-compose.yml
- Registry Compose override: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/deploy/docker-compose.registry.yml
- Production Dockerfile: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/deploy/Dockerfile
- C1 environment template: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/config/env/c1.env.example
- C2a environment template: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/config/env/c2a.env.example
- C2b environment template: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/config/env/c2b.env.example
- Configuration documentation: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/docs/configuration.md
- Operations documentation: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/docs/operations.md
- TLS setup documentation: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/docs/tls-setup.md
- Architecture documentation: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/docs/architecture.md
- Tools documentation: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/docs/tools.md
- Deployment timer: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/experiments/deployment_timer.py
- Run-summary and egress tool: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/experiments/run_summary.py
- Fault-injection runner: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/experiments/fault_injection.py
- Payload-capture utility: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/src/twin/capture_sample.py
- Publisher runtime: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/src/twin/publisher.py
- Storage-writer runtime: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/src/twin/storage_writer.py
- Shared InfluxDB queries: https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin/blob/main/src/twin/query.py

### Ubuntu and Docker

- Install Docker Engine on Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- Install the Docker Compose plugin: https://docs.docker.com/compose/install/linux/
- Docker Linux post-installation steps: https://docs.docker.com/engine/install/linux-postinstall/
- Docker Compose quick start and named volumes: https://docs.docker.com/compose/gettingstarted/
- Docker Compose profiles: https://docs.docker.com/compose/how-tos/profiles/
- Docker Compose environment variables: https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/
- `docker compose down` and `--volumes`: https://docs.docker.com/reference/cli/docker/compose/down/

### Python

- Python virtual environments: https://docs.python.org/3/library/venv.html

### Mosquitto

- `mosquitto_passwd` manual: https://www.mosquitto.org/man/mosquitto_passwd-1.html
- Mosquitto TLS manual: https://www.mosquitto.org/man/mosquitto-tls-7.html

### Managed brokers

- HiveMQ Cloud authentication and authorization: https://docs.hivemq.com/hivemq-cloud/authn-authz.html
- AWS IoT Core policy actions: https://docs.aws.amazon.com/iot/latest/developerguide/iot-policy-actions.html
- AWS IoT publish/subscribe policy examples: https://docs.aws.amazon.com/iot/latest/developerguide/pub-sub-policy.html

### Container package

- GitHub Container Registry documentation: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
