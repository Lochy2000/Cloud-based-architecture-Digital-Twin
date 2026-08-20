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


# def _optional(name: str, default: str) -> str:
#     return os.environ.get(name, default)

