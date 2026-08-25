"""
shared MQTT connection factory

publisher and storage_writer use the same connection and reconnect
logic, so M3.3 recovery time measures broker behaviour rather than a difference
between two hand-rolled clients

Branches on auth_mode: password for C1/C2a, mutual TLS with X.509 certificates
for C2b. Written against paho-mqtt 2.x callback signatures.
"""

import ssl
import threading

import paho.mqtt.client as mqtt

from twin.config import BrokerConfig
from twin.logging_setup import setup_logging

# Reconnect backoff bounds, seconds. paho doubles the delay on each failed
# attempt between these values.
RECONNECT_MIN_DELAY = 1
RECONNECT_MAX_DELAY = 32

class MQTTClientError(Exception):
    """Raised when a client cannot be constructed or the initial connect fails."""


def build_client(config: BrokerConfig, client_id: str, component: str) -> mqtt.Client:
    """
    construct a configured, not-yet-connected clien

    client_id must be unique per connection. AWS IoT Core disconnects an
    existing session when a second client presents the same ID, so the
    publisher and storage_writer must not share one
    """
    logger = setup_logging(component)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv311,
        clean_session=False if config.qos > 0 else True,
    )

    if config.auth_mode == "password":
        client.username_pw_set(config.username, config.password)
        if config.tls:
            client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
    else:
        client.tls_set(
            ca_certs=config.ca_cert,
            certfile=config.client_cert,
            keyfile=config.client_key,
            tls_version=ssl.PROTOCOL_TLSv1_2,
        )

    client.reconnect_delay_set(
        min_delay=RECONNECT_MIN_DELAY,
        max_delay=RECONNECT_MAX_DELAY,
    )

    _attach_logging_callbacks(client, logger, component)

    return client

def _attach_logging_callbacks(client: mqtt.Client, logger, component: str) -> None:
    """
    connection lifecycle events are logged with structured fields so
    fault-injection trials can extract detection and recovery times by
    parsing the log rather than by manual observation.
    """

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info(
                "broker connected",
                extra={"event": "connected", "component": component},
            )
        else:
            logger.error(
                "broker connection refused",
                extra={
                    "event": "connect_refused",
                    "reason_code": int(reason_code),
                    "component": component,
                },
            )
    def on_disconnect(client, userdata, flags, reason_code, properties):
    # reason_code 0 means a deliberate disconnect; anything else is a
    # broker or network failure, which is what fault injection produces.
        expected = int(reason_code) == 0
        logger.warning(
            "broker disconnected",
            extra={
                "event": "disconnected",
                "expected": expected,
                "reason_code": int(reason_code),
                "component": component,
            },
        )
def connect(client: mqtt.Client, config: BrokerConfig, timeout: float = 10.0) -> None:
    """
    connect and start the network loop in a background thread.

    this blocks until the broker confirms the connection or timeout elapses, so a
    misconfigured broker fails at startup rather than silently never publishing or pblish
    wrong values
    """
    connected = threading.Event()
    original_on_connect = client.on_connect

    def on_connect_wrapper(client, userdata, flags, reason_code, properties):
        original_on_connect(client, userdata, flags, reason_code, properties)
        if reason_code == 0:
            connected.set()

    client.on_connect = on_connect_wrapper

    try:
        client.connect(config.host, config.port, keepalive=config.keepalive)
    except (OSError, ssl.SSLError) as exc:
        raise MQTTClientError(
            f"could not connect to {config.host}:{config.port}: {exc}"
        ) from exc

    client.loop_start()

    if not connected.wait(timeout=timeout):
        client.loop_stop()
        raise MQTTClientError(
            f"no CONNACK from {config.host}:{config.port} within {timeout}s"
        )

    client.on_connect = original_on_connect