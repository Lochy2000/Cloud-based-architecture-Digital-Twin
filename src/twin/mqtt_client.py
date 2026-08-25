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