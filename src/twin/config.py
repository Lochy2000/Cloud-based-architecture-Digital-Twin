"""
Environment-driven configuration for the digital twin pipeline.

Serves D-18 (config read from environment only, never hardcoded), D-21
(fail loudly on missing or invalid values), D-26 (secrets sourced from
.env only, never committed).

Split into one loader per consumer rather than a single monolithic config
object: publisher.py only ever calls load_broker_config() and
load_workload_config(); storage_writer.py only calls load_broker_config()
and load_influx_config(). Each loader validates only what it needs, so an
entrypoint fails on a variable it actually uses — not on an unrelated one
it never touches.
"""

import os
from dataclasses import dataclass
from typing import Optional


class ConfigError(Exception):
    """Raised when a required environment variable is missing or invalid."""


# --- internal helpers ----------------------------------------------

def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value

def _require_int(name: str) -> int:
    raw = _require(name)
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"Environment variable {name}={raw!r} is not a valid integer")


def _require_float(name: str) -> float:
    raw = _require(name)
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(f"Environment variable {name}={raw!r} is not a valid number")


def _require_bool(name: str) -> bool:
    raw = _require(name).strip().lower()
    if raw in ("true", "1", "yes"):
        return True
    if raw in ("false", "0", "no"):
        return False
    raise ConfigError(f"Environment variable {name}={raw!r} must be true/false")


def _require_existing_file(name: str) -> str:
    path = _require(name)
    if not os.path.isfile(path):
        raise ConfigError(f"{name}={path!r} does not point to an existing file")
    return path


def _optional(name: str, default: str) -> str:
    return os.environ.get(name, default)

# --- broker config ------------------------------------------------------

@dataclass(frozen=True)
class BrokerConfig:
    host: str
    port: int
    tls: bool
    auth_mode: str          # "password" or "cert"
    username: Optional[str]
    password: Optional[str]
    ca_cert: Optional[str]
    client_cert: Optional[str]
    client_key: Optional[str]
    keepalive: int


def load_broker_config() -> BrokerConfig:
    """
    Shared by every entrypoint that talks to a broker (publisher.py,
    storage_writer.py, and any mqtt client).

    auth_mode branches the required variables, because C1/C2a use
    username+password while C2b (AWS IoT Core) uses mutual TLS with
    X.509 certificates — materially different, not a variant of the same
    thing.
    """
    host = _require("BROKER_HOST")
    port = _require_int("BROKER_PORT")
    tls = _require_bool("BROKER_TLS")
    auth_mode = _require("BROKER_AUTH_MODE").strip().lower()

    if auth_mode not in ("password", "cert"):
        raise ConfigError(
            f"BROKER_AUTH_MODE={auth_mode!r} must be 'password' or 'cert' "
            "('password' for C1/C2a, 'cert' for C2b)"
        )

    username = password = None
    ca_cert = client_cert = client_key = None

    if auth_mode == "password":
        username = _require("BROKER_USERNAME")
        password = _require("BROKER_PASSWORD")
    else:
        ca_cert = _require_existing_file("BROKER_CA_CERT")
        client_cert = _require_existing_file("BROKER_CLIENT_CERT")
        client_key = _require_existing_file("BROKER_CLIENT_KEY")

    keepalive = int(_optional("BROKER_KEEPALIVE", "60"))

    return BrokerConfig(
        host=host, port=port, tls=tls, auth_mode=auth_mode,
        username=username, password=password,
        ca_cert=ca_cert, client_cert=client_cert, client_key=client_key,
        keepalive=keepalive,
    )

# --- InfluxDB config ------------------------------------------------------

@dataclass(frozen=True)
class InfluxConfig:
    url: str
    token: str
    org: str
    bucket: str


def load_influx_config() -> InfluxConfig:
    """Needed only by storage_writer.py and the M1.6 payload-capture utility."""
    return InfluxConfig(
        url=_require("INFLUX_URL"),
        token=_require("INFLUX_TOKEN"),
        org=_require("INFLUX_ORG"),
        bucket=_require("INFLUX_BUCKET"),
    )