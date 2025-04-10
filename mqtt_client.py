"""MQTT client for publishing weather data & discovery configs."""

import json
import logging
import time
from typing import Optional

import paho.mqtt.client as mqtt

from scraper_page import WeatherData
from sensor import SENSOR_CONFIGS, BINARY_SENSOR_CONFIGS

# MQTT Constants
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_KEEPALIVE = 60
MQTT_DISCOVERY_PREFIX = "homeassistant"

# MQTT Topic Templates
MQTT_STATE_TOPIC_TEMPLATE = "tempestwx/{station_id}/state"
MQTT_AVAILABILITY_TOPIC_TEMPLATE = "tempestwx/{station_id}/status"

_LOGGER = logging.getLogger(__name__)

class MQTTClient:
    """MQTT client for publishing weather data & Home Assistant discovery configs."""

    def __init__(
        self,
        station_id: str,
        host: str,
        port: int = DEFAULT_MQTT_PORT,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.station_id = station_id
        self.host = host
        self.port = port

        # For example: "tempest/<station_id>/state"
        self.state_topic = MQTT_STATE_TOPIC_TEMPLATE.format(station_id=station_id)
        # e.g.: "tempest/<station_id>/availability"
        self.availability_topic = MQTT_AVAILABILITY_TOPIC_TEMPLATE.format(station_id=station_id)

        self._client = mqtt.Client(client_id=f"tempestwx_scraper_{station_id}")
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_publish = self._on_publish

        if username and password:
            self._client.username_pw_set(username, password)

        # Last Will & Testament => If we lose connection, we become "offline"
        self._client.will_set(
            self.availability_topic,
            payload="offline",
            qos=1,
            retain=True
        )

    def _on_connect(self, client, userdata, flags, rc):
        """Called when the client connects to MQTT."""
        if rc == 0:
            _LOGGER.info(f"Connected to MQTT broker at {self.host}")
            self.publish_availability("online")
            # Publish discovery configs so Home Assistant can auto-discover sensors
            self.publish_discovery_config()
        else:
            _LOGGER.error(f"Failed to connect to MQTT broker: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        _LOGGER.warning(f"Disconnected from MQTT broker: {rc}")

    def _on_publish(self, client, userdata, mid):
        _LOGGER.debug(f"Published message with ID={mid}")

    def connect(self) -> bool:
        """Connect to the MQTT broker and start the loop."""
        try:
            time.sleep(1)
            self._client.connect(self.host, self.port, DEFAULT_MQTT_KEEPALIVE)
            time.sleep(1)
            self._client.loop_start()
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def disconnect(self):
        """Gracefully disconnect from the broker."""
        self.publish_availability("offline")
        self._client.loop_stop()
        self._client.disconnect()

    def publish_availability(self, status: str):
        """Publish 'online' or 'offline' to the availability topic."""
        self._client.publish(
            self.availability_topic,
            payload=status,
            qos=1,
            retain=True
        )

    def publish_discovery_config(self):
        """
        Publishes discovery messages for each sensor & binary_sensor
        in the "single component" format:
        
          <discovery_prefix>/<component>/<unique_id>/config

        That unique_id is typically "tempest_<station_id>_<object_id>".
        """

        # Basic metadata about the device itself:
        device_info = {
            "identifiers": [f"tempest_{self.station_id}"],
            "name": "Tempest Weather Station",
            "manufacturer": "WeatherFlow",
            "model": "Tempest",
            "sw_version": "1.0",
        }

        # Publish each numeric/standard sensor
        for sensor in SENSOR_CONFIGS:
            # Build a truly unique ID
            unique_id = f"tempest_{self.station_id}_{sensor['object_id']}"
            config_topic = f"{MQTT_DISCOVERY_PREFIX}/sensor/{unique_id}/config"

            config_payload = {
                "name": sensor["name"],
                "unique_id": unique_id,
                # object_id is optional; if omitted, HA uses the slugified name or unique_id
                # "object_id": sensor["object_id"],  # uncomment if you want to control entity_id

                "state_topic": self.state_topic,
                "availability_topic": self.availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": device_info,
                "value_template": sensor.get("value_template"),

                # These can help with better UI and sensor history:
                "device_class": sensor.get("device_class"),
                "state_class": sensor.get("state_class"),
                "unit_of_measurement": sensor.get("unit_of_measurement"),

                # Usually we want discovery configs retained so HA remembers them on restart
                "enabled_by_default": True,
            }

            payload_str = json.dumps(config_payload)
            self._client.publish(
                config_topic,
                payload=payload_str,
                qos=1,
                retain=True
            )
            _LOGGER.debug(f"Published sensor discovery config => {config_topic}")

        # Publish each binary sensor
        for bsensor in BINARY_SENSOR_CONFIGS:
            unique_id = f"tempest_{self.station_id}_{bsensor['object_id']}"
            config_topic = f"{MQTT_DISCOVERY_PREFIX}/binary_sensor/{unique_id}/config"

            config_payload = {
                "name": bsensor["name"],
                "unique_id": unique_id,
                # "object_id": bsensor["object_id"],  # optional

                "state_topic": self.state_topic,
                "availability_topic": self.availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device": device_info,
                "value_template": bsensor.get("value_template"),

                # For binary_sensors, define how HA sees "on" vs "off":
                "payload_on": bsensor.get("payload_on", "true"),
                "payload_off": bsensor.get("payload_off", "false"),

                # Could also set device_class e.g. "moisture", "cold", "safety"
                "device_class": bsensor.get("device_class"),

                "enabled_by_default": True,
            }

            payload_str = json.dumps(config_payload)
            self._client.publish(
                config_topic,
                payload=payload_str,
                qos=1,
                retain=True
            )
            _LOGGER.debug(f"Published binary_sensor discovery config => {config_topic}")

        _LOGGER.info("Published all MQTT discovery configs for station %s", self.station_id)

    def publish_data(self, data: WeatherData) -> bool:
        """
        Publishes the entire WeatherData object in one JSON message
        to self.state_topic. The sensors/binary_sensors then parse
        out their respective fields using their value_template.
        """
        try:
            # Convert to JSON (default=str to handle datetimes gracefully)
            payload = json.dumps(data.__dict__, default=str)
            result = self._client.publish(
                self.state_topic,
                payload=payload,
                qos=1,
                retain=False  # Typically we don't retain ephemeral sensor states
            )
            result.wait_for_publish(timeout=5.0)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                _LOGGER.info("Published WeatherData to %s", self.state_topic)
                return True
            else:
                _LOGGER.error("publish_data() failed with RC=%s", result.rc)
                return False
        except Exception as e:
            _LOGGER.error("Error in publish_data: %s", e)
            return False
