"""EVO Mode Scheduler encoding and write path, using register values captured from an EVO 10-5-H.

See docs/evo/mode-scheduler.md for how these captures were made.
"""

from dataclasses import replace
from datetime import time
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.foxess_modbus.client.modbus_client import ModbusClientFailedError
from custom_components.foxess_modbus.common.evo_schedule import BLANK_GROUP
from custom_components.foxess_modbus.common.evo_schedule import GROUP_SIZE
from custom_components.foxess_modbus.common.evo_schedule import MANAGED_GROUP_COUNT
from custom_components.foxess_modbus.common.evo_schedule import ScheduleError
from custom_components.foxess_modbus.common.evo_schedule import build_managed_groups
from custom_components.foxess_modbus.common.evo_schedule import decode_groups
from custom_components.foxess_modbus.common.evo_schedule import make_group
from custom_components.foxess_modbus.common.types import InverterModel
from custom_components.foxess_modbus.const import DOMAIN
from custom_components.foxess_modbus.const import FRIENDLY_NAME
from custom_components.foxess_modbus.const import INVERTER_BASE
from custom_components.foxess_modbus.services import evo_schedule_service

# 48000-48089 with the Fox app in Mode Scheduler and three slots plus the remaining-time filler
_CAPTURE_SCHEDULED = [
    1, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    1, 261, 547, 6, 25610, 95, 11000, 0, 3, 1,
    1, 4106, 4392, 7, 25610, 25, 12000, 0, 3, 1,
    1, 5135, 5421, 2, 21790, 10, 0, 0, 1, 1,
    1, 0, 5947, 1, 25610, 10, 0, 0, 0, 1,
    0, 0, 0, 1, 25610, 10, 0, 0, 0, 1,
    0, 0, 0, 1, 25610, 10, 0, 0, 0, 1,
    0, 0, 0, 1, 25610, 10, 0, 0, 0, 1,
    0, 0, 0, 1, 25610, 10, 0, 0, 0, 1,
]  # fmt: skip

# 48000-48089 after deleting those slots in the app and selecting Self-Use
_CAPTURE_DELETED = [
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    1, 0, 5947, 1, 25610, 95, 11000, 0, 3, 1,
    0, 0, 0, 3, 25610, 25, 12000, 0, 0, 1,
    0, 0, 0, 2, 21790, 10, 0, 0, 0, 1,
    0, 0, 0, 1, 25610, 10, 0, 0, 0, 1,
    0, 0, 0, 1, 25610, 10, 0, 0, 0, 1,
    0, 0, 0, 1, 25610, 10, 0, 0, 0, 1,
    0, 0, 0, 1, 25610, 10, 0, 0, 0, 1,
    0, 0, 0, 1, 25610, 10, 0, 0, 0, 1,
]  # fmt: skip

_SELF_USE_FILLER = make_group(start=time(0, 0), end=time(23, 59), work_mode="self_use")


def _registers(capture: list[int]) -> dict[int, int]:
    return {48000 + i: value for i, value in enumerate(capture)}


class FakeEvo:
    """Holding registers of an EVO that, like the real one, rejects writes covering part of a 10-register block.

    The real inverter rejected both a 4-register group write and a single-register write to 48000.
    """

    def __init__(self, capture: list[int], *, ignored_address: int | None = None) -> None:
        self.registers = _registers(capture)
        self.writes: list[tuple[int, list[int]]] = []
        self._ignored_address = ignored_address

    async def read_registers(self, start: int, count: int, _register_type: Any) -> list[int]:
        return [self.registers.get(start + i, 0) for i in range(count)]

    async def write_registers(self, start: int, values: list[int]) -> None:
        whole_block = (start - 48000) % GROUP_SIZE == 0 and len(values) == GROUP_SIZE
        managed_groups = start == 48010 and len(values) == GROUP_SIZE * MANAGED_GROUP_COUNT  # confirmed on hardware
        if start >= 48000 and not (whole_block or managed_groups):
            raise ModbusClientFailedError("Error writing registers", "fake", "IllegalAddress")  # type: ignore[arg-type]
        self.writes.append((start, list(values)))
        for i, value in enumerate(values):
            if start + i != self._ignored_address:
                self.registers[start + i] = value
        # Like the real EVO: a Force Charge group written over Modbus stores 0 in its flags (+8)
        if start >= 48010:
            for group_start in range(0, len(values), GROUP_SIZE):
                if values[group_start + 3] == 6:
                    self.registers[start + group_start + 8] = 0

    async def write_register(self, address: int, value: int) -> None:
        await self.write_registers(address, [value])


