from unittest.mock import MagicMock

from custom_components.foxess_modbus.entities.modbus_alarm_sensor import FOXESS_INVERTER_ALARMS
from custom_components.foxess_modbus.entities.modbus_alarm_sensor import AlarmSensorMode
from custom_components.foxess_modbus.entities.modbus_alarm_sensor import ModbusAlarmSensor
from custom_components.foxess_modbus.entities.modbus_alarm_sensor import ModbusAlarmSensorDescription
from custom_components.foxess_modbus.entities.modbus_alarm_sensor import decode_active_alarms
from custom_components.foxess_modbus.entities.modbus_alarm_sensor import format_active_alarms
from custom_components.foxess_modbus.entities.modbus_alarm_sensor import format_alarm_event


def test_decode_active_alarms() -> None:
    controller = MagicMock()
    controller.read.side_effect = [0x0080, 0, 0x0200]  # grid outage; meter lost

    active = decode_active_alarms(controller, [39067, 39068, 39069], FOXESS_INVERTER_ALARMS)

    assert active == {"Grid power outage", "Meter lost"}


def test_format_active_alarms() -> None:
    assert format_active_alarms(set()) == "None"
    assert format_active_alarms({"BMS lost", "Meter lost"}) == "BMS lost; Meter lost"


def test_format_alarm_event() -> None:
    assert format_alarm_event({"Meter lost"}, set()) == "Raised: Meter lost"
    assert format_alarm_event(set(), {"Meter lost"}) == "Cleared: Meter lost"


def test_alarm_sensor_records_last_event_only_on_change() -> None:
    controller = MagicMock()
    controller.hass = MagicMock()
    controller.hass.bus = MagicMock()
    poll = {"n": 0}

    def mock_read(address, signed=False):
        if address == 39069 and poll["n"] >= 1:
            return 0x0200
        return 0

    controller.read.side_effect = mock_read

    description = ModbusAlarmSensorDescription(
        key="inverter_alarm_last",
        addresses=[],
        alarm_set=FOXESS_INVERTER_ALARMS,
        mode=AlarmSensorMode.LAST_EVENT,
        name="Inverter Alarm Last Event",
    )
    sensor = ModbusAlarmSensor(controller, description, [39067, 39068, 39069])
    sensor.entity_id = "sensor.inverter_alarm_last"
    sensor.schedule_update_ha_state = MagicMock()

    # Published once at start so it doesn't sit at "unknown", then only on a change
    sensor._address_updated()
    assert sensor.native_value == "None"
    assert sensor.schedule_update_ha_state.call_count == 1
    sensor._address_updated()
    assert sensor.schedule_update_ha_state.call_count == 1

    poll["n"] = 1
    sensor._address_updated()
    assert sensor.native_value == "Raised: Meter lost"
    assert sensor.schedule_update_ha_state.call_count == 2
    controller.hass.bus.fire.assert_called_once()

    sensor._address_updated()
    assert sensor.native_value == "Raised: Meter lost"
    assert sensor.schedule_update_ha_state.call_count == 2


def test_alarm_sensor_state_survives_a_restart() -> None:
    controller = MagicMock()
    controller.read.side_effect = lambda address, signed=False: 0x0200 if address == 39069 else 0  # meter lost
    description = ModbusAlarmSensorDescription(
        key="inverter_alarm_last",
        addresses=[],
        alarm_set=FOXESS_INVERTER_ALARMS,
        mode=AlarmSensorMode.LAST_EVENT,
        name="Inverter Alarm Last Event",
    )
    before = ModbusAlarmSensor(controller, description, [39067, 39068, 39069])
    before.entity_id = "sensor.inverter_alarm_last"
    before.schedule_update_ha_state = MagicMock()
    before._address_updated()
    saved = before.extra_restore_state_data.as_dict()
    assert saved == {"last_event": "Raised: Meter lost", "previous_active": ["Meter lost"]}

    # After the restart the still-active alarm isn't announced again
    after = ModbusAlarmSensor(controller, description, [39067, 39068, 39069])
    after.entity_id = "sensor.inverter_alarm_last"
    after.schedule_update_ha_state = MagicMock()
    after._last_event, after._previous_active = saved["last_event"], set(saved["previous_active"])
    after._address_updated()
    assert after.native_value == "Raised: Meter lost"
    controller.hass.bus.fire.assert_called_once()  # only the original raise, from `before`
