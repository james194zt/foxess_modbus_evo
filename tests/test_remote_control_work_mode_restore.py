"""Remote control puts back the work mode it replaced with its fallback when it is disabled.

Values follow the EVO: 49203 uses 1-based codes and reads 255 while under remote control.
"""

from typing import Any

from custom_components.foxess_modbus.common.entity_controller import RemoteControlMode
from custom_components.foxess_modbus.entities.modbus_remote_control_config import ModbusRemoteControlAddressConfig
from custom_components.foxess_modbus.entities.modbus_remote_control_config import WorkMode
from custom_components.foxess_modbus.remote_control_manager import RemoteControlManager

WORK_MODE = 49203
SELF_USE, FEED_IN, BACK_UP = 1, 2, 3

ADDRESSES = ModbusRemoteControlAddressConfig(
    remote_enable=46001,
    timeout_set=46002,
    active_power=[46004, 46003],
    work_mode=WORK_MODE,
    work_mode_map={WorkMode.SELF_USE: SELF_USE, WorkMode.FEED_IN_FIRST: FEED_IN, WorkMode.BACK_UP: BACK_UP},
    battery_soc=[39423],
    max_soc=46610,
    invbatpower=[39238, 39237],
    pwr_limit_bat_up=[46019, 46018],
    pv_voltages=[39070, 39072, 39074],
)


class FakeController:
    def __init__(self, registers: dict[int, int]) -> None:
        self.registers = dict(registers)
        self.is_connected = True
        self.inverter_capacity = 10000

    def register_modbus_entity(self, _entity: Any) -> None:
        pass

    def read(self, address: int | list[int], *, signed: bool) -> int | None:  # noqa: ARG002 — matches the real API
        if isinstance(address, list):
            address = address[0]
        return self.registers.get(address)

    async def write_register(self, address: int, value: int) -> None:
        self.registers[address] = value

    async def write_registers(self, start: int, values: list[int]) -> None:
        for i, value in enumerate(values):
            self.registers[start + i] = value


def _manager(work_mode: int, soc: int = 50) -> tuple[RemoteControlManager, FakeController]:
    controller = FakeController({WORK_MODE: work_mode, 39423: soc, 46610: 100})
    return RemoteControlManager(controller, ADDRESSES, poll_rate=10), controller  # type: ignore[arg-type]


async def test_force_discharge_then_disable_restores_previous_mode() -> None:
    manager, controller = _manager(SELF_USE)

    await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
    assert controller.registers[WORK_MODE] == FEED_IN  # fallback while remote control runs

    await manager.set_mode(RemoteControlMode.DISABLE)
    assert controller.registers[WORK_MODE] == SELF_USE
    assert controller.registers[46001] == 0


async def test_force_charge_then_disable_restores_previous_mode() -> None:
    manager, controller = _manager(FEED_IN)

    await manager.set_mode(RemoteControlMode.FORCE_CHARGE)
    assert controller.registers[WORK_MODE] == BACK_UP

    await manager.set_mode(RemoteControlMode.DISABLE)
    assert controller.registers[WORK_MODE] == FEED_IN


async def test_switching_between_force_modes_keeps_the_original_mode() -> None:
    manager, controller = _manager(SELF_USE)

    await manager.set_mode(RemoteControlMode.FORCE_CHARGE)
    await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
    await manager.set_mode(RemoteControlMode.DISABLE)

    assert controller.registers[WORK_MODE] == SELF_USE


async def test_does_not_restore_remote_control_state_255() -> None:
    # Integration restarted while the inverter was still under remote control
    manager, controller = _manager(255)

    await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
    await manager.set_mode(RemoteControlMode.DISABLE)

    assert controller.registers[WORK_MODE] == FEED_IN  # left on the fallback rather than writing 255
