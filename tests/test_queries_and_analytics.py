"""Tests for all 5 preset queries + extended analytics and DENSE_RANK benchmarks."""

from __future__ import annotations

from sqlalchemy import text

from warehouse_fleet.db import seed_routelog_r1_safe
from warehouse_fleet.queries import run_preset_query


def test_five_core_preset_queries(sqlite_engine) -> None:
    # 1) Robot & sensor count
    q1 = run_preset_query(sqlite_engine, "1_robot_sensor_count")
    counts = {row[0]: row[4] for row in q1.rows}
    assert counts == {"R1": 1, "R2": 1, "R3": 0, "R4": 0}

    # 2) Latest value per sensor
    q2 = run_preset_query(sqlite_engine, "2_latest_per_sensor")
    latest = {row[0]: (row[1], row[2], row[4]) for row in q2.rows}
    assert latest["S1"][0] == "Temp"
    assert latest["S1"][1] == "R1"
    assert float(latest["S1"][2]) == 28.50
    assert latest["S2"] == ("Camera", "R2", None)

    # 3) Temp logs of robot on date
    q3 = run_preset_query(
        sqlite_engine,
        "3_temp_logs_robot_date",
        robot_id="R1",
        target_date="2025-09-01",
    )
    assert len(q3.rows) == 1
    assert q3.rows[0][1] == "R1"
    assert q3.rows[0][2] == "S1"
    assert float(q3.rows[0][5]) == 28.50

    # 4) Sensors with NULL value
    q4 = run_preset_query(sqlite_engine, "4_null_value_sensors")
    assert len(q4.rows) == 1
    assert q4.rows[0][0] == "S2"
    assert q4.rows[0][1] == "Camera"
    assert q4.rows[0][5] is None

    # 5) Total logs per robot
    q5 = run_preset_query(sqlite_engine, "5_total_logs_per_robot")
    totals = {row[0]: row[2] for row in q5.rows}
    assert totals == {"R1": 1, "R2": 1, "R3": 0, "R4": 0}


def test_performance_demo_180s_vs_600s(sqlite_engine) -> None:
    res = run_preset_query(sqlite_engine, "6_performance_dense_rank")
    assert [(r[0], float(r[2]), r[4]) for r in res.rows] == [
        ("R1", 180.0, 1),
        ("R2", 600.0, 2),
    ]


def test_performance_dense_rank_ties(sqlite_engine) -> None:
    with sqlite_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO Performance (robot_id, task, start_time, end_time)
                VALUES ('R3', 'Pick Item', '2025-09-01 09:00:00', '2025-09-01 09:03:00')
                """
            )
        )
    res = run_preset_query(sqlite_engine, "6_performance_dense_rank")
    ranks = {r[0]: r[4] for r in res.rows}
    assert ranks == {"R1": 1, "R3": 1, "R2": 2}


def test_performance_benchmark_exact_dense_rank_averages(benchmark_engine) -> None:
    res = run_preset_query(benchmark_engine, "6_performance_dense_rank")
    got = [(r[0], r[1], float(r[3]), r[4]) for r in res.rows]
    assert got == [
        ("R1", 250, 8.4051, 1),
        ("R4", 250, 8.4160, 2),
        ("R3", 250, 8.7714, 3),
        ("R2", 250, 8.7920, 4),
    ]


def test_extended_commands_routelog_and_raw_route(sqlite_engine) -> None:
    seed_routelog_r1_safe(sqlite_engine, day="2025-09-01")
    cmds = run_preset_query(sqlite_engine, "7_robot_commands")
    assert len(cmds.rows) == 2
    assert {r[3] for r in cmds.rows} == {"Move to A", "OK"}

    routes_3nf = run_preset_query(sqlite_engine, "8_routelog_3nf_trace", robot_id="R1")
    assert len(routes_3nf.rows) == 25

    sensor_latest = run_preset_query(sqlite_engine, "9_sensorlog_mqtt_latest", robot_id="R1")
    assert len(sensor_latest.rows) == 12

    raw_trace = run_preset_query(
        sqlite_engine,
        "10_raw_route_trace",
        robot_id="R1",
        target_date="2025-09-01",
    )
    assert len(raw_trace.rows) > 0
    assert all(r[1] == "R1" for r in raw_trace.rows)
