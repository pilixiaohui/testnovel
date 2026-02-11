from pathlib import Path
from types import SimpleNamespace

import orchestrator.codex_runner as codex_runner


def test_resolve_agent_work_dir_main_uses_orchestrator_root() -> None:
    assert codex_runner._resolve_agent_work_dir("MAIN") == codex_runner.CONFIG.orchestrator_dir


def test_resolve_agent_work_dir_non_main_uses_agent_root(monkeypatch, tmp_path: Path) -> None:
    target_root = tmp_path / "project-root"
    target_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        codex_runner,
        "load_runtime_context",
        lambda **_: SimpleNamespace(agent_root=target_root),
    )

    assert codex_runner._resolve_agent_work_dir("IMPLEMENTER") == target_root
