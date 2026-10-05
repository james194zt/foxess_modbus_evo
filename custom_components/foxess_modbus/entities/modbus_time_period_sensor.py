"""A time period stored as three registers: enable, start, end (each time is hour * 256 + minute)."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressSpec
from .modbus_entity_mixin import ModbusEntityMixin

PERIOD_OFF = "Off"


def decode_time_period(enable: int, start: int, end: int) -> str | None:
    """'01:11-02:22', 'Off' if disabled, or None if a time isn't valid."""
    if not enable:
        return PERIOD_OFF
    times = []
    for value in (start, end):
        hour, minute = value >> 8, value & 0xFF
        if hour > 23 or minute > 59:
            return None
        times.append(f"{hour:02d}:{minute:02d}")
    return f"{times[0]}-{times[1]}"


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusTimePeriodSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """Description for ModbusTimePeriodSensor. The address is the enable register; start and end follow it."""

    address: list[ModbusAddressSpec]

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusTimePeriodSensor(controller, self, address) if address is not None else None

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        if address is None:
            return None

        return {
            "type": "time_period_sensor",
            "key": self.key,
            "name": self.name,
            "addresses": [address, address + 1, address + 2],
        }


class ModbusTimePeriodSensor(ModbusEntityMixin, SensorEntity):
    """Shows an enable/start/end register triple as e.g. '01:11-02:22', or 'Off'."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusTimePeriodSensorDescription,
        address: int,
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._address = address
        self.entity_id = self._get_entity_id(Platform.SENSOR)

    @property
    def native_value(self) -> str | None:
        values = [self._controller.read(address, signed=False) for address in self.addresses]
        if any(value is None for value in values):
            return None
        enable, start, end = (int(value) for value in values if value is not None)
        return decode_time_period(enable, start, end)

    @property
    def addresses(self) -> list[int]:
        return [self._address, self._address + 1, self._address + 2]
