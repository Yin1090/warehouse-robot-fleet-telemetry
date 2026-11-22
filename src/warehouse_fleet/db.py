"""Dual-dialect SQLAlchemy 2.x schema DDL, CSV loaders, and safe 3NF seeders."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine

from warehouse_fleet.config import DatabaseConfig

ZONES: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")
NUMERIC_SQL_TYPES: frozenset[str] = frozenset(
    {"tinyint", "smallint", "mediumint", "int", "integer", "bigint", "decimal", "numeric"}
)

ALLOWED_IMPORT_TABLES: frozenset[str] = frozenset(
    {
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
)


def create_fleet_engine(
    db_url: str | None = None,
    config: DatabaseConfig | None = None,
) -> Engine:
    """Create a SQLAlchemy 2.x engine with SQLite foreign-key enforcement."""
    if db_url is None:
        cfg = config or DatabaseConfig.from_env()
        db_url = cfg.sqlalchemy_url()

    engine = create_engine(db_url, pool_pre_ping=True, future=True)

    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_conn, _connection_record) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()

    return engine


def insert_ignore_sql(dialect_name: str, table: str, columns: Sequence[str]) -> str:
    """Build a dialect-aware INSERT IGNORE / INSERT OR IGNORE statement."""
    col_list = ", ".join(columns)
    val_list = ", ".join(f":{col}" for col in columns)
    verb = "INSERT OR IGNORE" if dialect_name == "sqlite" else "INSERT IGNORE"
    return f"{verb} INTO {table} ({col_list}) VALUES ({val_list})"


def _ddl_statements(dialect_name: str) -> list[str]:
    if dialect_name == "sqlite":
        int_pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
        big_pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
        suffix = ""
        fk_actions = "ON UPDATE CASCADE ON DELETE RESTRICT"
        fk_set_null = "ON UPDATE CASCADE ON DELETE SET NULL"
    else:
        int_pk = "INT NOT NULL AUTO_INCREMENT PRIMARY KEY"
        big_pk = "BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY"
        suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        fk_actions = "ON UPDATE CASCADE ON DELETE RESTRICT"
        fk_set_null = "ON UPDATE CASCADE ON DELETE SET NULL"

    return [
        f"""
        CREATE TABLE IF NOT EXISTS Robot (
            robot_id VARCHAR(10) NOT NULL PRIMARY KEY,
            name     VARCHAR(50) NOT NULL,
            type     VARCHAR(30) NULL DEFAULT 'AGV',
            year     INT         NULL DEFAULT 2024
        ){suffix}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS Sensor (
            sensor_id VARCHAR(10)   NOT NULL PRIMARY KEY,
            robot_id  VARCHAR(10)   NOT NULL,
            type      VARCHAR(30)   NOT NULL,
            value     DECIMAL(10,2) NULL,
            timestamp DATETIME      NULL,
            CONSTRAINT fk_sensor_robot
                FOREIGN KEY (robot_id) REFERENCES Robot(robot_id) {fk_actions}
        ){suffix}
        """,
        "CREATE INDEX IF NOT EXISTS idx_sensor_robot ON Sensor (robot_id)"
        if dialect_name == "sqlite"
        else None,
        f"""
        CREATE TABLE IF NOT EXISTS Operator (
            op_id {int_pk},
            name  VARCHAR(50) NOT NULL,
            shift VARCHAR(20) NULL DEFAULT 'Day'
        ){suffix}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS DataLog (
            log_id    {big_pk},
            op_id     INT           NULL,
            robot_id  VARCHAR(10)   NOT NULL,
            sensor_id VARCHAR(10)   NOT NULL,
            timestamp DATETIME      NOT NULL,
            value     DECIMAL(10,2) NULL,
            CONSTRAINT fk_datalog_operator
                FOREIGN KEY (op_id) REFERENCES Operator(op_id) {fk_set_null},
            CONSTRAINT fk_datalog_robot
                FOREIGN KEY (robot_id) REFERENCES Robot(robot_id) {fk_actions},
            CONSTRAINT fk_datalog_sensor
                FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) {fk_actions}
        ){suffix}
        """,
        "CREATE INDEX IF NOT EXISTS idx_datalog_robot_time ON DataLog (robot_id, timestamp)"
        if dialect_name == "sqlite"
        else None,
        "CREATE INDEX IF NOT EXISTS idx_datalog_sensor_time ON DataLog (sensor_id, timestamp)"
        if dialect_name == "sqlite"
        else None,
        f"""
        CREATE TABLE IF NOT EXISTS RobotRoute_raw (
            id         {big_pk},
            robot_id   VARCHAR(10) NOT NULL,
            robot_name VARCHAR(50) NOT NULL,
            location   VARCHAR(50) NOT NULL,
            operator   VARCHAR(50) NOT NULL,
            timestamp  DATETIME    NOT NULL
        ){suffix}
        """,
        "CREATE INDEX IF NOT EXISTS idx_rr_robot_time ON RobotRoute_raw (robot_id, timestamp)"
        if dialect_name == "sqlite"
        else None,
        "CREATE INDEX IF NOT EXISTS idx_rr_time ON RobotRoute_raw (timestamp)"
        if dialect_name == "sqlite"
        else None,
        f"""
        CREATE TABLE IF NOT EXISTS RobotMoveLog (
            id         {big_pk},
            robot_id   VARCHAR(10) NOT NULL,
            robot_name VARCHAR(50) NOT NULL,
            zone       VARCHAR(50) NOT NULL,
            operator   VARCHAR(50) NOT NULL,
            timestamp  DATETIME    NOT NULL
        ){suffix}
        """,
        "CREATE INDEX IF NOT EXISTS idx_rml_robot_time ON RobotMoveLog (robot_id, timestamp)"
        if dialect_name == "sqlite"
        else None,
        "CREATE INDEX IF NOT EXISTS idx_rml_time ON RobotMoveLog (timestamp)"
        if dialect_name == "sqlite"
        else None,
        f"""
        CREATE TABLE IF NOT EXISTS RouteLog (
            log_id    {big_pk},
            robot_id  VARCHAR(10) NOT NULL,
            op_id     INT         NOT NULL,
            location  VARCHAR(50) NOT NULL,
            timestamp DATETIME    NOT NULL,
            CONSTRAINT fk_routelog_robot
                FOREIGN KEY (robot_id) REFERENCES Robot(robot_id) {fk_actions},
            CONSTRAINT fk_routelog_operator
                FOREIGN KEY (op_id) REFERENCES Operator(op_id) {fk_actions}
        ){suffix}
        """,
        "CREATE INDEX IF NOT EXISTS idx_route_robot_time ON RouteLog (robot_id, timestamp)"
        if dialect_name == "sqlite"
        else None,
        f"""
        CREATE TABLE IF NOT EXISTS RobotCommand (
            cmd_id      {big_pk},
            sender_id   VARCHAR(10)  NOT NULL,
            receiver_id VARCHAR(10)  NOT NULL,
            cmd_content VARCHAR(200) NOT NULL,
            timestamp   DATETIME     NOT NULL,
            CONSTRAINT fk_cmd_sender
                FOREIGN KEY (sender_id) REFERENCES Robot(robot_id) {fk_actions},
            CONSTRAINT fk_cmd_receiver
                FOREIGN KEY (receiver_id) REFERENCES Robot(robot_id) {fk_actions}
        ){suffix}
        """,
        "CREATE INDEX IF NOT EXISTS idx_cmd_pair_time ON RobotCommand (sender_id, receiver_id, timestamp)"
        if dialect_name == "sqlite"
        else None,
        "CREATE INDEX IF NOT EXISTS idx_cmd_time ON RobotCommand (timestamp)"
        if dialect_name == "sqlite"
        else None,
        f"""
        CREATE TABLE IF NOT EXISTS ImageData (
            img_id    {int_pk},
            robot_id  VARCHAR(10)  NOT NULL,
            img_path  VARCHAR(255) NOT NULL,
            timestamp DATETIME     NOT NULL,
            CONSTRAINT fk_imagedata_robot
                FOREIGN KEY (robot_id) REFERENCES Robot(robot_id) {fk_actions}
        ){suffix}
        """,
        "CREATE INDEX IF NOT EXISTS idx_robot_time ON ImageData (robot_id, timestamp)"
        if dialect_name == "sqlite"
        else None,
        f"""
        CREATE TABLE IF NOT EXISTS Performance (
            perf_id    {big_pk},
            robot_id   VARCHAR(10)  NOT NULL,
            task       VARCHAR(100) NOT NULL,
            start_time DATETIME     NOT NULL,
            end_time   DATETIME     NOT NULL,
            CONSTRAINT fk_perf_robot
                FOREIGN KEY (robot_id) REFERENCES Robot(robot_id) {fk_actions}
        ){suffix}
        """,
        "CREATE INDEX IF NOT EXISTS idx_performance_robot_time ON Performance (robot_id, start_time)"
        if dialect_name == "sqlite"
        else None,
        f"""
        CREATE TABLE IF NOT EXISTS SensorLog (
            id         {int_pk},
            robot_id   VARCHAR(10)  NOT NULL,
            sensor     VARCHAR(30)  NOT NULL,
            temp_c     DECIMAL(5,2) NOT NULL,
            hum_pct    DECIMAL(5,2) NOT NULL,
            ts_epoch   BIGINT       NOT NULL,
            created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
        ){suffix}
        """,
        "CREATE INDEX IF NOT EXISTS idx_sensorlog_robot_ts ON SensorLog (robot_id, ts_epoch)"
        if dialect_name == "sqlite"
        else None,
        "CREATE INDEX IF NOT EXISTS idx_sensorlog_created ON SensorLog (created_at)"
        if dialect_name == "sqlite"
        else None,
    ]


def init_schema(engine: Engine) -> None:
    """Create all 11 Topic 5 tables and indexes for the active SQL dialect."""
    statements = [s for s in _ddl_statements(engine.dialect.name) if s is not None]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def get_column_type(
    engine: Engine,
    table_name: str,
    column_name: str,
) -> tuple[str | None, str | None]:
    """Return normalized (data_type, raw_column_type) for a table column."""
    if engine.dialect.name == "mysql":
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT DATA_TYPE, COLUMN_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND LOWER(TABLE_NAME) = LOWER(:tb)
                      AND LOWER(COLUMN_NAME) = LOWER(:col)
                    LIMIT 1
                    """
                ),
                {"tb": table_name, "col": column_name},
            ).fetchone()
            if row is not None:
                return str(row[0]).lower(), str(row[1]).lower()

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    matched_table = next((t for t in tables if t.lower() == table_name.lower()), None)
    if matched_table is None:
        return None, None

    for col in inspector.get_columns(matched_table):
        if col["name"].lower() == column_name.lower():
            raw = str(col["type"]).lower()
            base = raw.split("(", 1)[0].strip().lower()
            return base, raw
    return None, None


