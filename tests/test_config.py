"""
Tests for src/twin/config.py.

Evidence for Stage 1's acceptance test: a missing or invalid required
environment variable must raise ConfigError naming that variable, not a
raw KeyError/ValueError. Serves D-18, D-21.
"""

import pytest

from twin.config import (
    ConfigError,
    load_broker_config,
    load_influx_config,
    load_workload_config,
)

ALL_CONFIG_VARS = [
    "BROKER_HOST", "BROKER_PORT", "BROKER_TLS", "BROKER_AUTH_MODE",
    "BROKER_USERNAME", "BROKER_PASSWORD",
    "BROKER_CA_CERT", "BROKER_CLIENT_CERT", "BROKER_CLIENT_KEY",
    "BROKER_KEEPALIVE", "MQTT_QOS",
    "INFLUX_URL", "INFLUX_TOKEN", "INFLUX_ORG", "INFLUX_BUCKET",
    "ASSET_CONFIG_PATH", "PUBLISH_INTERVAL_SECONDS",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """
    Strip every config-relevant variable before each test, regardless of
    what's set in the shell running pytest. Without this, a variable
    left over from a real .env would make a "missing variable" test
    pass by accident, on this machine only.
    """
    for name in ALL_CONFIG_VARS:
        monkeypatch.delenv(name, raising=False)


# --- load_broker_config ----------------------------------------------

class TestLoadBrokerConfig:

    def test_password_auth_success(self, monkeypatch):
        monkeypatch.setenv("BROKER_HOST", "test-broker.example.com")
        monkeypatch.setenv("BROKER_PORT", "8883")
        monkeypatch.setenv("BROKER_TLS", "true")
        monkeypatch.setenv("BROKER_AUTH_MODE", "password")
        monkeypatch.setenv("BROKER_USERNAME", "twin-publisher")
        monkeypatch.setenv("BROKER_PASSWORD", "secret")
        monkeypatch.setenv("MQTT_QOS", "1") 

        cfg = load_broker_config()

        assert cfg.host == "test-broker.example.com"
        assert cfg.port == 8883
        assert cfg.tls is True
        assert cfg.auth_mode == "password"
        assert cfg.username == "twin-publisher"
        assert cfg.password == "secret"
        assert cfg.ca_cert is None
        assert cfg.keepalive == 60  # default, not set above
        assert cfg.qos == 1    

    def test_cert_auth_success(self, monkeypatch, tmp_path):
        ca = tmp_path / "ca.pem"
        cert = tmp_path / "client.pem"
        key = tmp_path / "client.key"
        for f in (ca, cert, key):
            f.write_text("placeholder")

        monkeypatch.setenv("BROKER_HOST", "xxx.iot.eu-west-2.amazonaws.com")
        monkeypatch.setenv("BROKER_PORT", "8883")
        monkeypatch.setenv("BROKER_TLS", "true")
        monkeypatch.setenv("BROKER_AUTH_MODE", "cert")
        monkeypatch.setenv("BROKER_CA_CERT", str(ca))
        monkeypatch.setenv("BROKER_CLIENT_CERT", str(cert))
        monkeypatch.setenv("BROKER_CLIENT_KEY", str(key))
        monkeypatch.setenv("MQTT_QOS", "1")

        cfg = load_broker_config()

        assert cfg.auth_mode == "cert"
        assert cfg.username is None
        assert cfg.ca_cert == str(ca)

    def test_missing_host_names_the_variable(self, monkeypatch):
        monkeypatch.setenv("BROKER_PORT", "8883")
        monkeypatch.setenv("BROKER_TLS", "true")
        monkeypatch.setenv("BROKER_AUTH_MODE", "password")
        monkeypatch.setenv("BROKER_USERNAME", "x")
        monkeypatch.setenv("BROKER_PASSWORD", "x")

        with pytest.raises(ConfigError, match="BROKER_HOST"):
            load_broker_config()

    def test_non_integer_port_raises_config_error_not_value_error(self, monkeypatch):
        monkeypatch.setenv("BROKER_HOST", "test")
        monkeypatch.setenv("BROKER_PORT", "not-a-number")
        monkeypatch.setenv("BROKER_TLS", "true")
        monkeypatch.setenv("BROKER_AUTH_MODE", "password")
        monkeypatch.setenv("BROKER_USERNAME", "x")
        monkeypatch.setenv("BROKER_PASSWORD", "x")

        with pytest.raises(ConfigError, match="BROKER_PORT"):
            load_broker_config()

    def test_invalid_auth_mode_rejected(self, monkeypatch):
        monkeypatch.setenv("BROKER_HOST", "test")
        monkeypatch.setenv("BROKER_PORT", "8883")
        monkeypatch.setenv("BROKER_TLS", "true")
        monkeypatch.setenv("BROKER_AUTH_MODE", "apikey")  # not a real mode

        with pytest.raises(ConfigError, match="BROKER_AUTH_MODE"):
            load_broker_config()

    def test_cert_path_that_does_not_exist_is_rejected(self, monkeypatch):
        monkeypatch.setenv("BROKER_HOST", "test")
        monkeypatch.setenv("BROKER_PORT", "8883")
        monkeypatch.setenv("BROKER_TLS", "true")
        monkeypatch.setenv("BROKER_AUTH_MODE", "cert")
        monkeypatch.setenv("BROKER_CA_CERT", "/nonexistent/ca.pem")
        monkeypatch.setenv("BROKER_CLIENT_CERT", "/nonexistent/client.pem")
        monkeypatch.setenv("BROKER_CLIENT_KEY", "/nonexistent/client.key")

        with pytest.raises(ConfigError, match="BROKER_CA_CERT"):
            load_broker_config()


# --- load_influx_config ----------------------------------------------

class TestLoadInfluxConfig:

    def test_success(self, monkeypatch):
        monkeypatch.setenv("INFLUX_URL", "http://localhost:8086")
        monkeypatch.setenv("INFLUX_TOKEN", "test-token")
        monkeypatch.setenv("INFLUX_ORG", "digital-twin")
        monkeypatch.setenv("INFLUX_BUCKET", "telemetry")

        cfg = load_influx_config()

        assert cfg.url == "http://localhost:8086"
        assert cfg.bucket == "telemetry"

    def test_missing_token_names_the_variable(self, monkeypatch):
        monkeypatch.setenv("INFLUX_URL", "http://localhost:8086")
        monkeypatch.setenv("INFLUX_ORG", "digital-twin")
        monkeypatch.setenv("INFLUX_BUCKET", "telemetry")

        with pytest.raises(ConfigError, match="INFLUX_TOKEN"):
            load_influx_config()


# --- load_workload_config ---------------------------------------------

class TestLoadWorkloadConfig:

    def test_success(self, monkeypatch, tmp_path):
        asset_file = tmp_path / "boiler_01.yaml"
        asset_file.write_text("asset_id: boiler_01")
        monkeypatch.setenv("ASSET_CONFIG_PATH", str(asset_file))
        monkeypatch.setenv("PUBLISH_INTERVAL_SECONDS", "30")

        cfg = load_workload_config()

        assert cfg.asset_config_path == str(asset_file)
        assert cfg.publish_interval_seconds == 30.0

    def test_missing_asset_file_is_rejected(self, monkeypatch):
        monkeypatch.setenv("ASSET_CONFIG_PATH", "/nonexistent/asset.yaml")
        monkeypatch.setenv("PUBLISH_INTERVAL_SECONDS", "30")

        with pytest.raises(ConfigError, match="ASSET_CONFIG_PATH"):
            load_workload_config()

    def test_zero_interval_is_rejected(self, monkeypatch, tmp_path):
        asset_file = tmp_path / "boiler_01.yaml"
        asset_file.write_text("asset_id: boiler_01")
        monkeypatch.setenv("ASSET_CONFIG_PATH", str(asset_file))
        monkeypatch.setenv("PUBLISH_INTERVAL_SECONDS", "0")

        with pytest.raises(ConfigError, match="PUBLISH_INTERVAL_SECONDS"):
            load_workload_config()

    def test_negative_interval_is_rejected(self, monkeypatch, tmp_path):
        asset_file = tmp_path / "boiler_01.yaml"
        asset_file.write_text("asset_id: boiler_01")
        monkeypatch.setenv("ASSET_CONFIG_PATH", str(asset_file))
        monkeypatch.setenv("PUBLISH_INTERVAL_SECONDS", "-5")

        with pytest.raises(ConfigError, match="PUBLISH_INTERVAL_SECONDS"):
            load_workload_config()