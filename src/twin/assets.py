"""
loads per-asset YAML configuration.

separate from config.py because asset parameters describe the simulated
physical system, not the deployment environment. config.py supplies the path;
this validates the contents.
"""

import yaml

class AssetError(Exception):
    """Raised when an asset configuration file is missing or malformed."""

REQUIRED_STRUCTURE = {
    "steady_state": ("supply_temperature", "return_temperature", "ambient_baseline"),
    "dynamics": ("heating_time_constant_seconds", "cooling_time_constant_seconds"),
    "duty_cycle": (
        "operating_hours_start",
        "operating_hours_end",
        "cycle_period_seconds",
        "on_fraction",
    ),
}
