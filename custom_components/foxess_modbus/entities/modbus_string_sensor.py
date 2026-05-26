"""Read ASCII strings from consecutive Modbus holding registers (FoxESS packed format)."""

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
from .inverter_model_spec import ModbusAddressSpec
from .modbus_entity_mixin import ModbusEntityMixin


def decode_foxess_ascii_registers(registers: list[int]) -> str:
    """Decode FoxESS string registers (one or two ASCII chars per 16-bit register)."""
    if not registers:
        return ""

    chars: list[str] = []
    packed = (registers[0] & 0xFF00) != 0

    if packed:
        for register in registers:
            if register == 0:
                break
            hi = (register >> 8) & 0xFF
            lo = register & 0xFF
            if lo == 0:
                # Padding (e.g. 0x3500): trailing digit/letter in high byte; skip 0x3000 null pad
                if 0x31 <= hi < 0x7F:
                    chars.append(chr(hi))
                break
            if 0x20 <= hi < 0x7F:
                chars.append(chr(hi))
            else:
                break
            if 0x20 <= lo < 0x7F:
                chars.append(chr(lo))
            else:
                break
        return "".join(chars).strip()

    for register in registers:
        if register == 0:
            break
        if 0x20 <= register < 0x7F:
            chars.append(chr(register))
        else:
            break
    return "".join(chars).strip()


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusStringSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """Description for ModbusStringSensor"""

    address: list[ModbusAddressSpec]
    register_count: int = 16

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        start = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusStringSensor(controller, self, start) if start is not None else None

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        start = self._address_for_inverter_model(self.address, inverter_model, register_type)
        if start is None:
            return None

        return {
            "type": "string_sensor",
            "key": self.key,
            "name": self.name,
            "addresses": list(range(start, start + self.register_count)),
            "register_count": self.register_count,
        }


class ModbusStringSensor(ModbusEntityMixin, SensorEntity):
    """Sensor for a FoxESS ASCII string in holding registers."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusStringSensorDescription,
        start_address: int,
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._start_address = start_address
        self._register_count = entity_description.register_count
        self.entity_id = self._get_entity_id(Platform.SENSOR)

    @property
    def native_value(self) -> str | None:
        registers: list[int] = []
        for offset in range(self._register_count):
            value = self._controller.read(self._start_address + offset, signed=False)
            if value is None:
                return None
            registers.append(value)
        return decode_foxess_ascii_registers(registers) or None

    @property
    def addresses(self) -> list[int]:
        return list(range(self._start_address, self._start_address + self._register_count))

    @property
    def register_poll_type(self) -> RegisterPollType:
        return RegisterPollType.ON_CONNECTION


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusProtocolVersionSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """FoxESS 32-bit protocol version at two consecutive holding registers (39000–39001)."""

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
        start = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusProtocolVersionSensor(controller, self, start) if start is not None else None

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        start = self._address_for_inverter_model(self.address, inverter_model, register_type)
        if start is None:
            return None

        return {
            "type": "protocol_version_sensor",
            "key": self.key,
            "name": self.name,
            "addresses": [start, start + 1],
        }


class ModbusProtocolVersionSensor(ModbusEntityMixin, SensorEntity):
    """Sensor for FoxESS Modbus protocol version (U32 → Vx.yy.zz.ww)."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusProtocolVersionSensorDescription,
        start_address: int,
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._start_address = start_address
        self.entity_id = self._get_entity_id(Platform.SENSOR)

    @property
    def native_value(self) -> str | None:
        hi = self._controller.read(self._start_address, signed=False)
        lo = self._controller.read(self._start_address + 1, signed=False)
        if hi is None or lo is None:
            return None
        version = ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)
        b0 = (version >> 24) & 0xFF
        b1 = (version >> 16) & 0xFF
        b2 = (version >> 8) & 0xFF
        b3 = version & 0xFF
        return f"V{b0}.{b1:02d}.{b2:02d}.{b3:02d}"

    @property
    def addresses(self) -> list[int]:
        return [self._start_address, self._start_address + 1]

    @property
    def register_poll_type(self) -> RegisterPollType:
        return RegisterPollType.ON_CONNECTION
