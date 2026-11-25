"""Unified command-line interface for Warehouse Robot Fleet Telemetry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from warehouse_fleet.config import DatabaseConfig, MqttConfig
from warehouse_fleet.datasets import generate_all_datasets
from warehouse_fleet.db import create_fleet_engine, init_schema, seed_demo_data, seed_routelog_r1_safe
from warehouse_fleet.mqtt_logger import FleetMqttLogger, SimulatedMqttBus
from warehouse_fleet.queries import PRESET_DEFINITIONS, run_preset_query


def _default_repo_root() -> Path:
    pkg_dir = Path(__file__).resolve().parent
    candidate = pkg_dir.parent.parent
    if (candidate / "pyproject.toml").exists():
        return candidate
    return Path.cwd()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="warehouse-fleet",
        description="Warehouse Robot Fleet Telemetry CLI (MySQL/SQLite, MQTT, Datasets, Dashboard)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db", help="Initialize database schema and seed Topic 5 fixtures")
    p_init.add_argument("--db-url", default=None, help="Explicit SQLAlchemy database URL")
    p_init.add_argument("--data-dir", default=None, help="Directory containing generated CSVs")
    p_init.add_argument(
        "--with-benchmark",
        action="store_true",
        help="Load performance_benchmark.csv instead of 3-row 180s/600s demo",
    )

    p_gen = sub.add_parser("generate-data", help="Generate deterministic Topic 5 CSVs and PNGs")
    p_gen.add_argument("--output-dir", default=None, help="Target data directory (default: ./data)")
    p_gen.add_argument("--seed", type=int, default=42, help="Deterministic RNG seed")

    p_seed = sub.add_parser("seed-routelog", help="Run safe 3NF RouteLog seeder for a robot/day")
    p_seed.add_argument("--db-url", default=None, help="Explicit SQLAlchemy database URL")
    p_seed.add_argument("--day", default="2025-09-01")
    p_seed.add_argument("--start", default="08:00:00")
    p_seed.add_argument("--end", default="10:00:00")
    p_seed.add_argument("--step-min", type=int, default=5)
    p_seed.add_argument("--robot-id", default="R1")

    p_query = sub.add_parser("query", help="Run one of the Topic 5 analytical preset queries")
    p_query.add_argument("--db-url", default=None, help="Explicit SQLAlchemy database URL")
    p_query.add_argument(
        "--preset",
        default="1_robot_sensor_count",
        choices=[p.preset_id for p in PRESET_DEFINITIONS],
    )
    p_query.add_argument("--robot-id", default="R1")
    p_query.add_argument("--date", default="2025-09-01")
    p_query.add_argument("--format", choices=("table", "json"), default="table")

    p_mqtt = sub.add_parser("mqtt-logger", help="Run SQL_Logger in simulated replay or live paho-mqtt mode")
    p_mqtt.add_argument("--db-url", default=None, help="Explicit SQLAlchemy database URL")
    p_mqtt.add_argument("--simulate", action="store_true", help="Replay simulated MQTT messages offline")
    p_mqtt.add_argument("--csv", default=None, help="Sensor CSV path for offline replay")

    p_dash = sub.add_parser("dashboard", help="Launch the 6-tab Tkinter telemetry dashboard")
    p_dash.add_argument("--db-url", default=None, help="Explicit SQLAlchemy database URL")
    p_dash.add_argument("--base-dir", default=None, help="Repository base directory for data/images")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    repo_root = _default_repo_root()

    if args.command == "generate-data":
        out_dir = Path(args.output_dir) if args.output_dir else (repo_root / "data")
        summary = generate_all_datasets(out_dir, seed=args.seed)
        print(
            json.dumps(
                {
                    "output_dir": str(out_dir),
                    "csv_files": [
                        str(summary["robot_route_csv"]),
                        str(summary["robot_movelog_csv"]),
                        str(summary["performance_benchmark_csv"]),
                        str(summary["sensor_log_csv"]),
                    ],
                    "images": [str(p) for p in summary["images"]],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "init-db":
        engine = create_fleet_engine(db_url=args.db_url, config=DatabaseConfig.from_env())
        init_schema(engine)
        data_dir = Path(args.data_dir) if args.data_dir else (repo_root / "data")
        seed_demo_data(
            engine,
            data_dir=data_dir if data_dir.exists() else None,
            include_benchmark=args.with_benchmark,
        )
        print("Database initialized and seeded.")
        return 0

    if args.command == "seed-routelog":
        engine = create_fleet_engine(db_url=args.db_url, config=DatabaseConfig.from_env())
        init_schema(engine)
        inserted = seed_routelog_r1_safe(
            engine,
            day=args.day,
            start=args.start,
            end=args.end,
            step_min=args.step_min,
            robot_id=args.robot_id,
        )
        print(f"Seeded {inserted} RouteLog rows for {args.robot_id} on {args.day}.")
        return 0

    if args.command == "query":
        engine = create_fleet_engine(db_url=args.db_url, config=DatabaseConfig.from_env())
        init_schema(engine)
        res = run_preset_query(
            engine,
            args.preset,
            robot_id=args.robot_id,
            target_date=args.date,
        )
        if args.format == "json":
            records = [dict(zip(res.columns, row)) for row in res.rows]
            print(json.dumps(records, indent=2, default=str))
        else:
            print(" | ".join(res.columns))
            print("-" * max(20, len(" | ".join(res.columns))))
            for row in res.rows:
                print(" | ".join("None" if v is None else str(v) for v in row))
        return 0

    if args.command == "mqtt-logger":
        engine = create_fleet_engine(db_url=args.db_url, config=DatabaseConfig.from_env())
        init_schema(engine)
        mqtt_logger = FleetMqttLogger(engine)

        if args.simulate:
            bus = SimulatedMqttBus()
            mqtt_logger.attach_to_bus(bus)
            bus.publish("robot/R1/status", "online")
            csv_path = Path(args.csv) if args.csv else (repo_root / "data" / "sensor_log_sample.csv")
            if csv_path.exists():
                bus.replay_sensor_csv(csv_path, topic="robot/R1/sensor/dht22")
            else:
                bus.publish(
                    "robot/R1/sensor/dht22",
                    json.dumps({"robot_id": "R1", "sensor": "DHT22", "temp": 23.5, "hum": 50.8}),
                )
            print(
                json.dumps(
                    {
                        "mode": "simulate",
                        "statuses": mqtt_logger.robot_statuses,
                        "ingested_rows": mqtt_logger.ingested_count,
                        "errors": len(mqtt_logger.errors),
                    }
                )
            )
            return 0

        cfg = MqttConfig.from_env()
        client = mqtt_logger.build_paho_client(cfg)
        client.connect(cfg.broker, cfg.port)
        client.loop_forever()
        return 0

    if args.command == "dashboard":
        from warehouse_fleet.dashboard import launch_dashboard

        launch_dashboard(
            db_url=args.db_url,
            base_dir=Path(args.base_dir) if args.base_dir else repo_root,
        )
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
