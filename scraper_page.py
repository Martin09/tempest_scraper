#!/usr/bin/env python3

"""
Web scraper for extracting weather data from a Tempest Weather Station grid view page.

This script uses Playwright to interact with the web page and BeautifulSoup
to parse the HTML content, extracting various weather metrics into a
structured format.
"""

import datetime
import json
import logging
import re
import time
from dataclasses import asdict, dataclass

from bs4 import BeautifulSoup, Tag
from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

# --- Configuration ---
# Using a common user agent can help avoid blocking
COMMON_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
)
# Standard viewport size
COMMON_VIEWPORT = {"width": 1920, "height": 1080}
# Default timeout for Playwright operations (in milliseconds)
DEFAULT_WAIT_TIMEOUT = 45000  # 45 seconds

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# --- Data Structure ---
@dataclass
class WeatherData:
    """
    Holds the scraped weather data with appropriate types and units.

    Attributes:
        station_name: Name of the weather station.
        data_updated: Timestamp (UTC) when the data was last updated on the site.
        data_available: Flag indicating if data was successfully scraped.
        temperature: Air temperature in degrees Celsius (°C).
        humidity: Relative humidity in percent (%).
        dew_point: Dew point temperature in degrees Celsius (°C).
        sea_level_pressure: Barometric pressure adjusted to sea level (mbar).
        station_pressure: Barometric pressure measured at the station (mbar).
        pressure_trend: Trend of barometric pressure (e.g., "Rising", "Falling", "Steady").
        wind_speed: Average wind speed in kilometers per hour (km/h).
        wind_gust: Maximum wind speed (gust) in kilometers per hour (km/h).
        wind_lull: Minimum wind speed (lull) in kilometers per hour (km/h).
        wind_direction: Wind direction in degrees (0-360).
        wind_cardinal: Wind direction as a cardinal point (e.g., "N", "SW").
        precipitation_rate: Current rate of precipitation in millimeters per hour (mm/hr).
                            Derived as 0 if description is "None".
        precipitation_today: Total precipitation recorded today in millimeters (mm).
        precipitation_yesterday: Total precipitation recorded yesterday in millimeters (mm).
        precipitation_duration_today: Duration of precipitation today in minutes.
        precipitation_duration_yesterday: Duration of precipitation yesterday in minutes.
        precipitation_description: Text description of current precipitation (e.g., "None", "Light Rain").
        uv_index: Ultraviolet radiation index.
        solar_radiation: Solar radiation intensity in Watts per square meter (W/m²).
        illuminance: Ambient light level in lux.
        voltage: Station battery voltage in volts.
        power_save_mode: Station power status or mode (e.g., "Good").
        wet_bulb_temperature: Wet bulb temperature in degrees Celsius (°C).
        wet_bulb_globe_temperature: Wet Bulb Globe Temperature (WBGT) in degrees Celsius (°C).
        delta_t: Delta T (difference between dry-bulb and wet-bulb temperature) in degrees Celsius (°C).
        is_raining: Boolean flag indicating if it is currently raining.
        is_freezing: Boolean flag indicating if the temperature is at or below freezing (0°C).
        is_lightning: Boolean flag indicating recent lightning activity (heuristic).
        time_of_last_lightning_strike: Timestamp (UTC) of the last detected lightning strike.
        distance_last_lightning_strike: Distance range of the last strike (e.g., "29 - 33 km").
        lightning_strikes_last_3_hours: Number of lightning strikes detected in the last 3 hours.
    """

    station_name: str | None = None
    data_updated: datetime.datetime | None = None
    data_available: bool = False

    # Core Metrics
    temperature: float | None = None  # °C
    humidity: float | None = None  # %
    dew_point: float | None = None  # °C
    sea_level_pressure: float | None = None  # mb
    station_pressure: float | None = None  # mb
    pressure_trend: str | None = None
    wind_speed: float | None = None  # km/h (average)
    wind_gust: float | None = None  # km/h
    wind_lull: float | None = None  # km/h
    wind_direction: int | None = None  # degrees
    wind_cardinal: str | None = None
    precipitation_rate: float | None = None  # mm/hr
    precipitation_today: float | None = None  # mm
    precipitation_yesterday: float | None = None  # mm
    precipitation_duration_today: int | None = None  # minutes
    precipitation_duration_yesterday: int | None = None  # minutes
    precipitation_description: str | None = None
    uv_index: float | None = None
    solar_radiation: int | None = None  # W/m²
    illuminance: int | None = None  # lux
    voltage: float | None = None  # volts
    power_save_mode: str | None = None

    # Derived/Calculated Metrics
    wet_bulb_temperature: float | None = None  # °C
    wet_bulb_globe_temperature: float | None = None  # °C
    delta_t: float | None = None  # °C

    # Flags & Lightning
    is_raining: bool = False
    is_freezing: bool = False
    is_lightning: bool = False  # Note: Simple heuristic based on recent strike count
    time_of_last_lightning_strike: datetime.datetime | None = None
    distance_last_lightning_strike: str | None = None
    lightning_strikes_last_3_hours: int | None = 0


