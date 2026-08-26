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

def load_asset(path: str) -> dict:
    """Read and validate an asset YAML file. Fails loudly on anything missing."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        raise AssetError(f"could not read asset config {path!r}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise AssetError(f"asset config {path!r} is not valid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise AssetError(f"asset config {path!r} must be a YAML mapping")

    if not data.get("asset_id"):
        raise AssetError(f"asset config {path!r} missing required field: asset_id")

    for section, fields in REQUIRED_STRUCTURE.items():
        if section not in data:
            raise AssetError(f"asset config {path!r} missing required section: {section}")
        if not isinstance(data[section], dict):
            raise AssetError(f"asset config {path!r}: {section} must be a mapping")
        for field in fields:
            if field not in data[section]:
                raise AssetError(
                    f"asset config {path!r} missing required field: {section}.{field}"
                )

    duty = data["duty_cycle"]
    if not 0 < duty["on_fraction"] <= 1:
        raise AssetError(
            f"asset config {path!r}: duty_cycle.on_fraction must be between 0 and 1, "
            f"got {duty['on_fraction']}"
        )
    if not 0 <= duty["operating_hours_start"] < duty["operating_hours_end"] <= 24:
        raise AssetError(
            f"asset config {path!r}: operating hours must satisfy "
            f"0 <= start < end <= 24, got {duty['operating_hours_start']} to "
            f"{duty['operating_hours_end']}"
        )

    return data