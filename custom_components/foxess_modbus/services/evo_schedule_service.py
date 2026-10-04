"""Services to read and write the FoxESS EVO Mode Scheduler (see docs/EVO_MODE_SCHEDULER.md)"""

import asyncio
import logging
from datetime import time
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.core import ServiceResponse
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ..client.modbus_client import ModbusClientFailedError
from ..common.evo_schedule import GROUP_SIZE
from ..common.evo_schedule import MANAGED_GROUP_COUNT
from ..common.evo_schedule import MAX_USER_GROUPS
from ..common.evo_schedule import SCHEDULER_ENABLE_ADDRESS
from ..common.evo_schedule import WORK_MODE_CODES
from ..common.evo_schedule import ScheduleError
from ..common.evo_schedule import ScheduleGroup
from ..common.evo_schedule import build_managed_groups
from ..common.evo_schedule import decode_groups
from ..common.evo_schedule import group_address
from ..common.evo_schedule import make_group
from ..common.types import InverterModel
from ..common.types import RegisterType
from ..const import DOMAIN
from ..const import INVERTER_BASE
from ..modbus_controller import ModbusController
from .utils import get_controller_from_friendly_name_or_device_id

_LOGGER: logging.Logger = logging.getLogger(__package__)

# 48000-48009 then the managed groups, in one read
_READ_START = SCHEDULER_ENABLE_ADDRESS
_READ_COUNT = group_address(MANAGED_GROUP_COUNT) - SCHEDULER_ENABLE_ADDRESS
_FIRST_GROUP_OFFSET = group_address(0) - SCHEDULER_ENABLE_ADDRESS
# Give the inverter a moment to apply writes before reading back
_VERIFY_DELAY_SECS = 1.0

_SOC = vol.All(vol.Coerce(int), vol.Range(min=0, max=100))

_SLOT_SCHEMA = vol.Schema(
    {
        vol.Required("start"): cv.time,
        vol.Required("end"): cv.time,
        vol.Required("work_mode"): vol.In(list(WORK_MODE_CODES)),
        vol.Optional("min_soc", default=10): _SOC,
        vol.Optional("max_soc", default=100): _SOC,
        vol.Optional("fd_soc", default=10): _SOC,
        vol.Optional("fd_pwr", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)

_REMAINING_SCHEMA = vol.Schema(
    {
        vol.Optional("work_mode", default="self_use"): vol.In(["self_use", "feed_in", "back_up"]),
        vol.Optional("min_soc", default=10): _SOC,
        vol.Optional("max_soc", default=100): _SOC,
    }
)

_SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("inverter"): vol.Any(cv.string, None),
        vol.Optional("enabled", default=True): cv.boolean,
        vol.Optional("slots", default=list): vol.All(cv.ensure_list, [_SLOT_SCHEMA], vol.Length(max=MAX_USER_GROUPS)),
        vol.Optional("remaining", default=dict): _REMAINING_SCHEMA,
    }
)

_SET_ENABLED_SCHEMA = vol.Schema(
    {
        vol.Required("inverter"): vol.Any(cv.string, None),
        vol.Required("enabled"): cv.boolean,
    }
)

_GET_SCHEDULE_SCHEMA = vol.Schema({vol.Required("inverter"): vol.Any(cv.string, None)})


def register(hass: HomeAssistant, controllers: list[ModbusController]) -> None:
    """Register the services with HA"""

    def _controller(service_data: ServiceCall) -> ModbusController:
        controller = get_controller_from_friendly_name_or_device_id(service_data.data["inverter"], controllers, hass)
        if controller.inverter_details[INVERTER_BASE] != InverterModel.EVO:
            raise ServiceValidationError("The Mode Scheduler services are only supported on FoxESS EVO inverters")
        return controller

    async def _get_schedule(service_data: ServiceCall) -> ServiceResponse:
        enabled, groups = await async_read_schedule(_controller(service_data))
        return _schedule_response(enabled, groups)

    async def _set_schedule(service_data: ServiceCall) -> ServiceResponse:
        controller = _controller(service_data)
        managed = _managed_groups_from_service_data(service_data.data)
        enabled, groups = await async_write_schedule(controller, managed, enabled=service_data.data["enabled"])
        return _schedule_response(enabled, groups) if service_data.return_response else None

    async def _set_enabled(service_data: ServiceCall) -> None:
        await async_write_schedule(_controller(service_data), None, enabled=service_data.data["enabled"])

    hass.services.async_register(
        DOMAIN, "get_evo_schedule", _get_schedule, _GET_SCHEDULE_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, "set_evo_schedule", _set_schedule, _SET_SCHEDULE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(DOMAIN, "set_evo_schedule_enabled", _set_enabled, _SET_ENABLED_SCHEMA)


def _managed_groups_from_service_data(data: dict[str, Any]) -> list[ScheduleGroup]:
    try:
        slots = [make_group(**slot) for slot in data["slots"]]
        remaining = make_group(start=time(0, 0), end=time(23, 59), **data["remaining"])
        return build_managed_groups(slots, remaining)
    except ScheduleError as ex:
        raise ServiceValidationError(str(ex)) from ex


def _schedule_response(enabled: bool, groups: list[ScheduleGroup]) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "slots": [{"slot": i + 1, **group.to_dict()} for i, group in enumerate(groups)],
    }


