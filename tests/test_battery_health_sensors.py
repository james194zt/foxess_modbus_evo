"""Tests for derived BMS health metric calculations."""

from custom_components.foxess_modbus.entities.modbus_battery_health_sensors import (
    battery_ah_remaining_from_soc_nominal,
    ohmic_resistance_milliohm,
    remaining_power_capacity_kw,
    round_trip_efficiency_remaining_percent,
    self_discharge_rate_percent_per_day,
)


def test_remaining_capacity_from_nominal_ah() -> None:
    assert battery_ah_remaining_from_soc_nominal([100.0, 50.0]) == 50.0
    assert battery_ah_remaining_from_soc_nominal([80.0, 50.0]) == 40.0


def test_remaining_power_capacity_kw() -> None:
    # 50 A limit, 220 V, 100% SOH -> 11 kW
    assert remaining_power_capacity_kw([50.0, 220.0, 100.0]) == 11.0


def test_round_trip_efficiency_from_totals() -> None:
    # 128.1 / 144 ≈ 89%
    assert round_trip_efficiency_remaining_percent([128.1, 144.0, 100.0]) == 89.0


def test_ohmic_resistance_under_load() -> None:
    assert ohmic_resistance_milliohm([3448.0, 3436.0, 2.0, 100.0]) == 6.0


def test_self_discharge_new_pack() -> None:
    assert self_discharge_rate_percent_per_day([100.0, 13.0]) == 0.041
