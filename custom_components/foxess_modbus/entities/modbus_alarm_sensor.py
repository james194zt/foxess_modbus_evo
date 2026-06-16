"""Decodes inverter alarm registers (FoxESS protocol section 4.1)."""

from dataclasses import dataclass
from enum import Enum
from typing import Any
from typing import cast

from homeassistant.components.logbook import async_log_entry
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from ..const import DOMAIN
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressesSpec
from .modbus_entity_mixin import ModbusEntityMixin
from .modbus_fault_sensor import FaultSet


# FoxESS Modbus Protocol v1.05.03.00 section 4.1 — alarm bitfields at holding 39067–39069.
FOXESS_INVERTER_ALARMS = FaultSet(
    faults=[
        [
            "PV Over-voltage",
            "DC arc fault",
            "String reverse connection",
            None,
            None,
            None,
            None,
            "Grid power outage",
            "Abnormal grid voltage",
            None,
            None,
            "Abnormal grid frequency",
            None,
            None,
            "Output overcurrent",
            "Output DC component too large",
        ],
        [
            "Residual current",
            "Grounding fault",
            "Low insulation resistance",
            "Inverter overtemperature",
            None,
            None,
            None,
            None,
            None,
            "Energy storage equipment abnormal",
            "Islanding",
            None,
            None,
            None,
            "Off-grid output overload",
            None,
        ],
        [
            None,
            None,
            None,
            "External fan fault",
            "Energy storage reverse connection",
            None,
            None,
            None,
            None,
            "Meter lost",
            "BMS lost",
            None,
            None,
            None,
            None,
            None,
        ],
    ],
    masks={},
)


class AlarmSensorMode(Enum):
    """How the alarm sensor reports state."""

    ACTIVE = "active"
    LAST_EVENT = "last_event"


def decode_active_alarms(
    controller: EntityController, addresses: list[int], alarm_set: FaultSet
) -> set[str] | None:
    """Return the set of active alarm names, or None if any register read failed."""

    active: set[str] = set()
    for i, address in enumerate(addresses):
        value = controller.read(address, signed=False)
        if value is None:
            return None
        if value == 0:
            continue
        for index, alarm_name in enumerate(alarm_set.faults[i]):
            if alarm_name is not None and (value & (1 << index)) > 0:
                active.add(alarm_name)

    to_remove: set[str] = set()
    for alarm in active:
        for mask in alarm_set.masks.get(alarm, []):
            if mask in active:
                to_remove.add(mask)
    return active - to_remove


def format_active_alarms(active: set[str]) -> str:
    if not active:
        return "None"
    return "; ".join(sorted(active))


def format_alarm_event(raised: set[str], cleared: set[str]) -> str:
    parts: list[str] = []
    if raised:
        parts.append(f"Raised: {format_active_alarms(raised)}")
    if cleared:
        parts.append(f"Cleared: {format_active_alarms(cleared)}")
    return "; ".join(parts)


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusAlarmSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """Description for ModbusAlarmSensor"""

    addresses: list[ModbusAddressesSpec]
    alarm_set: FaultSet
    mode: AlarmSensorMode = AlarmSensorMode.ACTIVE

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
        return ModbusAlarmSensor(controller, self, addresses) if addresses is not None else None

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        addresses = self._addresses_for_inverter_model(self.addresses, inverter_model, register_type)
        if addresses is None:
            return None

        return {
            "type": "alarm-sensor",
            "key": self.key,
            "name": self.name,
            "addresses": addresses,
            "mode": self.mode.value,
            "alarms": self.alarm_set.faults,
        }


class ModbusAlarmSensor(ModbusEntityMixin, SensorEntity):
    """Sensor for FoxESS inverter alarm bitfields."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusAlarmSensorDescription,
        addresses: list[int],
    ) -> None:
        assert len(addresses) == len(entity_description.alarm_set.faults)

        self._controller = controller
        self.entity_description = entity_description
        self._addresses = addresses
        self.entity_id = self._get_entity_id(Platform.SENSOR)
        self._previous_active: set[str] = set()
        self._last_event = "None"

    @property
    def addresses(self) -> list[int]:
        return self._addresses

    @property
    def native_value(self) -> str | None:
        entity_description = cast(ModbusAlarmSensorDescription, self.entity_description)
        active = decode_active_alarms(self._controller, self._addresses, entity_description.alarm_set)
        if active is None:
            return None

        if entity_description.mode == AlarmSensorMode.ACTIVE:
            return format_active_alarms(active)

        return self._last_event

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        entity_description = cast(ModbusAlarmSensorDescription, self.entity_description)
        active = decode_active_alarms(self._controller, self._addresses, entity_description.alarm_set)
        if active is None:
            return None

        attributes: dict[str, Any] = {"active_alarms": sorted(active)}
        if entity_description.mode == AlarmSensorMode.LAST_EVENT:
            attributes["last_event"] = self._last_event
        return attributes

    def _address_updated(self) -> None:
        entity_description = cast(ModbusAlarmSensorDescription, self.entity_description)
        active = decode_active_alarms(self._controller, self._addresses, entity_description.alarm_set)
        if active is None:
            self.schedule_update_ha_state()
            return

        raised = active - self._previous_active
        cleared = self._previous_active - active
        self._previous_active = active

        if raised or cleared:
            self._last_event = format_alarm_event(raised, cleared)
            self._log_alarm_changes(raised, cleared, active)
            self._controller.hass.bus.fire(
                f"{DOMAIN}_alarm",
                {
                    "entity_id": self.entity_id,
                    "raised": sorted(raised),
                    "cleared": sorted(cleared),
                    "active": sorted(active),
                },
            )

        if entity_description.mode == AlarmSensorMode.LAST_EVENT and not (raised or cleared):
            return

        self.schedule_update_ha_state()

    def _log_alarm_changes(self, raised: set[str], cleared: set[str], active: set[str]) -> None:
        for alarm in sorted(raised):
            async_log_entry(
                self._controller.hass,
                name=cast(str, self.name),
                message=f"Alarm raised: {alarm}",
                entity_id=self.entity_id,
                domain=DOMAIN,
            )
        for alarm in sorted(cleared):
            async_log_entry(
                self._controller.hass,
                name=cast(str, self.name),
                message=f"Alarm cleared: {alarm}",
                entity_id=self.entity_id,
                domain=DOMAIN,
            )
