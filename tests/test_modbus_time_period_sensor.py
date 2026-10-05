"""Tests for enable/start/end time period decoding (EVO battery warm-up periods)."""

from custom_components.foxess_modbus.entities.modbus_time_period_sensor import decode_time_period


def test_decode_enabled_period() -> None:
    # Read from an EVO with warm-up period 1 set to 01:11-02:22 in the Fox app (53403-53405)
    assert decode_time_period(1, 267, 534) == "01:11-02:22"


def test_decode_disabled_period() -> None:
    assert decode_time_period(0, 0, 0) == "Off"
    assert decode_time_period(0, 267, 534) == "Off"


def test_decode_invalid_time() -> None:
    assert decode_time_period(1, 24 * 256, 534) is None
    assert decode_time_period(1, 267, 60) is None
