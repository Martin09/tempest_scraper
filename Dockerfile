# check=skip=SecretsUsedInArgOrEnv

# Tempest Weather Station Scraper — Docker image
#
# Multi-stage build: uv resolves Python deps in a disposable builder stage,
# keeping the uv binary and its cache out of the final image.  The runtime
# stage carries only the virtualenv, Playwright's headless Chromium shell,
# and the minimal shared libraries Chromium actually links against.

# ---- Builder: resolve & install Python deps ----
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Cache mount persists the Chromium download across rebuilds, so bumping a
# Python dependency doesn't trigger re-downloading the ~560 MB browser binary.
#
# We copy only chromium_headless_shell (the binary actually used in headless
# mode) and stub out the full chromium directory with an empty folder so
# Playwright's integrity check passes without shipping ~300 MB of unused
# browser.  The glob dynamically picks up whatever revision Playwright
# downloads, so upgrading Playwright just requires a rebuild.
RUN --mount=type=cache,target=/var/cache/playwright \
    PLAYWRIGHT_BROWSERS_PATH=/var/cache/playwright \
    .venv/bin/python -m playwright install chromium \
    && mkdir -p /root/.cache/ms-playwright \
    && cp -R /var/cache/playwright/chromium_headless_shell-* /root/.cache/ms-playwright/ \
    && for d in /var/cache/playwright/chromium-*/; do \
    mkdir -p "/root/.cache/ms-playwright/$(basename "$d")"; \
    done

# ---- Runtime ----
FROM python:3.12-slim-bookworm

# Minimal shared libraries required by Playwright's bundled Chromium.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libwayland-client0 \
    libx11-6 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv .venv/
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright
COPY . .

ENV PATH="/app/.venv/bin:$PATH"

ENV STATION_ID=""
ENV MQTT_HOST=""
ENV MQTT_PORT="1883"
ENV MQTT_USERNAME=""
ENV MQTT_PASSWORD=""
ENV SCRAPE_INTERVAL_MINUTES="5"

HEALTHCHECK --interval=6m --timeout=15s --start-period=120s --retries=2 \
    CMD find /tmp/heartbeat -mmin -10 | grep -q heartbeat

CMD ["python", "main.py"]
