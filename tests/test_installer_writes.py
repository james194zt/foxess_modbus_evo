"""EVO installer settings: guarded writes (live read, unchanged skip, one change a minute, whole-block writes, read-back).

The fake inverter accepts only the write shapes an EVO 10-5-H accepted when tested: the 46616-46617 pair, 46503 alone
and the whole 46501-46514 block (46501-46502 / 46504-46505 on their own are refused with "illegal address").
"""

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.foxess_modbus.common.types import Inv
from custom_components.foxess_modbus.common.types import RegisterType
from custom_components.foxess_modbus.const import ENTITY_ID_PREFIX
from custom_components.foxess_modbus.const import FRIENDLY_NAME
from custom_components.foxess_modbus.entities import modbus_number
from custom_components.foxess_modbus.entities.entity_descriptions import ENTITIES
from custom_components.foxess_modbus.entities.modbus_number import ModbusNumber
from custom_components.foxess_modbus.entities.modbus_number import ModbusNumberDescription

ACCEPTED_WRITES = {(46616, 2), (46503, 1), (46501, 14)}


class FakeInverter:
    def __init__(self) -> None:
        self.registers = {a: 0 for a in range(46501, 46515)}
        self.registers.update({46502: 13000, 46505: 13000, 46616: 0, 46617: 15000})
        self.writes: list[tuple[int, list[int]]] = []
        self.inverter_details = {FRIENDLY_NAME: "", ENTITY_ID_PREFIX: ""}
        self.is_connected = True
        self.ignore_writes = False

    def read(self, address: int | list[int], *, signed: bool) -> int | None:  # noqa: ARG002
        if isinstance(address, list):
            return (self.registers[address[1]] << 16) | self.registers[address[0]]
        return self.registers.get(address)

    async def read_registers(self, start: int, count: int, register_type: RegisterType) -> list[int]:
        assert register_type == RegisterType.HOLDING
        return [self.registers[start + i] for i in range(count)]

    async def write_registers(self, start: int, values: list[int]) -> None:
        if (start, len(values)) not in ACCEPTED_WRITES:
            raise RuntimeError("Exception Response(144, 16, IllegalAddress)")
        self.writes.append((start, list(values)))
        if not self.ignore_writes:
            for i, value in enumerate(values):
                self.registers[start + i] = value

    async def write_register(self, address: int, value: int) -> None:
        await self.write_registers(address, [value])


@pytest.fixture(autouse=True)
def _no_verify_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modbus_number, "_VERIFY_DELAY_SECS", 0)


def _evo_number(key: str, inverter: FakeInverter) -> ModbusNumber:
    for description in ENTITIES:
        if isinstance(description, ModbusNumberDescription) and description.key == key:
            entity = description.create_entity_if_supported(inverter, Inv.EVO, RegisterType.HOLDING)  # type: ignore[arg-type]
            if entity is not None:
                assert isinstance(entity, ModbusNumber)
                entity.async_write_ha_state = lambda: None  # type: ignore[method-assign]
                return entity
    raise AssertionError(f"no EVO number {key}")


async def test_export_limit_writes_the_pair_and_reads_back() -> None:
    inverter = FakeInverter()
    number = _evo_number("export_power_limit", inverter)

    await number.async_set_native_value(0)

    assert inverter.writes == [(46616, [0, 0])]
    assert number.native_value == 0


async def test_unchanged_value_is_not_written() -> None:
    inverter = FakeInverter()
    number = _evo_number("export_power_limit", inverter)

    await number.async_set_native_value(15000)

    assert inverter.writes == []


async def test_second_change_within_a_minute_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    inverter = FakeInverter()
    number = _evo_number("export_power_limit", inverter)
    now = [1000.0]
    monkeypatch.setattr(modbus_number.time, "monotonic", lambda: now[0])

    await number.async_set_native_value(0)
    now[0] += 30
    with pytest.raises(HomeAssistantError, match="try again"):
        await number.async_set_native_value(15000)
    assert inverter.registers[46617] == 0

    # Setting the value it already has is not a change, so it isn't refused
    await number.async_set_native_value(0)

    now[0] += 31
    await number.async_set_native_value(15000)
    assert inverter.registers[46617] == 15000


async def test_import_limit_writes_the_whole_block_keeping_the_rest() -> None:
    inverter = FakeInverter()
    inverter.registers[46510] = 1234  # something else in the block must survive
    number = _evo_number("import_power_limit", inverter)

    await number.async_set_native_value(12000)

    assert len(inverter.writes) == 1
    start, values = inverter.writes[0]
    assert (start, len(values)) == (46501, 14)
    assert values[:2] == [0, 12000]
    assert values[4] == 13000  # peak shaving export limit untouched
    assert values[9] == 1234


async def test_peak_shaving_export_limit_uses_the_block() -> None:
    inverter = FakeInverter()
    number = _evo_number("peak_shaving_export_limit", inverter)

    await number.async_set_native_value(12000)

    assert inverter.registers[46505] == 12000
    assert inverter.registers[46502] == 13000


async def test_peak_shaving_soc_writes_one_register() -> None:
    inverter = FakeInverter()
    number = _evo_number("peak_shaving_threshold_soc", inverter)

    await number.async_set_native_value(10)

    assert inverter.writes == [(46503, [10])]


async def test_write_that_does_not_stick_raises() -> None:
    inverter = FakeInverter()
    inverter.ignore_writes = True
    number = _evo_number("export_power_limit", inverter)

    with pytest.raises(HomeAssistantError, match="reads back"):
        await number.async_set_native_value(0)


async def test_refused_write_raises() -> None:
    inverter = FakeInverter()
    number = _evo_number("export_power_limit", inverter)
    saved = set(ACCEPTED_WRITES)
    try:
        ACCEPTED_WRITES.discard((46616, 2))
        with pytest.raises(HomeAssistantError, match="refused"):
            await number.async_set_native_value(0)
    finally:
        ACCEPTED_WRITES.clear()
        ACCEPTED_WRITES.update(saved)


def test_kh_export_limit_number_is_unchanged() -> None:
    kh = [
        d
        for d in ENTITIES
        if isinstance(d, ModbusNumberDescription)
        and d.key == "export_power_limit"
        and d._addresses_for_inverter_model(d.addresses, Inv.KH_133, RegisterType.HOLDING) is not None
    ]
    assert len(kh) == 1
    assert kh[0].min_write_interval is None and kh[0].write_block is None
    assert kh[0].native_max_value == 99999
