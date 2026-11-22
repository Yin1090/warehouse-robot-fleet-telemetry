"""Tests for SimulatedMqttBus wildcard routing and FleetMqttLogger SQL_Logger."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import text

from warehouse_fleet.db import create_fleet_engine, init_schema
from warehouse_fleet.mqtt_logger import (
    FleetMqttLogger,
    SimulatedMqttBus,
    mqtt_topic_matches,
)


def test_mqtt_topic_wildcard_matching() -> None:
    assert mqtt_topic_matches("robot/+/status", "robot/R1/status")
    assert not mqtt_topic_matches("robot/+/status", "robot/R1/sensor/dht22")
    assert mqtt_topic_matches("robot/+/sensor/+", "robot/R1/sensor/dht22")
    assert mqtt_topic_matches("robot/#", "robot/R1/sensor/dht22")
    assert not mqtt_topic_matches("robot/+/sensor", "robot/R1/sensor/dht22")


def test_simulated_bus_replay_and_on_message(tmp_path: Path, data_dir: Path) -> None:
    db_file = tmp_path / "mqtt.db"
    engine = create_fleet_engine(f"sqlite:///{db_file.as_posix()}")
    init_schema(engine)

    bus = SimulatedMqttBus()
    mqtt_logger = FleetMqttLogger(engine)
    mqtt_logger.attach_to_bus(bus)

    bus.publish("robot/R1/status", "online")
    assert mqtt_logger.robot_statuses["R1"] == "online"

    replayed = bus.replay_sensor_csv(
        data_dir / "sensor_log_sample.csv",
        topic="robot/R1/sensor/dht22",
    )
    assert replayed == 12
    assert mqtt_logger.ingested_count == 12

    # Verify paho-mqtt style on_message callback with bytes payload
    msg = SimpleNamespace(
        topic="robot/R2/sensor/dht22",
        payload=json.dumps(
            {"robot_id": "R2", "sensor": "DHT22", "temp": 24.15, "hum": 49.70, "ts_epoch": 1756713999}
        ).encode("utf-8"),
    )
    assert mqtt_logger.on_message(None, None, msg) is True
    assert mqtt_logger.ingested_count == 13

    # Malformed payloads are caught safely without crashing
    assert mqtt_logger.handle_message("robot/R1/sensor/dht22", "{not-json") is False
    assert (
        mqtt_logger.handle_message(
            "robot/R1/sensor/dht22",
            json.dumps({"robot_id": "R1", "sensor": "DHT22", "temp": float("nan"), "hum": 50.0}),
        )
        is False
    )
    assert len(mqtt_logger.errors) == 2

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM SensorLog")).scalar_one()
    assert total == 13
    engine.dispose()
