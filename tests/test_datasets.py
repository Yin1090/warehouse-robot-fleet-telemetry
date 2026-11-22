"""Tests for deterministic CSV datasets and synthetic inspection PNGs."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from PIL import Image

from warehouse_fleet.datasets import (
    PERFORMANCE_TARGET_SECONDS,
    generate_all_datasets,
)


def test_committed_datasets_match_topic5_specifications(data_dir: Path) -> None:
    # 1. RobotRoute.csv (1,000 rows, 5*i % 600 min cadence)
    route_path = data_dir / "RobotRoute.csv"
    with route_path.open("r", encoding="utf-8", newline="") as handle:
        route_rows = list(csv.DictReader(handle))
    assert len(route_rows) == 1000
    assert route_rows[0]["timestamp"] == "2025-09-01 08:00:00"
    assert route_rows[119]["timestamp"] == "2025-09-01 17:55:00"
    assert route_rows[120]["timestamp"] == "2025-09-01 08:00:00"
    assert {r["robot_id"] for r in route_rows} == {"R1", "R2", "R3"}
    assert {r["location"] for r in route_rows} == {"Zone A", "Zone B", "Zone C", "Zone D"}
    assert {r["operator"] for r in route_rows} == {
        "Operator A",
        "Operator B",
        "Operator C",
        "Operator D",
    }

    # 2. robot_movelog_sample.csv
    movelog_path = data_dir / "robot_movelog_sample.csv"
    with movelog_path.open("r", encoding="utf-8", newline="") as handle:
        move_rows = list(csv.DictReader(handle))
    assert len(move_rows) == 48
    assert {r["robot_id"] for r in move_rows} == {"RB01", "RB02", "RB03"}
    assert {r["robot_name"] for r in move_rows} == {"NovaBot", "LunaBot", "OrionBot"}

    # 3. performance_benchmark.csv (250 tasks x 4 robots summing to exact target seconds)
    perf_path = data_dir / "performance_benchmark.csv"
    with perf_path.open("r", encoding="utf-8", newline="") as handle:
        perf_rows = list(csv.DictReader(handle))
    assert len(perf_rows) == 1000

    sums: dict[str, int] = {"R1": 0, "R2": 0, "R3": 0, "R4": 0}
    counts: dict[str, int] = {"R1": 0, "R2": 0, "R3": 0, "R4": 0}
    for row in perf_rows:
        t0 = datetime.strptime(row["start_time"], "%Y-%m-%d %H:%M:%S")
        t1 = datetime.strptime(row["end_time"], "%Y-%m-%d %H:%M:%S")
        dur = int((t1 - t0).total_seconds())
        assert 180 <= dur <= 900
        sums[row["robot_id"]] += dur
        counts[row["robot_id"]] += 1

    assert counts == {"R1": 250, "R2": 250, "R3": 250, "R4": 250}
    assert sums == PERFORMANCE_TARGET_SECONDS

    # 4. sensor_log_sample.csv (12 rows, id 415..426, 5s cadence)
    sensor_path = data_dir / "sensor_log_sample.csv"
    with sensor_path.open("r", encoding="utf-8", newline="") as handle:
        sensor_rows = list(csv.DictReader(handle))
    assert len(sensor_rows) == 12
    assert [int(r["id"]) for r in sensor_rows] == list(range(415, 427))
    epochs = [int(r["ts_epoch"]) for r in sensor_rows]
    assert all(b - a == 5 for a, b in zip(epochs, epochs[1:]))
    assert all(23.40 <= float(r["temp_c"]) <= 23.60 for r in sensor_rows)
    assert all(50.20 <= float(r["hum_pct"]) <= 51.20 for r in sensor_rows)

    # 5. Synthetic inspection PNGs
    expected_pngs = [
        "qr_zone_a1.png",
        "qr_zone_b2.png",
        "cam_r1_pick_01.png",
        "cam_r2_scan_01.png",
    ]
    for name in expected_pngs:
        png = data_dir / "images" / name
        assert png.is_file()
        with Image.open(png) as img:
            assert img.format == "PNG"
            assert img.size == (320, 240)


def test_dataset_generator_is_deterministic(tmp_path: Path, data_dir: Path) -> None:
    out_dir = tmp_path / "regen_data"
    generate_all_datasets(out_dir, seed=42)

    for fname in (
        "RobotRoute.csv",
        "robot_movelog_sample.csv",
        "performance_benchmark.csv",
        "sensor_log_sample.csv",
    ):
        assert (out_dir / fname).read_bytes() == (data_dir / fname).read_bytes()
