#!/usr/bin/env python3

"""Web scraper for the Tempest Weather Station grid/page view (alternative to map view).

Uses Playwright + BeautifulSoup to extract data from tempestwx.com/station/<id>/grid.
This scraper provides more structured tile-based parsing and an accurate epoch timestamp
for the last lightning strike.

To use this instead of scraper_map, set SCRAPER_MODE=grid in your .env.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict

from bs4 import BeautifulSoup, Tag
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from const import (
    COMMON_USER_AGENT,
    COMMON_VIEWPORT,
    DEFAULT_WAIT_TIMEOUT,
)
from models import WeatherData
from parsing import (
    degrees_to_cardinal,
    get_attr_safely,
    get_text_safely,
    parse_epoch_timestamp,
    safe_parse_float,
    safe_parse_int,
)

_LOGGER = logging.getLogger(__name__)

_BLOCK_PATTERNS = [
    "**/*.{png,jpg,jpeg,gif,svg,woff,woff2}",
    "**/google-analytics.com/**",
    "**/googletagmanager.com/**",
]


# ---------------------------------------------------------------------------
# Tile parsers
# ---------------------------------------------------------------------------


def _parse_station_info(soup: BeautifulSoup, data: WeatherData) -> None:
    station_tag = soup.find("p", class_="weather-tile-device-name")
    data.station_name = get_text_safely(station_tag)

    ts_tag = soup.find("p", class_="weather-tile-timestamp", attrs={"data-param": "param-timestamp"})
    data.data_updated = parse_epoch_timestamp(get_attr_safely(ts_tag, "data-timestamp"))


def _parse_temperature_humidity(tile: Tag, data: WeatherData) -> None:
    data.temperature = safe_parse_float(
        get_text_safely(tile.find("p", {"data-param": "param-air_temp_with_symbol_and_units"}))
    )
    data.is_freezing = data.temperature is not None and data.temperature <= 0.0
    data.humidity = safe_parse_float(get_text_safely(tile.find("p", {"data-param": "param-rh_with_symbol"})))
    dp_label = tile.find("p", {"data-param": "param-heat_index_or_dew_point_label"})
    dp_val = tile.find("p", {"data-param": "param-heat_index_or_dew_point_display"})
    if "dew point" in get_text_safely(dp_label, "").lower():
        data.dew_point = safe_parse_float(get_text_safely(dp_val))


def _parse_pressure(tile: Tag, data: WeatherData) -> None:
    data.sea_level_pressure = safe_parse_float(
        get_text_safely(tile.find("p", {"data-param": "param-sea_level_pres_display"}))
    )
    data.pressure_trend = get_text_safely(tile.find("p", {"data-param": "param-pres_trend_localized"}))


def _parse_lightning(tile: Tag, data: WeatherData) -> None:
    last_strike = tile.find("p", {"data-param": "param-lightning_last_strike_fuzzy"})
    data.time_of_last_lightning_strike = parse_epoch_timestamp(get_attr_safely(last_strike, "data-timestamp"))
    data.distance_last_lightning_strike = get_text_safely(
        tile.find("p", {"data-param": "param-lightning_last_strike_distance_text_display"})
    )
    data.lightning_strikes_last_3_hours = (
        safe_parse_int(get_text_safely(tile.find("p", {"data-param": "param-lightning_strike_count_last_3hrs"}))) or 0
    )
    data.is_lightning = data.lightning_strikes_last_3_hours > 0


def _parse_wind(tile: Tag, data: WeatherData) -> None:
    data.wind_direction = safe_parse_int(get_text_safely(tile.find("p", {"data-param": "param-wind_dir_display"})))
    data.wind_cardinal = degrees_to_cardinal(data.wind_direction)
    data.wind_speed = safe_parse_float(get_text_safely(tile.find("p", {"data-param": "param-wind_avg_display"})))
    lull_gust_text = get_text_safely(tile.find("p", {"data-param": "param-wind_lull_gust_with_units"}))
    if lull_gust_text:
        match = re.search(r"([\d.,]+)\s*-\s*([\d.,]+)", lull_gust_text)
        if match:
            data.wind_lull = safe_parse_float(match.group(1))
            data.wind_gust = safe_parse_float(match.group(2))


def _parse_rain(tile: Tag, data: WeatherData) -> None:
    desc = get_text_safely(tile.find("p", {"data-param": "param-precip_rate_text_display_localized"}))
    data.precipitation_description = desc
    if desc is None:
        data.is_raining = False
        data.precipitation_rate = None
    elif desc.lower() == "none":
        data.is_raining = False
        data.precipitation_rate = 0.0
    else:
        data.is_raining = True
        data.precipitation_rate = None  # Grid view doesn't expose numeric rate directly

    data.precipitation_today = safe_parse_float(
        get_text_safely(tile.find("p", {"data-param": "param-precip_accum_local_today_final_display_with_units"}))
    )
    data.precipitation_yesterday = safe_parse_float(
        get_text_safely(
            tile.find(
                "p",
                {"data-param": "param-precip_accumm_local_yesterday_final_display_with_units"},
            )
        )
    )


def _parse_light_uv(tile: Tag, data: WeatherData) -> None:
    data.uv_index = safe_parse_float(get_text_safely(tile.find("p", {"data-param": "param-uv_with_index"})))
    data.illuminance = safe_parse_int(get_text_safely(tile.find("p", {"data-param": "param-lux_display_with_units"})))
    data.solar_radiation = safe_parse_int(
        get_text_safely(tile.find("p", {"data-param": "param-solar_radiation_display_with_units"}))
    )


def _parse_diagnostics(tile: Tag, data: WeatherData) -> None:
    data.voltage = safe_parse_float(get_text_safely(tile.find("p", {"data-param": "param-battery"})))
    data.power_save_mode = get_text_safely(tile.find("p", {"data-param": "param-battery_state"}))


def _parse_advanced_stats(soup: BeautifulSoup, data: WeatherData) -> None:
    container = soup.find("div", {"id": "level2-more-cc"})
    if not container:
        return
    for li in container.find_all("li", class_="grid-stripe-item"):
        label_el = li.find("span", class_="lv-param-label")
        val_el = li.find("span", class_="lv-value-display")
        if not label_el or not val_el:
            continue
        label = get_text_safely(label_el, "").lower()
        val = get_text_safely(val_el)

        if "station pressure" in label:
            data.station_pressure = safe_parse_float(val)
        elif "dew point" in label and data.dew_point is None:
            data.dew_point = safe_parse_float(val)
        elif "delta t" in label:
            data.delta_t = safe_parse_float(val)
        elif "rain duration (today)" in label:
            data.precipitation_duration_today = safe_parse_int(val)
        elif "rain duration (yesterday)" in label:
            data.precipitation_duration_yesterday = safe_parse_int(val)
        elif "wet bulb globe temperature" in label:
            data.wet_bulb_globe_temperature = safe_parse_float(val)
        elif "wet bulb temperature" in label:
            data.wet_bulb_temperature = safe_parse_float(val)


_TILE_PARSERS = {
    "air_temperature_humidity": _parse_temperature_humidity,
    "barometric_pressure": _parse_pressure,
    "lightning": _parse_lightning,
    "wind": _parse_wind,
    "rain": _parse_rain,
    "light": _parse_light_uv,
    "diagnostics": _parse_diagnostics,
}


def _parse_html_content(html_content: str) -> WeatherData:
    data = WeatherData()
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        if not soup.find("div", class_="weather-tile"):
            _LOGGER.warning("No weather tiles found in HTML content.")
            return data

        data.data_available = True
        _parse_station_info(soup, data)

        for tile_type, parser in _TILE_PARSERS.items():
            tile = soup.find("div", {"data-tile-type": tile_type})
            if tile:
                try:
                    parser(tile, data)
                except Exception:
                    _LOGGER.error("Error parsing tile %r.", tile_type, exc_info=True)
            else:
                _LOGGER.warning("Weather tile not found for type: %r", tile_type)

        try:
            _parse_advanced_stats(soup, data)
        except Exception:
            _LOGGER.error("Error parsing advanced stats.", exc_info=True)

    except Exception:
        _LOGGER.exception("Error during HTML parsing.")
        data.data_available = False

    return data


# ---------------------------------------------------------------------------
# Playwright scraping — accepts a reusable Browser instance
# ---------------------------------------------------------------------------


async def scrape_weather_data(
    browser: Browser,
    url: str,
    container_selector: str = "section#grid-view",
    wait_timeout: int = DEFAULT_WAIT_TIMEOUT,
    save_html_path: str | None = None,
) -> WeatherData:
    """Scrape the grid-view page using an existing Playwright Browser."""
    data = WeatherData()
    context: BrowserContext | None = None

    try:
        context = await browser.new_context(user_agent=COMMON_USER_AGENT, viewport=COMMON_VIEWPORT)
        for pattern in _BLOCK_PATTERNS:
            await context.route(pattern, lambda route: route.abort())

        page: Page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=wait_timeout + 10_000)

        container = page.locator(container_selector)
        await container.wait_for(state="visible", timeout=wait_timeout)

        try:
            temp_sel = (
                f"{container_selector} .air_temperature_humidity "
                ".weather-tile-main-value[data-param='param-air_temp_with_symbol_and_units']"
            )
            await page.locator(temp_sel).wait_for(state="visible", timeout=wait_timeout // 2)
        except PlaywrightTimeoutError:
            _LOGGER.warning("Temperature element check timed out, proceeding anyway.")

        html = await container.inner_html()

        if save_html_path:
            filename = f"{save_html_path}_{time.strftime('%Y%m%d_%H%M%S')}.html"
            try:
                with open(filename, "w", encoding="utf-8") as fh:
                    fh.write(html)
            except OSError:
                _LOGGER.error("Failed to save HTML file.", exc_info=True)

        data = _parse_html_content(html)

    except Exception:
        _LOGGER.exception("Error during scraping.")
        data.data_available = False
    finally:
        if context:
            await context.close()

    return data


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------


class TempestWxScraperApiClientError(Exception):
    """Raised when the page scraper cannot retrieve data."""


class TempestWxScraperApiClient:
    """Async client for the TempestWX grid/page view (alternative scraper)."""

    def __init__(self, station_id: str) -> None:
        self.station_id = station_id
        self.url = f"https://tempestwx.com/station/{station_id}/grid"
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def _ensure_browser(self) -> Browser:
        if not self._browser:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    async def async_get_data(self, save_html_debug_path: str | None = None) -> WeatherData:
        try:
            browser = await self._ensure_browser()
            return await scrape_weather_data(
                browser=browser,
                url=self.url,
                container_selector="section#grid-view",
                wait_timeout=DEFAULT_WAIT_TIMEOUT,
                save_html_path=save_html_debug_path,
            )
        except Exception as exc:
            raise TempestWxScraperApiClientError(f"Failed to scrape data: {exc}") from exc

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


# ---------------------------------------------------------------------------
# Example / standalone usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    async def _main() -> None:
        client = TempestWxScraperApiClient(station_id="130627")
        try:
            data = await client.async_get_data()
            print(json.dumps(asdict(data), indent=2, default=str))
        finally:
            await client.close()

    asyncio.run(_main())
