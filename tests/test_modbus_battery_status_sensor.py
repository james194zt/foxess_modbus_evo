"""Tests for derived battery status sensor."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.foxess_modbus.entities.modbus_battery_status_sensor import ModbusBatteryStatusSensor
from custom_components.foxess_modbus.entities.modbus_battery_status_sensor import (
    ModbusBatteryStatusSensorDescription,
)


def _make_sensor(
    *,
    bms_state: int = 1,
    power_raw: int | None = -2500,
) -> ModbusBatteryStatusSensor:
    controller = MagicMock()

    def read(address, *, signed: bool):  # noqa: ANN001
        if address == 37002:
            return bms_state
        if address == [39231, 39230]:
            return power_raw
        return None

    controller.read.side_effect = read
    description = ModbusBatteryStatusSensorDescription(
        key="battery_status",
        models=[],
        power_address=[],
        bms_connect_state_address=[],
        name="Battery Status",
    )
    return ModbusBatteryStatusSensor(
        controller=controller,
        entity_description=description,
        power_address=[39231, 39230],
        bms_connect_state_address=37002,
        power_scale=0.001,
        power_threshold_kw=0.01,
    )


def test_charging_at_typical_power_not_unknown() -> None:
    """Raw -2500 = -2.5 kW charge; must not fail Range(-100,100) on raw value."""
    assert _make_sensor(power_raw=-2500).native_value == "Charging"


def test_discharging_at_typical_power() -> None:
    assert _make_sensor(power_raw=1800).native_value == "Discharging"


def test_idle_below_threshold() -> None:
    assert _make_sensor(power_raw=-5).native_value == "Idle"


def test_unknown_when_bms_ng() -> None:
    assert _make_sensor(bms_state=2, power_raw=-2500).native_value is None


def test_status_allowed_when_bms_initial_state() -> None:
    """EVO may report 0 (initial) while battery power is still valid."""
    assert _make_sensor(bms_state=0, power_raw=-2500).native_value == "Charging"