# --- Helper Functions ---


def _safe_parse_float(value: str | None) -> float | None:
    """
    Safely attempts to parse a string into a float.

    Handles potential None input, commas as decimal separators, and non-numeric values.
    Strips common units and symbols before parsing.

    Args:
        value: The string value to parse.

    Returns:
        The parsed float, or None if parsing fails or input is None.
    """
    if value is None:
        return None
    try:
        # Remove common units/symbols, replace comma decimal, strip whitespace
        cleaned_value = re.sub(r"[^\d.,-]", "", value).replace(",", ".").strip()
        # Handle empty strings or placeholders after cleaning
        if not cleaned_value or cleaned_value in ["---", "-"]:
            return None
        return float(cleaned_value)
    except (ValueError, TypeError):
        logging.debug(f"Could not parse float from: '{value}'")
        return None


def _safe_parse_int(value: str | None) -> int | None:
    """
    Safely attempts to parse a string into an integer.

    Uses _safe_parse_float first and then converts to int (rounding).

    Args:
        value: The string value to parse.

    Returns:
        The parsed integer, or None if parsing fails or input is None.
    """
    float_val = _safe_parse_float(value)
    if float_val is not None:
        try:
            return int(round(float_val))
        except (ValueError, TypeError):
            logging.debug(f"Could not convert float '{float_val}' to int.")
            return None
    return None


def _get_text_safely(element: Tag | None, default: str | None = None) -> str | None:
    """
    Extracts stripped text content from a BeautifulSoup Tag safely.

    Args:
        element: The BeautifulSoup Tag object.
        default: The value to return if the element is None.

    Returns:
        The stripped text content, or the default value.
    """
    return element.get_text(strip=True) if element else default


def _get_attr_safely(element: Tag | None, attr: str, default: str | None = None) -> str | None:
    """
    Extracts an attribute value from a BeautifulSoup Tag safely.

    Args:
        element: The BeautifulSoup Tag object.
        attr: The name of the attribute to extract.
        default: The value to return if the element is None or lacks the attribute.

    Returns:
        The attribute value, or the default value.
    """
    return element.get(attr, default) if element else default


def _parse_epoch_timestamp(ts_str: str | None) -> datetime.datetime | None:
    """
    Converts a string representing seconds since the epoch into a UTC datetime object.

    Args:
        ts_str: The string containing the epoch timestamp.

    Returns:
        A datetime object (UTC), or None if parsing fails or input is None.
    """
    if not ts_str:
        return None
    try:
        ts_val = int(ts_str)
        # Use timezone-aware UTC datetime
        return datetime.datetime.fromtimestamp(ts_val, tz=datetime.UTC)
    except (ValueError, TypeError):
        logging.debug(f"Could not parse epoch timestamp from: '{ts_str}'")
        return None


