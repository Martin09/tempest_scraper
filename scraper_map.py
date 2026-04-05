#!/usr/bin/env python3

"""
Web scraper for extracting weather data from a Tempest Weather Station map detail view.

This script uses Playwright to interact with the web page (loading the map and triggering
the station detail view) and BeautifulSoup to parse the HTML content of the detail view,
extracting various weather metrics into a structured format.
"""

import asyncio
import datetime
import json
import logging
import re
import time
from dataclasses import asdict
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # Use zoneinfo for timezone handling

from bs4 import BeautifulSoup, Tag
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from const import (
    COMMON_USER_AGENT,
    COMMON_VIEWPORT,
    DEFAULT_WAIT_TIMEOUT,
)
from models import WeatherData

_LOGGER = logging.getLogger(__name__)


# --- Helper Functions ---


def _safe_parse_float(value: Any | None) -> float | None:
    """Safely parses string or number to float, removing units like '°C', '%', etc."""
    if value is None:
        return None
    try:
        # Convert to string, remove common units/symbols, handle commas, strip
        text_value = str(value)
        cleaned_value = re.sub(r"[^0-9.,-]", "", text_value).replace(",", ".").strip()
        if not cleaned_value or cleaned_value in ["---", "-", "."]:
            return None
        if (
            cleaned_value.count(".") > 1
            or cleaned_value.count("-") > 1
            or (cleaned_value.count("-") == 1 and not cleaned_value.startswith("-"))
        ):
            return None
        return float(cleaned_value)
    except (ValueError, TypeError):
        logging.debug(f"Could not parse float from: '{value}'")
        return None


def _safe_parse_int(value: Any | None) -> int | None:
    """Safely parses string or number to integer (via float)."""
    float_val = _safe_parse_float(value)
    if float_val is not None:
        try:
            return int(round(float_val))
        except (ValueError, TypeError):
            logging.debug(f"Could not convert float '{float_val}' to int.")
            return None
    return None


def _get_text_safely(element: Tag | None, default: str | None = None) -> str | None:
    """Extracts stripped text content from a BeautifulSoup Tag safely."""
    return element.get_text(strip=True) if element else default


def _get_attr_safely(element: Tag | None, attr: str, default: str | None = None) -> str | None:
    """Extracts an attribute value from a BeautifulSoup Tag safely."""
    return element.get(attr, default) if element else default


def _degrees_to_cardinal(degrees: int | None) -> str | None:
    """Converts wind direction in degrees to a 16-point cardinal direction."""
    if degrees is None:
        return None
    degrees = degrees % 360
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = round(degrees / (360.0 / len(dirs)))
    return dirs[ix % len(dirs)]


def _cardinal_to_degrees(direction: str | None) -> int | None:
    """Convert a 16-point cardinal direction to an approximate degree measure."""
    if direction is None:
        return None
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    if direction not in dirs:
        logging.error(f"Invalid direction: {direction}")
        raise ValueError(f"Invalid cardinal direction: {direction}")
    index = dirs.index(direction)
    degrees = round(index * (360.0 / len(dirs)))
    return degrees % 360


def _parse_detailed_timestamp(timestamp_str: str | None, timezone_str: str | None) -> datetime.datetime | None:
    """
    Attempts to parse a timestamp string like 'MM/DD/YYYY HH:MM:SS am/pm'
    using a provided timezone string (e.g., 'Europe/Zurich').

    Args:
        timestamp_str: The timestamp string (e.g., "04/06/2025 3:16:25 pm").
        timezone_str: The IANA timezone name (e.g., "Europe/Zurich").

    Returns:
        A timezone-aware datetime object corresponding to the input,
        or None if parsing fails or inputs are invalid.

    Note: Uses the standard `zoneinfo` library. Assumes the format is
          consistently 'MM/DD/YYYY H:MM:SS am/pm' (case-insensitive am/pm).
          Handles potential timezone lookup errors.
    """
    if not timestamp_str or not timezone_str:
        logging.debug("Timestamp or timezone string missing for detailed parsing.")
        return None

    try:
        tz = ZoneInfo(timezone_str)
    except ZoneInfoNotFoundError:
        logging.warning(f"Timezone '{timezone_str}' not found. Cannot parse timestamp accurately.")
        return None
    except Exception as e:
        logging.error(f"Error loading timezone '{timezone_str}': {e}")
        return None

    parse_format = "%m/%d/%Y %I:%M:%S %p"

    try:
        naive_dt = datetime.datetime.strptime(timestamp_str.strip(), parse_format)
        aware_dt = naive_dt.replace(tzinfo=tz)
        logging.debug(f"Successfully parsed '{timestamp_str}' with timezone '{timezone_str}' to {aware_dt}")
        return aware_dt

    except ValueError:
        logging.warning(
            f"Could not parse timestamp string '{timestamp_str}' with format '{parse_format}'. Does it include 'am/pm'?"
        )
        return None
    except Exception as e:
        logging.error(f"Unexpected error parsing timestamp '{timestamp_str}' with timezone '{timezone_str}': {e}")
        return None