@pytest.fixture(autouse=True)
def _no_verify_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evo_schedule_service, "_VERIFY_DELAY_SECS", 0)


def test_decodes_app_written_schedule() -> None:
    groups = decode_groups(_CAPTURE_SCHEDULED[10:])

    assert [g.to_dict() for g in groups[:4]] == [
        {
            "enabled": True, "start": "01:05", "end": "02:35", "work_mode": "force_charge",
            "min_soc": 10, "max_soc": 100, "fd_soc": 95, "fd_pwr": 11000,
            "raw_reserved": 0, "raw_flags": 3, "raw_slot_marker": 1,
        },
        {
            "enabled": True, "start": "16:10", "end": "17:40", "work_mode": "force_discharge",
            "min_soc": 10, "max_soc": 100, "fd_soc": 25, "fd_pwr": 12000,
            "raw_reserved": 0, "raw_flags": 3, "raw_slot_marker": 1,
        },
        {
            "enabled": True, "start": "20:15", "end": "21:45", "work_mode": "feed_in",
            "min_soc": 30, "max_soc": 85, "fd_soc": 10, "fd_pwr": 0,
            "raw_reserved": 0, "raw_flags": 1, "raw_slot_marker": 1,
        },
        {
            "enabled": True, "start": "00:00", "end": "23:59", "work_mode": "self_use",
            "min_soc": 10, "max_soc": 100, "fd_soc": 10, "fd_pwr": 0,
            "raw_reserved": 0, "raw_flags": 0, "raw_slot_marker": 1,
        },
    ]  # fmt: skip
    assert groups[4:] == [BLANK_GROUP] * 4


@pytest.mark.parametrize("capture", [_CAPTURE_SCHEDULED, _CAPTURE_DELETED])
def test_decode_encode_round_trips(capture: list[int]) -> None:
    encoded = [r for g in decode_groups(capture[10:]) for r in g.to_registers()]
    assert encoded == capture[10:]


def test_make_group_matches_what_the_app_writes() -> None:
    assert (
        make_group(start=time(1, 5), end=time(2, 35), work_mode="force_charge", fd_soc=95, fd_pwr=11000).to_registers()
        == _CAPTURE_SCHEDULED[10:20]
    )
    assert (
        make_group(start=time(20, 15), end=time(21, 45), work_mode="feed_in", min_soc=30, max_soc=85).to_registers()
        == _CAPTURE_SCHEDULED[30:40]
    )
    assert _SELF_USE_FILLER.to_registers() == _CAPTURE_SCHEDULED[40:50]
    assert BLANK_GROUP.to_registers() == _CAPTURE_SCHEDULED[50:60]


def test_build_managed_groups_places_filler_after_slots() -> None:
    slot = make_group(start=time(1, 0), end=time(4, 0), work_mode="force_charge", fd_soc=90, fd_pwr=6000)

    managed = build_managed_groups([slot], _SELF_USE_FILLER)

    assert managed == [slot, _SELF_USE_FILLER] + [BLANK_GROUP] * (MANAGED_GROUP_COUNT - 2)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start": time(4, 0), "end": time(1, 0), "work_mode": "self_use"}, "must be after start"),
        ({"start": time(1, 0), "end": time(1, 0), "work_mode": "self_use"}, "must be after start"),
        ({"start": time(1, 0), "end": time(2, 0), "work_mode": "peak_shaving"}, "Unknown work mode"),
        ({"start": time(1, 0), "end": time(2, 0), "work_mode": "feed_in", "min_soc": 60, "max_soc": 50}, "min_soc"),
        ({"start": time(1, 0), "end": time(2, 0), "work_mode": "force_charge", "fd_pwr": 20000}, "fd_pwr"),
        ({"start": time(1, 0), "end": time(2, 0), "work_mode": "force_discharge", "fd_soc": 2}, "fd_soc"),
    ],
)
def test_make_group_rejects_invalid_slots(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ScheduleError, match=message):
        make_group(**kwargs)


def test_build_managed_groups_rejects_too_many_slots() -> None:
    slot = make_group(start=time(1, 0), end=time(2, 0), work_mode="self_use")
    with pytest.raises(ScheduleError, match="At most 7"):
        build_managed_groups([slot] * 8, _SELF_USE_FILLER)


