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


def test_paho_v2_callback_api_version_and_distance_mm(monkeypatch, tmp_path: Path) -> None:
    import sys
    from types import ModuleType

    captured_kwargs: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)
            self.on_connect = None
            self.on_message = None

        def username_pw_set(self, _u, _p):
            pass

    fake_paho_mqtt_client = ModuleType("paho.mqtt.client")
    fake_paho_mqtt_client.MQTTv311 = 4
    fake_paho_mqtt_client.CallbackAPIVersion = SimpleNamespace(VERSION1="V1")
    fake_paho_mqtt_client.Client = FakeClient
    fake_paho_mqtt = ModuleType("paho.mqtt")
    fake_paho_mqtt.client = fake_paho_mqtt_client
    fake_paho = ModuleType("paho")
    fake_paho.mqtt = fake_paho_mqtt

    monkeypatch.setitem(sys.modules, "paho", fake_paho)
    monkeypatch.setitem(sys.modules, "paho.mqtt", fake_paho_mqtt)
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", fake_paho_mqtt_client)

    db_file = tmp_path / "mqtt_v2.db"
    engine = create_fleet_engine(f"sqlite:///{db_file.as_posix()}")
    init_schema(engine)
    mqtt_logger = FleetMqttLogger(engine)

    client = mqtt_logger.build_paho_client()
    assert client is not None
    assert captured_kwargs.get("callback_api_version") == "V1"

    assert mqtt_logger.handle_message(
        "robot/R1/sensor/dht22",
        json.dumps({"robot_id": "R1", "sensor": "DHT22", "temp": 24.0, "hum": 50.0, "distance_mm": 325}),
    ) is True
    assert mqtt_logger.handle_message(
        "robot/R1/sensor/dht22",
        json.dumps({"robot_id": "R1", "sensor": "DHT22", "temp": 24.0, "hum": 50.0, "distance_mm": float("nan")}),
    ) is False
    engine.dispose()
