"""
thermal simulator for a single boiler asset, just function

using a given timestamp and ambient, compute supply/return temps using Newton's law
of cooling and a deterministic duty cycle

Newton's law of cooling: temperature approaches a target asymptotically.
 T(t) = T_target + (T_0 - T_target) * exp(-t / τ)
 where T_0 = ambient_baseline (initial condition at state transition),
T_target = supply_setpoint if boiler on, else ambient_baseline,
τ = time constant (tau_heat or tau_cool),
t = time_in_state (elapsed seconds in current on/off phase).
Per US Patent 9612030 (Automated Time Constant Determination for Control Devices),
applied to heating system dynamics where τ is heating or cooling time constant.
"""

from datetime import datetime
import math


def simulate(asset_config: dict, timestamp: datetime, ambient_temperature: float) -> dict:
    """Compute sensor readings at a given timestamp."""
    
    if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must be UTC")
    
    # Load parameters
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

    # Outside operating window: at ambient
    hour_of_day = timestamp.hour
    if not (op_start <= hour_of_day < op_end):
        return {
            "supply_temperature_c": ambient_baseline,
            "return_temperature_c": ambient_baseline,
            "ambient_temperature_c": ambient_temperature,
            "power_draw_kw": 0.0,
            "setpoint_c": supply_setpoint,
        }
    
    # Time into operating window (seconds from start hour)
    seconds_into_window = (timestamp.hour - op_start) * 3600 + timestamp.minute * 60 + timestamp.second
    
    # # Current position in duty cycle
    # cycle_position = seconds_into_window % cycle_period
    # on_duration = cycle_period * on_fraction
    # boiler_on = cycle_position < on_duration

    # # Time elapsed in current on/off state
    # time_in_state = cycle_position if boiler_on else (cycle_position - on_duration)
    
    # # Newton's law: approach target temperature exponentially
    # target = supply_setpoint if boiler_on else ambient_baseline
    # tau = tau_heat if boiler_on else tau_cool
    # supply_temp = target + (ambient_baseline - target) * math.exp(-time_in_state / tau)
    
    cycle_position = seconds_into_window % cycle_period
    on_duration = cycle_period * on_fraction
    off_duration = cycle_period - on_duration
    boiler_on = cycle_position < on_duration
    time_in_state = cycle_position if boiler_on else (cycle_position - on_duration)

    # Newton's law of cooling: T(t) = T_target + (T_0 - T_target) * exp(-t / tau)
    # Per US Patent 9612030, applied to heating system dynamics where tau is the
    # heating or cooling time constant.
    #
    # T_0 is the temperature at the last on/off transition. In a repeating cycle
    # these converge to fixed values, solved below so no stored history is needed.
    heat_decay = math.exp(-on_duration / tau_heat)
    cool_decay = math.exp(-off_duration / tau_cool)
    # temp_at_on_end is how hot the boiler gets by the end of a heating phase; temp_at_off_end is how far it has cooled by the end of an off phase. Because the cycle repeats, these settle to fixed values that can be worked out from the parameters directly — no need to remember the previous reading, so the function stays pure.

    # Added different starting points to the phases. Heating starts from temp_at_off_end and climbs toward the setpoint. Cooling starts from temp_at_on_end and falls toward ambient. The old code used ambient as the start for both, which is what made the cooling branch collapse to a constant.
    temp_at_on_end = (
        supply_setpoint * (1 - heat_decay) + heat_decay * ambient_baseline * (1 - cool_decay)
    ) / (1 - heat_decay * cool_decay)
    temp_at_off_end = ambient_baseline + (temp_at_on_end - ambient_baseline) * cool_decay

    if boiler_on:
        supply_temp = supply_setpoint + (temp_at_off_end - supply_setpoint) * math.exp(-time_in_state / tau_heat)
    else:
        supply_temp = ambient_baseline + (temp_at_on_end - ambient_baseline) * math.exp(-time_in_state / tau_cool)

    return_temp = supply_temp - return_delta

    # Clamp and return
    # supply_temp = max(ambient_baseline, min(supply_setpoint + 5, supply_temp))
    return_temp = supply_temp - return_delta
    power_draw = 5.0 if boiler_on else 0.0
    
    return {
        "supply_temperature_c": round(supply_temp, 2),
        "return_temperature_c": round(return_temp, 2),
        "ambient_temperature_c": ambient_temperature,
        "power_draw_kw": power_draw,
        "setpoint_c": supply_setpoint,
    }