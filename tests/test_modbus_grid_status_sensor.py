"""Tests for grid status decoding."""

from custom_components.foxess_modbus.entities.modbus_grid_status_sensor import grid_status_from_power_kw


def test_grid_status_export() -> None:
    assert grid_status_from_power_kw(0.5) == "Export"


def test_grid_status_import() -> None:
    assert grid_status_from_power_kw(-0.3) == "Import"


def test_grid_status_idle_within_threshold() -> None:
    assert grid_status_from_power_kw(0.01) == "Idle"
    assert grid_status_from_power_kw(-0.01) == "Idle"
    assert grid_status_from_power_kw(0.0) == "Idle"
