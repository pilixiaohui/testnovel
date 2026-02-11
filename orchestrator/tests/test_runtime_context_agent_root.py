import json
from pathlib import Path

from orchestrator.runtime_context import load_runtime_context


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _prepare_layout(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    repo_root = tmp_path / "repo"
    code_root = repo_root / "project" / "backend"
    frontend_root = repo_root / "project" / "frontend"
    python_bin = tmp_path / "shared-venv" / "bin" / "python3"

    code_root.mkdir(parents=True, exist_ok=True)
    frontend_root.mkdir(parents=True, exist_ok=True)
    python_bin.parent.mkdir(parents=True, exist_ok=True)
    python_bin.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    env_file = tmp_path / "project_env.json"
    return repo_root, code_root, frontend_root, python_bin, env_file


def test_load_runtime_context_derives_agent_root_from_code_and_frontend(tmp_path: Path) -> None:
    repo_root, code_root, frontend_root, python_bin, env_file = _prepare_layout(tmp_path)
    _write_json(
        env_file,
        {
            "project": {
                "root": str(repo_root),
                "code_root": str(code_root),
                "frontend_root": str(frontend_root),
            },
            "python": {"python_bin": str(python_bin)},
            "test_execution": {
                "frontend_dev_port": 5185,
                "backend_base_url": "http://127.0.0.1:8000",
                "service_startup_wait_seconds": 6,
                "test_timeout_seconds": {"unit": 1, "integration": 2, "e2e": 3},
            },
        },
    )

    ctx = load_runtime_context(project_env_file=env_file)
    assert ctx.project_root == repo_root.resolve()
    assert ctx.agent_root == (repo_root / "project").resolve()
    assert ctx.code_root == code_root.resolve()
    assert ctx.frontend_root == frontend_root.resolve()


def test_load_runtime_context_allows_python_bin_outside_project_root(tmp_path: Path) -> None:
    repo_root, code_root, frontend_root, python_bin, env_file = _prepare_layout(tmp_path)
    _write_json(
        env_file,
        {
            "project": {
                "root": str(repo_root),
                "code_root": str(code_root),
                "frontend_root": str(frontend_root),
            },
            "python": {"python_bin": str(python_bin)},
            "test_execution": {
                "frontend_dev_port": 5185,
                "backend_base_url": "http://127.0.0.1:8000",
                "service_startup_wait_seconds": 6,
                "test_timeout_seconds": {"unit": 1, "integration": 2, "e2e": 3},
            },
        },
    )

    ctx = load_runtime_context(project_env_file=env_file)
    assert ctx.python_bin == python_bin.resolve()
