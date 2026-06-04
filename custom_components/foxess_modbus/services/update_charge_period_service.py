"""Defines the services to update charge periods"""

import logging
from dataclasses import dataclass
from datetime import time
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from ..const import DOMAIN
from ..entities.modbus_charge_period_sensors import charge_period_start_register_value
from ..entities.modbus_charge_period_sensors import is_time_value_valid
from ..entities.modbus_charge_period_sensors import parse_time_value
from ..entities.modbus_charge_period_sensors import serialize_time_to_value
from ..client.modbus_client import ModbusClientFailedError
from ..modbus_controller import ModbusController
from ..vendor.pymodbus import ModbusIOException
from .utils import get_controller_from_friendly_name_or_device_id

_LOGGER: logging.Logger = logging.getLogger(__package__)


def _integer(value: Any) -> int:
    """Validate and coerce a boolean value."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    raise vol.Invalid(f"invalid int value {value}")


def _seconds_must_be_zero(value: time) -> time:
    if value.second != 0:
        raise vol.Invalid("Seconds component must be 0 if specified")
    return value


def _start_end_must_be_present_if_enabled(data: dict[str, Any]) -> dict[str, Any]:
    if data["enable_force_charge"]:
        if "start" not in data:
            raise vol.Invalid(
                "'start' must be specified if 'enable_force_charge' is True",
                path=["start"],
            )
        if "end" not in data:
            raise vol.Invalid("'end' must be specified if 'enable_force_charge' is True", path=["end"])
    return data


def _end_must_not_be_start_if_enabled(data: dict[str, Any]) -> dict[str, Any]:
    if data["enable_force_charge"] and "start" in data and "end" in data:
        start = data["start"]
        end = data["end"]
        if start.hour == end.hour and start.minute == end.minute:
            raise vol.Invalid("'end' must not be the same as 'start'", path=["end"])
    return data


_UPDATE_CHARGE_PERIOD_SCHEMA = vol.Schema(
    vol.All(
        {
            # Let the value to this be omitted, instead of forcing them to specify ''
            vol.Required("inverter", description="Inverter"): vol.Any(cv.string, None),
            vol.Required("charge_period", description="Charge Period"): vol.All(_integer, vol.Range(min=1, max=2)),
            vol.Required("enable_force_charge", description="Enable force charge"): cv.boolean,
            vol.Required("enable_charge_from_grid", description="Enable charge from grid"): cv.boolean,
            vol.Optional("start", description="Period Start"): vol.All(cv.time, _seconds_must_be_zero),
            vol.Optional("end", description="Period End"): vol.All(cv.time, _seconds_must_be_zero),
        },
        _start_end_must_be_present_if_enabled,
        _end_must_not_be_start_if_enabled,
    )
)

_UPDATE_ALL_CHARGE_PERIODS_SCHEMA = vol.Schema(
    {
        # Let the value to this be omitted, instead of forcing them to specify ''
        vol.Required("inverter", description="Inverter"): vol.Any(cv.string, None),
        vol.Required("charge_periods", description="Charge Periods"): vol.All(
            [
                vol.All(
                    {
                        vol.Required("enable_force_charge", description="Enable force charge"): cv.boolean,
                        vol.Required(
                            "enable_charge_from_grid",
                            description="Enable charge from grid",
                        ): cv.boolean,
                        vol.Optional("start", description="Period Start"): vol.All(cv.time, _seconds_must_be_zero),
                        vol.Optional("end", description="Period End"): vol.All(
                            cv.time,
                            _seconds_must_be_zero,
                        ),
                    },
                    _start_end_must_be_present_if_enabled,
                    _end_must_not_be_start_if_enabled,
                )
            ],
            vol.Length(min=2, max=2),
        ),
    }
)


def register(hass: HomeAssistant, controllers: list[ModbusController]) -> None:
    """Register the services with HA"""

    async def _update_charge_period_callback(service_data: ServiceCall) -> None:
        await hass.loop.create_task(_update_charge_period(controllers, service_data, hass))

    hass.services.async_register(
        DOMAIN,
        "update_charge_period",
        _update_charge_period_callback,
        _UPDATE_CHARGE_PERIOD_SCHEMA,
    )

    async def _update_all_charge_periods_callback(service_data: ServiceCall) -> None:
        await hass.loop.create_task(_update_all_charge_periods(controllers, service_data, hass))

    hass.services.async_register(
        DOMAIN,
        "update_all_charge_periods",
        _update_all_charge_periods_callback,
        _UPDATE_ALL_CHARGE_PERIODS_SCHEMA,
    )


@dataclass
class ChargePeriod:
    """Holds the data for a single charge period"""

    enable_force_charge: bool
    enable_charge_from_grid: bool
    start: time
    end: time


def _is_illegal_address_error(err: BaseException) -> bool:
    return "IllegalAddress" in str(err)


_EVO_MODE_REGISTERS = frozenset({48013, 48023})
_EVO_TIME_GROUP_ENABLE = 48000
# Extended time-group registers (H3-Smart / EVO mode planner); see evcc-io/evcc#25140
_EVO_PERIOD_EXTRA_DEFAULTS: tuple[tuple[int, int], ...] = (
    (4, 25615),
    (5, 100),
    (6, 6000),
    (9, 1),
)


def _evo_period_base(period_start_address: int) -> int | None:
    """Return 48010/48020 base address for an EVO charge period."""
    if period_start_address in {48011, 48021}:
        return period_start_address - 1
    return None


def _evo_extra_writes(period_start_address: int, *, enabled: bool, extended: bool) -> list[tuple[int, int]]:
    if not extended:
        return []
    base = _evo_period_base(period_start_address)
    if base is None or not enabled:
        return []
    return [(base + offset, value) for offset, value in _EVO_PERIOD_EXTRA_DEFAULTS]


def _charge_period_diagnostics(
    controller: ModbusController,
    addresses: Any,
) -> str:
    """Summarise current Modbus reads for charge-period registers."""
    parts: list[str] = []
    if addresses.period_start_address in {48011, 48021}:
        tg = controller.read(_EVO_TIME_GROUP_ENABLE, signed=False)
        parts.append(f"time_group @{_EVO_TIME_GROUP_ENABLE}={tg if tg is not None else 'unreadable'}")
    for label, addr in (
        ("grid", addresses.enable_charge_from_grid_address),
        ("start", addresses.period_start_address),
        ("end", addresses.period_end_address),
        *([("mode", addresses.mode_address)] if addresses.mode_address is not None else []),
    ):
        value = controller.read(addr, signed=False)
        parts.append(f"{label} @{addr}={value if value is not None else 'unreadable'}")
    return ", ".join(parts)


async def _try_enable_evo_time_group(controller: ModbusController) -> bool:
    """Enable register 48000 when supported (H3-Smart). EVO 10-H often has no 48000."""
    if controller.read(_EVO_TIME_GROUP_ENABLE, signed=False) is None:
        _LOGGER.debug("EVO time-group register %s unreadable; skipping enable", _EVO_TIME_GROUP_ENABLE)
        return False
    try:
        await controller.write_register(_EVO_TIME_GROUP_ENABLE, 1)
        return True
    except (ModbusIOException, ModbusClientFailedError) as ex:
        if _is_illegal_address_error(ex):
            _LOGGER.info(
                "EVO time-group register %s not writable (%s); using direct 48010 block writes",
                _EVO_TIME_GROUP_ENABLE,
                ex,
            )
            return False
        raise


async def _maybe_disable_evo_time_group(
    controller: ModbusController,
    charge_periods: list[ChargePeriod],
    *,
    was_enabled: bool,
) -> None:
    if not was_enabled:
        return
    if not any(p.enable_force_charge for p in charge_periods):
        try:
            await controller.write_register(_EVO_TIME_GROUP_ENABLE, 0)
        except (ModbusIOException, ModbusClientFailedError) as ex:
            _LOGGER.warning("Failed to disable EVO time-group register %s: %s", _EVO_TIME_GROUP_ENABLE, ex)


def _split_contiguous_writes(writes: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """Split register writes into contiguous FC16 blocks."""
    if not writes:
        return []
    sorted_writes = sorted(writes, key=lambda item: item[0])
    blocks: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = [sorted_writes[0]]
    for address, value in sorted_writes[1:]:
        if address == current[-1][0] + 1:
            current.append((address, value))
        else:
            blocks.append(current)
            current = [(address, value)]
    blocks.append(current)
    return blocks


def _build_contiguous_write(writes: list[tuple[int, int]]) -> tuple[int, list[int]]:
    """Pack register writes into one FC16 block."""
    write_start_address = min(w[0] for w in writes)
    write_end_address = max(w[0] for w in writes)
    write_values: list[int | None] = [None] * (write_end_address - write_start_address + 1)
    for address, value in writes:
        write_values[address - write_start_address] = value
    if any(x is None for x in write_values):
        raise ValueError(f"Incomplete charge-period write block: {writes}")
    return write_start_address, write_values  # type: ignore[return-value]


def _without_mode_register(
    writes: list[tuple[int, int]],
    mode_address: int | None,
) -> list[tuple[int, int]]:
    if mode_address is None:
        return writes
    return [(address, value) for address, value in writes if address != mode_address]


async def _write_charge_period_registers(
    controller: ModbusController,
    writes: list[tuple[int, int]],
    *,
    evo_style: bool,
    addresses: Any,
    charge_period: ChargePeriod | None = None,
    evo_extended: bool = False,
) -> None:
    """Write one charge period. EVO uses a contiguous FC16 block at 48010/48020."""
    diagnostics = _charge_period_diagnostics(controller, addresses)

    if evo_style and charge_period is not None:
        period_start = addresses.period_start_address
        writes = [
            (
                addresses.enable_charge_from_grid_address,
                1 if charge_period.enable_force_charge else 0,
            ),
            (
                addresses.period_start_address,
                charge_period_start_register_value(
                    charge_period.start,
                    charge_period.end,
                    enabled=charge_period.enable_force_charge,
                ),
            ),
            (
                addresses.period_end_address,
                serialize_time_to_value(charge_period.end) if charge_period.enable_force_charge else 0,
            ),
        ]
        if addresses.mode_address is not None:
            mode_value = (
                addresses.mode_charge_value
                if charge_period.enable_charge_from_grid
                else addresses.mode_no_charge_value
            )
            writes.append((addresses.mode_address, mode_value))
        writes.extend(
            _evo_extra_writes(period_start, enabled=charge_period.enable_force_charge, extended=evo_extended)
        )

    async def _try_batches(all_writes: list[tuple[int, int]]) -> None:
        for block in _split_contiguous_writes(all_writes):
            start, values = _build_contiguous_write(block)
            await controller.write_registers(start, values)

    try:
        await _try_batches(writes)
        return
    except (ModbusIOException, ModbusClientFailedError) as ex:
        if not _is_illegal_address_error(ex):
            raise
        _LOGGER.warning("Batch charge-period write failed (%s)", ex)

    if evo_style and addresses.mode_address is not None:
        writes_no_mode = _without_mode_register(writes, addresses.mode_address)
        if len(writes_no_mode) < len(writes):
            try:
                await _try_batches(writes_no_mode)
                return
            except (ModbusIOException, ModbusClientFailedError) as ex:
                if not _is_illegal_address_error(ex):
                    raise
                _LOGGER.warning("Batch charge-period write without mode register failed (%s)", ex)

    detail = f" Charge-period reads before write: {diagnostics}."
    raise HomeAssistantError(
        f"Charge-period write failed for registers {writes}.{detail} "
        "These sensors are read-only in HA — use foxess_modbus.update_all_charge_periods, not Developer Tools Set state. "
        "If writes fail, disable Fox app Mode Scheduler / cloud charge schedules."
    )


async def _update_all_charge_periods(
    controllers: list[ModbusController],
    service_data: ServiceCall,
    hass: HomeAssistant,
) -> None:
    controller = get_controller_from_friendly_name_or_device_id(service_data.data["inverter"], controllers, hass)

    charge_periods: list[ChargePeriod] = []
    for charge_period in service_data.data["charge_periods"]:
        charge_periods.append(
            ChargePeriod(
                enable_force_charge=charge_period["enable_force_charge"],
                enable_charge_from_grid=charge_period["enable_charge_from_grid"],
                start=charge_period.get("start", time(hour=0, minute=0)),
                end=charge_period.get("end", time(hour=0, minute=0)),
            )
        )

    await _set_charge_periods(controller, charge_periods)


async def _update_charge_period(
    controllers: list[ModbusController],
    service_data: ServiceCall,
    hass: HomeAssistant,
) -> None:
    controller = get_controller_from_friendly_name_or_device_id(service_data.data["inverter"], controllers, hass)
    charge_period_index = service_data.data["charge_period"] - 1

    if charge_period_index >= len(controller.charge_periods):
        raise HomeAssistantError(f"Inverter does not support setting charge period {charge_period_index + 1}")

    charge_periods: list[ChargePeriod] = [None] * len(controller.charge_periods)  # type: ignore

    charge_periods[charge_period_index] = ChargePeriod(
        enable_force_charge=service_data.data["enable_force_charge"],
        enable_charge_from_grid=service_data.data["enable_charge_from_grid"],
        start=service_data.data.get("start", time(hour=0, minute=0)),
        end=service_data.data.get("end", time(hour=0, minute=0)),
    )

    # Add the other charge periods, which aren't being set right now, to charge_periods
    for i, charge_period in enumerate(controller.charge_periods):
        if i == charge_period_index:
            continue

        period_start_time_value = controller.read(charge_period.addresses.period_start_address, signed=False)
        period_end_time_value = controller.read(charge_period.addresses.period_end_address, signed=False)
        period_enable_charge_from_grid_value = controller.read(
            charge_period.addresses.enable_charge_from_grid_address, signed=False
        )

        if (
            period_start_time_value is None
            or period_end_time_value is None
            or period_enable_charge_from_grid_value is None
        ):
            raise HomeAssistantError(
                f"Data for charge period {i + 1} is not available. Please try again in a few seconds"
            )
        if not is_time_value_valid(period_start_time_value) or not is_time_value_valid(period_end_time_value):
            raise HomeAssistantError(
                f"Start time '{period_start_time_value}' or end time '{period_end_time_value}' for charge period "
                f"{i + 1} is not valid"
            )

        charge_periods[i] = ChargePeriod(
            enable_force_charge=period_start_time_value > 0 or period_end_time_value > 0,
            enable_charge_from_grid=period_enable_charge_from_grid_value > 0,
            start=parse_time_value(period_start_time_value),
            end=parse_time_value(period_end_time_value),
        )

    await _set_charge_periods(controller, charge_periods)


async def _set_charge_periods(controller: ModbusController, charge_periods: list[ChargePeriod]) -> None:
    if len(controller.charge_periods) == 0:
        raise HomeAssistantError("Inverter does not support setting charge periods")
    if len(charge_periods) > len(controller.charge_periods):
        raise HomeAssistantError(f"Inverter does not support setting charge period {len(controller.charge_periods)}")
    if len(charge_periods) < len(controller.charge_periods):
        raise HomeAssistantError(
            f"Entries must be provided for all charge periods. Expected {len(controller.charge_periods)} "
            f"charge periods, got {len(charge_periods)}"
        )

    # The current foxcloud version doesn't seem to impose any restrictions on charge periods overlapping.
    # (One charge period can contain another, or starts/ends can overlap).
    # Mirror this for consistancy, even though it is a little odd.

    # Write each charge period separately so non-contiguous address ranges (e.g. EVO) are handled correctly
    evo_style = any(cp.addresses.mode_address is not None for cp in controller.charge_periods)
    evo_time_group_enabled = False
    if evo_style and any(p.enable_force_charge for p in charge_periods):
        evo_time_group_enabled = await _try_enable_evo_time_group(controller)

    for charge_period, config in zip(charge_periods, controller.charge_periods, strict=True):
        writes: list[tuple[int, int]] = [
            (
                config.addresses.period_start_address,
                charge_period_start_register_value(
                    charge_period.start,
                    charge_period.end,
                    enabled=charge_period.enable_force_charge,
                ),
            ),
            (
                config.addresses.period_end_address,
                serialize_time_to_value(charge_period.end) if charge_period.enable_force_charge else 0,
            ),
            (
                config.addresses.enable_charge_from_grid_address,
                1 if charge_period.enable_force_charge else 0,
            ),
        ]
        if config.addresses.mode_address is not None:
            mode_value = (
                config.addresses.mode_charge_value
                if charge_period.enable_charge_from_grid
                else config.addresses.mode_no_charge_value
            )
            writes.append((config.addresses.mode_address, mode_value))

        try:
            await _write_charge_period_registers(
                controller,
                writes,
                evo_style=config.addresses.mode_address is not None,
                addresses=config.addresses,
                charge_period=charge_period,
                evo_extended=evo_time_group_enabled,
            )
        except ModbusIOException as ex:
            _LOGGER.warning(ex, exc_info=True)
            raise HomeAssistantError(str(ex) or "Modbus IO error writing charge period") from ex
        except ModbusClientFailedError as ex:
            raise HomeAssistantError(str(ex)) from ex

    if evo_style:
        await _maybe_disable_evo_time_group(
            controller, charge_periods, was_enabled=evo_time_group_enabled
        )
