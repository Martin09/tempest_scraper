"""Home Assistant MQTT discovery configuration for WeatherData sensors.

Uses typed dataclasses instead of raw dicts so typos are caught at definition time.
value_template is auto-generated from the field name — no duplication.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SensorConfig:
    """Config for a standard (numeric/text) HA sensor."""

    object_id: str
    name: str
    field: str  # Matches the WeatherData attribute name exactly
    device_class: str | None = None
    state_class: str | None = None
    unit_of_measurement: str | None = None

    @property
    def value_template(self) -> str:
        return f"{{{{ value_json.{self.field} }}}}"


@dataclass(frozen=True)
class BinarySensorConfig:
    """Config for a boolean HA binary_sensor."""

    object_id: str
    name: str
    field: str  # Matches the WeatherData attribute name exactly
    device_class: str | None = None
    # Python's json.dumps serialises True/False → true/false (JSON).
    # HA Jinja2 renders {{ value_json.bool_field }} as "True" / "False".
    payload_on: str = "True"
    payload_off: str = "False"

    @property
    def value_template(self) -> str:
        return f"{{{{ value_json.{self.field} }}}}"


SENSOR_CONFIGS: list[SensorConfig] = [
    SensorConfig(
        object_id="temperature", name="Temperature", field="temperature",
        device_class="temperature", state_class="measurement", unit_of_measurement="°C",
    ),
    SensorConfig(
        object_id="humidity", name="Humidity", field="humidity",
        device_class="humidity", state_class="measurement", unit_of_measurement="%",
    ),
    SensorConfig(
        object_id="dew_point", name="Dew Point", field="dew_point",
        device_class="temperature", state_class="measurement", unit_of_measurement="°C",
    ),
    SensorConfig(
        object_id="sea_level_pressure", name="Sea Level Pressure", field="sea_level_pressure",
        device_class="pressure", state_class="measurement", unit_of_measurement="mbar",
    ),
    SensorConfig(
        object_id="station_pressure", name="Station Pressure", field="station_pressure",
        device_class="pressure", state_class="measurement", unit_of_measurement="mbar",
    ),
    SensorConfig(
        object_id="pressure_trend", name="Pressure Trend", field="pressure_trend",
    ),
    SensorConfig(
        object_id="wind_speed", name="Wind Speed", field="wind_speed",
        device_class="wind_speed", state_class="measurement", unit_of_measurement="km/h",
    ),
    SensorConfig(
        object_id="wind_gust", name="Wind Gust", field="wind_gust",
        device_class="wind_speed", state_class="measurement", unit_of_measurement="km/h",
    ),
    SensorConfig(
        object_id="wind_lull", name="Wind Lull", field="wind_lull",
        device_class="wind_speed", state_class="measurement", unit_of_measurement="km/h",
    ),
    SensorConfig(
        object_id="wind_direction", name="Wind Direction", field="wind_direction",
        unit_of_measurement="°",
    ),
    SensorConfig(
        object_id="wind_cardinal", name="Wind Cardinal", field="wind_cardinal",
    ),
    SensorConfig(
        object_id="precipitation_rate", name="Precipitation Rate", field="precipitation_rate",
        state_class="measurement", unit_of_measurement="mm/h",
    ),
    # total_increasing: accumulates during the day, resets at midnight — HA handles the reset
    SensorConfig(
        object_id="precipitation_today", name="Precipitation Today", field="precipitation_today",
        state_class="total_increasing", unit_of_measurement="mm",
    ),
    # measurement: a fixed snapshot of the previous day's total
    SensorConfig(
        object_id="precipitation_yesterday", name="Precipitation Yesterday",
        field="precipitation_yesterday", state_class="measurement", unit_of_measurement="mm",
    ),
    SensorConfig(
        object_id="precipitation_duration_today", name="Precip Duration Today",
        field="precipitation_duration_today", state_class="measurement", unit_of_measurement="min",
    ),
    SensorConfig(
        object_id="precipitation_duration_yesterday", name="Precip Duration Yesterday",
        field="precipitation_duration_yesterday", state_class="measurement", unit_of_measurement="min",
    ),
    SensorConfig(
        object_id="precipitation_description", name="Precipitation Description",
        field="precipitation_description",
    ),
    SensorConfig(
        object_id="uv_index", name="UV Index", field="uv_index",
        state_class="measurement",
    ),
    SensorConfig(
        object_id="solar_radiation", name="Solar Radiation", field="solar_radiation",
        state_class="measurement", unit_of_measurement="W/m²",
    ),
    SensorConfig(
        object_id="illuminance", name="Illuminance", field="illuminance",
        device_class="illuminance", state_class="measurement", unit_of_measurement="lx",
    ),
    SensorConfig(
        object_id="voltage", name="Battery Voltage", field="voltage",
        device_class="voltage", state_class="measurement", unit_of_measurement="V",
    ),
    SensorConfig(
        object_id="power_save_mode", name="Power Save Mode", field="power_save_mode",
    ),
    SensorConfig(
        object_id="wet_bulb_temperature", name="Wet Bulb Temperature", field="wet_bulb_temperature",
        device_class="temperature", state_class="measurement", unit_of_measurement="°C",
    ),
    SensorConfig(
        object_id="wet_bulb_globe_temperature", name="WBGT", field="wet_bulb_globe_temperature",
        device_class="temperature", state_class="measurement", unit_of_measurement="°C",
    ),
    SensorConfig(
        object_id="delta_t", name="Delta T", field="delta_t",
        device_class="temperature", state_class="measurement", unit_of_measurement="°C",
    ),
    SensorConfig(
        object_id="time_of_last_lightning_strike", name="Time of Last Lightning Strike",
        field="time_of_last_lightning_strike", device_class="timestamp",
    ),
    SensorConfig(
        object_id="distance_last_lightning_strike", name="Distance Last Lightning Strike",
        field="distance_last_lightning_strike",
    ),
    SensorConfig(
        object_id="lightning_strikes_last_3_hours", name="Lightning Strikes Last 3h",
        field="lightning_strikes_last_3_hours", state_class="measurement",
    ),
]

BINARY_SENSOR_CONFIGS: list[BinarySensorConfig] = [
    BinarySensorConfig(
        object_id="is_raining", name="Is Raining", field="is_raining",
        device_class="moisture",
    ),
    BinarySensorConfig(
        object_id="is_freezing", name="Is Freezing", field="is_freezing",
        device_class="cold",
    ),
    BinarySensorConfig(
        object_id="is_lightning", name="Is Lightning", field="is_lightning",
        device_class="safety",
    ),
]
