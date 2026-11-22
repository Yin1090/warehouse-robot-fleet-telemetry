"""Pure-Python MVC controller for the Warehouse Fleet Dashboard & CLI."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

from PIL import Image
from sqlalchemy import text
from sqlalchemy.engine import Engine

from warehouse_fleet.db import (
    ALLOWED_IMPORT_TABLES,
    load_csv_into_table,
    seed_routelog_r1_safe,
)
from warehouse_fleet.mqtt_logger import FleetMqttLogger, SimulatedMqttBus
from warehouse_fleet.queries import (
    PRESET_DEFINITIONS,
    PresetDefinition,
    QueryResult,
    fetch_table_rows,
    run_preset_query,
)

ALLOWED_TABLES: frozenset[str] = ALLOWED_IMPORT_TABLES


class FleetDashboardController:
    """Headless business-logic controller decoupled from Tkinter widgets."""

    def __init__(self, engine: Engine, base_dir: Path | str | None = None) -> None:
        self.engine = engine
        self.base_dir = Path(base_dir).resolve() if base_dir is not None else Path.cwd().resolve()

    def list_tables(self) -> list[str]:
        return sorted(ALLOWED_TABLES)

    def list_presets(self) -> tuple[PresetDefinition, ...]:
        return PRESET_DEFINITIONS

    def fetch_table(
        self,
        table_name: str,
        *,
        limit: int = 500,
        robot_id: str | None = None,
    ) -> QueryResult:
        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Unsupported or disallowed table: {table_name!r}")
        return fetch_table_rows(self.engine, table_name, limit=limit, robot_id=robot_id)

    def run_preset(
        self,
        preset_id: str,
        *,
        robot_id: str = "R1",
        target_date: str = "2025-09-01",
        limit: int = 500,
    ) -> QueryResult:
        return run_preset_query(
            self.engine,
            preset_id,
            robot_id=robot_id,
            target_date=target_date,
            limit=limit,
        )

    def seed_routelog_r1(
        self,
        *,
        day: str = "2025-09-01",
        start: str = "08:00:00",
        end: str = "10:00:00",
        step_min: int = 5,
        robot_id: str = "R1",
    ) -> int:
        return seed_routelog_r1_safe(
            self.engine,
            day=day,
            start=start,
            end=end,
            step_min=step_min,
            robot_id=robot_id,
        )

    def simulate_mqtt_sample(self, *, robot_id: str = "R1") -> int:
        """Publish a deterministic simulated ESP32 status + DHT22 sample into SensorLog."""
        bus = SimulatedMqttBus()
        mqtt_logger = FleetMqttLogger(self.engine)
        mqtt_logger.attach_to_bus(bus)
        bus.publish(f"robot/{robot_id}/status", "online")
        payload = json.dumps(
            {
                "robot_id": robot_id,
                "sensor": "DHT22",
                "temp": 23.50,
                "hum": 50.80,
                "ts_epoch": int(time.time()),
            }
        )
        bus.publish(f"robot/{robot_id}/sensor/dht22", payload)
        return mqtt_logger.ingested_count

    def export_csv(self, result: QueryResult, out_path: Path | str) -> Path:
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(result.columns)
            for row in result.rows:
                writer.writerow(["" if val is None else val for val in row])
        return target

    def import_csv(
        self,
        table_name: str,
        csv_path: Path | str,
        *,
        replace: bool = False,
    ) -> int:
        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Unsupported or disallowed table: {table_name!r}")
        return load_csv_into_table(self.engine, table_name, Path(csv_path), replace=replace)

    def list_images(self, robot_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT img_id, robot_id, img_path, timestamp FROM ImageData"
        params: dict[str, Any] = {}
        if robot_id:
            sql += " WHERE robot_id = :robot_id"
            params["robot_id"] = robot_id
        sql += " ORDER BY img_id ASC"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [dict(row) for row in rows]

    def resolve_image_path(self, img_path: str) -> Path:
        """Resolve an image path inside base_dir, rejecting path traversal."""
        if not img_path or not img_path.strip():
            raise ValueError("Image path must not be empty.")

        candidate = Path(img_path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.base_dir / candidate).resolve()

        try:
            resolved.relative_to(self.base_dir)
        except ValueError as exc:
            raise ValueError(
                f"Image path escapes base directory {self.base_dir}: {img_path!r}"
            ) from exc

        if not resolved.is_file():
            raise FileNotFoundError(f"Inspection image file not found: {resolved}")
        return resolved

    def load_image(self, img_path: str) -> Image.Image:
        resolved = self.resolve_image_path(img_path)
        with Image.open(resolved) as img:
            return img.copy()
