from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.validation import (
    _extract_report_coverage_percent,
    _extract_report_verdict,
    _parse_test_requirements,
    _validate_dev_plan_text,
)


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


def test_parse_test_requirements_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import orchestrator.validation as v

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
    monkeypatch.setattr(v, "VERIFICATION_POLICY_FILE", path)

    assert _parse_test_requirements() is None


def test_parse_test_requirements_enabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import orchestrator.validation as v

    policy = {
        "version": 1,
        "test_requirements": {"min_coverage": 80, "must_pass_before_review": True},
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
    monkeypatch.setattr(v, "VERIFICATION_POLICY_FILE", path)

    assert _parse_test_requirements() == (80, True)

    report = "结论：PASS\n阻塞：无\ncoverage: 82.5%\n"
    assert _extract_report_verdict(report_text=report) == "PASS"
    assert _extract_report_coverage_percent(report_text=report) == 82.5

