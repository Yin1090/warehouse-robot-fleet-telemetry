"""Shared pytest fixtures for Warehouse Robot Fleet Telemetry."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from warehouse_fleet.db import create_fleet_engine, init_schema, seed_demo_data


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def data_dir(repo_root: Path) -> Path:
    return repo_root / "data"


@pytest.fixture()
def sqlite_engine(tmp_path: Path, data_dir: Path) -> Engine:
    db_file = tmp_path / "test_fleet.db"
    engine = create_fleet_engine(f"sqlite:///{db_file.as_posix()}")
    init_schema(engine)
    seed_demo_data(engine, data_dir=data_dir)
    yield engine
    engine.dispose()


@pytest.fixture()
def benchmark_engine(tmp_path: Path, data_dir: Path) -> Engine:
    db_file = tmp_path / "test_benchmark.db"
    engine = create_fleet_engine(f"sqlite:///{db_file.as_posix()}")
    init_schema(engine)
    seed_demo_data(engine, data_dir=data_dir, include_benchmark=True)
    yield engine
    engine.dispose()