async def test_write_schedule_writes_whole_groups_then_switch() -> None:
    inverter = FakeEvo(_CAPTURE_DELETED)
    slot = make_group(start=time(1, 0), end=time(4, 30), work_mode="force_charge", fd_soc=95, fd_pwr=6000)

    enabled, groups = await evo_schedule_service.async_write_schedule(
        inverter,  # type: ignore[arg-type]
        build_managed_groups([slot], _SELF_USE_FILLER),
        enabled=True,
    )

    # All eight managed groups in one write (atomic), then the switch block.
    managed = build_managed_groups([slot], _SELF_USE_FILLER)
    assert inverter.writes == [
        (48010, [r for group in managed for r in group.to_registers()]),
        (48000, [1, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    ]
    assert enabled is True
    assert groups[0] == replace(slot, flags=0)  # the inverter clears flags on a Force Charge slot
    assert groups[1] == _SELF_USE_FILLER


async def test_force_charge_slot_passes_read_back_although_inverter_clears_flags() -> None:
    inverter = FakeEvo(_CAPTURE_DELETED)
    slot = make_group(start=time(21, 45), end=time(22, 5), work_mode="force_charge", fd_soc=58, fd_pwr=1000)
    managed = build_managed_groups([slot], _SELF_USE_FILLER)

    await evo_schedule_service.async_write_schedule(inverter, managed, enabled=True)  # type: ignore[arg-type]
    assert inverter.registers[48018] == 0  # app value 3 written, inverter kept 0

    inverter.writes.clear()
    await evo_schedule_service.async_write_schedule(inverter, managed, enabled=True)  # type: ignore[arg-type]
    assert inverter.writes == []  # the cleared flags field doesn't make the slot look changed


async def test_write_schedule_skips_unchanged_groups() -> None:
    inverter = FakeEvo(_CAPTURE_SCHEDULED)
    unchanged = decode_groups(_CAPTURE_SCHEDULED[10:])

    await evo_schedule_service.async_write_schedule(inverter, unchanged, enabled=True)  # type: ignore[arg-type]

    assert inverter.writes == []


async def test_set_enabled_only_writes_switch() -> None:
    inverter = FakeEvo(_CAPTURE_SCHEDULED)

    enabled, _ = await evo_schedule_service.async_write_schedule(inverter, None, enabled=False)  # type: ignore[arg-type]

    assert inverter.writes == [(48000, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0])]
    assert enabled is False


async def test_write_schedule_fails_when_read_back_differs() -> None:
    inverter = FakeEvo(_CAPTURE_DELETED, ignored_address=48016)
    slot = make_group(start=time(1, 0), end=time(4, 30), work_mode="force_charge", fd_soc=95, fd_pwr=6000)

    with pytest.raises(HomeAssistantError, match="48016: wrote 6000, read 11000"):
        await evo_schedule_service.async_write_schedule(
            inverter,  # type: ignore[arg-type]
            build_managed_groups([slot], _SELF_USE_FILLER),
            enabled=True,
        )


async def test_get_evo_schedule_service_returns_schedule(hass: HomeAssistant) -> None:
    inverter = FakeEvo(_CAPTURE_SCHEDULED)
    inverter.inverter_details = {FRIENDLY_NAME: "EVO-10", INVERTER_BASE: InverterModel.EVO}  # type: ignore[attr-defined]
    evo_schedule_service.register(hass, [inverter])  # type: ignore[list-item]

    response = await hass.services.async_call(
        DOMAIN, "get_evo_schedule", {"inverter": "EVO-10"}, blocking=True, return_response=True
    )

    assert response is not None
    assert response["enabled"] is True
    assert response["slots"][0]["work_mode"] == "force_charge"
    assert len(response["slots"]) == MANAGED_GROUP_COUNT


async def test_write_schedule_reports_rejected_write() -> None:
    inverter = FakeEvo(_CAPTURE_DELETED)

    async def _reject(*_args: Any) -> None:
        raise ModbusClientFailedError("Error writing registers", "fake", "IllegalAddress")  # type: ignore[arg-type]

    inverter.write_registers = _reject  # type: ignore[method-assign]
    slot = make_group(start=time(1, 0), end=time(4, 30), work_mode="self_use")

    with pytest.raises(HomeAssistantError, match="schedule slots at 48010"):
        await evo_schedule_service.async_write_schedule(
            inverter,  # type: ignore[arg-type]
            build_managed_groups([slot], _SELF_USE_FILLER),
            enabled=True,
        )
