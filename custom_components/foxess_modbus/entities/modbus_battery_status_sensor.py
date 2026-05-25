"""Sensor for battery operating status derived from inverter battery power registers."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .validation import Range
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .inverter_model_spec import ModbusAddressSpec
from .inverter_model_spec import ModbusAddressesSpec
from .modbus_entity_mixin import ModbusEntityMixin

_STATUS_ICONS = {
    "Charging": "mdi:battery-arrow-up",
    "Discharging": "mdi:battery-arrow-down",
    "Idle": "mdi:battery",
}


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusBatteryStatusSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """Description for a sensor which reports Charging / Discharging / Idle from battery power."""

    models: list[EntitySpec]
    power_address: list[ModbusAddressesSpec]
    bms_connect_state_address: list[ModbusAddressSpec]
    power_scale: float = 0.001
    power_threshold_kw: float = 0.01

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        power_address = self._addresses_for_inverter_model(self.power_address, inverter_model, register_type)
        bms_connect_state_address = self._address_for_inverter_model(
            self.bms_connect_state_address, inverter_model, register_type
        )
        if power_address is None or bms_connect_state_address is None:
            return None

        return ModbusBatteryStatusSensor(
            controller=controller,
            entity_description=self,
            power_address=power_address,
            bms_connect_state_address=bms_connect_state_address,
            power_scale=self.power_scale,
            power_threshold_kw=self.power_threshold_kw,
        )

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        power_address = self._addresses_for_inverter_model(self.power_address, inverter_model, register_type)
        if power_address is None:
            return None

        return {
            "type": "sensor",
            "key": self.key,
            "name": self.name,
            "addresses": power_address,
            "scale": self.power_scale,
            "signed": True,
        }


class ModbusBatteryStatusSensor(ModbusEntityMixin, SensorEntity):
    """Battery status from signed inverter battery power (positive = discharge, negative = charge)."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusBatteryStatusSensorDescription,
        power_address: list[int],
        bms_connect_state_address: int,
        power_scale: float,
        power_threshold_kw: float,
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._power_address = power_address
        self._bms_connect_state_address = bms_connect_state_address
        self._power_scale = power_scale
        self._power_threshold_kw = power_threshold_kw

    @property
    def native_value(self) -> str | None:
        bms_connect_state = self._controller.read(self._bms_connect_state_address, signed=False)
        if bms_connect_state == 0 or bms_connect_state == 2:
            return None

        power_raw = self._controller.read(self._power_address, signed=True)
        if power_raw is None:
            return None

        if not self._validate(
            [Range(-100, 100)],
            power_raw,
            power_raw,
            address_override=self._power_address[0],
        ):
            return None

        power_kw = power_raw * self._power_scale
        if power_kw > self._power_threshold_kw:
            return "Discharging"
        if power_kw < -self._power_threshold_kw:
            return "Charging"
        return "Idle"

    @property
    def icon(self) -> str | None:
        status = self.native_value
        if status is None:
            return self.entity_description.icon
        return _STATUS_ICONS.get(status, self.entity_description.icon)

    @property
    def addresses(self) -> list[int]:
        return self._power_address + [self._bms_connect_state_address]
