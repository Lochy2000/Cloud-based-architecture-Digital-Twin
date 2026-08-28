"""
for src/twin/asset.py.

asset YAML is the only file the pipeline reads at runtime, so a malformed
or incomplete one must fail at startup with a named field rather than
producing wrong readings silently.
"""

import pytest

from twin.asset import AssetError, load_asset

VALID_YAML = """
asset_id: boiler_01
asset_type: thermal_system

steady_state:
  supply_temperature: 65.0
  return_temperature: 55.0
  ambient_baseline: 20.0

dynamics:
  heating_time_constant_seconds: 25
  cooling_time_constant_seconds: 600

duty_cycle:
  operating_hours_start: 6
  operating_hours_end: 22
  cycle_period_seconds: 1200
  on_fraction: 0.5
"""


def _write(tmp_path, text, name="boiler_01.yaml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)