def _extract_station_name(soup: BeautifulSoup) -> str | None:
    """Extract station name from the BeautifulSoup object."""
    station_name_tag = soup.find("h2", id="station-name")
    if station_name_tag:
        name_link = station_name_tag.find("a")
        return _get_text_safely(name_link)
    logging.warning("Station name tag (h2#station-name) not found within provided HTML content.")
    return None


def _extract_list_data(list_ul: Tag) -> dict[str, Any]:
    """Extract data from list items."""
    raw_data: dict[str, Any] = {}

    list_items = list_ul.find_all("li")
    logging.info(f"Found {len(list_items)} list items in ul.sw-list.")

    for item in list_items:
        label_span = item.find("span", class_="lv-param-label")
        value_span = item.find("span", class_="lv-value-display")

        if not value_span:
            continue

        param_key = _get_attr_safely(value_span, "data-param")
        param_value = _get_text_safely(value_span)
        label_text = _get_text_safely(label_span, "").lower()

        determined_key = param_key or ("timezone" if label_text == "timezone" else None)

        if determined_key and param_value is not None:
            raw_data[determined_key] = param_value

    return raw_data


def _process_wind_direction(value: str | None) -> tuple[int | None, str | None]:
    """Process wind direction value and return direction in degrees and cardinal."""
    if not value:
        return None, None

    wind_val = value.strip()
    if not wind_val:
        return None, None

    if "°" in wind_val or wind_val.isdigit():
        direction = _safe_parse_int(wind_val)
        return direction, _degrees_to_cardinal(direction)
    else:
        return _cardinal_to_degrees(wind_val), wind_val


def _map_raw_data_to_weather(raw_data: dict[str, Any], data: WeatherData) -> WeatherData:
    """Map raw data to WeatherData object."""
    mapping = {
        "air_temperature": ("temperature", _safe_parse_float),
        "barometric_pressure": ("station_pressure", _safe_parse_float),
        "brightness": ("illuminance", _safe_parse_int),
        "delta_t": ("delta_t", _safe_parse_float),
        "dew_point": ("dew_point", _safe_parse_float),
        "humidity": ("humidity", _safe_parse_float),
        "lightning_strike_count_last_3hr": ("lightning_strikes_last_3_hours", _safe_parse_int),
        "lightning_strike_last_distance": ("distance_last_lightning_strike", str),
        "precip_accum_local_day": ("precipitation_today", _safe_parse_float),
        "precip_accum_local_yesterday": ("precipitation_yesterday", _safe_parse_float),
        "precip_minutes_local_day": ("precipitation_duration_today", _safe_parse_int),
        "precip_minutes_local_yesterday": ("precipitation_duration_yesterday", _safe_parse_int),
        "sea_level_pressure": ("sea_level_pressure", _safe_parse_float),
        "solar_radiation": ("solar_radiation", _safe_parse_int),
        "uv": ("uv_index", _safe_parse_float),
        "wet_bulb_temperature": ("wet_bulb_temperature", _safe_parse_float),
        "wet_bulb_globe_temperature": ("wet_bulb_globe_temperature", _safe_parse_float),
        "wind_avg": ("wind_speed", _safe_parse_float),
        "wind_gust": ("wind_gust", _safe_parse_float),
        "wind_lull": ("wind_lull", _safe_parse_float),
    }

    # Process standard mappings
    for raw_key, (data_key, parser) in mapping.items():
        if raw_key in raw_data:
            setattr(data, data_key, parser(raw_data[raw_key]))

    # Handle wind direction separately as it needs special processing
    if "wind_direction" in raw_data:
        direction, cardinal = _process_wind_direction(raw_data["wind_direction"])
        data.wind_direction = direction
        data.wind_cardinal = cardinal

    # Handle timestamp and timezone
    if "timestamp" in raw_data and "timezone" in raw_data:
        data.timezone_str = raw_data["timezone"]
        data.data_updated = _parse_detailed_timestamp(raw_data["timestamp"], raw_data["timezone"])

    return data


