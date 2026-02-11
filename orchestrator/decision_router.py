from __future__ import annotations

from typing import Mapping, TypedDict

from .contracts import IssueCategory, OverallVerdict


class RoutedDecision(TypedDict):
    overall_verdict: OverallVerdict
    reason: str
    decision_basis: list[str]
    blockers: list[str]
    recommendations: list[str]


def _extract_basis(validator: str, category: str, findings: list[str]) -> str:
    first = findings[0] if findings else "(无详细 finding)"
    return f"{validator}: {category} - {first}"


def route_validation_results(results: Mapping[str, Mapping[str, object]]) -> RoutedDecision:
    non_pass: list[tuple[str, IssueCategory, list[str], str]] = []

    for validator, result in results.items():
        verdict = str(result.get("verdict", "")).upper()
        if verdict == "PASS":
            continue

        category = str(result.get("category", "CODE_DEFECT")).upper()
        if category not in {"CODE_DEFECT", "INFRA", "NOISE", "EVIDENCE_GAP"}:
            category = "CODE_DEFECT"

        findings = [str(item) for item in result.get("findings", []) if isinstance(item, str)]
        evidence = str(result.get("evidence", ""))
        non_pass.append((validator, category, findings, evidence))

    if not non_pass:
        return {
            "overall_verdict": "PASS",
            "reason": "全部验证器通过",
            "decision_basis": ["All validators passed"],
            "blockers": [],
            "recommendations": ["可以继续 FINISH_CHECK"],
        }

    infra_items = [item for item in non_pass if item[1] == "INFRA"]
    code_items = [item for item in non_pass if item[1] == "CODE_DEFECT"]
    evidence_items = [item for item in non_pass if item[1] in {"NOISE", "EVIDENCE_GAP"}]

    if infra_items:
        return {
            "overall_verdict": "BLOCKED",
            "reason": "存在基础设施阻塞，禁止派发业务修复",
            "decision_basis": [_extract_basis(v, c, f) for v, c, f, _ in infra_items],
            "blockers": [f"{v}: {f[0] if f else e}" for v, _, f, e in infra_items],
            "recommendations": [
                "先修复前后端可达性与运行环境，再重新触发 VALIDATE",
                "环境恢复后重跑全部验证器，禁止跳过场景",
            ],
        }

    if code_items:
        return {
            "overall_verdict": "REWORK",
            "reason": "存在真实代码缺陷，需派发 IMPLEMENTER",
            "decision_basis": [_extract_basis(v, c, f) for v, c, f, _ in code_items],
            "blockers": [f"{v}: {f[0] if f else e}" for v, _, f, e in code_items],
            "recommendations": [
                "仅针对 CODE_DEFECT 发现修复代码",
                "修复后要求完整自测并回填结构化证据",
            ],
        }

    # 仅噪声或证据缺失
    return {
        "overall_verdict": "BLOCKED",
        "reason": "当前仅存在噪声/证据缺失，不能判定业务通过",
        "decision_basis": [_extract_basis(v, c, f) for v, c, f, _ in evidence_items],
        "blockers": [f"{v}: {f[0] if f else e}" for v, _, f, e in evidence_items],
        "recommendations": [
            "补齐 modified_files / 测试证据后重新验证",
            "收紧扫描范围，排除第三方依赖噪声",
        ],
    }
