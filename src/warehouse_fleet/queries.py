"""Dual-dialect analytical & preset queries for Topic 5 Warehouse Fleet."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from warehouse_fleet.db import ALLOWED_IMPORT_TABLES


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Tabular query output shared by CLI, controller, and Tkinter UI."""

    columns: list[str]
    rows: list[tuple[Any, ...]]


@dataclass(frozen=True, slots=True)
class PresetDefinition:
    preset_id: str
    label: str
    description: str


PRESET_DEFINITIONS: tuple[PresetDefinition, ...] = (
    PresetDefinition(
        "1_robot_sensor_count",
        "1) Robot & sensor count",
        "Count attached sensors per robot across Robot LEFT JOIN Sensor.",
    ),
    PresetDefinition(
        "2_latest_per_sensor",
        "2) Latest value per sensor",
        "Most recent DataLog measurement for each sensor.",
    ),
    PresetDefinition(
        "3_temp_logs_robot_date",
        "3) Temp logs of robot on date",
        "Temperature readings for a selected robot on YYYY-MM-DD.",
    ),
    PresetDefinition(
        "4_null_value_sensors",
        "4) Sensors with NULL value",
        "Sensors or DataLog records containing NULL values (e.g. Camera).",
    ),
    PresetDefinition(
        "5_total_logs_per_robot",
        "5) Total logs per robot",
        "Total DataLog records grouped by robot.",
    ),
    PresetDefinition(
        "6_performance_dense_rank",
        "6) Task performance DENSE_RANK",
        "Average task duration (s & min) ranked via DENSE_RANK() ASC.",
    ),
    PresetDefinition(
        "7_robot_commands",
        "7) Inter-robot commands (RobotCommand)",
        "Sender-receiver command handshake log.",
    ),
    PresetDefinition(
        "8_routelog_3nf_trace",
        "8) 3NF RouteLog trace",
        "Normalized RouteLog joined with Robot and Operator for selected robot.",
    ),
    PresetDefinition(
        "9_sensorlog_mqtt_latest",
        "9) Latest ESP32 SensorLog telemetry",
        "Recent DHT22 MQTT telemetry frames from SensorLog.",
    ),
    PresetDefinition(
        "10_raw_route_trace",
        "10) Raw route trace (RobotRoute_raw)",
        "Denormalized RobotRoute_raw trajectory for selected robot and date.",
    ),
)

PRESET_LABELS: dict[str, str] = {p.preset_id: p.label for p in PRESET_DEFINITIONS}


def _duration_seconds_expr(dialect_name: str) -> str:
    if dialect_name == "sqlite":
        return "CAST(ROUND((julianday(end_time) - julianday(start_time)) * 86400.0) AS INTEGER)"
    return "TIMESTAMPDIFF(SECOND, start_time, end_time)"


