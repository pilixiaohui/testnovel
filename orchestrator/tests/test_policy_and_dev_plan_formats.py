from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.parsing import (
    extract_report_coverage_percent,
    extract_report_verdict,
    parse_parsing_rules,
)
from orchestrator.validation import _validate_dev_plan_text


def test_validate_dev_plan_text_legacy_ok(tmp_path: Path) -> None:
    dev_plan = """# Dev Plan

## Milestone M0: Demo

### M0-T1: Title
- status: TODO
- acceptance:
- a
- evidence:
"""
    _validate_dev_plan_text(text=dev_plan, source=tmp_path / "dev_plan.md")


def test_validate_dev_plan_text_phased_ok(tmp_path: Path) -> None:
    dev_plan = """# Dev Plan

## Milestone M0: Demo

### M0-T1: Title
- acceptance:
- a

#### 测试阶段
- status: DONE
- evidence:

#### 实现阶段
- status: DONE
- evidence:

#### 审阅阶段
- status: VERIFIED
- evidence: Iteration 1 REVIEW: pytest -q => PASS
"""
    _validate_dev_plan_text(text=dev_plan, source=tmp_path / "dev_plan.md")


def test_validate_dev_plan_text_phased_requires_all_phases(tmp_path: Path) -> None:
    dev_plan = """# Dev Plan

### M0-T1: Title
- acceptance:
- a

#### 测试阶段
- status: DONE
- evidence:

#### 审阅阶段
- status: VERIFIED
- evidence: Iteration 1 REVIEW: PASS
"""
    with pytest.raises(RuntimeError):
        _validate_dev_plan_text(text=dev_plan, source=tmp_path / "dev_plan.md")


def test_parse_parsing_rules_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import orchestrator.parsing as p

    policy = {
        "version": 1,
        "report_rules": {
            "apply_to": ["TEST"],
            "require_verdict": True,
            "verdict_prefix": "结论：",
            "verdict_allowed": ["PASS", "FAIL", "BLOCKED"],
            "blocker_prefix": "阻塞：",
            "blocker_clear_value": "无",
        },
    }
    path = tmp_path / "verification_policy.json"
    path.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(p, "VERIFICATION_POLICY_FILE", path)

    rules = parse_parsing_rules()
    assert rules.critical_fields == {"iteration"}
    assert rules.optional_fields == {"verdict", "blockers"}
    assert rules.use_defaults_on_failure is True


def test_extract_report_parsing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import orchestrator.parsing as p

    policy = {
        "version": 1,
        "report_rules": {
            "apply_to": ["TEST"],
            "require_verdict": True,
            "verdict_prefix": "结论：",
            "verdict_allowed": ["PASS", "FAIL", "BLOCKED"],
            "blocker_prefix": "阻塞：",
            "blocker_clear_value": "无",
        },
        "parsing_rules": {
            "critical_fields": ["iteration"],
            "optional_fields": ["verdict", "blockers"],
            "use_defaults_on_failure": True,
        },
    }
    path = tmp_path / "verification_policy.json"
    path.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(p, "VERIFICATION_POLICY_FILE", path)

    report = "结论：PASS\n阻塞：无\ncoverage: 82.5%\n"
    assert extract_report_verdict(report_text=report) == "PASS"
    assert extract_report_coverage_percent(report_text=report) == 82.5
