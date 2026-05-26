"""Tests for FoxESS Modbus ASCII string decoding."""

from custom_components.foxess_modbus.entities.modbus_string_sensor import decode_foxess_ascii_registers


def test_decode_evo_model_name() -> None:
    registers = [17750, 20256, 12592, 11573, 11592, 0, 0, 0]
    assert decode_foxess_ascii_registers(registers) == "EVO 10-5-H"


def test_decode_evo_serial_number() -> None:
    registers = [13872, 14390, 13616, 12850, 13874, 13890, 12337, 12288, 0]
    assert decode_foxess_ascii_registers(registers) == "60865022626B01"


def test_decode_one_char_per_register() -> None:
    registers = [ord(c) for c in "H1-3.7-E"] + [0]
    assert decode_foxess_ascii_registers(registers) == "H1-3.7-E"


def test_decode_bms_pack_serial_trailing_char_in_padding_register() -> None:
    # Final register 0x3500 appends high-byte '5' after …LD08 (e.g. register 37104)
    registers = [0x4C44, 0x3038, 0x3500]
    assert decode_foxess_ascii_registers(registers) == "LD085"


def test_modbus_protocol_version_u32() -> None:
    hi, lo = 261, 1024
    version = ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)
    b0 = (version >> 24) & 0xFF
    b1 = (version >> 16) & 0xFF
    b2 = (version >> 8) & 0xFF
    b3 = version & 0xFF
    assert f"V{b0}.{b1:02d}.{b2:02d}.{b3:02d}" == "V1.05.04.00"
