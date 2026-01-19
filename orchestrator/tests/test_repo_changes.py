from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from orchestrator.dev_plan import find_open_test_required_task_ids
from orchestrator.repo_changes import capture_dirty_file_digests, diff_dirty_file_digests
from orchestrator.workflow import _load_stage_changes, _validate_tdd_main_decision, _write_stage_changes


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_diff_dirty_file_digests_detects_changes() -> None:
    before = {"a.py": "1", "b.py": None}
    after = {"a.py": "2", "b.py": None, "c.py": "3"}
    assert diff_dirty_file_digests(before, after) == ["a.py", "c.py"]


def test_capture_dirty_file_digests_modified_and_untracked(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")

    tracked = tmp_path / "tracked.py"
    tracked.write_text("print('v1')\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.py")
    _git(tmp_path, "commit", "-m", "init")

    tracked.write_text("print('v2')\n", encoding="utf-8")
    untracked = tmp_path / "new.txt"
    untracked.write_text("hello\n", encoding="utf-8")

    snap = capture_dirty_file_digests(project_root=tmp_path)
    assert set(snap) == {"tracked.py", "new.txt"}
    assert snap["tracked.py"] == _sha256_bytes(tracked.read_bytes())
    assert snap["new.txt"] == _sha256_bytes(untracked.read_bytes())


def test_capture_dirty_file_digests_rename_uses_new_path(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")

    old = tmp_path / "old.py"
    old.write_text("print('x')\n", encoding="utf-8")
    _git(tmp_path, "add", "old.py")
    _git(tmp_path, "commit", "-m", "init")

    _git(tmp_path, "mv", "old.py", "new.py")

    snap = capture_dirty_file_digests(project_root=tmp_path)
    assert set(snap) == {"new.py"}
    assert snap["new.py"] == _sha256_bytes((tmp_path / "new.py").read_bytes())


def test_capture_dirty_file_digests_deleted_file_records_none(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")

    gone = tmp_path / "gone.py"
    gone.write_text("print('gone')\n", encoding="utf-8")
    _git(tmp_path, "add", "gone.py")
    _git(tmp_path, "commit", "-m", "init")

    gone.unlink()

    snap = capture_dirty_file_digests(project_root=tmp_path)
    assert snap == {"gone.py": None}


def test_capture_dirty_file_digests_exclude_prefixes(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")

    skip_dir = tmp_path / "orchestrator" / "memory"
    skip_dir.mkdir(parents=True)
    skip = skip_dir / "skip.py"
    skip.write_text("print('x')\n", encoding="utf-8")
    _git(tmp_path, "add", "orchestrator/memory/skip.py")
    _git(tmp_path, "commit", "-m", "init")

    skip.write_text("print('y')\n", encoding="utf-8")

    snap = capture_dirty_file_digests(
        project_root=tmp_path,
        exclude_prefixes=("orchestrator/memory/",),
    )
    assert snap == {}


def test_stage_changes_write_and_load(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import orchestrator.workflow as w

    stage_file = tmp_path / "report_stage_changes.json"
    monkeypatch.setattr(w, "REPORT_STAGE_CHANGES_FILE", stage_file)

    _write_stage_changes(
        iteration=3,
        agent="DEV",
        changed_files=["a.py", "README.md", "cfg.toml"],
    )
    payload = _load_stage_changes()
    assert payload["schema_version"] == 1
    assert payload["iteration"] == 3
    assert payload["agent"] == "DEV"
    assert payload["changed_files"] == ["a.py", "README.md", "cfg.toml"]
    assert payload["code_changed"] is True
    assert payload["code_changed_files"] == ["a.py", "cfg.toml"]


def test_validate_tdd_main_decision() -> None:
    warnings = _validate_tdd_main_decision(
        next_agent="REVIEW",
        must_test_after_dev=True,
        test_required_task_ids=[],
        last_test_verdict=None,
        min_coverage=None,
        coverage_ok=True,
    )
    assert warnings

    warnings = _validate_tdd_main_decision(
        next_agent="TEST",
        must_test_after_dev=True,
        test_required_task_ids=[],
        last_test_verdict=None,
        min_coverage=None,
        coverage_ok=True,
    )
    assert warnings == []

    with pytest.raises(ValueError):
        _validate_tdd_main_decision(
            next_agent="DEV",
            must_test_after_dev=False,
            test_required_task_ids=["M1-T1"],
            last_test_verdict=None,
            min_coverage=None,
            coverage_ok=True,
        )

    warnings = _validate_tdd_main_decision(
        next_agent="DEV",
        must_test_after_dev=False,
        test_required_task_ids=["M1-T1"],
        last_test_verdict="PASS",
        min_coverage=None,
        coverage_ok=True,
    )
    assert warnings

    with pytest.raises(ValueError):
        _validate_tdd_main_decision(
            next_agent="DEV",
            must_test_after_dev=False,
            test_required_task_ids=["M1-T1"],
            last_test_verdict="PASS",
            min_coverage=80,
            coverage_ok=False,
        )

    warnings = _validate_tdd_main_decision(
        next_agent="USER",
        must_test_after_dev=False,
        test_required_task_ids=["M1-T1"],
        last_test_verdict=None,
        min_coverage=None,
        coverage_ok=True,
    )
    assert warnings == []


def test_find_open_test_required_task_ids_first_status_drives_gate() -> None:
    dev_plan = """# Dev Plan

### M1-T1: A
- status: TODO
- test_required: true

### M1-T2: B
- status: DONE
- test_required: true

### M1-T3: C
- test_required: true
- status: DONE
- status: TODO
"""
    assert find_open_test_required_task_ids(dev_plan) == ["M1-T1"]
