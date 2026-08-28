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

class TestValidAsset:

    def test_loads_all_sections(self, tmp_path):
        asset = load_asset(_write(tmp_path, VALID_YAML))

        assert asset["asset_id"] == "boiler_01"
        assert asset["steady_state"]["supply_temperature"] == 65.0
        assert asset["dynamics"]["cooling_time_constant_seconds"] == 600
        assert asset["duty_cycle"]["on_fraction"] == 0.5

    def test_output_is_accepted_by_simulator(self, tmp_path):
        # The contract that actually matters: what load_asset returns must be
        # directly usable by simulate() without reshaping.
        from datetime import datetime, timezone
        from twin.simulator import simulate

        asset = load_asset(_write(tmp_path, VALID_YAML))
        readings = simulate(asset, datetime(2026, 8, 20, 6, 5, tzinfo=timezone.utc), 12.0)

        assert readings["power_draw_kw"] == 5.0

class TestMissingFields:

    def test_missing_asset_id(self, tmp_path):
        text = VALID_YAML.replace("asset_id: boiler_01\n", "")
        with pytest.raises(AssetError, match="asset_id"):
            load_asset(_write(tmp_path, text))

    def test_missing_section(self, tmp_path):
        text = VALID_YAML.split("dynamics:")[0]
        with pytest.raises(AssetError, match="dynamics"):
            load_asset(_write(tmp_path, text))

    def test_missing_field_names_section_and_field(self, tmp_path):
        text = VALID_YAML.replace("  cooling_time_constant_seconds: 600\n", "")
        with pytest.raises(AssetError, match=r"dynamics\.cooling_time_constant_seconds"):
            load_asset(_write(tmp_path, text))

    def test_section_that_is_not_a_mapping(self, tmp_path):
        text = VALID_YAML.replace(
            "dynamics:\n  heating_time_constant_seconds: 25\n  cooling_time_constant_seconds: 600\n",
            "dynamics: not-a-mapping\n",
        )
        with pytest.raises(AssetError, match="dynamics"):
            load_asset(_write(tmp_path, text))
