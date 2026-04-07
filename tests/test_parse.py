"""Parametric tests for _safe_parse_float and _safe_parse_int.

Covers the solar-radiation / trailing-unit-digit bug (gh-fix 2026-04-07)
and a broad set of edge cases for numeric parsing of scraped text.
"""

from __future__ import annotations

import pytest

from scraper_map import _safe_parse_float, _safe_parse_int

# ── _safe_parse_float ────────────────────────────────────────────────────────


class TestSafeParseFloat:
    """Verify first-numeric-token extraction and comma handling."""

    # fmt: off
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # --- Plain numbers ---
            ("789",           789.0),
            ("0",             0.0),
            ("3",             3.0),
            ("0.0",           0.0),
            ("-12.3",        -12.3),
            ("1013.25",      1013.25),

            # --- Number followed by unit text (no problematic digits) ---
            ("789 W/m²",      789.0),
            ("787.2 W/m²",    787.2),
            ("-12.3°C",      -12.3),
            ("85%",           85.0),
            ("45 km/h",       45.0),
            ("1013.25 mbar",  1013.25),

            # Bug Regression: unit contains ASCII digit (m² rendered as m<sup>2</sup>)
            ("789 W/m2",      789.0),
            ("787.2 W/m2",    787.2),
            ("0 W/m2",        0.0),

            # --- European comma-decimal ---
            ("787,2",         787.2),
            ("787,2 W/m²",    787.2),
            ("787,2 W/m2",    787.2),
            ("-3,5°C",       -3.5),

            # --- Thousands separator (comma + exactly 3-digit groups) ---
            ("1,089",         1089.0),
            ("1,089 W/m²",    1089.0),
            ("12,345.67",     12345.67),

            # --- None / empty / placeholder ---
            (None,            None),
            ("",              None),
            ("---",           None),
            ("-",             None),

            # --- Pure non-numeric text ---
            ("N/A",           None),
            ("abc",           None),
        ],
    )
    # fmt: on
    def test_parse_float(self, raw: str | None, expected: float | None) -> None:
        result = _safe_parse_float(raw)
        if expected is None:
            assert result is None, f"Expected None for {raw!r}, got {result}"
        else:
            assert result == pytest.approx(expected), f"For {raw!r}: expected {expected}, got {result}"


# ── _safe_parse_int ──────────────────────────────────────────────────────────


class TestSafeParseInt:
    """Verify float→int rounding used by integer fields like solar_radiation."""

    # fmt: off
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # --- Exact integers ---
            ("789",           789),
            ("0",             0),
            ("3",             3),

            # --- Decimals round to nearest int ---
            ("787.2",         787),
            ("787.6",         788),
            ("0.0",           0),

            # --- BUG REGRESSION: solar radiation with trailing unit digit ---
            ("789 W/m2",      789),
            ("787.2 W/m2",    787),

            # --- European comma-decimal ---
            ("787,2 W/m2",    787),

            # --- Thousands separator ---
            ("1,089 W/m²",    1089),
            ("12,345.67",     12346),

            # --- Negative ---
            ("-12.3°C",      -12),

            # --- None / empty ---
            (None,            None),
            ("",              None),
            ("---",           None),
        ],
    )
    # fmt: on
    def test_parse_int(self, raw: str | None, expected: int | None) -> None:
        result = _safe_parse_int(raw)
        if expected is None:
            assert result is None, f"Expected None for {raw!r}, got {result}"
        else:
            assert result == expected, f"For {raw!r}: expected {expected}, got {result}"
