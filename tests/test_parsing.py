"""Tests for shared parsing utilities."""

from __future__ import annotations

import datetime
import pytest

from parsing import (
    degrees_to_cardinal,
    cardinal_to_degrees,
    parse_epoch_timestamp,
    safe_parse_float,
    safe_parse_int,
)


class TestSafeParseFloat:
    def test_plain_number(self):
        assert safe_parse_float("3.14") == pytest.approx(3.14)

    def test_strips_units(self):
        assert safe_parse_float("22.5°C") == pytest.approx(22.5)
        assert safe_parse_float("1013.2 mbar") == pytest.approx(1013.2)

    def test_comma_decimal(self):
        assert safe_parse_float("3,14") == pytest.approx(3.14)

    def test_negative(self):
        assert safe_parse_float("-5.0") == pytest.approx(-5.0)

    def test_none_input(self):
        assert safe_parse_float(None) is None

    def test_placeholder_values(self):
        assert safe_parse_float("---") is None
        assert safe_parse_float("-") is None
        assert safe_parse_float("") is None

    def test_integer_string(self):
        assert safe_parse_float("42") == pytest.approx(42.0)

    def test_numeric_input(self):
        assert safe_parse_float(3.14) == pytest.approx(3.14)


class TestSafeParseInt:
    def test_plain(self):
        assert safe_parse_int("42") == 42

    def test_rounds(self):
        assert safe_parse_int("2.7") == 3

    def test_none(self):
        assert safe_parse_int(None) is None

    def test_with_units(self):
        assert safe_parse_int("100 lux") == 100


class TestDegreesToCardinal:
    @pytest.mark.parametrize("degrees,expected", [
        (0, "N"),
        (90, "E"),
        (180, "S"),
        (270, "W"),
        (360, "N"),   # wraps
        (45, "NE"),
        (315, "NW"),
    ])
    def test_known_directions(self, degrees, expected):
        assert degrees_to_cardinal(degrees) == expected

    def test_none(self):
        assert degrees_to_cardinal(None) is None


class TestCardinalToDegrees:
    def test_north(self):
        assert cardinal_to_degrees("N") == 0

    def test_east(self):
        assert cardinal_to_degrees("E") == 90

    def test_south(self):
        assert cardinal_to_degrees("S") == 180

    def test_west(self):
        assert cardinal_to_degrees("W") == 270

    def test_none(self):
        assert cardinal_to_degrees(None) is None

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            cardinal_to_degrees("XX")


class TestParseEpochTimestamp:
    def test_known_epoch(self):
        result = parse_epoch_timestamp("0")
        assert result == datetime.datetime(1970, 1, 1, 0, 0, 0, tzinfo=datetime.UTC)

    def test_none(self):
        assert parse_epoch_timestamp(None) is None

    def test_empty_string(self):
        assert parse_epoch_timestamp("") is None

    def test_non_numeric(self):
        assert parse_epoch_timestamp("not-a-number") is None

    def test_is_utc_aware(self):
        result = parse_epoch_timestamp("1700000000")
        assert result is not None
        assert result.tzinfo is not None
