"""Shared parsing utilities for weather data scrapers."""

from __future__ import annotations

import datetime
import logging
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bs4 import Tag

_LOGGER = logging.getLogger(__name__)

_CARDINALS = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
]


def safe_parse_float(value: Any) -> float | None:
    """Safely parse a string or number to float, stripping unit suffixes."""
    if value is None:
        return None
    try:
        cleaned = re.sub(r"[^0-9.,-]", "", str(value)).replace(",", ".").strip()
        if not cleaned or cleaned in {"---", "-", "."}:
            return None
        if (
            cleaned.count(".") > 1
            or cleaned.count("-") > 1
            or (cleaned.count("-") == 1 and not cleaned.startswith("-"))
        ):
            return None
        return float(cleaned)
    except (ValueError, TypeError):
        _LOGGER.debug("Could not parse float from: %r", value)
        return None


def safe_parse_int(value: Any) -> int | None:
    """Safely parse a string or number to int (via float)."""
    fval = safe_parse_float(value)
    if fval is not None:
        try:
            return int(round(fval))
        except (ValueError, TypeError):
            _LOGGER.debug("Could not convert float %r to int.", fval)
    return None


def get_text_safely(element: Tag | None, default: str | None = None) -> str | None:
    """Return stripped text from a BeautifulSoup Tag, or default."""
    return element.get_text(strip=True) if element else default


def get_attr_safely(element: Tag | None, attr: str, default: str | None = None) -> str | None:
    """Return an attribute value from a BeautifulSoup Tag, or default."""
    return element.get(attr, default) if element else default


def degrees_to_cardinal(degrees: int | None) -> str | None:
    """Convert wind direction in degrees to a 16-point cardinal string."""
    if degrees is None:
        return None
    idx = round((degrees % 360) / (360.0 / len(_CARDINALS)))
    return _CARDINALS[idx % len(_CARDINALS)]


def cardinal_to_degrees(direction: str | None) -> int | None:
    """Convert a 16-point cardinal direction to approximate degrees."""
    if direction is None:
        return None
    if direction not in _CARDINALS:
        raise ValueError(f"Invalid cardinal direction: {direction!r}")
    return round(_CARDINALS.index(direction) * (360.0 / len(_CARDINALS))) % 360


def parse_epoch_timestamp(ts_str: str | None) -> datetime.datetime | None:
    """Convert a Unix epoch string to a UTC-aware datetime."""
    if not ts_str:
        return None
    try:
        return datetime.datetime.fromtimestamp(int(ts_str), tz=datetime.UTC)
    except (ValueError, TypeError):
        _LOGGER.debug("Could not parse epoch timestamp from: %r", ts_str)
        return None


def parse_detailed_timestamp(timestamp_str: str | None, timezone_str: str | None) -> datetime.datetime | None:
    """Parse 'MM/DD/YYYY HH:MM:SS am/pm' into a timezone-aware datetime.

    Note: Uses zoneinfo.ZoneInfo. replace(tzinfo=tz) is correct for zoneinfo
    (unlike pytz.localize). For ambiguous DST times, fold=0 (DST-on) is assumed.
    """
    if not timestamp_str or not timezone_str:
        _LOGGER.debug("Timestamp or timezone string missing.")
        return None
    try:
        tz = ZoneInfo(timezone_str)
    except ZoneInfoNotFoundError:
        _LOGGER.warning("Timezone %r not found.", timezone_str)
        return None
    except Exception:
        _LOGGER.exception("Error loading timezone %r.", timezone_str)
        return None

    fmt = "%m/%d/%Y %I:%M:%S %p"
    try:
        naive = datetime.datetime.strptime(timestamp_str.strip(), fmt)
        return naive.replace(tzinfo=tz)
    except ValueError:
        _LOGGER.warning("Could not parse timestamp %r with format %r.", timestamp_str, fmt)
        return None
    except Exception:
        _LOGGER.exception("Unexpected error parsing timestamp %r.", timestamp_str)
        return None
