from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.constants import DEFAULT_BRANCH_ID
from app.models import SceneNode


def _base_scene_payload() -> dict:
    return {
        "id": uuid4(),
        "branch_id": DEFAULT_BRANCH_ID,
        "expected_outcome": "Outcome",
        "conflict_type": "internal",
        "actual_outcome": "Actual",
        "is_dirty": False,
        "title": "Scene 1",
        "sequence_index": 0,
    }


def _frontend_scene_node_block() -> str:
    repo_root = Path(__file__).resolve().parents[4]
    types_path = repo_root / "project" / "frontend" / "src" / "types" / "snowflake.ts"
    content = types_path.read_text(encoding="utf-8")
    match = re.search(r"export interface SceneNode\s*\{(.*?)\}", content, re.S)
    assert match, "frontend SceneNode interface missing"
    return match.group(1)


def test_scene_node_includes_title_and_sequence_index_fields():
    fields = SceneNode.model_fields
    assert "title" in fields
    assert "sequence_index" in fields


def test_scene_node_rejects_empty_title():
    payload = _base_scene_payload()
    payload["title"] = ""
    with pytest.raises(ValidationError):
        SceneNode(**payload)


def test_scene_node_rejects_negative_sequence_index():
    payload = _base_scene_payload()
    payload["sequence_index"] = -1
    with pytest.raises(ValidationError):
        SceneNode(**payload)


def test_frontend_scene_node_has_title_and_sequence_index_fields():
    block = _frontend_scene_node_block()
    assert re.search(r"\btitle\b", block)
    assert re.search(r"\bsequence_index\b", block)
