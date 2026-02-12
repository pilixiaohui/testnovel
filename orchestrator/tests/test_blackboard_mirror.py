from pathlib import Path
from types import SimpleNamespace

import pytest

import orchestrator.blackboard_mirror as blackboard_mirror


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _prepare_source_tree(repo_root: Path) -> None:
    source_root = repo_root / "orchestrator"
    _write_text(source_root / "memory" / "global_context.md", "# global\n")
    _write_text(source_root / "workspace" / "implementer" / "current_task.md", "# task\n")
    _write_text(source_root / "reports" / "report_implementer.md", "# report\n")
    _write_text(source_root / "memory" / "verification_policy.json", "{}")


def test_sync_project_blackboard_mirror_copies_md_and_json_to_agent_root(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    agent_root = repo_root / "project"
    agent_root.mkdir(parents=True, exist_ok=True)
    _prepare_source_tree(repo_root)

    monkeypatch.setattr(blackboard_mirror, "PROJECT_ROOT", repo_root)

    context = SimpleNamespace(agent_root=agent_root)
    result = blackboard_mirror.sync_project_blackboard_mirror(
        context=context,
        iteration=3,
        triggered_by="dispatch:IMPLEMENTER",
    )

    mirror_root = agent_root / ".orchestrator_ctx"
    assert result.mirror_root == mirror_root
    assert (mirror_root / "memory" / "global_context.md").is_file()
    assert (mirror_root / "workspace" / "implementer" / "current_task.md").is_file()
    assert (mirror_root / "reports" / "report_implementer.md").is_file()
    assert (mirror_root / "memory" / "verification_policy.json").is_file()

    manifest = mirror_root / ".sync_manifest.json"
    assert manifest.is_file()
    manifest_payload = manifest.read_text(encoding="utf-8")
    assert '"schema_version": 2' in manifest_payload
    assert '".json"' in manifest_payload

    blackboard_mirror.assert_project_mirror_unchanged(
        mirror_root=mirror_root,
        expected_hash=result.content_hash,
        stage="IMPLEMENTER",
    )



def test_assert_project_mirror_unchanged_detects_mutation(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    agent_root = repo_root / "project"
    agent_root.mkdir(parents=True, exist_ok=True)
    _prepare_source_tree(repo_root)

    monkeypatch.setattr(blackboard_mirror, "PROJECT_ROOT", repo_root)
    context = SimpleNamespace(agent_root=agent_root)

    result = blackboard_mirror.sync_project_blackboard_mirror(
        context=context,
        iteration=5,
        triggered_by="dispatch:VALIDATE",
    )
    mirror_root = result.mirror_root

    target = mirror_root / "memory" / "global_context.md"
    target.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="mirror modified"):
        blackboard_mirror.assert_project_mirror_unchanged(
            mirror_root=mirror_root,
            expected_hash=result.content_hash,
            stage="VALIDATE",
        )
