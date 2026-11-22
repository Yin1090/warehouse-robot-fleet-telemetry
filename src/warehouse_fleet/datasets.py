"""Deterministic dataset & synthetic inspection image generators for Topic 5."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

PERFORMANCE_TARGET_SECONDS: dict[str, int] = {
    "R1": 126076,  # 126076 / (250 * 60) = 8.40506667 -> 8.4051 min
    "R4": 126240,  # 126240 / (250 * 60) = 8.41600000 -> 8.4160 min
    "R3": 131571,  # 131571 / (250 * 60) = 8.77140000 -> 8.7714 min
    "R2": 131880,  # 131880 / (250 * 60) = 8.79200000 -> 8.7920 min
}


def generate_robot_route_csv(out_path: Path, rows: int = 1000, seed: int = 42) -> Path:
    """Generate RobotRoute.csv matching Topic 5 Q2 (1,000 rows, 5*i % 600 min)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    robots = [("R1", "AlphaBot"), ("R2", "BetaBot"), ("R3", "GammaBot")]
    zones = ["Zone A", "Zone B", "Zone C", "Zone D"]
    operators = ["Operator A", "Operator B", "Operator C", "Operator D"]
    t0 = datetime(2025, 9, 1, 8, 0, 0)

    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["robot_id", "robot_name", "location", "operator", "timestamp"])
        for i in range(rows):
            robot_id, robot_name = rng.choice(robots)
            ts = t0 + timedelta(minutes=(5 * i) % 600)
            writer.writerow(
                [
                    robot_id,
                    robot_name,
                    rng.choice(zones),
                    rng.choice(operators),
                    ts.strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )
    return out_path


def generate_robot_movelog_csv(out_path: Path, rows: int = 48, seed: int = 42) -> Path:
    """Generate sanitized RobotMoveLog sample spanning 2025-10-06..07 across RB01..RB03."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    fleet = [
        ("RB01", "NovaBot", "Operator A"),
        ("RB02", "LunaBot", "Operator B"),
        ("RB03", "OrionBot", "Operator C"),
    ]
    zones = ["Zone A", "Zone B", "Zone C", "Zone D", "Zone E", "Zone F"]
    base_day1 = datetime(2025, 10, 6, 8, 0, 0)
    base_day2 = datetime(2025, 10, 7, 8, 0, 0)

    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["robot_id", "robot_name", "zone", "operator", "timestamp"])
        for i in range(rows):
            robot_id, robot_name, operator = fleet[i % len(fleet)]
            base = base_day1 if i < rows // 2 else base_day2
            step_idx = i if i < rows // 2 else (i - rows // 2)
            ts = base + timedelta(minutes=15 * step_idx)
            writer.writerow(
                [
                    robot_id,
                    robot_name,
                    rng.choice(zones),
                    operator,
                    ts.strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )
    return out_path


def _distribute_exact_durations(
    rng: random.Random,
    count: int,
    target_total_s: int,
    low_s: int = 180,
    high_s: int = 900,
) -> list[int]:
    durations = [rng.randint(300, 720) for _ in range(count)]
    delta = target_total_s - sum(durations)
    idx = 0
    while delta != 0:
        if delta > 0 and durations[idx] < high_s:
            durations[idx] += 1
            delta -= 1
        elif delta < 0 and durations[idx] > low_s:
            durations[idx] -= 1
            delta += 1
        idx = (idx + 1) % count
    return durations


def generate_performance_benchmark_csv(out_path: Path, seed: int = 42) -> Path:
    """Generate 1,000-row Performance benchmark (250 tasks x 4 robots) matching exact 4-decimal averages."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    tasks = ["Pick Item", "Drop Item", "Scan Zone", "Dock Charge", "Transfer Pallet"]
    tasks_per_robot = 250

    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["robot_id", "task", "start_time", "end_time"])

        for robot_idx, (robot_id, target_total_s) in enumerate(PERFORMANCE_TARGET_SECONDS.items()):
            durations = _distribute_exact_durations(rng, tasks_per_robot, target_total_s)
            cursor = datetime(2025, 9, 2, 8, 0, 0) + timedelta(days=robot_idx)
            for task_idx, dur_s in enumerate(durations):
                end_dt = cursor + timedelta(seconds=dur_s)
                writer.writerow(
                    [
                        robot_id,
                        tasks[task_idx % len(tasks)],
                        cursor.strftime("%Y-%m-%d %H:%M:%S"),
                        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    ]
                )
                cursor = end_dt + timedelta(seconds=60)
    return out_path