def is_numeric_column_type(dtype: str | None) -> bool:
    if not dtype:
        return False
    base = dtype.split("(", 1)[0].strip().lower()
    return base in NUMERIC_SQL_TYPES


def load_csv_into_table(
    engine: Engine,
    table_name: str,
    csv_path: Path,
    *,
    replace: bool = False,
) -> int:
    """Load CSV rows into an allowlisted table using parameterized inserts."""
    if table_name not in ALLOWED_IMPORT_TABLES:
        raise ValueError(f"Table {table_name!r} is not in ALLOWED_IMPORT_TABLES.")

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return 0
        rows = list(reader)

    if not rows:
        return 0

    inspector = inspect(engine)
    table_cols = {col["name"] for col in inspector.get_columns(table_name)}
    insert_cols = [col for col in reader.fieldnames if col in table_cols]
    if not insert_cols:
        raise ValueError(
            f"CSV columns {reader.fieldnames} do not match table {table_name} columns {sorted(table_cols)}."
        )

    cleaned_rows = []
    for row in rows:
        cleaned_rows.append(
            {col: (None if row[col] == "" else row[col]) for col in insert_cols}
        )

    sql = insert_ignore_sql(engine.dialect.name, table_name, insert_cols)
    with engine.begin() as conn:
        if replace:
            conn.execute(text(f"DELETE FROM {table_name}"))
        conn.execute(text(sql), cleaned_rows)
    return len(cleaned_rows)


