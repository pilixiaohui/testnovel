import json

import pytest

from orchestrator.config import (
    IMPLEMENTER_TASK_FILE,
    SPEC_ANALYZER_TASK_FILE,
    REPORT_IMPLEMENTER_FILE,
    REPORT_SPEC_ANALYZER_FILE,
    REPORT_ITERATION_SUMMARY_FILE,
    REPORT_MAIN_DECISION_FILE,
)
from orchestrator.file_ops import _rel_path
from orchestrator.summary import _parse_iteration_summary


def _build_summary_payload() -> dict:
    return {
        "iteration": 1,
        "main_session_id": "main-session",
        "subagent_session_id": "sub-session",
        "main_decision": {"next_agent": "IMPLEMENTER", "reason": "dispatch"},
        "subagent": {
            "agent": "IMPLEMENTER",
            "task_summary": "执行实现任务",
            "report_summary": "实现完成并提交报告",
        },
        "steps": [
            {"step": 1, "actor": "MAIN", "detail": "MAIN 派发任务"},
            {"step": 2, "actor": "IMPLEMENTER", "detail": "IMPLEMENTER 实现并验证"},
            {"step": 3, "actor": "ORCHESTRATOR", "detail": "编排器归档产物"},
        ],
        "summary": "IMPLEMENTER 完成实现并提交报告",
        "artifacts": {
            "main_decision_file": _rel_path(REPORT_MAIN_DECISION_FILE),
            "task_file": _rel_path(IMPLEMENTER_TASK_FILE),
            "report_file": _rel_path(REPORT_IMPLEMENTER_FILE),
            "summary_file": _rel_path(REPORT_ITERATION_SUMMARY_FILE),
        },
        "requirement_matrix": {
            "requirements": {
                "REQ-001": "VERIFIED",
                "REQ-002": "IN_PROGRESS",
            }
        },
        "proof_coverage_rate": 50,
    }


def test_parse_iteration_summary_accepts_requirement_fields() -> None:
    payload = _build_summary_payload()
    parsed = _parse_iteration_summary(
        json.dumps(payload, ensure_ascii=False),
        iteration=1,
        expected_agent="IMPLEMENTER",
        main_session_id="main-session",
        subagent_session_id="sub-session",
        main_decision_file=REPORT_MAIN_DECISION_FILE,
        task_file=IMPLEMENTER_TASK_FILE,
        report_file=REPORT_IMPLEMENTER_FILE,
        summary_file=REPORT_ITERATION_SUMMARY_FILE,
    )

    assert parsed["requirement_matrix"]["requirements"]["REQ-001"] == "VERIFIED"
    assert parsed["proof_coverage_rate"] == 50.0


def test_parse_iteration_summary_rejects_invalid_requirement_status() -> None:
    payload = _build_summary_payload()
    payload["requirement_matrix"]["requirements"]["REQ-001"] = "BAD"

    with pytest.raises(ValueError, match="requirement_matrix"):
        _parse_iteration_summary(
            json.dumps(payload, ensure_ascii=False),
            iteration=1,
            expected_agent="IMPLEMENTER",
            main_session_id="main-session",
            subagent_session_id="sub-session",
            main_decision_file=REPORT_MAIN_DECISION_FILE,
            task_file=IMPLEMENTER_TASK_FILE,
            report_file=REPORT_IMPLEMENTER_FILE,
            summary_file=REPORT_ITERATION_SUMMARY_FILE,
        )


def test_parse_iteration_summary_rejects_invalid_proof_coverage_rate() -> None:
    payload = _build_summary_payload()
    payload["proof_coverage_rate"] = 120

    with pytest.raises(ValueError, match="proof_coverage_rate"):
        _parse_iteration_summary(
            json.dumps(payload, ensure_ascii=False),
            iteration=1,
            expected_agent="IMPLEMENTER",
            main_session_id="main-session",
            subagent_session_id="sub-session",
            main_decision_file=REPORT_MAIN_DECISION_FILE,
            task_file=IMPLEMENTER_TASK_FILE,
            report_file=REPORT_IMPLEMENTER_FILE,
            summary_file=REPORT_ITERATION_SUMMARY_FILE,
        )


def test_parse_iteration_summary_accepts_spec_analyzer_actor() -> None:
    payload = _build_summary_payload()
    payload["main_decision"] = {"next_agent": "SPEC_ANALYZER", "reason": "规格分析"}
    payload["subagent"]["agent"] = "SPEC_ANALYZER"
    payload["subagent"]["task_summary"] = "分析代码并生成规格草案"
    payload["subagent"]["report_summary"] = "产出规格草案与需求矩阵"
    payload["steps"][1]["actor"] = "SPEC_ANALYZER"
    payload["steps"][2]["actor"] = "SPEC_ANALYZER"
    payload["summary"] = "SPEC_ANALYZER 完成规格分析"
    payload["changes"] = None
    payload["artifacts"] = {
        "main_decision_file": _rel_path(REPORT_MAIN_DECISION_FILE),
        "task_file": _rel_path(SPEC_ANALYZER_TASK_FILE),
        "report_file": _rel_path(REPORT_SPEC_ANALYZER_FILE),
        "summary_file": _rel_path(REPORT_ITERATION_SUMMARY_FILE),
    }

    parsed = _parse_iteration_summary(
        json.dumps(payload, ensure_ascii=False),
        iteration=1,
        expected_agent="SPEC_ANALYZER",
        main_session_id="main-session",
        subagent_session_id="sub-session",
        main_decision_file=REPORT_MAIN_DECISION_FILE,
        task_file=SPEC_ANALYZER_TASK_FILE,
        report_file=REPORT_SPEC_ANALYZER_FILE,
        summary_file=REPORT_ITERATION_SUMMARY_FILE,
    )

    assert parsed["subagent"]["agent"] == "SPEC_ANALYZER"