def _process_precipitation(precip_str: str) -> tuple[float | None, str, bool]:
    """Process precipitation string and return rate, description, and is_raining."""
    precip_str = precip_str.lower()
    if "none" in precip_str or "(0.0 mm" in precip_str:
        return 0.0, "None", False

    rate_match = re.search(r"\(([\d.,]+)\s*mm\s*/\s*hour\)", precip_str)
    rate = _safe_parse_float(rate_match.group(1)) if rate_match else None

    desc_match = re.match(r"^(.*?)\s*\(", precip_str)
    description = desc_match.group(1).strip().capitalize() if desc_match else precip_str.strip().capitalize()

    return rate, description, True


def _parse_html_content(html_content: str, station_id: str | None) -> WeatherData:
    """Parse HTML content into WeatherData object."""
    data = WeatherData(station_id=station_id)

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        data.station_name = _extract_station_name(soup)

        list_view = soup.find("div", id="list-view")
        if not list_view:
            logging.error("Could not find 'div#list-view' within the container.")
            return data

        list_ul = list_view.find("ul", class_="sw-list")
        if not list_ul:
            logging.error("Could not find 'ul.sw-list' within the list view.")
            return data

        raw_data = _extract_list_data(list_ul)
        data = _map_raw_data_to_weather(raw_data, data)

        # Process precipitation data
        if "precip" in raw_data:
            rate, desc, is_raining = _process_precipitation(raw_data["precip"])
            data.precipitation_rate = rate
            data.precipitation_description = desc
            data.is_raining = is_raining

        # Set final flags
        data.is_freezing = data.temperature is not None and data.temperature <= 0.0
        data.is_lightning = (data.lightning_strikes_last_3_hours or 0) > 0

        # Check data availability
        core_data_points = [data.temperature, data.humidity, data.sea_level_pressure, data.wind_speed]
        data.data_available = any(dp is not None for dp in core_data_points)

    except Exception as e:
        logging.error(f"Critical error during HTML parsing: {e}", exc_info=True)
        data.data_available = False

    return data


# --- Browser Setup Functions ---


async def _setup_browser_context() -> tuple[Playwright, Browser, BrowserContext]:
    """Set up browser context with proper configuration."""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent=COMMON_USER_AGENT, viewport=COMMON_VIEWPORT, java_script_enabled=True
    )
    return playwright, browser, context


async def _setup_resource_blocking(context: BrowserContext):
    """Set up resource blocking for better performance."""
    try:
        resources = [
            "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}",
            "**/google-analytics.com/**",
            "**/googletagmanager.com/**",
            "**/bugsnag.com/**",
        ]
        for resource in resources:
            await context.route(resource, lambda route: route.abort())
        logging.info("Resource routes blocked successfully.")
    except Exception as e:
        logging.warning(f"Could not set up all route blocking: {e}")


