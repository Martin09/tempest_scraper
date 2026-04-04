"""MQTT client for publishing weather data and HA discovery configs."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import paho.mqtt.client as mqtt

from const import (
    DEFAULT_MQTT_KEEPALIVE,
    DEFAULT_MQTT_PORT,
    HOMEASSISTANT_STATUS_TOPIC,
    MQTT_AVAILABILITY_TOPIC_TEMPLATE,
    MQTT_DISCOVERY_PREFIX,
    MQTT_STATE_TOPIC_TEMPLATE,
)
from models import WeatherData
from sensor import BINARY_SENSOR_CONFIGS, SENSOR_CONFIGS

_LOGGER = logging.getLogger(__name__)


def _get_sw_version() -> str:
    try:
        return version("tempest-scraper")
    except PackageNotFoundError:
        return "0.1.0"


def _strip_none(d: dict[str, Any]) -> dict[str, Any]:
    """Remove keys with None values so HA discovery payloads stay clean."""
    return {k: v for k, v in d.items() if v is not None}


class MQTTClient:
    """MQTT client for publishing weather data and Home Assistant discovery configs."""

    def __init__(
        self,
        station_id: str,
        host: str,
        port: int = DEFAULT_MQTT_PORT,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.station_id = station_id
        self.host = host
        self.port = port
        self.state_topic = MQTT_STATE_TOPIC_TEMPLATE.format(station_id=station_id)
        self.availability_topic = MQTT_AVAILABILITY_TOPIC_TEMPLATE.format(station_id=station_id)

        # paho-mqtt v2 requires an explicit CallbackAPIVersion
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"tempestwx_scraper_{station_id}",
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_publish = self._on_publish
        self._client.on_message = self._on_message

        if username and password:
            self._client.username_pw_set(username, password)

        # LWT: if we lose connection the broker will publish "offline" for us
        self._client.will_set(self.availability_topic, payload="offline", qos=1, retain=True)

    # ------------------------------------------------------------------
    # Callbacks (paho-mqtt v2 signatures)
    # ------------------------------------------------------------------

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        if reason_code.is_failure:
            _LOGGER.error("Failed to connect to MQTT broker: %s", reason_code)
            return
        _LOGGER.info("Connected to MQTT broker at %s", self.host)
        # Subscribe to HA status topic so we can re-publish discovery when HA restarts
        client.subscribe(HOMEASSISTANT_STATUS_TOPIC, qos=1)
        self.publish_availability("online")
        self.publish_discovery_config()

    def _on_disconnect(
        self, client: mqtt.Client, userdata: Any, disconnect_flags: Any, reason_code: Any, properties: Any
    ) -> None:
        _LOGGER.warning("Disconnected from MQTT broker: %s", reason_code)

    def _on_publish(self, client: mqtt.Client, userdata: Any, mid: int, *args: Any) -> None:
        _LOGGER.debug("Published message mid=%s", mid)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """Re-publish discovery configs when Home Assistant comes back online."""
        if msg.topic == HOMEASSISTANT_STATUS_TOPIC:
            payload = msg.payload.decode(errors="replace").strip()
            if payload == "online":
                _LOGGER.info("Home Assistant online — re-publishing discovery configs.")
                self.publish_discovery_config()
                self.publish_availability("online")

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Connect to the MQTT broker and start the background loop."""
        try:
            self._client.connect(self.host, self.port, DEFAULT_MQTT_KEEPALIVE)
            self._client.loop_start()
            return True
        except Exception:
            _LOGGER.error("Failed to connect to MQTT broker.", exc_info=True)
            return False

    def disconnect(self) -> None:
        """Gracefully disconnect: publish offline status, stop loop."""
        self.publish_availability("offline")
        self._client.loop_stop()
        self._client.disconnect()

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish_availability(self, status: str) -> None:
        """Publish 'online' or 'offline' to the availability topic."""
        self._client.publish(self.availability_topic, payload=status, qos=1, retain=True)

    def publish_discovery_config(self) -> None:
        """Publish MQTT discovery payloads for all sensors and binary sensors."""
        device_info = {
            "identifiers": [f"tempest_{self.station_id}"],
            "name": "Tempest Weather Station",
            "manufacturer": "WeatherFlow",
            "model": "Tempest",
            "sw_version": _get_sw_version(),
        }

        common = {
            "state_topic": self.state_topic,
            "availability_topic": self.availability_topic,
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": device_info,
            "enabled_by_default": True,
        }

        for sensor in SENSOR_CONFIGS:
            unique_id = f"tempest_{self.station_id}_{sensor.object_id}"
            cfg = _strip_none(
                {
                    **common,
                    "name": sensor.name,
                    "unique_id": unique_id,
                    "value_template": sensor.value_template,
                    "device_class": sensor.device_class,
                    "state_class": sensor.state_class,
                    "unit_of_measurement": sensor.unit_of_measurement,
                }
            )
            topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{unique_id}/config"
            self._client.publish(topic, payload=json.dumps(cfg), qos=1, retain=True)
            _LOGGER.debug("Published sensor discovery → %s", topic)

        for bsensor in BINARY_SENSOR_CONFIGS:
            unique_id = f"tempest_{self.station_id}_{bsensor.object_id}"
            cfg = _strip_none(
                {
                    **common,
                    "name": bsensor.name,
                    "unique_id": unique_id,
                    "value_template": bsensor.value_template,
                    "device_class": bsensor.device_class,
                    "payload_on": bsensor.payload_on,
                    "payload_off": bsensor.payload_off,
                }
            )
            topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/{unique_id}/config"
            self._client.publish(topic, payload=json.dumps(cfg), qos=1, retain=True)
            _LOGGER.debug("Published binary_sensor discovery → %s", topic)

        _LOGGER.info("Published all MQTT discovery configs for station %s.", self.station_id)

    def publish_data(self, data: WeatherData) -> bool:
        """Publish the full WeatherData payload as a single JSON state message."""
        try:
            payload = json.dumps(asdict(data), default=str)
            result = self._client.publish(self.state_topic, payload=payload, qos=1, retain=False)
            result.wait_for_publish(timeout=5.0)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                _LOGGER.info("Published WeatherData to %s", self.state_topic)
                return True
            _LOGGER.error("publish_data() failed with rc=%s", result.rc)
            return False
        except Exception:
            _LOGGER.exception("Error in publish_data.")
            return False
