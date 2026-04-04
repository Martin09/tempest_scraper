"""Alignment test: every sensor value_template field must exist on WeatherData.

This test would have caught the field-name mismatch between sensor.py templates
and the WeatherData model that caused most HA sensors to show 'unavailable'.
"""

from __future__ import annotations

import re
from dataclasses import fields

import pytest

from models import WeatherData
from sensor import BINARY_SENSOR_CONFIGS, SENSOR_CONFIGS

_WEATHER_FIELDS = {f.name for f in fields(WeatherData)}
_ALL_CONFIGS = [*SENSOR_CONFIGS, *BINARY_SENSOR_CONFIGS]


@pytest.mark.parametrize("sensor", _ALL_CONFIGS, ids=lambda s: s.object_id)
def test_value_template_references_valid_field(sensor):
    """Each sensor's value_template must reference an existing WeatherData field."""
    match = re.search(r"value_json\.(\w+)", sensor.value_template)
    assert match, (
        f"Sensor '{sensor.object_id}' value_template has no 'value_json.<field>' reference: {sensor.value_template!r}"
    )
    field_name = match.group(1)
    assert field_name in _WEATHER_FIELDS, (
        f"Sensor '{sensor.object_id}' references field '{field_name}' "
        f"which does not exist on WeatherData. "
        f"Available fields: {sorted(_WEATHER_FIELDS)}"
    )


def test_no_duplicate_object_ids():
    """All sensor object_ids must be unique."""
    all_ids = [s.object_id for s in _ALL_CONFIGS]
    seen = set()
    duplicates = [sid for sid in all_ids if sid in seen or seen.add(sid)]
    assert not duplicates, f"Duplicate sensor object_ids: {duplicates}"


def test_sensor_configs_have_required_fields():
    """Every SensorConfig must have object_id, name, field, and value_template."""
    for sensor in SENSOR_CONFIGS:
        assert sensor.object_id
        assert sensor.name
        assert sensor.field
        assert "value_json." in sensor.value_template


def test_binary_sensor_payload_values():
    """Binary sensors must define non-empty payload_on and payload_off."""
    for bsensor in BINARY_SENSOR_CONFIGS:
        assert bsensor.payload_on, f"{bsensor.object_id} missing payload_on"
        assert bsensor.payload_off, f"{bsensor.object_id} missing payload_off"
        assert bsensor.payload_on != bsensor.payload_off, (
            f"{bsensor.object_id}: payload_on and payload_off are the same"
        )