def _degrees_to_cardinal(degrees: int | None) -> str | None:
    """
    Converts wind direction in degrees to a 16-point cardinal direction.

    Args:
        degrees: The wind direction in degrees (0-360).

    Returns:
        The cardinal direction string (e.g., "N", "NNE", "SW"), or None if input is None.
    """
    if degrees is None:
        return None
    # Ensure degrees are within 0-359 range
    degrees = degrees % 360
    dirs = [
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
    # Calculate the index for the 16-point compass rose
    ix = round(degrees / (360.0 / len(dirs)))
    return dirs[ix % len(dirs)]


# --- Parsing Logic for HTML Sections ---


def _parse_station_info(soup: BeautifulSoup, data: WeatherData) -> None:
    """Parses station name and update timestamp."""
    station_tag = soup.find("p", class_="weather-tile-device-name")
    data.station_name = _get_text_safely(station_tag)

    timestamp_tag = soup.find("p", class_="weather-tile-timestamp", attrs={"data-param": "param-timestamp"})
    timestamp_str = _get_attr_safely(timestamp_tag, "data-timestamp")
    data.data_updated = _parse_epoch_timestamp(timestamp_str)


def _parse_temperature_humidity(tile: Tag, data: WeatherData) -> None:
    """Parses temperature, humidity, and dew point from its tile."""
    temp_val_tag = tile.find("p", {"data-param": "param-air_temp_with_symbol_and_units"})
    data.temperature = _safe_parse_float(_get_text_safely(temp_val_tag))
    data.is_freezing = data.temperature is not None and data.temperature <= 0.0

    rh_val_tag = tile.find("p", {"data-param": "param-rh_with_symbol"})
    data.humidity = _safe_parse_float(_get_text_safely(rh_val_tag))

    # Dew Point / Heat Index share the same elements
    dp_label_tag = tile.find("p", {"data-param": "param-heat_index_or_dew_point_label"})
    dp_val_tag = tile.find("p", {"data-param": "param-heat_index_or_dew_point_display"})
    label = _get_text_safely(dp_label_tag, "").lower()
    value = _get_text_safely(dp_val_tag)

    if "dew point" in label:
        data.dew_point = _safe_parse_float(value)
    # elif "heat index" in label:
    #     data.heat_index = _safe_parse_float(value) # If needed


def _parse_pressure(tile: Tag, data: WeatherData) -> None:
    """Parses sea level pressure and trend from its tile."""
    slp_val_tag = tile.find("p", {"data-param": "param-sea_level_pres_display"})
    data.sea_level_pressure = _safe_parse_float(_get_text_safely(slp_val_tag))

    trend_val_tag = tile.find("p", {"data-param": "param-pres_trend_localized"})
    data.pressure_trend = _get_text_safely(trend_val_tag)


def _parse_lightning(tile: Tag, data: WeatherData) -> None:
    """Parses lightning data from its tile."""
    last_strike_tag = tile.find("p", {"data-param": "param-lightning_last_strike_fuzzy"})
    timestamp_str = _get_attr_safely(last_strike_tag, "data-timestamp")
    data.time_of_last_lightning_strike = _parse_epoch_timestamp(timestamp_str)

    dist_val_tag = tile.find("p", {"data-param": "param-lightning_last_strike_distance_text_display"})
    data.distance_last_lightning_strike = _get_text_safely(dist_val_tag)

    strike_3h_tag = tile.find("p", {"data-param": "param-lightning_strike_count_last_3hrs"})
    data.lightning_strikes_last_3_hours = (
        _safe_parse_int(_get_text_safely(strike_3h_tag)) or 0
    )  # Default to 0 if parsing fails

    # Simple heuristic: consider it "lightning" if there were strikes in the last 3 hours
    data.is_lightning = (data.lightning_strikes_last_3_hours or 0) > 0


def _parse_wind(tile: Tag, data: WeatherData) -> None:
    """Parses wind speed, direction, lull, and gust from its tile."""
    wind_dir_tag = tile.find("p", {"data-param": "param-wind_dir_display"})
    direction_text = _get_text_safely(wind_dir_tag)
    data.wind_direction = _safe_parse_int(direction_text)  # Extracts digits before °
    data.wind_cardinal = _degrees_to_cardinal(data.wind_direction)

    wind_speed_tag = tile.find("p", {"data-param": "param-wind_avg_display"})
    data.wind_speed = _safe_parse_float(_get_text_safely(wind_speed_tag))

    lull_gust_tag = tile.find("p", {"data-param": "param-wind_lull_gust_with_units"})
    lull_gust_text = _get_text_safely(lull_gust_tag)
    if lull_gust_text:
        # Regex to find two numbers separated by a hyphen, ignoring units
        match = re.search(r"([\d.,]+)\s*-\s*([\d.,]+)", lull_gust_text)
        if match:
            data.wind_lull = _safe_parse_float(match.group(1))
            data.wind_gust = _safe_parse_float(match.group(2))


def _parse_rain(tile: Tag, data: WeatherData) -> None:
    """Parses precipitation data from its tile."""
    desc_tag = tile.find("p", {"data-param": "param-precip_rate_text_display_localized"})
    data.precipitation_description = _get_text_safely(desc_tag)

    # Determine rain status and rate based on description
    if data.precipitation_description and data.precipitation_description.lower() == "none":
        data.precipitation_rate = 0.0
        data.is_raining = False
    elif data.precipitation_description:
        # Site doesn't seem to provide a numeric rate directly in this tile,
        # only the description. We infer raining status.
        data.precipitation_rate = None  # Unknown rate
        data.is_raining = True
    else:
        # No description found
        data.precipitation_rate = None
        data.is_raining = False

    prec_today_tag = tile.find("p", {"data-param": "param-precip_accum_local_today_final_display_with_units"})
    data.precipitation_today = _safe_parse_float(_get_text_safely(prec_today_tag))

    prec_yest_tag = tile.find("p", {"data-param": "param-precip_accumm_local_yesterday_final_display_with_units"})
    data.precipitation_yesterday = _safe_parse_float(_get_text_safely(prec_yest_tag))


def _parse_light_uv(tile: Tag, data: WeatherData) -> None:
    """Parses UV index, illuminance, and solar radiation from its tile."""
    uv_tag = tile.find("p", {"data-param": "param-uv_with_index"})
    data.uv_index = _safe_parse_float(_get_text_safely(uv_tag))

    illum_tag = tile.find("p", {"data-param": "param-lux_display_with_units"})
    data.illuminance = _safe_parse_int(_get_text_safely(illum_tag))

    sol_tag = tile.find("p", {"data-param": "param-solar_radiation_display_with_units"})
    data.solar_radiation = _safe_parse_int(_get_text_safely(sol_tag))


def _parse_diagnostics(tile: Tag, data: WeatherData) -> None:
    """Parses battery voltage and state from its tile."""
    volt_tag = tile.find("p", {"data-param": "param-battery"})
    data.voltage = _safe_parse_float(_get_text_safely(volt_tag))

    state_tag = tile.find("p", {"data-param": "param-battery_state"})
    data.power_save_mode = _get_text_safely(state_tag)


def _parse_advanced_stats(soup: BeautifulSoup, data: WeatherData) -> None:
    """Parses additional stats from the 'level2-more-cc' section."""
    adv_container = soup.find("div", {"id": "level2-more-cc"})
    if not adv_container:
        return

    items = adv_container.find_all("li", class_="grid-stripe-item")
    for li in items:
        label_el = li.find("span", class_="lv-param-label")
        val_el = li.find("span", class_="lv-value-display")
        if not label_el or not val_el:
            continue

        label_text = _get_text_safely(label_el, "").lower()
        val_text = _get_text_safely(val_el)

        if "station pressure" in label_text:
            data.station_pressure = _safe_parse_float(val_text)
        elif "dew point" in label_text and data.dew_point is None:  # Avoid overwriting if already parsed
            data.dew_point = _safe_parse_float(val_text)
        elif "delta t" in label_text:
            data.delta_t = _safe_parse_float(val_text)
        elif "rain duration (today)" in label_text:
            data.precipitation_duration_today = _safe_parse_int(val_text)
        elif "rain duration (yesterday)" in label_text:
            data.precipitation_duration_yesterday = _safe_parse_int(val_text)
        elif "wet bulb temperature" in label_text:
            data.wet_bulb_temperature = _safe_parse_float(val_text)
        elif "wet bulb globe temperature" in label_text:
            data.wet_bulb_globe_temperature = _safe_parse_float(val_text)


def _parse_html_content(html_content: str) -> WeatherData:
    """
    Parses the HTML content using BeautifulSoup and extracts weather data.

    Args:
        html_content: The HTML string to parse.

    Returns:
        A WeatherData object populated with the extracted data. Returns an object
        with data_available=False if parsing is unsuccessful.
    """
    data = WeatherData()
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Check if the main container or any tiles exist
        if not soup.find("div", class_="weather-tile"):
            logging.warning("No weather tiles found in the HTML content.")
            return data  # Return default object with data_available=False

        data.data_available = True  # Assume data is available if tiles are found

        # --- Parse different sections ---
        _parse_station_info(soup, data)

        # Find tiles by their type attribute
        tile_parsers = {
            "air_temperature_humidity": _parse_temperature_humidity,
            "barometric_pressure": _parse_pressure,
            "lightning": _parse_lightning,
            "wind": _parse_wind,
            "rain": _parse_rain,
            "light": _parse_light_uv,
            "diagnostics": _parse_diagnostics,
        }

        for tile_type, parser_func in tile_parsers.items():
            tile = soup.find("div", {"data-tile-type": tile_type})
            if tile:
                try:
                    parser_func(tile, data)
                except Exception as e:
                    logging.error(f"Error parsing tile '{tile_type}': {e}", exc_info=True)
            else:
                logging.warning(f"Weather tile not found for type: '{tile_type}'")

        # Parse the advanced stats section
        try:
            _parse_advanced_stats(soup, data)
        except Exception as e:
            logging.error(f"Error parsing advanced stats: {e}", exc_info=True)

    except Exception as e:
        logging.error(f"Error during HTML parsing: {e}", exc_info=True)
        data.data_available = False  # Mark as unavailable on general parsing error

    return data


# --- Main Scraper Function ---


async def scrape_weather_data(
    url: str,
    container_selector: str = "section#grid-view",
    wait_timeout: int = DEFAULT_WAIT_TIMEOUT,
    save_html: bool = False,
) -> WeatherData:
    """Scrapes weather data using Playwright's async API."""
    data = WeatherData()
    playwright: Playwright | None = None
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None

    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=COMMON_USER_AGENT, viewport=COMMON_VIEWPORT)

        # Block resources
        await context.route("**/*.{png,jpg,jpeg,gif,svg,css}", lambda route: route.abort())
        await context.route("**/google-analytics.com/**", lambda route: route.abort())
        await context.route("**/googletagmanager.com/**", lambda route: route.abort())

        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=wait_timeout + 10000)

        container_locator: Locator = page.locator(container_selector)
        await container_locator.wait_for(state="visible", timeout=wait_timeout)

        try:
            temp_selector = f"{container_selector} .air_temperature_humidity .weather-tile-main-value[data-param='param-air_temp_with_symbol_and_units']"
            await page.locator(temp_selector).wait_for(state="visible", timeout=wait_timeout // 2)
        except PlaywrightTimeoutError:
            logging.warning("Temperature element check timed out, proceeding anyway.")

        grid_view_html = await container_locator.inner_html()

        if save_html:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"scraped_content_{timestamp}.html"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(grid_view_html)
            except OSError as e:
                logging.error(f"Failed to save HTML file: {e}")

        data = _parse_html_content(grid_view_html)

    except Exception as e:
        logging.error(f"Error during scraping: {e}", exc_info=True)
        data.data_available = False
    finally:
        if page:
            await page.close()
        if context:
            await context.close()
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()

    return data


# --- API Client ---


class TempestWxScraperApiClientError(Exception):
    """Custom exception for API client errors."""

    pass


class TempestWxScraperApiClient:
    def __init__(self, station_id: str):
        self.station_id = station_id
        self.url = f"https://tempestwx.com/station/{station_id}/grid"

    async def async_get_data(self) -> WeatherData:
        """Asynchronously fetch weather data from the station."""
        try:
            return await scrape_weather_data(
                url=self.url, container_selector="section#grid-view", wait_timeout=DEFAULT_WAIT_TIMEOUT
            )
        except Exception as e:
            raise TempestWxScraperApiClientError(f"Failed to scrape data: {e}") from e


# --- Example Usage ---
if __name__ == "__main__":
    import asyncio

    async def main():
        # URL of the specific weather station grid view
        target_url = "https://tempestwx.com/station/130627/grid"

        logging.info(f"Attempting to scrape data from: {target_url}")

        # Call the main scraping function, enable saving HTML for debugging
        weather_info = await scrape_weather_data(target_url, save_html=True)

        print("\n" + "=" * 30)
        print("--- Scraped Weather Data ---")
        print("=" * 30)

        if weather_info.data_available:
            # Convert dataclass to dict for easy JSON serialization
            # Handle datetime objects by converting them to ISO format strings
            weather_dict = asdict(weather_info)
            print(json.dumps(weather_dict, indent=2, default=str))

            # Example of accessing specific fields after checking availability
            print("-" * 30)
            print("Selected Fields:")
            print(f"  Station: {weather_info.station_name}")
            print(f"  Updated (UTC): {weather_info.data_updated}")
            print(f"  Temperature: {weather_info.temperature}°C")
            print(f"  Is Raining: {weather_info.is_raining}")
            print(
                f"  Wind: {weather_info.wind_speed} km/h from {weather_info.wind_cardinal} ({weather_info.wind_direction}°)"
            )
            print(f"  Lightning (last 3h): {weather_info.lightning_strikes_last_3_hours}")
        else:
            print("Scraping failed or no data was retrieved.")
            print("Check log messages above for details.")

        print("=" * 30 + "\n")

    asyncio.run(main())
