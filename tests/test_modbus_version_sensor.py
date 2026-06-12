"""Version sensor formatting (EVO pack tokens and PCS hex)."""

from custom_components.foxess_modbus.entities.modbus_version_sensor import format_pack_token


def test_evo_pack_version_token_decode() -> None:
    assert format_pack_token(0x1000) == "1.000"
    assert format_pack_token(0x1001) == "1.001"
    assert format_pack_token(0x2000) == "2.000"


def test_evo_pack_version_sub_register_merge() -> None:
    assert format_pack_token(0x1000, sub_register=4) == "1.004"


def test_pcs_hex_version_decode() -> None:
    value = 0x0101
    major = value >> 8
    minor = value & 0xFF
    assert f"{major:X}.{minor:02X}" == "1.01"