def seed_performance_demo(engine: Engine, *, replace: bool = True) -> int:
    """Seed the minimal Q5 180s vs 600s Performance demo rows."""
    demo_rows = [
        {
            "perf_id": 1,
            "robot_id": "R1",
            "task": "Pick Item",
            "start_time": "2025-09-01 08:00:00",
            "end_time": "2025-09-01 08:03:00",
        },
        {
            "perf_id": 2,
            "robot_id": "R1",
            "task": "Drop Item",
            "start_time": "2025-09-01 08:05:00",
            "end_time": "2025-09-01 08:08:00",
        },
        {
            "perf_id": 3,
            "robot_id": "R2",
            "task": "Scan Zone",
            "start_time": "2025-09-01 08:10:00",
            "end_time": "2025-09-01 08:20:00",
        },
    ]
    sql = insert_ignore_sql(
        engine.dialect.name,
        "Performance",
        ("perf_id", "robot_id", "task", "start_time", "end_time"),
    )
    with engine.begin() as conn:
        if replace:
            conn.execute(text("DELETE FROM Performance"))
        conn.execute(text(sql), demo_rows)
    return len(demo_rows)


def seed_demo_data(
    engine: Engine,
    data_dir: Path | None = None,
    *,
    include_benchmark: bool = False,
) -> None:
    """Seed core Q1-Q8 sample records (and optional CSV datasets from data_dir)."""
    dialect = engine.dialect.name

    robots = [
        {"robot_id": "R1", "name": "AlphaBot", "type": "AGV", "year": 2023},
        {"robot_id": "R2", "name": "BetaBot", "type": "Drone", "year": 2024},
        {"robot_id": "R3", "name": "GammaBot", "type": "AGV", "year": 2024},
        {"robot_id": "R4", "name": "DeltaBot", "type": "AGV", "year": 2024},
    ]
    operators = [
        {"op_id": 1, "name": "Operator A", "shift": "Morning"},
        {"op_id": 2, "name": "Operator B", "shift": "Night"},
    ]
    sensors = [
        {
            "sensor_id": "S1",
            "robot_id": "R1",
            "type": "Temp",
            "value": 28.50,
            "timestamp": "2025-09-01 08:00:00",
        },
        {
            "sensor_id": "S2",
            "robot_id": "R2",
            "type": "Camera",
            "value": None,
            "timestamp": "2025-09-01 08:05:00",
        },
    ]
    datalogs = [
        {
            "log_id": 1,
            "op_id": 1,
            "robot_id": "R1",
            "sensor_id": "S1",
            "timestamp": "2025-09-01 08:00:00",
            "value": 28.50,
        },
        {
            "log_id": 2,
            "op_id": 2,
            "robot_id": "R2",
            "sensor_id": "S2",
            "timestamp": "2025-09-01 08:05:00",
            "value": None,
        },
    ]
    commands = [
        {
            "cmd_id": 1,
            "sender_id": "R1",
            "receiver_id": "R2",
            "cmd_content": "Move to A",
            "timestamp": "2025-09-01 08:00:00",
        },
        {
            "cmd_id": 2,
            "sender_id": "R2",
            "receiver_id": "R1",
            "cmd_content": "OK",
            "timestamp": "2025-09-01 08:01:00",
        },
    ]
    images = [
        {
            "img_id": 1,
            "robot_id": "R1",
            "img_path": "data/images/qr_zone_a1.png",
            "timestamp": "2025-09-01 08:00:00",
        },
        {
            "img_id": 2,
            "robot_id": "R2",
            "img_path": "data/images/qr_zone_b2.png",
            "timestamp": "2025-09-01 08:30:00",
        },
        {
            "img_id": 3,
            "robot_id": "R1",
            "img_path": "data/images/cam_r1_pick_01.png",
            "timestamp": "2025-09-01 08:02:00",
        },
        {
            "img_id": 4,
            "robot_id": "R2",
            "img_path": "data/images/cam_r2_scan_01.png",
            "timestamp": "2025-09-01 08:12:00",
        },
    ]

    with engine.begin() as conn:
        conn.execute(text(insert_ignore_sql(dialect, "Robot", ("robot_id", "name", "type", "year"))), robots)
        conn.execute(text(insert_ignore_sql(dialect, "Operator", ("op_id", "name", "shift"))), operators)
        conn.execute(
            text(insert_ignore_sql(dialect, "Sensor", ("sensor_id", "robot_id", "type", "value", "timestamp"))),
            sensors,
        )
        conn.execute(
            text(
                insert_ignore_sql(
                    dialect,
                    "DataLog",
                    ("log_id", "op_id", "robot_id", "sensor_id", "timestamp", "value"),
                )
            ),
            datalogs,
        )
        conn.execute(
            text(
                insert_ignore_sql(
                    dialect,
                    "RobotCommand",
                    ("cmd_id", "sender_id", "receiver_id", "cmd_content", "timestamp"),
                )
            ),
            commands,
        )
        conn.execute(
            text(insert_ignore_sql(dialect, "ImageData", ("img_id", "robot_id", "img_path", "timestamp"))),
            images,
        )

    if include_benchmark and data_dir is not None and (data_dir / "performance_benchmark.csv").exists():
        load_csv_into_table(engine, "Performance", data_dir / "performance_benchmark.csv", replace=True)
    else:
        existing_perf = 0
        with engine.connect() as conn:
            existing_perf = conn.execute(text("SELECT COUNT(*) FROM Performance")).scalar_one()
        if existing_perf == 0:
            seed_performance_demo(engine, replace=False)

    if data_dir is not None:
        route_csv = data_dir / "RobotRoute.csv"
        if route_csv.exists():
            with engine.connect() as conn:
                count_rr = conn.execute(text("SELECT COUNT(*) FROM RobotRoute_raw")).scalar_one()
            if count_rr == 0:
                load_csv_into_table(engine, "RobotRoute_raw", route_csv)

        movelog_csv = data_dir / "robot_movelog_sample.csv"
        if movelog_csv.exists():
            with engine.connect() as conn:
                count_rml = conn.execute(text("SELECT COUNT(*) FROM RobotMoveLog")).scalar_one()
            if count_rml == 0:
                load_csv_into_table(engine, "RobotMoveLog", movelog_csv)

        sensorlog_csv = data_dir / "sensor_log_sample.csv"
        if sensorlog_csv.exists():
            with engine.connect() as conn:
                count_sl = conn.execute(text("SELECT COUNT(*) FROM SensorLog")).scalar_one()
            if count_sl == 0:
                load_csv_into_table(engine, "SensorLog", sensorlog_csv)


