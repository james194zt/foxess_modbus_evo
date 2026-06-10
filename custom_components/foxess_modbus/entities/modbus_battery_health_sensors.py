"""Fox-style battery health metrics derived from Modbus inputs (estimates until BMS registers are mapped)."""

from __future__ import annotations


def battery_ah_remaining_from_soc_nominal(values: list[float]) -> float | None:
    """Remaining capacity (Ah) using Fox app nominal bucket (register 37616), not live FCC."""
    if len(values) != 2:
        return None
    soc, nominal_ah = values
    if nominal_ah <= 0:
        return None
    return round(soc / 100.0 * nominal_ah, 1)


def remaining_power_capacity_kw(values: list[float]) -> float | None:
    """Max discharge power at present SOH: I_max × V_pack / 1000."""
    if len(values) != 3:
        return None
    max_discharge_a, pack_voltage_v, soh = values
    if max_discharge_a <= 0 or pack_voltage_v <= 0:
        return None
    return round(max_discharge_a * pack_voltage_v / 1000.0 * (soh / 100.0), 2)


def round_trip_efficiency_remaining_percent(values: list[float]) -> float | None:
    """Lifetime energy round-trip ratio, capped for display as 'remaining' efficiency."""
    if len(values) != 3:
        return None
    discharge_kwh, charge_kwh, soh = values
    if charge_kwh <= 0:
        return None
    measured = discharge_kwh / charge_kwh * 100.0
    measured = min(99.0, max(50.0, measured))
    soh_ceiling = 85.0 + (soh / 100.0) * 15.0
    return round(min(measured, soh_ceiling), 1)


def ohmic_resistance_milliohm(values: list[float]) -> float | None:
    """Pack resistance estimate: dynamic under load, SOH-based baseline at rest."""
    if len(values) != 4:
        return None
    mv_high, mv_low, pack_current_a, soh = values
    delta_mv = abs(mv_high - mv_low)
    abs_i = abs(pack_current_a)
    if abs_i >= 2.0:
        return round(delta_mv / abs_i, 1)
    baseline = 35.0 + (100.0 - soh) * 1.5
    return round(baseline + delta_mv * 0.5, 1)


def self_discharge_rate_percent_per_day(values: list[float]) -> float | None:
    """Estimated idle self-discharge trend; low on new packs, rises with wear and cycles."""
    if len(values) != 2:
        return None
    soh, cycles = values
    base = 0.015
    wear = max(0.0, 100.0 - soh) * 0.005 + max(0.0, cycles) * 0.002
    return round(base + wear, 3)


def harmful_event_count_zero(_values: list[float]) -> float:
    """Placeholder until harmful-event counters are mapped on Modbus."""
    return 0.0
