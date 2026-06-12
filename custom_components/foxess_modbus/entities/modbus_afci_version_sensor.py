"""AFCI firmware version — address varies on EVO; probe likely holding registers near 36001–36003."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from typing import cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterPollType
from ..common.types import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)

# Holding registers to try after master/slave/manager at 36001–36003.
# 36004 was an unverified guess and returns IllegalAddress on many EVO units.
EVO_AFCI_HOLDING_CANDIDATES: tuple[int, ...] = tuple(range(36004, 36013)) + (
    39004,
    39005,
    39006,
    39007,
    39008,
    39019,
    39020,
)

EVO_AFCI_INPUT_CANDIDATES: tuple[int, ...] = tuple(range(10019, 10024))


def format_afci_version(value: int, *, hex_style: bool) -> str:
    if hex_style:
        major = value >> 8
        minor = value & 0xFF
        return f"{major:X}.{minor:02X}"
    major = value // 100
    minor = value % 100
    return f"{major}.{minor:02d}"


def is_plausible_afci_raw(value: int) -> bool:
    """Reject unrelated registers that decode like versions (e.g. 0x3130 → 31.30)."""
    if value <= 0 or value > 0xFFFF:
        return False
    # PCS-style AFCI versions match manager at 36003 (0x0030 → 0.30): major byte is small.
    return (value >> 8) <= 9


def decode_afci_version_guesses(value: int) -> list[tuple[str, bool]]:
    """Return (formatted, hex_style) pairs that could match Fox Version_AFCI (e.g. 0.37)."""
    if value < 0 or value > 0xFFFF:
        return []
    guesses: list[tuple[str, bool]] = []
    hex_formatted = format_afci_version(value, hex_style=True)
    dec_formatted = format_afci_version(value, hex_style=False)
    for formatted, hex_style in ((hex_formatted, True), (dec_formatted, False)):
        if formatted.count(".") != 1:
            continue
        left, right = formatted.split(".", 1)
        if not left.isalnum() or not right.isalnum():
            continue
        if len(right) not in (2, 3):
            continue
        guesses.append((formatted, hex_style))
    return guesses


def pick_afci_decode(value: int) -> str | None:
    """Prefer PCS-style hex (matches EVO manager 0.30 at 36003)."""
    if not is_plausible_afci_raw(value):
        return None
    guesses = decode_afci_version_guesses(value)
    if not guesses:
        return None
    for formatted, hex_style in guesses:
        if hex_style:
            return formatted
    return guesses[0][0]


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusAfciVersionSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """Description for ModbusAfciVersionSensor."""

    models: Inv

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        if inverter_model not in self.models:
            return None
        return ModbusAfciVersionSensor(controller, self)

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        if inverter_model not in self.models:
            return None
        return {
            "type": "afci_version_sensor",
            "key": self.key,
            "name": self.name,
            "holding_candidates": list(EVO_AFCI_HOLDING_CANDIDATES),
            "input_candidates": list(EVO_AFCI_INPUT_CANDIDATES),
        }


class ModbusAfciVersionSensor(ModbusEntityMixin, SensorEntity):
    """Probe AFCI version registers on connect; only poll the address that responds."""

    def __init__(self, controller: EntityController, entity_description: ModbusAfciVersionSensorDescription) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._address: int | None = None
        self._hex_style = True
        self._probe_done = False
        self._probe_raw: int | None = None
        self.entity_id = self._get_entity_id(Platform.SENSOR)

    @property
    def native_value(self) -> str | None:
        if self._address is None:
            return None
        value = self._controller.read(self._address, signed=False)
        if value is None:
            value = self._probe_raw
        if value is None:
            return None
        return format_afci_version(value, hex_style=self._hex_style)

    @property
    def addresses(self) -> list[int]:
        return [self._address] if self._address is not None else []

    @property
    def register_poll_type(self) -> RegisterPollType:
        return RegisterPollType.ON_CONNECTION

    async def async_added_to_hass(self) -> None:
        await SensorEntity.async_added_to_hass(self)
        self._controller.register_modbus_entity(self)
        if self._controller.is_connected:
            await self._probe_for_address()

    async def async_will_remove_from_hass(self) -> None:
        self._controller.remove_modbus_entity(self)
        await SensorEntity.async_will_remove_from_hass(self)

    def is_connected_changed_callback(self) -> None:
        if self._controller.is_connected and not self._probe_done:
            self.hass.async_create_task(self._probe_for_address())
        self.schedule_update_ha_state()

    async def _probe_for_address(self) -> None:
        if self._probe_done or self._address is not None:
            return
        self._probe_done = True
        controller = cast(Any, self._controller)
        for register_type, candidates in (
            (RegisterType.HOLDING, EVO_AFCI_HOLDING_CANDIDATES),
            (RegisterType.INPUT, EVO_AFCI_INPUT_CANDIDATES),
        ):
            for address in candidates:
                try:
                    values = await controller.read_registers(address, 1, register_type)
                except Exception as ex:
                    _LOGGER.debug("AFCI probe %s %s failed: %s", register_type, address, ex)
                    continue
                if not values:
                    continue
                value = int(values[0])
                if not is_plausible_afci_raw(value):
                    _LOGGER.debug(
                        "AFCI probe skipping %s %s raw=%s (implausible firmware version)",
                        register_type.name,
                        address,
                        value,
                    )
                    continue
                formatted = pick_afci_decode(value)
                if formatted is None:
                    continue
                if register_type is not RegisterType.HOLDING:
                    _LOGGER.debug(
                        "AFCI probe found %s %s=%s (%s) but EVO polling uses holding only; skipping",
                        register_type.name,
                        address,
                        value,
                        formatted,
                    )
                    continue
                self._address = address
                self._probe_raw = value
                self._hex_style = format_afci_version(value, hex_style=True) == formatted
                _LOGGER.info(
                    "AFCI version probe found register %s %s raw=%s -> %s",
                    register_type.name,
                    address,
                    value,
                    formatted,
                )
                self._controller.register_modbus_entity(self)
                self.schedule_update_ha_state()
                return
        _LOGGER.info("AFCI version probe found no readable register on this EVO")