def run_preset_query(
    engine: Engine,
    preset_id: str,
    *,
    robot_id: str = "R1",
    target_date: str = "2025-09-01",
    limit: int = 500,
) -> QueryResult:
    """Execute one of the Topic 5 preset or extended analytical queries."""
    dialect = engine.dialect.name
    params: dict[str, Any] = {
        "robot_id": robot_id,
        "target_date": target_date,
        "limit": limit,
    }

    if preset_id == "1_robot_sensor_count":
        sql = """
            SELECT r.robot_id,
                   r.name,
                   r.type,
                   r.year,
                   COUNT(s.sensor_id) AS sensor_count
            FROM Robot r
            LEFT JOIN Sensor s ON r.robot_id = s.robot_id
            GROUP BY r.robot_id, r.name, r.type, r.year
            ORDER BY r.robot_id ASC
        """
    elif preset_id == "2_latest_per_sensor":
        sql = """
            SELECT sensor_id, type, robot_id, timestamp, value
            FROM (
                SELECT s.sensor_id,
                       s.type,
                       s.robot_id,
                       d.timestamp,
                       d.value,
                       ROW_NUMBER() OVER (
                           PARTITION BY s.sensor_id
                           ORDER BY d.timestamp DESC, d.log_id DESC
                       ) AS rn
                FROM Sensor s
                LEFT JOIN DataLog d ON s.sensor_id = d.sensor_id
            ) ranked
            WHERE rn = 1
            ORDER BY sensor_id ASC
        """
    elif preset_id == "3_temp_logs_robot_date":
        sql = """
            SELECT d.log_id,
                   d.robot_id,
                   s.sensor_id,
                   s.type,
                   d.timestamp,
                   d.value
            FROM DataLog d
            JOIN Sensor s ON d.sensor_id = s.sensor_id
            WHERE d.robot_id = :robot_id
              AND s.type = 'Temp'
              AND DATE(d.timestamp) = :target_date
            ORDER BY d.timestamp ASC
        """
    elif preset_id == "4_null_value_sensors":
        sql = """
            SELECT s.sensor_id,
                   s.type,
                   s.robot_id,
                   d.log_id,
                   d.timestamp,
                   d.value
            FROM Sensor s
            LEFT JOIN DataLog d ON s.sensor_id = d.sensor_id
            WHERE d.value IS NULL OR s.value IS NULL
            ORDER BY s.sensor_id ASC, d.timestamp ASC
        """
    elif preset_id == "5_total_logs_per_robot":
        sql = """
            SELECT r.robot_id,
                   r.name,
                   COUNT(d.log_id) AS total_logs
            FROM Robot r
            LEFT JOIN DataLog d ON r.robot_id = d.robot_id
            GROUP BY r.robot_id, r.name
            ORDER BY total_logs DESC, r.robot_id ASC
        """
    elif preset_id == "6_performance_dense_rank":
        dur_expr = _duration_seconds_expr(dialect)
        sql = f"""
            SELECT robot_id,
                   COUNT(*) AS task_count,
                   ROUND(AVG({dur_expr}), 4) AS avg_task_time_s,
                   ROUND(AVG({dur_expr}) / 60.0, 4) AS avg_task_time_min,
                   DENSE_RANK() OVER (ORDER BY AVG({dur_expr}) ASC) AS perf_rank
            FROM Performance
            GROUP BY robot_id
            ORDER BY perf_rank ASC, robot_id ASC
        """
    elif preset_id == "7_robot_commands":
        sql = """
            SELECT cmd_id, sender_id, receiver_id, cmd_content, timestamp
            FROM RobotCommand
            ORDER BY timestamp DESC, cmd_id DESC
            LIMIT :limit
        """
    elif preset_id == "8_routelog_3nf_trace":
        sql = """
            SELECT rl.log_id,
                   rl.robot_id,
                   r.name AS robot_name,
                   o.op_id,
                   o.name AS operator_name,
                   rl.location,
                   rl.timestamp
            FROM RouteLog rl
            JOIN Robot r ON rl.robot_id = r.robot_id
            JOIN Operator o ON rl.op_id = o.op_id
            WHERE rl.robot_id = :robot_id
            ORDER BY rl.timestamp ASC
            LIMIT :limit
        """
    elif preset_id == "9_sensorlog_mqtt_latest":
        sql = """
            SELECT id, robot_id, sensor, temp_c, hum_pct, ts_epoch, created_at
            FROM SensorLog
            WHERE robot_id = :robot_id
            ORDER BY ts_epoch DESC, id DESC
            LIMIT :limit
        """
    elif preset_id == "10_raw_route_trace":
        sql = """
            SELECT id, robot_id, robot_name, location, operator, timestamp
            FROM RobotRoute_raw
            WHERE robot_id = :robot_id
              AND DATE(timestamp) = :target_date
            ORDER BY timestamp ASC
            LIMIT :limit
        """
    else:
        raise ValueError(f"Unknown preset_id: {preset_id!r}")

    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        columns = list(result.keys())
        rows = [tuple(r) for r in result.fetchall()]
    return QueryResult(columns=columns, rows=rows)


def fetch_table_rows(
    engine: Engine,
    table_name: str,
    *,
    limit: int = 500,
    robot_id: str | None = None,
) -> QueryResult:
    """Safely fetch rows from an allowlisted fleet table."""
    if table_name not in ALLOWED_IMPORT_TABLES:
        raise ValueError(f"Table {table_name!r} is not allowed.")

    order_clauses = {
        "Robot": "robot_id ASC",
        "Sensor": "sensor_id ASC",
        "Operator": "op_id ASC",
        "DataLog": "log_id ASC",
        "RobotRoute_raw": "timestamp ASC, id ASC",
        "RobotMoveLog": "timestamp ASC, id ASC",
        "RouteLog": "timestamp ASC, log_id ASC",
        "RobotCommand": "timestamp DESC, cmd_id DESC",
        "ImageData": "img_id ASC",
        "Performance": "perf_id ASC",
        "SensorLog": "id DESC",
    }
    order_by = order_clauses.get(table_name, "1 ASC")
    params: dict[str, Any] = {"limit": limit}
    where_clause = ""

    if robot_id and table_name in {
        "Robot",
        "Sensor",
        "DataLog",
        "RobotRoute_raw",
        "RobotMoveLog",
        "RouteLog",
        "ImageData",
        "Performance",
        "SensorLog",
    }:
        where_clause = "WHERE robot_id = :robot_id"
        params["robot_id"] = robot_id
    elif robot_id and table_name == "RobotCommand":
        where_clause = "WHERE sender_id = :robot_id OR receiver_id = :robot_id"
        params["robot_id"] = robot_id

    sql = f"SELECT * FROM {table_name} {where_clause} ORDER BY {order_by} LIMIT :limit"
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        columns = list(result.keys())
        rows = [tuple(r) for r in result.fetchall()]
    return QueryResult(columns=columns, rows=rows)
