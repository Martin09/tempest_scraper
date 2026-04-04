"""Unified WeatherData model shared by all scrapers and publishers."""

from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass
class WeatherData:
    """Canonical weather data model for the Tempest scraper.

    Field names here are the single source of truth; both scrapers and all
    MQTT sensor templates must reference these exact names.
    """

    # Meta
    station_id: str | None = None
    station_name: str | None = None
    data_updated: datetime.datetime | None = None
    data_available: bool = False
    timezone_str: str | None = None

    # Temperature & Humidity
    temperature: float | None = None  # °C
    humidity: float | None = None  # %
    dew_point: float | None = None  # °C
    feels_like: float | None = None  # °C
    heat_index: float | None = None  # °C
    wind_chill: float | None = None  # °C

    # Pressure
    sea_level_pressure: float | None = None  # mbar
    station_pressure: float | None = None  # mbar
    pressure_trend: str | None = None

    # Wind
    wind_speed: float | None = None  # km/h (average)
    wind_gust: float | None = None  # km/h
    wind_lull: float | None = None  # km/h
    wind_direction: int | None = None  # degrees
    wind_cardinal: str | None = None

    # Precipitation
    precipitation_rate: float | None = None  # mm/hr
    precipitation_today: float | None = None  # mm
    precipitation_yesterday: float | None = None  # mm
    precipitation_duration_today: int | None = None  # minutes
    precipitation_duration_yesterday: int | None = None  # minutes
    precipitation_description: str | None = None

    # Light & UV
    uv_index: float | None = None
    solar_radiation: int | None = None  # W/m²
    illuminance: int | None = None  # lux

    # Power / Diagnostics
    voltage: float | None = None  # V
    power_save_mode: str | None = None

    # Advanced
    wet_bulb_temperature: float | None = None  # °C
    wet_bulb_globe_temperature: float | None = None  # °C
    delta_t: float | None = None  # °C
    air_density: float | None = None  # kg/m³

    # Flags
    is_raining: bool = False
    is_freezing: bool = False
    is_lightning: bool = False

    # Lightning
    time_of_last_lightning_strike: datetime.datetime | None = None
    distance_last_lightning_strike: str | None = None
    lightning_strikes_last_3_hours: int = 0
    lightning_strike_count: int | None = None
