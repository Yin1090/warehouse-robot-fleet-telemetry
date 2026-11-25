"""Tests for FleetDashboardController MVC logic and Tkinter WarehouseFleetApp."""

from __future__ import annotations

import csv
import tkinter as tk
from pathlib import Path

import pytest

from warehouse_fleet.controller import FleetDashboardController
from warehouse_fleet.dashboard import WarehouseFleetApp


def test_controller_allowlist_and_csv_roundtrip(
    sqlite_engine, repo_root: Path, tmp_path: Path
) -> None:
    ctrl = FleetDashboardController(sqlite_engine, base_dir=repo_root)

    with pytest.raises(ValueError):
        ctrl.fetch_table("Robot; DROP TABLE Robot")

    with pytest.raises(ValueError):
        ctrl.import_csv("NonExistentTable", tmp_path / "dummy.csv")

    res = ctrl.run_preset("1_robot_sensor_count")
    exported = ctrl.export_csv(res, tmp_path / "out.csv")
    with exported.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["robot_id", "name", "type", "year", "sensor_count"]
    assert len(rows) == 5

    # Import new Robot row via CSV allowlist
    import_file = tmp_path / "new_robot.csv"
    import_file.write_text(
        "robot_id,name,type,year\nR9,ScoutBot,AGV,2025\n",
        encoding="utf-8",
    )
    imported = ctrl.import_csv("Robot", import_file)
    assert imported == 1
    robots = ctrl.fetch_table("Robot")
    assert any(r[0] == "R9" for r in robots.rows)

    # Full-table fetch with limit=None does not truncate 1,000-row tables
    all_routes = ctrl.fetch_table("RobotRoute_raw", limit=None)
    assert len(all_routes.rows) == 1000


def test_controller_image_path_safety_and_missing_file(
    sqlite_engine, repo_root: Path
) -> None:
    ctrl = FleetDashboardController(sqlite_engine, base_dir=repo_root)

    resolved = ctrl.resolve_image_path("data/images/qr_zone_a1.png")
    assert resolved.is_file()
    img = ctrl.load_image("data/images/qr_zone_a1.png")
    assert img.size == (320, 240)

    with pytest.raises(ValueError):
        ctrl.resolve_image_path("../../outside.png")

    with pytest.raises(FileNotFoundError):
        ctrl.resolve_image_path("data/images/does_not_exist.png")


def test_tkinter_app_smoke_and_missing_image_handling(
    sqlite_engine, repo_root: Path
) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Headless display unavailable for Tkinter smoke test: {exc}")

    try:
        root.withdraw()
        ctrl = FleetDashboardController(sqlite_engine, base_dir=repo_root)
        app = WarehouseFleetApp(root, ctrl)
        root.update_idletasks()

        assert len(app.notebook.tabs()) == 6
        assert app.display_image_path("data/images/qr_zone_a1.png") is True
        assert app.display_image_path("data/images/missing_file.png") is False
        assert "Error:" in app.image_status_var.get()

        app._on_simulate_mqtt()
        app._on_seed_routelog()
        root.update_idletasks()
    finally:
        root.destroy()
