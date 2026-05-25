"""Sensor for calculated battery cycle count from charge/discharge totals and nameplate capacity."""

import math
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .validation import Min
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .inverter_model_spec import ModbusAddressSpec
from .inverter_model_spec import ModbusAddressesSpec
from .modbus_entity_mixin import ModbusEntityMixin


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusBatteryCyclesSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """Description for a sensor which calculates battery cycles from energy throughput registers."""

    models: list[EntitySpec]
    charge_total_address: list[ModbusAddressesSpec]
    discharge_total_address: list[ModbusAddressesSpec]
    capacity_address: list[ModbusAddressSpec]
    bms_connect_state_address: list[ModbusAddressSpec]
    energy_scale: float = 0.01
    capacity_scale: float = 0.01

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        charge_total_address = self._addresses_for_inverter_model(
            self.charge_total_address, inverter_model, register_type
        )
        discharge_total_address = self._addresses_for_inverter_model(
            self.discharge_total_address, inverter_model, register_type
        )
        capacity_address = self._address_for_inverter_model(self.capacity_address, inverter_model, register_type)
        bms_connect_state_address = self._address_for_inverter_model(
            self.bms_connect_state_address, inverter_model, register_type
        )
        if (
            charge_total_address is None
            or discharge_total_address is None
            or capacity_address is None
            or bms_connect_state_address is None
        ):
            return None

        return ModbusBatteryCyclesSensor(
            controller=controller,
            entity_description=self,
            charge_total_address=charge_total_address,
            discharge_total_address=discharge_total_address,
            capacity_address=capacity_address,
            bms_connect_state_address=bms_connect_state_address,
            energy_scale=self.energy_scale,
            capacity_scale=self.capacity_scale,
        )

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        charge_total_address = self._addresses_for_inverter_model(
            self.charge_total_address, inverter_model, register_type
        )
        discharge_total_address = self._addresses_for_inverter_model(
            self.discharge_total_address, inverter_model, register_type
        )
        capacity_address = self._address_for_inverter_model(self.capacity_address, inverter_model, register_type)
        if charge_total_address is None or discharge_total_address is None or capacity_address is None:
            return None

        return {
            "type": "sensor",
            "key": self.key,
            "name": self.name,
            "addresses": charge_total_address + discharge_total_address + [capacity_address],
            "scale": self.energy_scale,
            "signed": False,
        }


class ModbusBatteryCyclesSensor(ModbusEntityMixin, SensorEntity):
    """Battery cycle count derived from total charge/discharge energy and nameplate capacity."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusBatteryCyclesSensorDescription,
        charge_total_address: list[int],
        discharge_total_address: list[int],
        capacity_address: int,
        bms_connect_state_address: int,
        energy_scale: float,
        capacity_scale: float,
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._charge_total_address = charge_total_address
        self._discharge_total_address = discharge_total_address
        self._capacity_address = capacity_address
        self._bms_connect_state_address = bms_connect_state_address
        self._energy_scale = energy_scale
        self._capacity_scale = capacity_scale

    @property
    def native_value(self) -> int | None:
        bms_connect_state = self._controller.read(self._bms_connect_state_address, signed=False)
        if bms_connect_state == 0 or bms_connect_state == 2:
            return None

        charge_raw = self._controller.read(self._charge_total_address, signed=False)
        discharge_raw = self._controller.read(self._discharge_total_address, signed=False)
        capacity_raw = self._controller.read(self._capacity_address, signed=False)
        if charge_raw is None or discharge_raw is None or capacity_raw is None:
            return None

        if not self._validate([Min(0)], charge_raw, charge_raw, address_override=self._charge_total_address[0]):
            return None
        if not self._validate(
            [Min(0)], discharge_raw, discharge_raw, address_override=self._discharge_total_address[0]
        ):
            return None
        if not self._validate([Min(0)], capacity_raw, capacity_raw, address_override=self._capacity_address):
            return None

        charge_kwh = charge_raw * self._energy_scale
        discharge_kwh = discharge_raw * self._energy_scale
        capacity_kwh = capacity_raw * self._capacity_scale
        if capacity_kwh <= 0:
            return None

        # Fox app shows whole cycles (truncates); round() can read one high vs the app.
        return math.floor((charge_kwh + discharge_kwh) / (capacity_kwh * 2))

    @property
    def addresses(self) -> list[int]:
        return (
            self._charge_total_address
            + self._discharge_total_address
            + [self._capacity_address, self._bms_connect_state_address]
        )