def generate_sensor_log_csv(out_path: Path) -> Path:
    """Generate deterministic 12-row DHT22 SensorLog sample (id 415..426, 5s cadence)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temps = [23.40, 23.40, 23.50, 23.50, 23.50, 23.50, 23.60, 23.60, 23.50, 23.50, 23.60, 23.60]
    hums = [50.20, 50.40, 50.60, 50.60, 50.70, 50.80, 50.90, 51.00, 51.00, 51.10, 51.10, 51.20]
    base_epoch = 1756713600  # 2025-09-01 08:00:00 UTC
    base_dt = datetime(2025, 9, 1, 8, 0, 0)

    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["id", "robot_id", "sensor", "temp_c", "hum_pct", "ts_epoch", "created_at"])
        for i in range(12):
            writer.writerow(
                [
                    415 + i,
                    "R1",
                    "DHT22",
                    f"{temps[i]:.2f}",
                    f"{hums[i]:.2f}",
                    base_epoch + 5 * i,
                    (base_dt + timedelta(seconds=5 * i)).strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )
    return out_path


def _draw_qr_matrix(draw: ImageDraw.ImageDraw, origin_x: int, origin_y: int, cell: int, rng: random.Random) -> None:
    size = 21
    for r in range(size):
        for c in range(size):
            in_tl = r < 7 and c < 7
            in_tr = r < 7 and c >= size - 7
            in_bl = r >= size - 7 and c < 7
            if in_tl or in_tr or in_bl:
                lr = r if r < 7 else r - (size - 7)
                lc = c if c < 7 else c - (size - 7)
                black = (
                    lr in (0, 6)
                    or lc in (0, 6)
                    or (2 <= lr <= 4 and 2 <= lc <= 4)
                )
            else:
                black = rng.random() < 0.48
            if black:
                x0 = origin_x + c * cell
                y0 = origin_y + r * cell
                draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=(15, 23, 42))


def generate_inspection_images(images_dir: Path, seed: int = 42) -> list[Path]:
    """Create 4 deterministic 320x240 RGB PNG warehouse QR/camera inspection assets."""
    images_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    generated: list[Path] = []

    qr_specs = [
        ("qr_zone_a1.png", "ZONE A1 | R1 | 2025-09-01 08:00:00", (226, 232, 240)),
        ("qr_zone_b2.png", "ZONE B2 | R2 | 2025-09-01 08:30:00", (219, 234, 254)),
    ]
    for filename, label, bg_color in qr_specs:
        img = Image.new("RGB", (320, 240), color=bg_color)
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 310, 230], outline=(30, 41, 59), width=2)
        draw.rectangle([82, 26, 238, 182], fill=(255, 255, 255), outline=(51, 65, 85), width=2)
        _draw_qr_matrix(draw, origin_x=97, origin_y=41, cell=6, rng=rng)
        draw.rectangle([16, 194, 304, 222], fill=(15, 23, 42))
        draw.text((26, 202), label, fill=(248, 250, 252))
        out = images_dir / filename
        img.save(out, format="PNG")
        generated.append(out)

    cam_specs = [
        ("cam_r1_pick_01.png", "CAM R1 | PICK ITEM | 2025-09-01 08:02:00", (20, 83, 45), (34, 197, 94)),
        ("cam_r2_scan_01.png", "CAM R2 | SCAN ZONE | 2025-09-01 08:12:00", (30, 58, 138), (56, 189, 248)),
    ]
    for filename, label, base_fill, accent in cam_specs:
        img = Image.new("RGB", (320, 240), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        # Simulated warehouse shelf & pallet bounding box overlay
        draw.rectangle([12, 12, 308, 228], outline=accent, width=2)
        draw.rectangle([38, 52, 146, 178], fill=base_fill, outline=accent, width=2)
        draw.rectangle([172, 68, 282, 178], fill=(51, 65, 85), outline=(148, 163, 184), width=2)
        draw.line([(160, 40), (160, 188)], fill=(100, 116, 139), width=1)
        draw.rectangle([12, 196, 308, 228], fill=(2, 6, 23))
        draw.text((20, 206), label, fill=(241, 245, 249))
        out = images_dir / filename
        img.save(out, format="PNG")
        generated.append(out)

    return generated


def generate_all_datasets(data_dir: Path, seed: int = 42) -> dict[str, Any]:
    """Generate all deterministic Topic 5 CSV fixtures and inspection PNG images."""
    return {
        "robot_route_csv": generate_robot_route_csv(data_dir / "RobotRoute.csv", rows=1000, seed=seed),
        "robot_movelog_csv": generate_robot_movelog_csv(data_dir / "robot_movelog_sample.csv", rows=48, seed=seed),
        "performance_benchmark_csv": generate_performance_benchmark_csv(
            data_dir / "performance_benchmark.csv", seed=seed
        ),
        "sensor_log_csv": generate_sensor_log_csv(data_dir / "sensor_log_sample.csv"),
        "images": generate_inspection_images(data_dir / "images", seed=seed),
    }