def seed_routelog_r1_safe(
    engine: Engine,
    day: str = "2025-09-01",
    start: str = "08:00:00",
    end: str = "10:00:00",
    step_min: int = 5,
    robot_id: str = "R1",
    seed: int = 42,
) -> int:
    """Safely seed 3NF RouteLog rows across ZONES while adapting to op_id column type."""
    if step_min <= 0:
        raise ValueError("step_min must be positive.")

    t0 = datetime.strptime(f"{day} {start}", "%Y-%m-%d %H:%M:%S")
    t1 = datetime.strptime(f"{day} {end}", "%Y-%m-%d %H:%M:%S")
    if t1 < t0:
        raise ValueError("end time must not be earlier than start time.")

    times: list[datetime] = []
    cur = t0
    while cur <= t1:
        times.append(cur)
        cur += timedelta(minutes=step_min)

    day_start = f"{day} 00:00:00"
    next_day = (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")

    dtype, _ = get_column_type(engine, "RouteLog", "op_id")
    is_numeric = is_numeric_column_type(dtype)
    dialect = engine.dialect.name
    rng = random.Random(seed)

    inspector = inspect(engine)
    table_names = {t.lower(): t for t in inspector.get_table_names()}

    if is_numeric:
        with engine.begin() as conn:
            if "robot" in table_names:
                conn.execute(
                    text(insert_ignore_sql(dialect, table_names["robot"], ("robot_id", "name"))),
                    {"robot_id": robot_id, "name": f"Robot-{robot_id}"},
                )

            conn.execute(
                text(
                    """
                    DELETE FROM RouteLog
                    WHERE robot_id = :rid
                      AND timestamp >= :d0
                      AND timestamp < :d1
                    """
                ),
                {"rid": robot_id, "d0": day_start, "d1": next_day},
            )

            max_op = 0
            if "operator" in table_names:
                max_op = int(
                    conn.execute(text(f"SELECT COALESCE(MAX(op_id), 0) FROM {table_names['operator']}")).scalar_one()
                )
            else:
                max_op = int(
                    conn.execute(text("SELECT COALESCE(MAX(op_id), 0) FROM RouteLog")).scalar_one()
                )

            op_ids = [max_op + 1 + idx for idx in range(len(times))]

            if "operator" in table_names:
                op_table = table_names["operator"]
                op_cols = {c["name"].lower() for c in inspector.get_columns(op_table)}
                if "name" in op_cols:
                    op_rows = [{"op_id": oid, "name": f"SIM-{robot_id}"} for oid in op_ids]
                    conn.execute(text(insert_ignore_sql(dialect, op_table, ("op_id", "name"))), op_rows)
                else:
                    op_rows = [{"op_id": oid} for oid in op_ids]
                    conn.execute(text(insert_ignore_sql(dialect, op_table, ("op_id",))), op_rows)

            route_rows = [
                {
                    "robot_id": robot_id,
                    "op_id": op_ids[idx],
                    "location": rng.choice(ZONES),
                    "timestamp": tt.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for idx, tt in enumerate(times)
            ]
            conn.execute(
                text(
                    """
                    INSERT INTO RouteLog (robot_id, op_id, location, timestamp)
                    VALUES (:robot_id, :op_id, :location, :timestamp)
                    """
                ),
                route_rows,
            )
            return len(route_rows)

    # String op_id fallback path (legacy or string-typed op_id schema)
    route_rows = [
        {
            "robot_id": robot_id,
            "op_id": f"OP-{robot_id}-{tt.strftime('%Y%m%d-%H%M%S')}",
            "location": rng.choice(ZONES),
            "timestamp": tt.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for tt in times
    ]

    if dialect == "sqlite":
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys = OFF")
            conn.commit()
            try:
                with conn.begin():
                    if "robot" in table_names:
                        conn.execute(
                            text(insert_ignore_sql(dialect, table_names["robot"], ("robot_id", "name"))),
                            {"robot_id": robot_id, "name": f"Robot-{robot_id}"},
                        )
                    conn.execute(
                        text(
                            """
                            DELETE FROM RouteLog
                            WHERE robot_id = :rid
                              AND timestamp >= :d0
                              AND timestamp < :d1
                            """
                        ),
                        {"rid": robot_id, "d0": day_start, "d1": next_day},
                    )
                    conn.execute(
                        text(
                            """
                            INSERT INTO RouteLog (robot_id, op_id, location, timestamp)
                            VALUES (:robot_id, :op_id, :location, :timestamp)
                            """
                        ),
                        route_rows,
                    )
            finally:
                conn.exec_driver_sql("PRAGMA foreign_keys = ON")
                conn.commit()
        return len(route_rows)

    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        try:
            if "robot" in table_names:
                conn.execute(
                    text(insert_ignore_sql(dialect, table_names["robot"], ("robot_id", "name"))),
                    {"robot_id": robot_id, "name": f"Robot-{robot_id}"},
                )
            conn.execute(
                text(
                    """
                    DELETE FROM RouteLog
                    WHERE robot_id = :rid
                      AND timestamp >= :d0
                      AND timestamp < :d1
                    """
                ),
                {"rid": robot_id, "d0": day_start, "d1": next_day},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO RouteLog (robot_id, op_id, location, timestamp)
                    VALUES (:robot_id, :op_id, :location, :timestamp)
                    """
                ),
                route_rows,
            )
        finally:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    return len(route_rows)
