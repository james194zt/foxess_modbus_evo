"""Sensor for calculated battery Ah remaining from SoC and nominal capacity registers."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .validation import Min
from .validation import Range
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .inverter_model_spec import ModbusAddressSpec
from .modbus_entity_mixin import ModbusEntityMixin


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusBatteryAhRemainingSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """Remaining Ah from SoC % and Fox nominal capacity register (37616)."""

    models: list[EntitySpec]
    soc_address: list[ModbusAddressSpec]
    capacity_address: list[ModbusAddressSpec]
    bms_connect_state_address: list[ModbusAddressSpec]
    capacity_scale: float = 0.1

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        soc_address = self._address_for_inverter_model(self.soc_address, inverter_model, register_type)
        capacity_address = self._address_for_inverter_model(self.capacity_address, inverter_model, register_type)
        bms_connect_state_address = self._address_for_inverter_model(
            self.bms_connect_state_address, inverter_model, register_type
        )
        if soc_address is None or capacity_address is None or bms_connect_state_address is None:
            return None

        return ModbusBatteryAhRemainingSensor(
            controller=controller,
            entity_description=self,
            soc_address=soc_address,
            capacity_address=capacity_address,
            bms_connect_state_address=bms_connect_state_address,
            capacity_scale=self.capacity_scale,
        )


class ModbusBatteryAhRemainingSensor(ModbusEntityMixin, SensorEntity):
    """Remaining battery capacity (Ah) from SoC and nominal Ah register."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusBatteryAhRemainingSensorDescription,
        soc_address: int,
        capacity_address: int,
        bms_connect_state_address: int,
        capacity_scale: float,
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._soc_address = soc_address
        self._capacity_address = capacity_address
        self._bms_connect_state_address = bms_connect_state_address
        self._capacity_scale = capacity_scale

    @property
    def native_value(self) -> float | None:
        bms_connect_state = self._controller.read(self._bms_connect_state_address, signed=False)
        if bms_connect_state == 0 or bms_connect_state == 2:
            return None

        soc = self._controller.read(self._soc_address, signed=False)
        capacity_raw = self._controller.read(self._capacity_address, signed=False)
        if soc is None or capacity_raw is None:
            return None

        if not self._validate([Range(0, 100)], soc, soc, address_override=self._soc_address):
            return None
        if not self._validate([Min(0)], capacity_raw, capacity_raw, address_override=self._capacity_address):
            return None

        capacity_ah = capacity_raw * self._capacity_scale
        return round(soc / 100 * capacity_ah, 1)

    @property
    def addresses(self) -> list[int]:
        return [self._soc_address, self._capacity_address, self._bms_connect_state_address]
