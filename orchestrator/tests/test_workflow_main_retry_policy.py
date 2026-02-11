from pathlib import Path

import orchestrator.workflow as workflow
from orchestrator.errors import TemporaryError


def test_run_main_decision_stage_uses_main_retry_backoff(monkeypatch, tmp_path: Path) -> None:
    run_calls: list[int] = []
    backoff_calls: list[tuple[float, float]] = []
    guard_check_calls: list[dict] = []

    monkeypatch.setattr(workflow, "_snapshot_files", lambda _paths: {})

    def _record_guard(snapshot: dict, *, label: str) -> None:
        guard_check_calls.append(snapshot)

    monkeypatch.setattr(workflow, "_assert_files_unchanged", _record_guard)

    def _fake_run_cli_exec(**_kwargs):
        run_calls.append(1)
        if len(run_calls) == 1:
            raise TemporaryError("first failure")
        return {"last_message": "{}", "session_id": "session-id"}

    monkeypatch.setattr(workflow, "_run_cli_exec", _fake_run_cli_exec)
    monkeypatch.setattr(
        workflow,
        "_parse_main_output",
        lambda _raw, strict=True: {
            "decision": {"next_agent": "VALIDATE", "reason": "ok"},
            "history_append": "## Iteration 1:\nnext_agent: VALIDATE",
            "task_body": None,
            "dev_plan_next": None,
            "doc_patches": None,
        },
    )

    def _record_backoff(*, label: str, attempt: int, base_seconds: float, max_seconds: float) -> None:
        backoff_calls.append((base_seconds, max_seconds))

    monkeypatch.setattr(workflow, "_sleep_backoff", _record_backoff)

    output, session_id = workflow._run_main_decision_stage(
        prompt="main prompt",
        guard_paths=[tmp_path / "guard.md"],
        label="MAIN",
        sandbox_mode="workspace-write",
        approval_policy="on-request",
        control=None,
        resume_session_id=None,
        post_validate=None,
        system_prompt="system",
    )

    assert output["decision"]["next_agent"] == "VALIDATE"
    assert session_id == "session-id"
    assert len(run_calls) == 2
    assert len(guard_check_calls) == 1
    assert backoff_calls == [
        (
            workflow._MAIN_BACKOFF_BASE_SECONDS,
            workflow._MAIN_BACKOFF_MAX_SECONDS,
        )
    ]
