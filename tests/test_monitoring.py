"""Unit tests for the pure health-monitoring decision logic."""

import os
from pathlib import Path

from app.services.monitoring import (
    CheckResult,
    evaluate_backup,
    evaluate_disk,
    newest_backup_age_hours,
    transitions,
)


def test_evaluate_backup_flags_missing_and_stale() -> None:
    assert evaluate_backup(None, 26).healthy is False
    assert evaluate_backup(30.0, 26).healthy is False
    assert evaluate_backup(2.0, 26).healthy is True


def test_evaluate_disk_uses_inclusive_threshold() -> None:
    assert evaluate_disk(50.0, 85).healthy is True
    assert evaluate_disk(85.0, 85).healthy is False
    assert evaluate_disk(91.0, 85).healthy is False


def test_transitions_only_reports_state_changes() -> None:
    healthy = {"database": CheckResult(True, "ok")}
    unhealthy = {"database": CheckResult(False, "down")}

    # First observation of a healthy signal stays quiet.
    assert transitions(healthy, {}) == []
    # Healthy -> unhealthy raises an alert.
    assert transitions(unhealthy, {"database": True}) == ["\U0001f534 database: down"]
    # Unhealthy -> healthy raises a recovery notice.
    assert transitions(healthy, {"database": False}) == ["✅ database recovered: ok"]
    # Stable healthy stays quiet.
    assert transitions(healthy, {"database": True}) == []


def test_newest_backup_age_hours_reads_latest_mtime(tmp_path: Path) -> None:
    assert newest_backup_age_hours(tmp_path, now=1000.0 * 3600) is None

    old = tmp_path / "daily" / "db-old.sql.gz"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"x")
    recent = tmp_path / "last" / "db-recent.sql.gz"
    recent.parent.mkdir(parents=True)
    recent.write_bytes(b"x")

    now = 1000.0 * 3600
    os.utime(old, (now - 10 * 3600, now - 10 * 3600))
    os.utime(recent, (now - 2 * 3600, now - 2 * 3600))

    age = newest_backup_age_hours(tmp_path, now=now)
    assert age is not None
    assert abs(age - 2.0) < 1e-6
