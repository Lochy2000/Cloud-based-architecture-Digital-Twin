"""A deterministic boiler simulator using Newton-style heating and cooling."""

from datetime import datetime
import math


def simulate(asset_config: dict, timestamp: datetime, ambient_temperature: float) -> dict:
    """Compute sensor readings at a given timestamp."""
    
    if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must be UTC")
    
    supply_setpoint = asset_config["steady_state"]["supply_temperature"]
    return_delta = (asset_config["steady_state"]["supply_temperature"] - 
                    asset_config["steady_state"]["return_temperature"])
    ambient_baseline = asset_config["steady_state"]["ambient_baseline"]
    tau_heat = asset_config["dynamics"]["heating_time_constant_seconds"]
    tau_cool = asset_config["dynamics"]["cooling_time_constant_seconds"]
    
    op_start = asset_config["duty_cycle"]["operating_hours_start"]
    op_end = asset_config["duty_cycle"]["operating_hours_end"]
    cycle_period = asset_config["duty_cycle"]["cycle_period_seconds"]
    on_fraction = asset_config["duty_cycle"]["on_fraction"]

    # The boiler sits at its baseline outside the operating window.
    hour_of_day = timestamp.hour
    if not (op_start <= hour_of_day < op_end):
        return {
            "supply_temperature_c": ambient_baseline,
            "return_temperature_c": ambient_baseline,
            "ambient_temperature_c": ambient_temperature,
            "power_draw_kw": 0.0,
            "setpoint_c": supply_setpoint,
        }
    
    # Seconds since today's operating window opened.
    seconds_into_window = (timestamp.hour - op_start) * 3600 + timestamp.minute * 60 + timestamp.second
    
    cycle_position = seconds_into_window % cycle_period
    completed_cycles = int(seconds_into_window // cycle_period)

    on_duration = cycle_period * on_fraction
    off_duration = cycle_period - on_duration

    # Cold start at the beginning of each operating day.
    cycle_start_temp = ambient_baseline

    # Carry residual heat through the completed cycles.
    for _ in range(completed_cycles):
        end_of_heating = supply_setpoint + (
            cycle_start_temp - supply_setpoint
        ) * math.exp(-on_duration / tau_heat)

        cycle_start_temp = ambient_baseline + (
            end_of_heating - ambient_baseline
        ) * math.exp(-off_duration / tau_cool)

    boiler_on = cycle_position < on_duration

    if boiler_on:
        time_in_state = cycle_position
        supply_temp = supply_setpoint + (
            cycle_start_temp - supply_setpoint
        ) * math.exp(-time_in_state / tau_heat)
    else:
        time_in_state = cycle_position - on_duration

        end_of_heating = supply_setpoint + (
            cycle_start_temp - supply_setpoint
        ) * math.exp(-on_duration / tau_heat)

        supply_temp = ambient_baseline + (
            end_of_heating - ambient_baseline
        ) * math.exp(-time_in_state / tau_cool)

    return_temp = supply_temp - return_delta
    power_draw = 5.0 if boiler_on else 0.0
    
    return {
        "supply_temperature_c": round(supply_temp, 2),
        "return_temperature_c": round(return_temp, 2),
        "ambient_temperature_c": ambient_temperature,
        "power_draw_kw": power_draw,
        "setpoint_c": supply_setpoint,
    }
