from pathlib import Path
from types import SimpleNamespace

import orchestrator.workflow as workflow


def test_to_agent_visible_path_maps_orchestrator_path_to_mirror(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    orchestrator_file = repo_root / "orchestrator" / "memory" / "global_context.md"
    agent_root = repo_root / "project"

    orchestrator_file.parent.mkdir(parents=True, exist_ok=True)
    agent_root.mkdir(parents=True, exist_ok=True)
    orchestrator_file.write_text("# ctx\n", encoding="utf-8")

    monkeypatch.setattr(workflow, "PROJECT_ROOT", repo_root)
    context = SimpleNamespace(agent_root=agent_root)

    actual = workflow._to_agent_visible_path(context=context, source_path=orchestrator_file)
    expected = (agent_root / ".orchestrator_ctx" / "memory" / "global_context.md").as_posix()
    assert actual == expected


def test_to_agent_visible_path_maps_agent_root_to_relative(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    agent_root = repo_root / "project"
    file_in_project = agent_root / "backend" / "main.py"

    file_in_project.parent.mkdir(parents=True, exist_ok=True)
    agent_root.mkdir(parents=True, exist_ok=True)
    file_in_project.write_text("print(ok)\n", encoding="utf-8")

    monkeypatch.setattr(workflow, "PROJECT_ROOT", repo_root)
    context = SimpleNamespace(agent_root=agent_root)

    assert workflow._to_agent_visible_path(context=context, source_path=agent_root) == "."
    assert workflow._to_agent_visible_path(context=context, source_path=file_in_project) == "./backend/main.py"


def test_to_agent_visible_path_returns_absolute_for_external_path(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    agent_root = repo_root / "project"
    external_file = tmp_path / "external" / "x.md"

    external_file.parent.mkdir(parents=True, exist_ok=True)
    external_file.write_text("x\n", encoding="utf-8")
    agent_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(workflow, "PROJECT_ROOT", repo_root)
    context = SimpleNamespace(agent_root=agent_root)

    actual = workflow._to_agent_visible_path(context=context, source_path=external_file)
    assert actual == external_file.resolve().as_posix()
