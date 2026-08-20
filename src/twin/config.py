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