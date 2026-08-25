"""
thermal simulator for a single boiler asset, just function

using a given timestamp and ambient, compute supply/return temps using Newton's law
of cooling and a deterministic duty cycle
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