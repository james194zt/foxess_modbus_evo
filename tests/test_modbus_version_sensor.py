"""Version sensor formatting (EVO pack tokens and PCS hex)."""


def _format_pack_token(value: int) -> str:
    major = (value >> 12) & 0xF
    minor = value & 0xFFF
    return f"{major}.{minor:03d}"


def test_evo_pack_version_token_decode() -> None:
    assert _format_pack_token(0x1000) == "1.000"
    assert _format_pack_token(0x1001) == "1.001"
    assert _format_pack_token(0x2000) == "2.000"


def test_pcs_hex_version_decode() -> None:
    value = 0x0101
    major = value >> 8
    minor = value & 0xFF
    assert f"{major:X}.{minor:02X}" == "1.01"
