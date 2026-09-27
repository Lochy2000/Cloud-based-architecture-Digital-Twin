"""Shared MQTT setup for the publisher and storage writer."""

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
    """Build a configured client without connecting it yet."""
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
            client.tls_set(ca_certs=config.ca_cert, tls_version=ssl.PROTOCOL_TLSv1_2)
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
    """Log connection changes used by the fault-injection runs."""

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
                    "reason_code": reason_code.value,
                    "component": component,
                },
            )
    def on_disconnect(client, userdata, flags, reason_code, properties):
        # Zero is our clean shutdown; anything else may be the injected fault.
        expected = reason_code.value == 0
        logger.warning(
            "broker disconnected",
            extra={
                "event": "disconnected",
                "expected": expected,
                "reason_code": reason_code.value,
                "component": component,
            },
        )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

def connect(client: mqtt.Client, config: BrokerConfig, timeout: float = 10.0) -> None:
    """Connect, wait for CONNACK, then leave Paho's network loop running."""
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

def disconnect(client: mqtt.Client) -> None:
    """Send DISCONNECT before stopping the network loop."""
    client.disconnect()
    client.loop_stop()
