"""Dual-mode MQTT SQL_Logger (offline SimulatedMqttBus + optional live paho-mqtt)."""

from __future__ import annotations

import csv
import json
import logging
import math
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from warehouse_fleet.config import MqttConfig

logger = logging.getLogger(__name__)

MqttCallback = Callable[[str, str | bytes], None]


def mqtt_topic_matches(pattern: str, topic: str) -> bool:
    """Match an MQTT topic against a filter supporting '+' and '#' wildcards."""
    if not pattern or not topic:
        return False

    pat_levels = pattern.split("/")
    top_levels = topic.split("/")

    for idx, pat in enumerate(pat_levels):
        if pat == "#":
            return idx == len(pat_levels) - 1
        if idx >= len(top_levels):
            return False
        if pat != "+" and pat != top_levels[idx]:
            return False

    return len(pat_levels) == len(top_levels)


class SimulatedMqttBus:
    """Synchronous in-memory MQTT broker/bus for offline testing and CSV replay."""

    def __init__(self) -> None:
        self._subscriptions: list[tuple[str, MqttCallback]] = []
        self.published_messages: list[tuple[str, str]] = []

    def subscribe(self, topic_filter: str, callback: MqttCallback) -> None:
        self._subscriptions.append((topic_filter, callback))

    def publish(self, topic: str, payload: str | bytes) -> int:
        text_payload = payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)
        self.published_messages.append((topic, text_payload))
        delivered = 0
        for topic_filter, callback in self._subscriptions:
            if mqtt_topic_matches(topic_filter, topic):
                callback(topic, payload)
                delivered += 1
        return delivered

    def replay_messages(self, messages: Iterable[tuple[str, str | bytes]]) -> int:
        count = 0
        for topic, payload in messages:
            self.publish(topic, payload)
            count += 1
        return count

    def replay_sensor_csv(
        self,
        csv_path: Path,
        *,
        topic: str = "robot/R1/sensor/dht22",
    ) -> int:
        count = 0
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                payload = json.dumps(
                    {
                        "robot_id": row["robot_id"],
                        "sensor": row["sensor"],
                        "temp": float(row["temp_c"]),
                        "hum": float(row["hum_pct"]),
                        "ts_epoch": int(row["ts_epoch"]),
                    }
                )
                self.publish(topic, payload)
                count += 1
        return count


class FleetMqttLogger:
    """SQL_Logger persisting ESP32 MQTT telemetry frames into SensorLog."""

    def __init__(self, engine: Engine, client_id: str = "SQL_Logger") -> None:
        self.engine = engine
        self.client_id = client_id
        self.robot_statuses: dict[str, str] = {}
        self.errors: list[str] = []
        self.ingested_count: int = 0

    def attach_to_bus(self, bus: SimulatedMqttBus) -> None:
        bus.subscribe("robot/+/status", self.handle_message)
        bus.subscribe("robot/+/sensor/+", self.handle_message)

    def handle_message(self, topic: str, payload: str | bytes) -> bool:
        """Parse status or JSON telemetry message and persist valid SensorLog rows."""
        try:
            raw_text = (
                payload.decode("utf-8")
                if isinstance(payload, (bytes, bytearray))
                else str(payload)
            ).strip()
        except UnicodeDecodeError as exc:
            msg = f"Invalid UTF-8 payload on topic {topic}: {exc}"
            self.errors.append(msg)
            logger.warning(msg)
            return False

        if mqtt_topic_matches("robot/+/status", topic):
            robot_id = topic.split("/")[1]
            self.robot_statuses[robot_id] = raw_text
            return True

        if mqtt_topic_matches("robot/+/sensor/+", topic):
            try:
                data = json.loads(raw_text)
                if not isinstance(data, dict):
                    raise ValueError("Telemetry JSON payload must be an object.")
                robot_id = str(data["robot_id"]).strip()
                sensor = str(data["sensor"]).strip()
                temp_c = float(data["temp"])
                hum_pct = float(data["hum"])
                if not robot_id or not sensor:
                    raise ValueError("robot_id and sensor must be non-empty.")
                if not (math.isfinite(temp_c) and math.isfinite(hum_pct)):
                    raise ValueError("temp and hum must be finite numbers.")
                if "distance_mm" in data and data["distance_mm"] is not None:
                    distance_mm = float(data["distance_mm"])
                    if not math.isfinite(distance_mm):
                        raise ValueError("distance_mm must be a finite number.")
                ts_epoch = int(data.get("ts_epoch", int(time.time())))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                msg = f"Malformed telemetry payload on {topic}: {exc}"
                self.errors.append(msg)
                logger.warning(msg)
                return False

            try:
                with self.engine.begin() as conn:
                    conn.execute(
                        text(
                            """
                            INSERT INTO SensorLog (robot_id, sensor, temp_c, hum_pct, ts_epoch)
                            VALUES (:robot_id, :sensor, :temp_c, :hum_pct, :ts_epoch)
                            """
                        ),
                        {
                            "robot_id": robot_id,
                            "sensor": sensor,
                            "temp_c": round(temp_c, 2),
                            "hum_pct": round(hum_pct, 2),
                            "ts_epoch": ts_epoch,
                        },
                    )
                self.ingested_count += 1
                return True
            except SQLAlchemyError as exc:
                msg = f"Database write failed for {topic}: {exc}"
                self.errors.append(msg)
                logger.error(msg)
                return False

        msg = f"Ignored unsupported topic: {topic}"
        self.errors.append(msg)
        return False

    def on_message(self, _client, _userdata, msg) -> bool:
        """paho-mqtt compatible on_message callback."""
        return self.handle_message(msg.topic, msg.payload)

    def build_paho_client(self, config: MqttConfig | None = None):
        """Lazily construct an authenticated paho-mqtt MQTTv311 client."""
        try:
            import paho.mqtt.client as mqtt  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "paho-mqtt is an optional dependency and is not installed. "
                "Install with `pip install paho-mqtt` or use --simulate mode."
            ) from exc

        cfg = config or MqttConfig.from_env()
        client_kwargs: dict[str, Any] = {
            "client_id": cfg.client_id or self.client_id,
            "protocol": mqtt.MQTTv311,
        }
        callback_api = getattr(mqtt, "CallbackAPIVersion", None)
        if callback_api is not None:
            client_kwargs["callback_api_version"] = callback_api.VERSION1
        client = mqtt.Client(**client_kwargs)
        if cfg.username:
            client.username_pw_set(cfg.username, cfg.password)

        def _on_connect(cli, _userdata, _flags, rc):
            if rc == 0:
                cli.subscribe("robot/+/status")
                cli.subscribe(cfg.topic or "robot/+/sensor/+")
            else:
                logger.error("MQTT connection failed with rc=%s", rc)

        client.on_connect = _on_connect
        client.on_message = self.on_message
        return client
