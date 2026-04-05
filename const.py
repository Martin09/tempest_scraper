"""Constants for the Tempest Weather Station scraper."""

# --- Browser ---
COMMON_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
)
COMMON_VIEWPORT = {"width": 1920, "height": 1080}
DEFAULT_WAIT_TIMEOUT = 45_000  # milliseconds

# --- MQTT ---
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_KEEPALIVE = 60
MQTT_DISCOVERY_PREFIX = "homeassistant"
MQTT_STATE_TOPIC_TEMPLATE = "tempestwx/{station_id}/state"
MQTT_AVAILABILITY_TOPIC_TEMPLATE = "tempestwx/{station_id}/status"
HOMEASSISTANT_STATUS_TOPIC = "homeassistant/status"

# --- Scraper ---
DEFAULT_UPDATE_INTERVAL = 5  # minutes
MAX_RETRY_ATTEMPTS = 3
