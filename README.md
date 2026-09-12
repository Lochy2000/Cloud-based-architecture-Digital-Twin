# Cloud-Native Digital Twin — SME Thermal Asset Monitoring

MSc dissertation prototype for comparing MQTT broker deployment configurations
in a thermal-asset digital twin. The system simulates an asset, publishes a
validated telemetry payload over MQTT, stores it in InfluxDB, and visualises it
with Grafana.

The project compares three broker configurations while keeping the remaining
pipeline consistent: C1 is self-hosted Mosquitto, C2a is a managed broker using
password authentication, and C2b is a managed broker using mutual TLS.

### Documentation

- [Architecture](architecture.md): components, data flow, telemetry, and recovery.
- [Configuration](configuration.md): assets, environment variables, and variants.
- [Development](development.md): repository structure, tests, and change guidance.
- [Operations](operations.md): deployment, TLS, observability, and troubleshooting.
- [TLS setup](tls-setup.md): concise C1 certificate and credential requirements.
- [Grafana](grafana.md): dashboard provisioning and query maintenance.
- [Tools and references](tools.md): dependencies and official documentation.
- [Ubuntu experiment runbook](docs/run.md): C1, C2a, C2b, and measurement commands.




For Ubuntu deployment and experiment execution, follow [docs/run.md](docs/run.md).
