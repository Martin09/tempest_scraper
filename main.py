#!/usr/bin/env python3

"""Main module for the Tempest Weather Station scraper."""

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta

import schedule

from mqtt_client import MQTTClient
from scraper_map import TempestWxScraperApiClient

DEFAULT_UPDATE_INTERVAL = 5  # Default update interval in minutes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_LOGGER = logging.getLogger(__name__)


class TempestScraper:
    """Main scraper class coordinating API and MQTT clients."""

    def __init__(self):
        """Initialize the scraper."""
        self.station_id = os.environ.get("STATION_ID")
        self.mqtt_host = os.environ.get("MQTT_HOST")
        self.mqtt_port = int(os.environ.get("MQTT_PORT", 1883))
        self.mqtt_username = os.environ.get("MQTT_USERNAME")
        self.mqtt_password = os.environ.get("MQTT_PASSWORD")
        self.update_interval = int(os.environ.get("SCRAPE_INTERVAL_MINUTES", DEFAULT_UPDATE_INTERVAL))

        self.api_client: TempestWxScraperApiClient | None = None
        self.mqtt_client: MQTTClient | None = None
        self.last_successful_scrape: datetime | None = None

    def initialize(self) -> bool:
        """Initialize clients."""
        try:
            # Initialize API client
            self.api_client = TempestWxScraperApiClient(self.station_id)

            # Initialize MQTT client
            self.mqtt_client = MQTTClient(
                station_id=self.station_id,
                host=self.mqtt_host,
                port=self.mqtt_port,
                username=self.mqtt_username,
                password=self.mqtt_password,
            )

            if not self.mqtt_client.connect():
                raise RuntimeError("Failed to connect to MQTT broker")

            return True

        except Exception as e:
            _LOGGER.error(f"Initialization failed: {e}")
            self.cleanup()
            return False

    async def scrape_and_publish(self):
        """Perform scraping and publish results."""
        try:
            weather_data = await self.api_client.async_get_data()

            if weather_data.data_available:
                self.last_successful_scrape = datetime.now()
                if self.mqtt_client.publish_data(weather_data):
                    _LOGGER.info(f"Published data for station {self.station_id}. Temp: {weather_data.temperature}°C")
                else:
                    _LOGGER.error("Failed to publish data")
            else:
                self._handle_failed_scrape()

        except Exception as e:
            _LOGGER.error(f"Error during scrape and publish: {e}")
            self._handle_failed_scrape()

    def _handle_failed_scrape(self):
        """Handle failed scrape attempts."""
        if self.last_successful_scrape and (datetime.now() - self.last_successful_scrape) > timedelta(
            minutes=self.update_interval * 3
        ):
            _LOGGER.warning("Multiple scrape failures, marking as offline")
            self.mqtt_client.publish_availability("offline")

    def cleanup(self):
        """Clean up resources."""
        if self.mqtt_client:
            self.mqtt_client.disconnect()

        if self.api_client:
            asyncio.run(self.api_client.close())

    def run(self):
        """Run the main scraper loop."""
        if not self.initialize():
            return

        _LOGGER.info(f"Starting scraper for station {self.station_id} with {self.update_interval} minute interval")

        # Initial scrape
        asyncio.run(self.scrape_and_publish())

        # Schedule future scrapes
        schedule.every(self.update_interval).minutes.do(lambda: asyncio.run(self.scrape_and_publish()))

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            _LOGGER.info("Shutdown requested")
        finally:
            self.cleanup()


def main():
    """Main entry point."""
    scraper = TempestScraper()
    scraper.run()


if __name__ == "__main__":
    main()
