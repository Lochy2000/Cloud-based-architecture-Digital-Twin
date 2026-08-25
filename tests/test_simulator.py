"""
Tests for src/twin/simulator.py.

Evidence for Stage 3 acceptance: simulator is a pure function of timestamp
and ambient temp, produces correct supply/return readings via Newton's law,
boiler on/off state is deterministic from duty cycle, no stored state.
"""

from datetime import datetime, timezone, timedelta
import math
import pytest

from twin.simulator import simulate


@pytest.fixture
def boiler_config():
    return {
        "steady_state": {
            "supply_temperature": 65.0,
            "return_temperature": 55.0,
            "ambient_baseline": 20.0,
        },
        "dynamics": {
            "heating_time_constant_seconds": 25,
            "cooling_time_constant_seconds": 600,
        },
        "duty_cycle": {
            "operating_hours_start": 6,
            "operating_hours_end": 22,
            "cycle_period_seconds": 1200,
            "on_fraction": 0.5,
        },
    }


def _timestamp(hour, minute=0, second=0):
    return datetime(2026, 8, 20, hour, minute, second, tzinfo=timezone.utc)


class TestOutsideOperatingHours:

    def test_returns_ambient_before_start(self, boiler_config):
        ts = _timestamp(5, 30)
        result = simulate(boiler_config, ts, 15.0)

        assert result["supply_temperature_c"] == 20.0
        assert result["return_temperature_c"] == 20.0
        assert result["power_draw_kw"] == 0.0
        assert result["ambient_temperature_c"] == 15.0

    def test_returns_ambient_after_end(self, boiler_config):
        ts = _timestamp(23, 0)
        result = simulate(boiler_config, ts, 12.0)

        assert result["supply_temperature_c"] == 20.0
        assert result["power_draw_kw"] == 0.0


class TestBoilerOnOff:

    def test_boiler_on_in_first_half_of_cycle(self, boiler_config):
        # 6am + 5 minutes into the day = first on period (cycle is 20 min, 50% on)
        ts = _timestamp(6, 5)
        result = simulate(boiler_config, ts, 15.0)

        assert result["power_draw_kw"] == 5.0

    def test_boiler_off_in_second_half_of_cycle(self, boiler_config):
        # 6am + 15 minutes = in the off period
        ts = _timestamp(6, 15)
        result = simulate(boiler_config, ts, 15.0)

        assert result["power_draw_kw"] == 0.0

    def test_boiler_cycles_predictably(self, boiler_config):
        # Times safely within each on/off state, not at boundaries
        times_and_expected_power = [
            (_timestamp(6, 5), 5.0),   # 300s: in on period
            (_timestamp(6, 12), 0.0),  # 600s + 120s: in off period
            (_timestamp(6, 25), 5.0),  # 1500s % 1200 = 300s: cycle repeats, on
            (_timestamp(6, 35), 0.0),  # 1500s + 600s: in off period
        ]


        for ts, expected_power in times_and_expected_power:
            result = simulate(boiler_config, ts, 15.0)
            assert result["power_draw_kw"] == expected_power


class TestNewtonsCooling:

    def test_supply_temp_on_is_higher_than_baseline(self, boiler_config):
        # Boiler on should have supply temp rising toward setpoint (65°C)
        ts = _timestamp(6, 5)  # In on period
        result = simulate(boiler_config, ts, 15.0)

        assert result["supply_temperature_c"] > 20.0
        assert result["supply_temperature_c"] <= 65.0

    def test_supply_temp_off_approaches_ambient(self, boiler_config):
        # Boiler off should have supply temp at or near ambient baseline
        ts = _timestamp(6, 15)  # In off period
        result = simulate(boiler_config, ts, 15.0)

        assert result["supply_temperature_c"] <= 20.0

    def test_return_temperature_delta_preserved(self, boiler_config):
        # Return should always be supply - 10°C
        ts = _timestamp(6, 5)
        result = simulate(boiler_config, ts, 15.0)

        delta = result["supply_temperature_c"] - result["return_temperature_c"]
        assert abs(delta - 10.0) < 0.1

    def test_exponential_approach_heating(self, boiler_config):
        # At t = one time constant, temp should reach ~63% of the way to target
        # tau_heat = 25s, so at 25s into an on period:
        # T = 65 + (20 - 65) * exp(-25/25) = 65 - 45*exp(-1) = 65 - 16.55 ≈ 48.5
        ts = _timestamp(6, 0, 25)  # 25 seconds into on period at 6:00am
        result = simulate(boiler_config, ts, 15.0)

        expected = 65.0 + (20.0 - 65.0) * math.exp(-1.0)
        assert abs(result["supply_temperature_c"] - expected) < 0.5


class TestAmbientsAndSetpoint:

    def test_setpoint_always_reported(self, boiler_config):
        ts = _timestamp(6, 0)
        result = simulate(boiler_config, ts, 15.0)

        assert result["setpoint_c"] == 65.0

    def test_ambient_temperature_passed_through(self, boiler_config):
        ts = _timestamp(6, 0)
        result = simulate(boiler_config, ts, 12.5)

        assert result["ambient_temperature_c"] == 12.5


class TestTimezoneValidation:

    def test_rejects_naive_timestamp(self, boiler_config):
        ts = datetime(2026, 8, 20, 6, 0, 0)  # No tzinfo
        with pytest.raises(ValueError, match="UTC"):
            simulate(boiler_config, ts, 15.0)

    def test_rejects_non_utc_timezone(self, boiler_config):
        from datetime import timedelta
        bst = timezone(timedelta(hours=1))
        ts = datetime(2026, 8, 20, 6, 0, 0, tzinfo=bst)

        with pytest.raises(ValueError, match="UTC"):
            simulate(boiler_config, ts, 15.0)