"""Tests for SQL schema DDL, foreign keys, 3NF sharing, and seed_routelog_r1_safe."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from warehouse_fleet.db import (
    create_fleet_engine,
    get_column_type,
    init_schema,
    seed_demo_data,
    seed_routelog_r1_safe,
)


def test_all_11_tables_exist_and_seeded(sqlite_engine) -> None:
    inspector = inspect(sqlite_engine)
    tables = set(inspector.get_table_names())
    expected = {
        "Robot",
        "Sensor",
        "Operator",
        "DataLog",
        "RobotRoute_raw",
        "RobotMoveLog",
        "RouteLog",
        "RobotCommand",
        "ImageData",
        "Performance",
        "SensorLog",
    }
    assert expected.issubset(tables)

    with sqlite_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM Robot")).scalar_one() == 4
        assert conn.execute(text("SELECT COUNT(*) FROM Sensor")).scalar_one() == 2
        assert conn.execute(text("SELECT COUNT(*) FROM DataLog")).scalar_one() == 2
        assert conn.execute(text("SELECT COUNT(*) FROM RobotCommand")).scalar_one() == 2
        assert conn.execute(text("SELECT COUNT(*) FROM ImageData")).scalar_one() == 4
        assert conn.execute(text("SELECT COUNT(*) FROM Performance")).scalar_one() == 3
        assert conn.execute(text("SELECT COUNT(*) FROM RobotRoute_raw")).scalar_one() == 1000
        assert conn.execute(text("SELECT COUNT(*) FROM SensorLog")).scalar_one() == 12


def test_sqlite_foreign_keys_enforced(sqlite_engine) -> None:
    with sqlite_engine.begin() as conn:
        pragma_fk = conn.execute(text("PRAGMA foreign_keys")).scalar_one()
        assert pragma_fk == 1

    # ON DELETE RESTRICT prevents removing Robot referenced by Sensor/DataLog/RobotCommand
    with pytest.raises(IntegrityError):
        with sqlite_engine.begin() as conn:
            conn.execute(text("DELETE FROM Robot WHERE robot_id = 'R1'"))

    # Invalid FK insertion is rejected
    with pytest.raises(IntegrityError):
        with sqlite_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO RobotCommand (sender_id, receiver_id, cmd_content, timestamp)
                    VALUES ('R99', 'R1', 'PING', '2025-09-01 08:10:00')
                    """
                )
            )


def test_seed_routelog_r1_safe_numeric_and_idempotent(sqlite_engine) -> None:
    dtype, _ = get_column_type(sqlite_engine, "RouteLog", "op_id")
    assert dtype in {"integer", "int", "bigint"}

    count1 = seed_routelog_r1_safe(sqlite_engine, day="2025-09-01", seed=42)
    assert count1 == 25

    with sqlite_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT rl.robot_id, rl.op_id, rl.location, rl.timestamp, o.name
                FROM RouteLog rl
                JOIN Operator o ON rl.op_id = o.op_id
                WHERE rl.robot_id = 'R1'
                ORDER BY rl.timestamp ASC
                """
            )
        ).fetchall()

    assert len(rows) == 25
    assert rows[0][3] == "2025-09-01 08:00:00"
    assert rows[-1][3] == "2025-09-01 10:00:00"
    assert all(r[4] == "SIM-R1" for r in rows)
    assert all(r[2] in {"A1", "A2", "B1", "B2", "C1", "C2"} for r in rows)

    # Running a second time replaces the same day's R1 rows without duplicating RouteLog or leaking Operator rows
    with sqlite_engine.connect() as conn:
        op_count_1 = conn.execute(text("SELECT COUNT(*) FROM Operator")).scalar_one()

    count2 = seed_routelog_r1_safe(sqlite_engine, day="2025-09-01", seed=42)
    assert count2 == 25
    with sqlite_engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM RouteLog WHERE robot_id = 'R1'")
        ).scalar_one()
        op_count_2 = conn.execute(text("SELECT COUNT(*) FROM Operator")).scalar_one()
    assert total == 25
    assert op_count_2 == op_count_1


def test_mysql_ddl_includes_indexes_and_sql01_seeds_r4(repo_root: Path) -> None:
    from warehouse_fleet.db import _ddl_statements

    mysql_stmts = [s for s in _ddl_statements("mysql") if s is not None]
    joined = "\n".join(mysql_stmts)
    for idx_name in (
        "idx_sensor_robot",
        "idx_datalog_robot_time",
        "idx_rr_robot_time",
        "idx_route_robot_time",
        "idx_performance_robot_time",
        "idx_sensorlog_robot_ts",
    ):
        assert idx_name in joined

    sql01 = (repo_root / "sql" / "01_core_erd_schema.sql").read_text(encoding="utf-8")
    assert "'R4'" in sql01


def test_seed_routelog_r1_safe_string_op_id_schema(tmp_path: Path) -> None:
    db_file = tmp_path / "string_op_id.db"
    engine = create_fleet_engine(f"sqlite:///{db_file.as_posix()}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE Robot (
                    robot_id VARCHAR(10) PRIMARY KEY,
                    name VARCHAR(50) NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE Operator (
                    op_id INT PRIMARY KEY,
                    name VARCHAR(50) NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE RouteLog (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    robot_id VARCHAR(10) NOT NULL,
                    op_id VARCHAR(50) NOT NULL,
                    location VARCHAR(50) NOT NULL,
                    timestamp DATETIME NOT NULL,
                    FOREIGN KEY (robot_id) REFERENCES Robot(robot_id),
                    FOREIGN KEY (op_id) REFERENCES Operator(op_id)
                )
                """
            )
        )

    dtype, _ = get_column_type(engine, "RouteLog", "op_id")
    assert dtype == "varchar"

    inserted = seed_routelog_r1_safe(engine, day="2025-09-01", seed=42)
    assert inserted == 25

    with engine.connect() as conn:
        op_ids = [
            row[0]
            for row in conn.execute(
                text("SELECT op_id FROM RouteLog ORDER BY timestamp ASC")
            ).fetchall()
        ]
    assert op_ids[0] == "OP-R1-20250901-080000"
    assert op_ids[-1] == "OP-R1-20250901-100000"
    engine.dispose()


def test_q1_and_q6_tables_coexist_without_collision(tmp_path: Path) -> None:
    db_file = tmp_path / "coexist.db"
    engine = create_fleet_engine(f"sqlite:///{db_file.as_posix()}")
    init_schema(engine)
    seed_demo_data(engine)
    seed_routelog_r1_safe(engine)
    with engine.connect() as conn:
        q1_robots = conn.execute(text("SELECT robot_id, type, year FROM Robot ORDER BY robot_id")).fetchall()
        q6_routes = conn.execute(text("SELECT COUNT(*) FROM RouteLog")).scalar_one()
    assert q1_robots[0] == ("R1", "AGV", 2023)
    assert q6_routes == 25
    engine.dispose()