async def _read_raw(controller: ModbusController) -> list[int]:
    try:
        return await controller.read_registers(_READ_START, _READ_COUNT, RegisterType.HOLDING)
    except ModbusClientFailedError as ex:
        raise HomeAssistantError(f"Failed to read the EVO schedule: {ex}") from ex


def _decode(raw: list[int]) -> tuple[bool, list[ScheduleGroup]]:
    try:
        return raw[0] != 0, decode_groups(raw[_FIRST_GROUP_OFFSET:])
    except ScheduleError as ex:
        raise HomeAssistantError(f"The inverter returned an unreadable schedule: {ex}") from ex


async def async_read_schedule(controller: ModbusController) -> tuple[bool, list[ScheduleGroup]]:
    """Read the scheduler switch (48000) and managed groups 1-8."""
    return _decode(await _read_raw(controller))


async def async_write_schedule(
    controller: ModbusController,
    managed: list[ScheduleGroup] | None,
    *,
    enabled: bool,
) -> tuple[bool, list[ScheduleGroup]]:
    """Write changed groups as whole 10-register blocks, then the scheduler switch, then verify.

    `managed` must hold all MANAGED_GROUP_COUNT groups, or be None to only change the switch.
    The inverter rejects writes covering part of a 10-register block (including 48000-48009, the
    block holding the switch), so blocks are only ever written whole.
    """
    assert managed is None or len(managed) == MANAGED_GROUP_COUNT

    current_raw = await _read_raw(controller)
    current_enabled, current_groups = _decode(current_raw)
    wanted = managed if managed is not None else current_groups

    expected_raw = list(current_raw)
    expected_raw[0] = 1 if enabled else 0

    for index, group in enumerate(wanted):
        registers = group.to_registers()
        offset = _FIRST_GROUP_OFFSET + index * GROUP_SIZE
        expected_raw[offset : offset + GROUP_SIZE] = registers
        if current_groups[index].to_registers() == registers:
            continue
        address = group_address(index)
        try:
            # write_registers mutates its argument, so hand it a copy
            await controller.write_registers(address, list(registers))
        except ModbusClientFailedError as ex:
            raise HomeAssistantError(f"Failed to write schedule slot {index + 1} at {address}: {ex}") from ex

    if current_enabled != enabled:
        try:
            # A single-register write to 48000 is rejected; the whole 48000-48009 block is accepted
            await controller.write_registers(SCHEDULER_ENABLE_ADDRESS, expected_raw[:_FIRST_GROUP_OFFSET])
        except ModbusClientFailedError as ex:
            raise HomeAssistantError(f"Failed to set the scheduler switch ({SCHEDULER_ENABLE_ADDRESS}): {ex}") from ex

    await asyncio.sleep(_VERIFY_DELAY_SECS)
    actual_raw = await _read_raw(controller)
    mismatches = [
        f"{_READ_START + i}: wrote {want}, read {got}"
        for i, (want, got) in enumerate(zip(expected_raw, actual_raw, strict=True))
        if want != got
    ]
    if mismatches:
        raise HomeAssistantError(f"The inverter didn't keep the schedule that was written ({'; '.join(mismatches)})")

    _LOGGER.info("EVO schedule written (scheduler %s)", "on" if enabled else "off")
    return _decode(actual_raw)
