import json
from pathlib import Path

import pytest

import orchestrator.workflow as workflow


def _write_spec_state(path: Path, *, phase: str = "TASK_READY", user_confirmed: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "active_change_id": "CHG-0001",
                "phase": phase,
                "user_confirmed": user_confirmed,
                "last_updated_iteration": 1,
                "notes": "test",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_change_tasks(changes_dir: Path, *, body: str) -> None:
    change_dir = changes_dir / "CHG-0001"
    change_dir.mkdir(parents=True, exist_ok=True)
    (change_dir / "tasks.md").write_text(body, encoding="utf-8")


def _build_output(*, implementation_scope: list[str]) -> dict:
    return {
        "decision": {"next_agent": "IMPLEMENTER", "reason": "dispatch"},
        "history_append": "## Iteration 1:\nnext_agent: IMPLEMENTER\nreason: dispatch",
        "task_body": "## 任务目标\n实现功能",
        "active_change_id": "CHG-0001",
        "implementation_scope": implementation_scope,
        "artifact_updates": None,
        "change_action": "none",
    }


def _patch_spec_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    specs_dir = tmp_path / "specs"
    changes_dir = specs_dir / "changes"
    archive_dir = specs_dir / "archive"
    state_file = specs_dir / "state.json"

    changes_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workflow, "SPECS_DIR", specs_dir)
    monkeypatch.setattr(workflow, "SPECS_CHANGES_DIR", changes_dir)
    monkeypatch.setattr(workflow, "SPECS_ARCHIVE_DIR", archive_dir)
    monkeypatch.setattr(workflow, "SPECS_STATE_FILE", state_file)

    return changes_dir, state_file


def test_validate_main_output_accepts_implementation_scope_from_tasks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    changes_dir, state_file = _patch_spec_paths(monkeypatch, tmp_path)
    _write_spec_state(state_file)
    _write_change_tasks(
        changes_dir,
        body="# Tasks\n\n- [ ] TASK-001 | status: TODO\n- [ ] TASK-002 | status: TODO\n",
    )

    workflow._validate_main_output_fields(
        iteration=1,
        output=_build_output(implementation_scope=["TASK-001"]),
    )


def test_validate_main_output_rejects_unknown_scope_task_ids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    changes_dir, state_file = _patch_spec_paths(monkeypatch, tmp_path)
    _write_spec_state(state_file)
    _write_change_tasks(
        changes_dir,
        body="# Tasks\n\n- [ ] TASK-001 | status: TODO\n",
    )

    with pytest.raises(ValueError, match="implementation_scope"):
        workflow._validate_main_output_fields(
            iteration=1,
            output=_build_output(implementation_scope=["TASK-999"]),
        )


def test_validate_main_output_blocks_implementer_when_user_confirmation_pending(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    changes_dir, state_file = _patch_spec_paths(monkeypatch, tmp_path)
    _write_spec_state(state_file, phase="USER_CONFIRM", user_confirmed=False)
    _write_change_tasks(changes_dir, body="# Tasks\n\n- [ ] TASK-001 | status: TODO\n")

    with pytest.raises(ValueError, match="Spec confirmation pending"):
        workflow._validate_main_output_fields(
            iteration=1,
            output=_build_output(implementation_scope=["TASK-001"]),
        )
