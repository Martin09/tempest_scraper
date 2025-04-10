"""
Defines Home Assistant MQTT discovery configs for WeatherData fields.

SENSOR_CONFIGS: Standard numeric/text sensors
BINARY_SENSOR_CONFIGS: Boolean sensors (is_raining, is_freezing, etc.)
"""

SENSOR_CONFIGS = [
    {
        # Air temperature
        "object_id": "temperature",
        "name": "Temperature",
        "field": "temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
        "value_template": "{{ value_json.temperature }}",
    },
    {
        # Relative humidity
        "object_id": "humidity",
        "name": "Humidity",
        "field": "humidity",
        "device_class": "humidity",
        "state_class": "measurement",
        "unit_of_measurement": "%",
        "value_template": "{{ value_json.humidity }}",
    },
    {
        # Dew point temperature
        "object_id": "dew_point",
        "name": "Dew Point",
        "field": "dew_point",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
        "value_template": "{{ value_json.dew_point }}",
    },
    {
        # Sea-level pressure (mbar)
        "object_id": "sea_level_pressure",
        "name": "Sea Level Pressure",
        "field": "sea_level_pressure",
        "device_class": "pressure",
        "state_class": "measurement",
        "unit_of_measurement": "mbar",
        "value_template": "{{ value_json.sea_level_pressure }}",
    },
    {
        # Station pressure
        "object_id": "station_pressure",
        "name": "Station Pressure",
        "field": "station_pressure",
        "device_class": "pressure",
        "state_class": "measurement",
        "unit_of_measurement": "mbar",
        "value_template": "{{ value_json.station_pressure }}",
    },
    {
        # Pressure trend (string: "Rising", "Falling", etc.)
        "object_id": "pressure_trend",
        "name": "Pressure Trend",
        "field": "pressure_trend",
        "value_template": "{{ value_json.pressure_trend }}",
    },
    {
        # Average wind speed
        "object_id": "wind_speed",
        "name": "Wind Speed",
        "field": "wind_speed",
        "state_class": "measurement",
        "unit_of_measurement": "km/h",
        "value_template": "{{ value_json.wind_speed }}",
    },
    {
        # Wind gust
        "object_id": "wind_gust",
        "name": "Wind Gust",
        "field": "wind_gust",
        "state_class": "measurement",
        "unit_of_measurement": "km/h",
        "value_template": "{{ value_json.wind_gust }}",
    },
    {
        # Wind lull
        "object_id": "wind_lull",
        "name": "Wind Lull",
        "field": "wind_lull",
        "state_class": "measurement",
        "unit_of_measurement": "km/h",
        "value_template": "{{ value_json.wind_lull }}",
    },
    {
        # Wind direction (degrees)
        "object_id": "wind_direction",
        "name": "Wind Direction",
        "field": "wind_direction",
        "unit_of_measurement": "°",
        "value_template": "{{ value_json.wind_direction }}",
    },
    {
        # Wind direction cardinal (e.g. "NNE", "SW")
        "object_id": "wind_cardinal",
        "name": "Wind Cardinal",
        "field": "wind_cardinal",
        "value_template": "{{ value_json.wind_cardinal }}",
    },
    {
        # Current precipitation rate (mm/hr)
        "object_id": "precipitation_rate",
        "name": "Precipitation Rate",
        "field": "precipitation_rate",
        "state_class": "measurement",
        "unit_of_measurement": "mm/hr",
        "value_template": "{{ value_json.precipitation_rate }}",
    },
    {
        # Total precipitation recorded today
        "object_id": "precipitation_today",
        "name": "Precipitation Today",
        "field": "precipitation_today",
        "state_class": "total",
        "unit_of_measurement": "mm",
        "value_template": "{{ value_json.precipitation_today }}",
    },
    {
        # Total precipitation recorded yesterday
        "object_id": "precipitation_yesterday",
        "name": "Precipitation Yesterday",
        "field": "precipitation_yesterday",
        "state_class": "total",
        "unit_of_measurement": "mm",
        "value_template": "{{ value_json.precipitation_yesterday }}",
    },
    {
        # Duration of precipitation today (minutes)
        "object_id": "precipitation_duration_today",
        "name": "Precip Duration Today",
        "field": "precipitation_duration_today",
        "state_class": "measurement",
        "unit_of_measurement": "min",
        "value_template": "{{ value_json.precipitation_duration_today }}",
    },
    {
        # Duration of precipitation yesterday (minutes)
        "object_id": "precipitation_duration_yesterday",
        "name": "Precip Duration Yesterday",
        "field": "precipitation_duration_yesterday",
        "state_class": "measurement",
        "unit_of_measurement": "min",
        "value_template": "{{ value_json.precipitation_duration_yesterday }}",
    },
    {
        # Precipitation description (e.g. "None", "Light Rain")
        "object_id": "precipitation_description",
        "name": "Precipitation Description",
        "field": "precipitation_description",
        "value_template": "{{ value_json.precipitation_description }}",
    },
    {
        # UV index
        "object_id": "uv_index",
        "name": "UV Index",
        "field": "uv_index",
        "state_class": "measurement",
        "value_template": "{{ value_json.uv_index }}",
    },
    {
        # Solar radiation (W/m^2)
        "object_id": "solar_radiation",
        "name": "Solar Radiation",
        "field": "solar_radiation",
        "state_class": "measurement",
        "unit_of_measurement": "W/m²",
        "value_template": "{{ value_json.solar_radiation }}",
    },
    {
        # Illuminance (lux)
        "object_id": "illuminance",
        "name": "Illuminance",
        "field": "illuminance",
        "device_class": "illuminance",
        "state_class": "measurement",
        "unit_of_measurement": "lx",
        "value_template": "{{ value_json.illuminance }}",
    },
    {
        # Station battery voltage
        "object_id": "voltage",
        "name": "Battery Voltage",
        "field": "voltage",
        "device_class": "voltage",
        "state_class": "measurement",
        "unit_of_measurement": "V",
        "value_template": "{{ value_json.voltage }}",
    },
    {
        # Power save mode (e.g., "Good", "OK", "Bad")
        "object_id": "power_save_mode",
        "name": "Power Save Mode",
        "field": "power_save_mode",
        "value_template": "{{ value_json.power_save_mode }}",
    },
    {
        # Wet bulb temperature
        "object_id": "wet_bulb_temperature",
        "name": "Wet Bulb Temperature",
        "field": "wet_bulb_temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
        "value_template": "{{ value_json.wet_bulb_temperature }}",
    },
    {
        # Wet Bulb Globe Temperature
        "object_id": "wet_bulb_globe_temperature",
        "name": "WBGT",
        "field": "wet_bulb_globe_temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
        "value_template": "{{ value_json.wet_bulb_globe_temperature }}",
    },
    {
        # Delta T
        "object_id": "delta_t",
        "name": "Delta T",
        "field": "delta_t",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
        "value_template": "{{ value_json.delta_t }}",
    },
    {
        # Timestamp of last lightning strike
        # Marked as a "timestamp" device_class sensor in HA
        "object_id": "time_of_last_lightning_strike",
        "name": "Time of Last Lightning Strike",
        "field": "time_of_last_lightning_strike",
        "device_class": "timestamp",
        "value_template": "{{ value_json.time_of_last_lightning_strike }}",
    },
    {
        # Distance range of last lightning strike (e.g., "29 - 33 km")
        "object_id": "distance_last_lightning_strike",
        "name": "Distance Last Lightning Strike",
        "field": "distance_last_lightning_strike",
        "value_template": "{{ value_json.distance_last_lightning_strike }}",
    },
    {
        # Number of lightning strikes in the past 3 hours
        "object_id": "lightning_strikes_last_3_hours",
        "name": "Lightning Strikes Last 3h",
        "field": "lightning_strikes_last_3_hours",
        "state_class": "measurement",
        "value_template": "{{ value_json.lightning_strikes_last_3_hours }}",
    },
]

BINARY_SENSOR_CONFIGS = [
    {
        # is_raining -> True/False
        "object_id": "is_raining",
        "name": "Is Raining",
        "field": "is_raining",
        "device_class": "moisture",
        "value_template": "{{ value_json.is_raining }}",
        "payload_on": "true",
        "payload_off": "false",
    },
    {
        # is_freezing -> True/False
        "object_id": "is_freezing",
        "name": "Is Freezing",
        "field": "is_freezing",
        "device_class": "cold",
        "value_template": "{{ value_json.is_freezing }}",
        "payload_on": "true",
        "payload_off": "false",
    },
    {
        # is_lightning -> True/False
        "object_id": "is_lightning",
        "name": "Is Lightning",
        "field": "is_lightning",
        "device_class": "safety",
        "value_template": "{{ value_json.is_lightning }}",
        "payload_on": "true",
        "payload_off": "false",
    },
]
