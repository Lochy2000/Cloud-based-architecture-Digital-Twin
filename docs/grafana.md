# Grafana dashboard

Grafana is a read-only visualisation layer in this project. It does not produce
or store telemetry.

The InfluxDB data source is provisioned from
`deploy/grafana/provisioning/datasources/influxdb.yml`. The dashboard provider is
under `deploy/grafana/provisioning/dashboards`, and dashboard definitions are
mounted from `deploy/grafana/dashboards`.

`telemetry.json` displays:

- supply and return temperature;
- power draw;
- messages stored per minute;
- latest publisher sequence number.

Queries read the InfluxDB bucket and measurement named `telemetry`. If either
name or the telemetry schema changes, update the dashboard JSON with the source
code and tests.

Provisioned dashboards are configuration as code. Browser edits do not survive
redeployment because `allowUiUpdates` is disabled. Edit the JSON file, validate
it, and allow the provider refresh interval to apply the change; restart Grafana
when diagnosing provisioning changes.

Refer to the official [Grafana provisioning documentation](https://grafana.com/docs/grafana/latest/administration/provisioning/)
and [InfluxDB query documentation](https://docs.influxdata.com/influxdb/v2/query-data/flux/).
