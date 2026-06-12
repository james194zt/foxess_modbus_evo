"""AFCI version decode helpers."""

from custom_components.foxess_modbus.entities.modbus_afci_version_sensor import format_afci_version
from custom_components.foxess_modbus.entities.modbus_afci_version_sensor import pick_afci_decode


def test_afci_pcs_hex_decode_matches_fox() -> None:
    assert format_afci_version(0x0037, hex_style=True) == "0.37"
    assert format_afci_version(0x0030, hex_style=True) == "0.30"
    assert pick_afci_decode(0x0037) == "0.37"


def test_afci_decimal_decode() -> None:
    assert format_afci_version(37, hex_style=False) == "0.37"
    assert pick_afci_decode(37) in ("0.37", "0.25")
