"""Grid import/export status from grid CT active power (Fox app: Grid Status)."""

from dataclasses import dataclass
from typing import Any
from typing import cast

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressesSpec
from .modbus_entity_mixin import ModbusEntityMixin

GRID_STATUS_OPTIONS = ("Idle", "Import", "Export")


def grid_status_from_power_kw(power_kw: float, *, threshold_kw: float = 0.02) -> str:
    """Map signed grid CT power to Fox-style grid status labels."""
    if power_kw > threshold_kw:
        return "Export"
    if power_kw < -threshold_kw:
        return "Import"
    return "Idle"


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusGridStatusSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """Description for ModbusGridStatusSensor."""

    addresses: list[ModbusAddressesSpec]
    scale: float
    signed: bool = True
    invert_sign: bool = False
    power_threshold_kw: float = 0.02

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        addresses = self._addresses_for_inverter_model(self.addresses, inverter_model, register_type)
        return ModbusGridStatusSensor(controller, self, addresses) if addresses is not None else None

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        addresses = self._addresses_for_inverter_model(self.addresses, inverter_model, register_type)
        if addresses is None:
            return None

        return {
            "type": "grid_status_sensor",
            "key": self.key,
            "name": self.name,
            "addresses": addresses,
            "scale": self.scale,
            "signed": self.signed,
            "invert_sign": self.invert_sign,
        }


class ModbusGridStatusSensor(ModbusEntityMixin, SensorEntity):
    """Fox app-style grid status (export / import / idle) from grid CT power."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusGridStatusSensorDescription,
        addresses: list[int],
    ) -> None:
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = list(GRID_STATUS_OPTIONS)

        self._controller = controller
        self.entity_description = entity_description
        self._addresses = addresses
        self.entity_id = self._get_entity_id(Platform.SENSOR)

    @property
    def native_value(self) -> str | None:
        entity_description = cast(ModbusGridStatusSensorDescription, self.entity_description)
        raw = self._controller.read(self._addresses, signed=entity_description.signed)
        if raw is None:
            return None
        power_kw = float(raw) * entity_description.scale
        if entity_description.invert_sign:
            power_kw = -power_kw
        return grid_status_from_power_kw(power_kw, threshold_kw=entity_description.power_threshold_kw)

    @property
    def addresses(self) -> list[int]:
        return self._addresses
