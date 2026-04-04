#!/usr/bin/env python3

"""Main entry point for the Tempest Weather Station scraper.

Reads configuration from environment variables (load from .env automatically).
Uses a single persistent asyncio event loop — no repeated asyncio.run() calls
and no `schedule` dependency. The Playwright browser is kept alive between
scrapes inside the API client.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from datetime import datetime, timedelta

from dotenv import load_dotenv

# Load .env BEFORE any os.environ.get() calls
load_dotenv()

from const import DEFAULT_UPDATE_INTERVAL, MAX_RETRY_ATTEMPTS, OFFLINE_THRESHOLD_MULTIPLIER
from models import WeatherData
from mqtt_client import MQTTClient
from scraper_page import TempestWxScraperApiClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_LOGGER = logging.getLogger(__name__)


class TempestScraper:
    """Coordinates the page scraper and MQTT publisher."""

    def __init__(self) -> None:
        self.station_id = os.environ.get("STATION_ID", "").strip()
        self.mqtt_host = os.environ.get("MQTT_HOST", "").strip()
        self.mqtt_port = int(os.environ.get("MQTT_PORT", 1883))
        self.mqtt_username = os.environ.get("MQTT_USERNAME") or None
        self.mqtt_password = os.environ.get("MQTT_PASSWORD") or None
        self.update_interval = int(
            os.environ.get("SCRAPE_INTERVAL_MINUTES", DEFAULT_UPDATE_INTERVAL)
        )

        if not self.station_id:
            raise ValueError("STATION_ID environment variable is required.")
        if not self.mqtt_host:
            raise ValueError("MQTT_HOST environment variable is required.")

        self.api_client: TempestWxScraperApiClient | None = None
        self.mqtt_client: MQTTClient | None = None
        self.last_successful_scrape: datetime | None = None

    def initialize(self) -> bool:
        """Initialise the API and MQTT clients."""
        try:
            self.api_client = TempestWxScraperApiClient(self.station_id)
            self.mqtt_client = MQTTClient(
                station_id=self.station_id,
                host=self.mqtt_host,
                port=self.mqtt_port,
                username=self.mqtt_username,
                password=self.mqtt_password,
            )
            if not self.mqtt_client.connect():
                raise RuntimeError("Failed to connect to MQTT broker.")
            return True
        except Exception:
            _LOGGER.exception("Initialization failed.")
            self._sync_cleanup()
            return False

    async def scrape_and_publish(self) -> bool:
        """Scrape data with exponential-backoff retries; publish on success."""
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                data: WeatherData = await self.api_client.async_get_data()
                if data.data_available:
                    self.last_successful_scrape = datetime.now()
                    if self.mqtt_client.publish_data(data):
                        _LOGGER.info(
                            "Published data for station %s — temp: %s°C",
                            self.station_id,
                            data.temperature,
                        )
                        return True
                    _LOGGER.error(
                        "MQTT publish failed (attempt %d/%d).", attempt, MAX_RETRY_ATTEMPTS
                    )
                else:
                    _LOGGER.warning(
                        "No data available from scraper (attempt %d/%d).",
                        attempt,
                        MAX_RETRY_ATTEMPTS,
                    )
            except Exception:
                _LOGGER.exception(
                    "Error during scrape/publish (attempt %d/%d).", attempt, MAX_RETRY_ATTEMPTS
                )

            if attempt < MAX_RETRY_ATTEMPTS:
                wait = 2**attempt
                _LOGGER.info("Retrying in %ds…", wait)
                await asyncio.sleep(wait)

        self._handle_failed_scrape()
        return False

    def _handle_failed_scrape(self) -> None:
        """Mark the station offline if it has been unreachable for too long."""
        threshold = timedelta(minutes=self.update_interval * OFFLINE_THRESHOLD_MULTIPLIER)
        if self.last_successful_scrape and (datetime.now() - self.last_successful_scrape) > threshold:
            _LOGGER.warning("Repeated scrape failures — publishing offline status.")
            self.mqtt_client.publish_availability("offline")

    async def _async_cleanup(self) -> None:
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        if self.api_client:
            await self.api_client.close()

    def _sync_cleanup(self) -> None:
        """Synchronous cleanup used only during initialization failures."""
        if self.mqtt_client:
            self.mqtt_client.disconnect()

    async def run(self) -> None:
        """Main async loop — runs until SIGTERM/SIGINT is received."""
        if not self.initialize():
            return

        _LOGGER.info(
            "Starting scraper for station %s, polling every %d min.",
            self.station_id,
            self.update_interval,
        )

        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def _request_stop() -> None:
            _LOGGER.info("Shutdown signal received.")
            stop_event.set()

        # Signal handlers (Unix / Linux containers); silently ignored on Windows
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _request_stop)
            except NotImplementedError:
                pass  # Windows does not support add_signal_handler

        try:
            while not stop_event.is_set():
                await self.scrape_and_publish()
                # Wait for the next poll or an early stop signal
                try:
                    await asyncio.wait_for(
                        stop_event.wait(), timeout=self.update_interval * 60
                    )
                except asyncio.TimeoutError:
                    pass  # Normal timeout — time for the next scrape
        finally:
            await self._async_cleanup()
            _LOGGER.info("Scraper shut down cleanly.")


def main() -> None:
    """Entry point."""
    try:
        scraper = TempestScraper()
    except ValueError as exc:
        logging.critical("Configuration error: %s", exc)
        return
    asyncio.run(scraper.run())


if __name__ == "__main__":
    main()