async def _wait_for_content(page: Page, container_selector: str, wait_timeout: int):
    """Wait for content to be available on the page."""
    container_locator = page.locator(container_selector)
    await container_locator.wait_for(state="visible", timeout=wait_timeout)

    timestamp_selector = f"{container_selector} span[data-param='timestamp']"
    await page.locator(timestamp_selector).wait_for(state="visible", timeout=wait_timeout // 2)
    await page.wait_for_timeout(500)
    return container_locator


async def _cleanup_resources(playwright: Playwright | None, browser: Browser | None, context: BrowserContext | None):
    """Clean up Playwright resources."""
    if context:
        await context.close()
    if browser:
        await browser.close()
    if playwright:
        await playwright.stop()


# --- Main Scraper Function ---


async def scrape_weather_data(
    url: str,
    container_selector: str = "div#station-detail",
    wait_timeout: int = DEFAULT_WAIT_TIMEOUT,
    save_html_path: str | None = None,
) -> WeatherData:
    """Scrape weather data from the station's map detail view."""
    station_id = url.split("/")[-1] if "/map/" in url else None
    data = WeatherData(station_id=station_id)
    resources = None

    try:
        # Set up browser
        playwright, browser, context = await _setup_browser_context()
        resources = (playwright, browser, context)

        # Set up blocking
        await _setup_resource_blocking(context)

        # Navigate to page
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=wait_timeout + 15000)

        # Wait for content
        container_locator = await _wait_for_content(page, container_selector, wait_timeout)

        # Extract and parse HTML
        detail_view_html = await container_locator.inner_html()

        if save_html_path:
            detail_html_filename = f"{save_html_path}_detail_{time.strftime('%Y%m%d_%H%M%S')}.html"
            try:
                with open(detail_html_filename, "w", encoding="utf-8") as f:
                    f.write(detail_view_html)
                logging.info(f"Saved detail view HTML to {detail_html_filename}")
            except OSError as e_save_detail:
                logging.error(f"Failed to save detail HTML file: {e_save_detail}")

        if detail_view_html:
            data = _parse_html_content(detail_view_html, station_id)

    except Exception as e:
        logging.error(f"Scraping failed: {e}", exc_info=True)
        data.data_available = False

    finally:
        await _cleanup_resources(*resources if resources else (None, None, None))

    return data


# --- API Client ---


class TempestWxScraperApiClientError(Exception):
    """Custom exception for API client errors."""

    pass


class TempestWxScraperApiClient:
    def __init__(self, station_id: str):
        if not station_id or not str(station_id).isdigit():
            raise ValueError("Invalid station_id provided.")
        self.station_id = station_id
        # Use the MAP view URL structure
        self.url = f"https://tempestwx.com/map/{self.station_id}"
        logging.info(f"API Client initialized for station {self.station_id} (Map View) at URL: {self.url}")

    async def async_get_data(self, save_html_debug_path: str | None = None) -> WeatherData:
        """Asynchronously fetch weather data from the station's map detail view."""
        try:
            # Use the correct container selector for the map view's detail panel
            return await scrape_weather_data(
                url=self.url,
                container_selector="div#station-detail",  # Selector for the detail panel
                wait_timeout=DEFAULT_WAIT_TIMEOUT,
                save_html_path=save_html_debug_path,
            )
        except Exception as e:
            logging.error(f"Scraping failed within API client for station {self.station_id}: {e}", exc_info=False)
            raise TempestWxScraperApiClientError(f"Failed to scrape data for station {self.station_id}: {e}") from e


# --- Example Usage ---
if __name__ == "__main__":

    async def main():
        # --- Configuration ---
        STATION_ID = "130627"  # Use the example ID provided by the user
        DEBUG_SAVE_HTML = False  # Set to True to save HTML files
        # --- End Configuration ---

        logging.info(f"Attempting to scrape data for station ID: {STATION_ID} using Map View")

        # Use the API Client
        client = TempestWxScraperApiClient(station_id=STATION_ID)
        try:
            weather_info = await client.async_get_data(
                save_html_debug_path=f"debug_station_{STATION_ID}" if DEBUG_SAVE_HTML else None
            )
        except TempestWxScraperApiClientError as e:
            logging.error(f"API Client failed: {e}")
            weather_info = WeatherData(station_id=STATION_ID, data_available=False)

        print("\n" + "=" * 30)
        print("--- Scraped Weather Data ---")
        print("=" * 30)
        if weather_info and weather_info.data_available:
            weather_dict = asdict(weather_info)
            print(json.dumps(weather_dict, indent=2, default=str, ensure_ascii=False))  # Use default=str for datetime
        else:
            print(f"Scraping failed or no data was retrieved for station {STATION_ID}.")
            print("Check log messages above. If DEBUG_SAVE_HTML was True, check the saved HTML files.")
        print("=" * 30 + "\n")

    asyncio.run(main())
