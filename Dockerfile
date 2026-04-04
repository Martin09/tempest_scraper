# Tempest Weather Station Scraper — Docker image
#
# Single-stage build using the official uv base image (Debian Bookworm slim).
# Bookworm provides the glibc environment required by Playwright/Chromium.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install system deps needed by Playwright's Chromium (handled mostly by
# `playwright install --with-deps`, but a few libs need to be present first).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifests first so Docker can cache the install layer.
# This layer is only invalidated when pyproject.toml or uv.lock changes.
COPY pyproject.toml uv.lock ./

# Install runtime dependencies only (no dev extras)
RUN uv sync --frozen --no-dev

# Install Chromium browser and its OS-level dependencies
RUN uv run playwright install --with-deps chromium

# Copy application source
COPY . .

# Runtime configuration — override all at `docker run` time or via --env-file
ENV STATION_ID=""
ENV MQTT_HOST=""
ENV MQTT_PORT="1883"
ENV MQTT_USERNAME=""
ENV MQTT_PASSWORD=""
ENV SCRAPE_INTERVAL_MINUTES="5"

# Health check: ensure a successful scrape has occurred within the last 10 minutes
# (2× the default 5-min interval — allows one missed cycle before alerting).
# main.py touches /tmp/heartbeat after every successful scrape + publish.
HEALTHCHECK --interval=6m --timeout=15s --start-period=120s --retries=2 \
    CMD find /tmp/heartbeat -mmin -10 | grep -q heartbeat

CMD ["uv", "run", "main.py"]
