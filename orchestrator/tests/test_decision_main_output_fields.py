import json

import pytest

from orchestrator.decision import _parse_main_output


def _build_payload(*, next_agent: str = "IMPLEMENTER") -> dict:
    payload = {
        "next_agent": next_agent,
        "reason": "dispatch",
        "history_append": f"## Iteration 1:\nnext_agent: {next_agent}\nreason: test",
        "task_body": None,
        "active_change_id": None,
        "implementation_scope": None,
        "artifact_updates": None,
        "change_action": "none",
    }

    if next_agent == "IMPLEMENTER":
        payload["task_body"] = "## 任务目标\n实现功能"
        payload["active_change_id"] = "CHG-0001"
        payload["implementation_scope"] = ["TASK-001"]
    elif next_agent == "SPEC_ANALYZER":
        payload["task_body"] = "## 任务目标\n生成规格草案"
        payload["active_change_id"] = "CHG-0001"

    return payload


def test_parse_main_output_accepts_implementer_spec_protocol() -> None:
    parsed = _parse_main_output(json.dumps(_build_payload(), ensure_ascii=False), strict=True)

    assert parsed["decision"]["next_agent"] == "IMPLEMENTER"
    assert parsed["active_change_id"] == "CHG-0001"
    assert parsed["implementation_scope"] == ["TASK-001"]


def test_parse_main_output_accepts_spec_analyzer_task_body() -> None:
    parsed = _parse_main_output(
        json.dumps(_build_payload(next_agent="SPEC_ANALYZER"), ensure_ascii=False),
        strict=True,
    )

    assert parsed["decision"]["next_agent"] == "SPEC_ANALYZER"
    assert parsed["task_body"] is not None
    assert parsed["implementation_scope"] is None


@pytest.mark.parametrize("legacy_field,legacy_value", [
    ("task", "legacy body"),
    ("dev_plan_next", "# dev plan"),
    ("spec_anchor_next", "# spec anchor"),
    ("target_reqs", ["REQ-001"]),
])
def test_parse_main_output_rejects_legacy_fields(legacy_field: str, legacy_value: object) -> None:
    payload = _build_payload()
    payload[legacy_field] = legacy_value

    with pytest.raises(ValueError, match="legacy field"):
        _parse_main_output(json.dumps(payload, ensure_ascii=False), strict=True)


def test_parse_main_output_requires_implementation_scope_for_implementer() -> None:
    payload = _build_payload()
    payload["implementation_scope"] = None

    with pytest.raises(ValueError, match="implementation_scope"):
        _parse_main_output(json.dumps(payload, ensure_ascii=False), strict=True)


def test_parse_main_output_rejects_implementation_scope_for_non_implementer() -> None:
    payload = _build_payload(next_agent="VALIDATE")
    payload["implementation_scope"] = ["TASK-001"]

    with pytest.raises(ValueError, match="implementation_scope"):
        _parse_main_output(json.dumps(payload, ensure_ascii=False), strict=True)


def test_parse_main_output_requires_active_change_id_for_spec_analyzer() -> None:
    payload = _build_payload(next_agent="SPEC_ANALYZER")
    payload["active_change_id"] = None

    with pytest.raises(ValueError, match="active_change_id"):
        _parse_main_output(json.dumps(payload, ensure_ascii=False), strict=True)


def test_parse_main_output_rejects_artifact_updates_when_change_action_none() -> None:
    payload = _build_payload(next_agent="VALIDATE")
    payload["artifact_updates"] = [
        {
            "file": "changes/CHG-0001/tasks.md",
            "action": "append",
            "content": "- [ ] TASK-003",
        }
    ]

    with pytest.raises(ValueError, match="artifact_updates"):
        _parse_main_output(json.dumps(payload, ensure_ascii=False), strict=True)


def test_parse_main_output_rejects_unsafe_artifact_update_path() -> None:
    payload = _build_payload(next_agent="SPEC_ANALYZER")
    payload["change_action"] = "update"
    payload["artifact_updates"] = [
        {
            "file": "../outside.md",
            "action": "append",
            "content": "bad",
        }
    ]

    with pytest.raises(ValueError, match="safe relative path"):
        _parse_main_output(json.dumps(payload, ensure_ascii=False), strict=True)


def test_parse_main_output_rejects_artifact_update_with_non_active_change_id() -> None:
    payload = _build_payload(next_agent="SPEC_ANALYZER")
    payload["change_action"] = "update"
    payload["artifact_updates"] = [
        {
            "file": "changes/CHG-9999/tasks.md",
            "action": "append",
            "content": "- [ ] TASK-999",
        }
    ]

    with pytest.raises(ValueError, match="must target active change"):
        _parse_main_output(json.dumps(payload, ensure_ascii=False), strict=True)


def test_parse_main_output_rejects_artifact_update_with_unsupported_artifact_name() -> None:
    payload = _build_payload(next_agent="SPEC_ANALYZER")
    payload["change_action"] = "update"
    payload["artifact_updates"] = [
        {
            "file": "changes/CHG-0001/unknown.md",
            "action": "append",
            "content": "content",
        }
    ]

    with pytest.raises(ValueError, match="unsupported artifact"):
        _parse_main_output(json.dumps(payload, ensure_ascii=False), strict=True)


def test_parse_main_output_accepts_artifact_update_for_active_change_and_allowed_file() -> None:
    payload = _build_payload(next_agent="SPEC_ANALYZER")
    payload["change_action"] = "update"
    payload["artifact_updates"] = [
        {
            "file": "changes/CHG-0001/tasks.md",
            "action": "append",
            "content": "- [ ] TASK-003",
        }
    ]

    parsed = _parse_main_output(json.dumps(payload, ensure_ascii=False), strict=True)
    updates = parsed["artifact_updates"]
    assert isinstance(updates, list)
    assert updates[0]["file"] == "changes/CHG-0001/tasks.md"


def test_parse_main_output_rejects_invalid_active_change_id_format() -> None:
    payload = _build_payload(next_agent="SPEC_ANALYZER")
    payload["active_change_id"] = "bad-change"

    with pytest.raises(ValueError, match="CHG-<digits>"):
        _parse_main_output(json.dumps(payload, ensure_ascii=False), strict=True)


def test_parse_main_output_normalizes_lowercase_active_change_id() -> None:
    payload = _build_payload(next_agent="SPEC_ANALYZER")
    payload["active_change_id"] = "chg-0001"
    payload["change_action"] = "update"
    payload["artifact_updates"] = [
        {
            "file": "changes/chg-0001/tasks.md",
            "action": "append",
            "content": "- [ ] TASK-004",
        }
    ]

    parsed = _parse_main_output(json.dumps(payload, ensure_ascii=False), strict=True)
    assert parsed["active_change_id"] == "CHG-0001"
