"""Tests for the WeatherData model defaults and invariants."""

from __future__ import annotations

from models import WeatherData


def test_default_data_not_available():
    data = WeatherData()
    assert data.data_available is False


def test_default_flags_are_false():
    data = WeatherData()
    assert data.is_raining is False
    assert data.is_freezing is False
    assert data.is_lightning is False


def test_default_numeric_fields_are_none():
    data = WeatherData()
    assert data.temperature is None
    assert data.humidity is None
    assert data.sea_level_pressure is None
    assert data.wind_speed is None


def test_lightning_strikes_default_is_zero():
    # Ensures the field is 0 (not None) for safe arithmetic in templates
    data = WeatherData()
    assert data.lightning_strikes_last_3_hours == 0


def test_station_id_stored():
    data = WeatherData(station_id="12345")
    assert data.station_id == "12345"
