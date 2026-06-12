"""Version sensor formatting (PCS hex)."""


def test_pcs_hex_version_decode() -> None:
    value = 0x0101
    major = value >> 8
    minor = value & 0xFF
    assert f"{major:X}.{minor:02X}" == "1.01"
