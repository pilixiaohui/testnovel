import json
from pathlib import Path

import pytest

import orchestrator.workflow as workflow


def _patch_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, pending: bool) -> None:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    state_file = specs_dir / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "active_change_id": "CHG-0001",
                "phase": "USER_CONFIRM" if pending else "TASK_READY",
                "user_confirmed": not pending,
                "last_updated_iteration": 1,
                "notes": "test",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(workflow, "SPECS_STATE_FILE", state_file)


def test_validate_main_output_accepts_user_decision_with_spec_confirmation_options(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_state(monkeypatch, tmp_path, pending=True)

    output = {
        "decision": {
            "next_agent": "USER",
            "reason": "confirm spec",
            "decision_title": "规格确认",
            "question": "是否确认当前规格草案？",
            "options": [
                {"option_id": "accept_spec", "description": "确认规格并进入开发"},
                {"option_id": "refine_spec", "description": "补充需求后重新分析"},
            ],
            "recommended_option_id": "accept_spec",
            "doc_patches": None,
        },
        "history_append": "## Iteration 1:\nnext_agent: USER\nreason: confirm spec",
        "task_body": None,
        "active_change_id": None,
        "implementation_scope": None,
        "artifact_updates": None,
        "change_action": "none",
    }

    workflow._validate_main_output_fields(iteration=1, output=output)


def test_validate_main_output_rejects_user_decision_without_spec_confirmation_options(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_state(monkeypatch, tmp_path, pending=True)

    output = {
        "decision": {
            "next_agent": "USER",
            "reason": "confirm spec",
            "decision_title": "规格确认",
            "question": "是否确认当前规格草案？",
            "options": [
                {"option_id": "accept", "description": "确认"},
                {"option_id": "refine", "description": "补充"},
            ],
            "recommended_option_id": "accept",
            "doc_patches": None,
        },
        "history_append": "## Iteration 1:\nnext_agent: USER\nreason: confirm spec",
        "task_body": None,
        "active_change_id": None,
        "implementation_scope": None,
        "artifact_updates": None,
        "change_action": "none",
    }

    with pytest.raises(ValueError, match="accept_spec/refine_spec"):
        workflow._validate_main_output_fields(iteration=1, output=output)


def test_resume_blackboard_paths_support_spec_analyzer_after_subagent() -> None:
    required, optional = workflow._resume_blackboard_paths(
        phase="after_subagent",
        next_agent="SPEC_ANALYZER",
    )

    assert workflow.SPEC_ANALYZER_TASK_FILE in required
    assert workflow.REPORT_SPEC_ANALYZER_FILE in required
    assert workflow.DEV_PLAN_STAGED_FILE in optional
