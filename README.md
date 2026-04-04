# Tempest Weather Station Scraper

[![Tests](https://github.com/Martin09/tempest_scraper/actions/workflows/tests.yml/badge.svg)](https://github.com/Martin09/tempest_scraper/actions/workflows/tests.yml)
[![Build and Push Docker Image](https://github.com/Martin09/tempest_scraper/actions/workflows/docker.yml/badge.svg)](https://github.com/Martin09/tempest_scraper/actions/workflows/docker.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python-based web scraper that extracts weather data from TempestWX.com stations and publishes it to MQTT for Home Assistant integration.

## Features

- 🌡️ Scrapes real-time weather data from TempestWX.com stations
- 🔄 Auto-discovery integration with Home Assistant via MQTT
- 📊 Comprehensive weather metrics including:
  - Temperature, humidity, and pressure
  - Wind speed, direction, and gusts
  - Precipitation and lightning data
  - UV index and solar radiation
  - Station diagnostics
- ⚡ Async-first design using Playwright
- 🏃‍♂️ Lightweight and efficient resource usage
- 🐳 Docker support

## Prerequisites

- [uv](https://github.com/astral-sh/uv) package installer
- [HomeAssistant](https://www.home-assistant.io/)
- MQTT broker (e.g., Mosquitto)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Martin09/tempest_scraper.git
cd tempest-scraper
```

2. Create and sync virtual environment using `uv`:
```bash
uv sync
```

3. Install Playwright browser:
```bash
playwright install chromium
```

## Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your settings.

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `STATION_ID` | Your TempestWX.com station ID | - | Yes |
| `MQTT_HOST` | IP address or hostname of your MQTT Broker | - | Yes |
| `MQTT_PORT` | Port of your MQTT Broker | `1883` | No |
| `MQTT_USERNAME` | Username for MQTT Broker | - | No |
| `MQTT_PASSWORD` | Password for MQTT Broker | - | No |
| `SCRAPE_INTERVAL_MINUTES` | Frequency of scraping in minutes | `5` | No |

## Usage

Run the scraper:
```bash
uv run main.py
```

## Docker Support

### Using the Pre-built Image (Recommended)
You can directly use the completely pre-built image automatically updated on GitHub Container Registry (GHCR):

```bash
docker run -d \
  --name tempest-scraper \
  --restart unless-stopped \
  --env-file .env \
  ghcr.io/martin09/tempest_scraper:latest
```

### Build Locally
Alternatively, you can build the image yourself from the source:

1. Build the container:
```bash
docker build -t tempest-scraper .
```

2. Run with environment variables:
```bash
docker run -d \
  --name tempest-scraper \
  --restart unless-stopped \
  --env-file .env \
  tempest-scraper
```

## Home Assistant Integration

The scraper automatically configures device discovery in Home Assistant when:
1. Your MQTT broker is configured in Home Assistant
2. MQTT discovery is enabled in your configuration
3. The scraper successfully connects to MQTT

All sensors will appear under a single device named "Tempest Weather Station".

## Available Sensors

- **Core Metrics**
  - Temperature
  - Humidity
  - Barometric Pressure
  - Wind Speed/Direction
  - Precipitation
  - UV Index
  - Solar Radiation

- **Advanced Metrics**
  - Wet Bulb Temperature
  - Delta T
  - Lightning Data

- **Binary Sensors**
  - Is Raining
  - Is Freezing
  - Lightning Activity

## Troubleshooting

1. **Connection Issues**
   - Verify your station ID is correct
   - Check MQTT broker connectivity
   - Ensure your network can reach tempestwx.com

2. **No Data**
   - Check logs for scraping errors
   - Verify station is online and public
   - Try increasing `SCRAPE_INTERVAL_MINUTES`

## Contributing

1. Fork the repository
2. Create your feature branch
3. Install pre-commit hooks:
```bash
uv run prek install
```
4. Run tests and linting (these will also run automatically on commit if hooks are installed):
```bash
uv run ruff check .
uv run pytest
```
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
