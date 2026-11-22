"""CLI end-to-end tests and repository-wide sanitization compliance checks."""

from __future__ import annotations

import json
import re
from pathlib import Path

from warehouse_fleet import cli

SANITIZATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("rfc1918_192", re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b")),
    ("rfc1918_10", re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
    (
        "rfc1918_172",
        re.compile(r"\b172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}\b"),
    ),
    ("windows_user_path", re.compile(r"[A-Za-z]:[/\\]Users[/\\]", re.IGNORECASE)),
    ("linux_home_path", re.compile(r"/home/[a-zA-Z0-9._-]+/")),
    ("personal_gmail", re.compile(r"[A-Za-z0-9._%+-]+@gmail\.com\b", re.IGNORECASE)),
    (
        "mit_app_inventor",
        re.compile(
            r"(?:\."
            + "aia"
            + r"\b|\."
            + "bky"
            + r"\b|\."
            + "scm"
            + r"\b|App\s*"
            + "Inventor|Block"
            + "ly)",
            re.IGNORECASE,
        ),
    ),
    ("student_id_10digit", re.compile(r"\b2\d{9}\b")),
)


def test_cli_end_to_end_workflow(tmp_path: Path, capsys) -> None:
    gen_dir = tmp_path / "generated_data"
    db_file = tmp_path / "cli_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    assert cli.main(["generate-data", "--output-dir", str(gen_dir)]) == 0
    gen_out = json.loads(capsys.readouterr().out)
    assert len(gen_out["csv_files"]) == 4
    assert len(gen_out["images"]) == 4

    assert (
        cli.main(
            [
                "init-db",
                "--db-url",
                db_url,
                "--data-dir",
                str(gen_dir),
                "--with-benchmark",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert cli.main(["seed-routelog", "--db-url", db_url, "--robot-id", "R1"]) == 0
    assert "Seeded 25 RouteLog rows" in capsys.readouterr().out

    assert (
        cli.main(
            [
                "query",
                "--db-url",
                db_url,
                "--preset",
                "6_performance_dense_rank",
                "--format",
                "json",
            ]
        )
        == 0
    )
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["robot_id"] == "R1"
    assert float(rows[0]["avg_task_time_min"]) == 8.4051

    assert (
        cli.main(
            [
                "mqtt-logger",
                "--db-url",
                db_url,
                "--simulate",
                "--csv",
                str(gen_dir / "sensor_log_sample.csv"),
            ]
        )
        == 0
    )
    mqtt_out = json.loads(capsys.readouterr().out)
    assert mqtt_out["ingested_rows"] == 12
    assert mqtt_out["statuses"]["R1"] == "online"


def test_repository_sanitization_clean(repo_root: Path) -> None:
    text_suffixes = {
        ".py",
        ".sql",
        ".ino",
        ".h",
        ".example",
        ".md",
        ".toml",
        ".txt",
        ".csv",
        ".gitignore",
    }
    excluded_dirs = {".git", "__pycache__", ".pytest_cache", ".venv", "dist", "build"}
    findings: list[str] = []

    for path in repo_root.rglob("*"):
        if any(part in excluded_dirs for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in text_suffixes and path.name not in {
            ".env.example",
            ".gitignore",
        }:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        for rule_name, pattern in SANITIZATION_PATTERNS:
            if pattern.search(content):
                findings.append(f"{rule_name}: {path.relative_to(repo_root)}")

    assert findings == []
