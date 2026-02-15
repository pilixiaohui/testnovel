import importlib
import importlib.util

import pytest


def _import_module(module_path: str):
    try:
        spec = importlib.util.find_spec(module_path)
    except ModuleNotFoundError as exc:
        pytest.fail(f"{module_path} module is missing: {exc}", pytrace=False)
    if spec is None:
        pytest.fail(f"{module_path} module is missing", pytrace=False)
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        missing = exc.name
        if missing in {"gqlalchemy", "neo4j"}:
            pytest.fail(
                f"{module_path} requires {missing} but it is missing: {exc}",
                pytrace=False,
            )
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)
    except ImportError as exc:
        message = str(exc)
        if "gqlalchemy" in message or "neo4j" in message:
            pytest.fail(
                f"{module_path} dependency import failed: {exc}",
                pytrace=False,
            )
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def get_schema_model(name: str):
    module = _import_module("app.storage.schema")
    if not hasattr(module, name):
        pytest.fail(f"schema.{name} is missing", pytrace=False)
    return getattr(module, name)


def get_default_branch_id() -> str:
    module = _import_module("app.constants")
    if not hasattr(module, "DEFAULT_BRANCH_ID"):
        pytest.fail("DEFAULT_BRANCH_ID is missing", pytrace=False)
    return module.DEFAULT_BRANCH_ID


def seed_root_with_branch(
    storage, *, root_id: str, branch_id: str, commit_id: str
) -> None:
    root_cls = get_schema_model("Root")
    branch_cls = get_schema_model("Branch")
    branch_head_cls = get_schema_model("BranchHead")
    commit_cls = get_schema_model("Commit")

    root = root_cls(
        id=root_id,
        logline="seed",
        theme="seed",
        ending="seed",
        created_at="2024-01-01T00:00:00Z",
    )
    storage.create_root(root)

    branch = branch_cls(
        id=f"{root_id}:{branch_id}",
        root_id=root_id,
        branch_id=branch_id,
        parent_branch_id=None,
        fork_scene_origin_id=None,
        fork_commit_id=None,
    )
    storage.create_branch(branch)

    commit = commit_cls(
        id=commit_id,
        parent_id=None,
        message="seed",
        created_at="2024-01-01T00:00:00Z",
        root_id=root_id,
        branch_id=branch_id,
    )
    storage.create_commit(commit)

    branch_head = branch_head_cls(
        id=f"{root_id}:{branch_id}:head",
        root_id=root_id,
        branch_id=branch_id,
        head_commit_id=commit_id,
        version=1,
    )
    storage.create_branch_head(branch_head)


def create_scene_origin(
    storage,
    *,
    root_id: str,
    branch_id: str,
    title: str = "Scene 1",
    parent_act_id: str = "act-1",
) -> dict:
    content = {
        "expected_outcome": "safe",
        "conflict_type": "internal",
        "actual_outcome": "safe",
        "summary": "seed summary",
        "rendered_content": "seed render",
        "pov_character_id": "pov-1",
        "status": "draft",
    }
    return storage.create_scene_origin(
        root_id=root_id,
        branch_id=branch_id,
        title=title,
        parent_act_id=parent_act_id,
        content=content,
    )


def fetch_one(storage, query: str, params: dict):
    return next(storage.db.execute_and_fetch(query, params), None)
