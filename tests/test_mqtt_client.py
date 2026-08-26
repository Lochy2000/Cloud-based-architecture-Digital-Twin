"""
Tests for src/twin/mqtt_client.py.

These verify the client is constructed correctly — credentials, certificates,
QoS-derived session persistence, reconnect bounds, callbacks — without a live
broker. Connecting to Mosquitto, HiveMQ Cloud and AWS IoT Core is Stage 4's
integration acceptance and cannot be covered here.
"""

from unittest.mock import patch
import ssl

import paho.mqtt.client as mqtt
import pytest

from twin.config import BrokerConfig
from twin.mqtt_client import (
    RECONNECT_MAX_DELAY, RECONNECT_MIN_DELAY,
    MQTTClientError, build_client, connect, disconnect,
)


def _password_config(qos=1, tls=True):
    return BrokerConfig(
        host="broker.example.com", port=8883, tls=tls, auth_mode="password",
        username="twin-publisher", password="secret",
        ca_cert=None, client_cert=None, client_key=None,
        keepalive=60, qos=qos,
    )


def _cert_config(qos=1):
    return BrokerConfig(
        host="xxx.iot.eu-west-2.amazonaws.com", port=8883, tls=True, auth_mode="cert",
        username=None, password=None,
        ca_cert="/certs/ca.pem", client_cert="/certs/client.pem", client_key="/certs/client.key",
        keepalive=60, qos=qos,
    )


class TestBuildClient:

    def test_client_id_is_applied(self):
        with patch.object(mqtt.Client, "tls_set"):
            client = build_client(_password_config(), "twin-publisher-01", "test.build")
        assert client._client_id == b"twin-publisher-01"

    def test_password_auth_sets_credentials(self):
        with patch.object(mqtt.Client, "tls_set"):
            client = build_client(_password_config(), "id-1", "test.pwd")
        assert client._username == b"twin-publisher"
        assert client._password == b"secret"

    def test_password_auth_enables_tls_when_configured(self):
        with patch.object(mqtt.Client, "tls_set") as tls_set:
            build_client(_password_config(tls=True), "id-2", "test.tls_on")
        tls_set.assert_called_once()

    def test_password_auth_skips_tls_when_disabled(self):
        with patch.object(mqtt.Client, "tls_set") as tls_set:
            build_client(_password_config(tls=False), "id-3", "test.tls_off")
        tls_set.assert_not_called()

    def test_cert_auth_passes_all_three_certificate_paths(self):
        with patch.object(mqtt.Client, "tls_set") as tls_set:
            build_client(_cert_config(), "id-4", "test.cert")
        kwargs = tls_set.call_args.kwargs
        assert kwargs["ca_certs"] == "/certs/ca.pem"
        assert kwargs["certfile"] == "/certs/client.pem"
        assert kwargs["keyfile"] == "/certs/client.key"
        assert kwargs["tls_version"] == ssl.PROTOCOL_TLSv1_2

    def test_cert_auth_does_not_set_username(self):
        with patch.object(mqtt.Client, "tls_set"):
            client = build_client(_cert_config(), "id-5", "test.cert_nouser")
        assert client._username is None

    def test_reconnect_backoff_bounds_applied(self):
        with patch.object(mqtt.Client, "tls_set"):
            client = build_client(_password_config(), "id-6", "test.backoff")
        assert client._reconnect_min_delay == RECONNECT_MIN_DELAY
        assert client._reconnect_max_delay == RECONNECT_MAX_DELAY

    def test_lifecycle_callbacks_are_attached(self):
        with patch.object(mqtt.Client, "tls_set"):
            client = build_client(_password_config(), "id-7", "test.callbacks")
        assert client.on_connect is not None
        assert client.on_disconnect is not None


class TestCleanSessionFollowsQoS:
    """
    clean_session is derived from QoS, not set independently: QoS 1 needs a
    persistent session for the broker to redeliver missed messages, which is
    the behaviour M3.3 recovery time measures.
    """

    def test_qos_1_uses_persistent_session(self):
        with patch.object(mqtt.Client, "tls_set"):
            client = build_client(_password_config(qos=1), "id-8", "test.qos1")
        assert client._clean_session is False

    def test_qos_0_uses_clean_session(self):
        with patch.object(mqtt.Client, "tls_set"):
            client = build_client(_password_config(qos=0), "id-9", "test.qos0")
        assert client._clean_session is True


class TestConnect:

    def test_unreachable_broker_raises_named_error(self):
        config = _password_config()
        with patch.object(mqtt.Client, "tls_set"):
            client = build_client(config, "id-10", "test.unreachable")

        with patch.object(mqtt.Client, "connect", side_effect=OSError("nodename nor servname provided")):
            with pytest.raises(MQTTClientError, match="broker.example.com:8883"):
                connect(client, config)

    def test_no_connack_within_timeout_raises(self):
        config = _password_config()
        with patch.object(mqtt.Client, "tls_set"):
            client = build_client(config, "id-11", "test.timeout")

        # connect() and loop_start() succeed, but no CONNACK callback ever fires
        with patch.object(mqtt.Client, "connect"), patch.object(mqtt.Client, "loop_start"), \
            patch.object(mqtt.Client, "loop_stop"):
            with pytest.raises(MQTTClientError, match="no CONNACK"):
                connect(client, config, timeout=0.1)

    def test_successful_connack_returns_and_restores_callback(self):
        config = _password_config()
        with patch.object(mqtt.Client, "tls_set"):
            client = build_client(config, "id-12", "test.connack")

        original_on_connect = client.on_connect

        def fire_connack(*args, **kwargs):
            # Simulate the broker accepting the connection
            client.on_connect(client, None, {}, 0, None)

        with patch.object(mqtt.Client, "connect"), \
            patch.object(mqtt.Client, "loop_start", side_effect=fire_connack), \
            patch.object(mqtt.Client, "loop_stop"):
            connect(client, config, timeout=1.0)

        assert client.on_connect is original_on_connect


class TestDisconnect:

    def test_disconnect_stops_network_loop(self):
        with patch.object(mqtt.Client, "tls_set"):
            client = build_client(_password_config(), "id-13", "test.disconnect")

        with patch.object(mqtt.Client, "disconnect") as disc, patch.object(mqtt.Client, "loop_stop") as stop:
            disconnect(client)

        disc.assert_called_once()
        stop.assert_called_once()