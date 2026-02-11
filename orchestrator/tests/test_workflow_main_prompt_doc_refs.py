from pathlib import Path

import pytest

import orchestrator.workflow as workflow


def test_build_main_prompt_injects_doc_refs(monkeypatch, tmp_path: Path) -> None:
    captured: list[list[str]] = []

    monkeypatch.setattr(workflow, "_load_system_prompt", lambda _: "main-system")
    monkeypatch.setattr(workflow, "_inject_file", lambda *_args, **_kwargs: "[injected]")
    monkeypatch.setattr(workflow, "_resolve_target_agent_root", lambda: tmp_path)
    monkeypatch.setattr(workflow, "_build_project_tree", lambda _project_dir: "tree")
    monkeypatch.setattr(workflow, "_extract_recent_user_decisions", lambda lookback=5: [])

    def _fake_doc_injection(refs: list[str]) -> list[str]:
        captured.append(refs)
        return [f"[doc] {ref}" for ref in refs]

    monkeypatch.setattr(workflow, "_inject_doc_references", _fake_doc_injection)

    _, user_prompt, _ = workflow._build_main_prompt(
        iteration=1,
        user_task="执行任务 @doc:requirements/frontend_implementation_spec.md",
        extra_instructions=[],
        last_user_decision_iteration=None,
        last_subagent=None,
        is_resume=False,
        last_compact_iteration=0,
        milestone_changed=False,
    )

    assert captured == [["requirements/frontend_implementation_spec.md"]]
    assert "[doc] requirements/frontend_implementation_spec.md" in user_prompt


def test_build_main_prompt_doc_injection_failure_fast(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(workflow, "_load_system_prompt", lambda _: "main-system")
    monkeypatch.setattr(workflow, "_inject_file", lambda *_args, **_kwargs: "[injected]")
    monkeypatch.setattr(workflow, "_resolve_target_agent_root", lambda: tmp_path)
    monkeypatch.setattr(workflow, "_build_project_tree", lambda _project_dir: "tree")
    monkeypatch.setattr(workflow, "_extract_recent_user_decisions", lambda lookback=5: [])

    def _raise_doc_missing(_refs: list[str]) -> list[str]:
        raise ValueError("doc missing")

    monkeypatch.setattr(workflow, "_inject_doc_references", _raise_doc_missing)

    with pytest.raises(ValueError, match="doc missing"):
        workflow._build_main_prompt(
            iteration=1,
            user_task="执行任务 @doc:requirements/missing.md",
            extra_instructions=[],
            last_user_decision_iteration=None,
            last_subagent=None,
            is_resume=False,
            last_compact_iteration=0,
            milestone_changed=False,
        )
