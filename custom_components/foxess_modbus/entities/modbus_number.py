"""Select"""

import asyncio
import logging
import time
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Callable
from typing import cast

from homeassistant.components.number import NumberEntity
from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.number import NumberMode
from homeassistant.const import Platform
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .base_validator import BaseValidator
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import InverterModelSpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER: logging.Logger = logging.getLogger(__package__)

# Wait before reading a guarded write back
_VERIFY_DELAY_SECS = 1.0


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusNumberDescription(NumberEntityDescription, EntityFactory):  # type: ignore[misc]
    """Custom number entity description"""

    addresses: list[InverterModelSpec]
    mode: NumberMode = NumberMode.AUTO
    scale: float | None = None
    post_process: Callable[[float], float] | None = None
    validate: list[BaseValidator] = field(default_factory=list)
    # Guarded write for settings the inverter probably keeps in flash (installer settings): read the
    # registers live, skip the write if nothing changes, refuse writes closer together than this many
    # seconds, and read back afterwards. None = plain write every time.
    min_write_interval: float | None = None
    # (start, count): the inverter only accepts these registers as part of this whole block, so read the
    # block live, replace our registers in it and write it back in one go. Implies a guarded write.
    write_block: tuple[int, int] | None = None

    @property
    def entity_type(self) -> type[Entity]:
        return NumberEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        addresses = self._addresses_for_inverter_model(self.addresses, inverter_model, register_type)
        return ModbusNumber(controller, self, addresses, register_type) if addresses is not None else None

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        addresses = self._addresses_for_inverter_model(self.addresses, inverter_model, register_type)
        if addresses is None:
            return None

        return {
            "type": "number",
            "key": self.key,
            "name": self.name,
            "addresses": addresses,
            "scale": self.scale,
        }


class ModbusNumber(ModbusEntityMixin, NumberEntity):
    """Number class"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusNumberDescription,
        addresses: list[int],
        register_type: RegisterType = RegisterType.HOLDING,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._addresses = addresses
        self._register_type = register_type
        self._pending_value: float | None = None
        self._last_write: float | None = None
        self.entity_id = self._get_entity_id(Platform.NUMBER)

    @property
    def native_value(self) -> int | float | None:
        """Return the value reported by the sensor."""
        if self._pending_value is not None:
            return self._pending_value
        entity_description = cast(ModbusNumberDescription, self.entity_description)
        value: float | int | None = self._controller.read(self._addresses, signed=False)
        original = value
        if value is None:
            return None
        if entity_description.scale is not None:
            value = value * entity_description.scale
        if entity_description.post_process is not None:
            value = entity_description.post_process(float(value))
        if not self._validate(entity_description.validate, value, original):
            return None

        return value

    @property
    def mode(self) -> NumberMode:
        return cast(ModbusNumberDescription, self.entity_description).mode

    async def async_set_native_value(self, value: float) -> None:
        entity_description = cast(ModbusNumberDescription, self.entity_description)
        if (
            self.entity_description.native_min_value is not None
            and self.entity_description.native_max_value is not None
        ):
            value = max(
                self.entity_description.native_min_value,
                min(self.entity_description.native_max_value, value),
            )

        # Show the new value immediately in the UI. Without this, if a poll fires
        # during a slow write (~10s for some KH_133 registers), native_value would
        # return the stale read_value and the UI would jump back to the old value.
        self._pending_value = value
        self.async_write_ha_state()

        try:
            if entity_description.scale is not None:
                value = value / entity_description.scale

            int_value = int(round(value))

            if entity_description.min_write_interval is not None or entity_description.write_block is not None:
                await self._guarded_write(entity_description, int_value)
            elif len(self._addresses) == 1:
                await self._controller.write_register(self._addresses[0], int_value)
            else:
                # I32: self._addresses follows read() convention: [low_word_reg, high_word_reg]
                # write_registers(start, [v0, v1]) writes v0→start, v1→start+1
                # so start from the high-word register (index 1) and write [hi, lo]
                high_word_reg = self._addresses[1]
                hi = (int_value >> 16) & 0xFFFF
                lo = int_value & 0xFFFF
                await self._controller.write_registers(high_word_reg, [hi, lo])
        finally:
            self._pending_value = None
            self.async_write_ha_state()

    def _target_words(self, int_value: int) -> dict[int, int]:
        """Register address -> raw word to write"""
        if len(self._addresses) == 1:
            return {self._addresses[0]: int_value & 0xFFFF}
        # [low_word_reg, high_word_reg]
        return {self._addresses[1]: (int_value >> 16) & 0xFFFF, self._addresses[0]: int_value & 0xFFFF}

    async def _read_live(self, start: int, count: int) -> list[int]:
        try:
            return await self._controller.read_registers(start, count, self._register_type)
        except Exception as ex:
            raise HomeAssistantError(f"{self.name}: couldn't read registers {start}-{start + count - 1}: {ex}") from ex

    async def _guarded_write(self, entity_description: ModbusNumberDescription, int_value: int) -> None:
        target = self._target_words(int_value)
        if entity_description.write_block is not None:
            start, count = entity_description.write_block
        else:
            start, count = min(target), len(target)

        current = await self._read_live(start, count)
        values = list(current)
        for address, word in target.items():
            values[address - start] = word
        if values == current:
            _LOGGER.debug("%s: already %s, not writing", self.name, int_value)
            return

        interval = entity_description.min_write_interval
        if interval is not None and self._last_write is not None:
            wait = interval - (time.monotonic() - self._last_write)
            if wait > 0:
                raise HomeAssistantError(
                    f"{self.name} was changed less than {interval:.0f} s ago; try again in {wait:.0f} s "
                    "(limited to protect the inverter's settings memory)"
                )

        self._last_write = time.monotonic()
        try:
            await self._controller.write_registers(start, values)
        except Exception as ex:
            raise HomeAssistantError(f"{self.name}: the inverter refused the write: {ex}") from ex

        await asyncio.sleep(_VERIFY_DELAY_SECS)
        actual = await self._read_live(start, count)
        if any(actual[address - start] != word for address, word in target.items()):
            raise HomeAssistantError(f"{self.name}: wrote {int_value} but the inverter reads back something else")

    @property
    def addresses(self) -> list[int]:
        return self._addresses
