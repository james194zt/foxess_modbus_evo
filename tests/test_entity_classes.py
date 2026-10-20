"""Every sensor's device class, state class and unit must be a combination Home Assistant accepts.

HA only logs these at startup ("is using state class 'measurement' which is impossible considering device class
('energy')"), so check them all here against HA's own tables.
"""

from homeassistant.components.sensor import DEVICE_CLASS_STATE_CLASSES
from homeassistant.components.sensor import DEVICE_CLASS_UNITS
from homeassistant.components.sensor import SensorEntityDescription

from custom_components.foxess_modbus.entities.entity_descriptions import ENTITIES


def _sensor_descriptions() -> list[SensorEntityDescription]:
    return [d for d in ENTITIES if isinstance(d, SensorEntityDescription)]


def test_state_class_fits_device_class() -> None:
    bad = [
        f"{d.key}: {d.device_class} + {d.state_class}"
        for d in _sensor_descriptions()
        if d.device_class is not None
        and d.state_class is not None
        and d.device_class in DEVICE_CLASS_STATE_CLASSES
        and d.state_class not in DEVICE_CLASS_STATE_CLASSES[d.device_class]
    ]
    assert not bad, bad


def test_unit_fits_device_class() -> None:
    bad = [
        f"{d.key}: {d.device_class} in {d.native_unit_of_measurement}"
        for d in _sensor_descriptions()
        if d.device_class is not None
        and d.device_class in DEVICE_CLASS_UNITS
        and d.native_unit_of_measurement not in DEVICE_CLASS_UNITS[d.device_class]
    ]
    assert not bad, bad
