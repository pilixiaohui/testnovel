from __future__ import annotations

from .contracts import IssueCategory, VALID_ISSUE_CATEGORIES


_INFRA_KEYWORDS = (
    "err_connection_refused",
    "connection refused",
    "服务不可访问",
    "后端不可达",
    "前端不可达",
    "unreachable",
    "timeout",
    "transport closed",
    "permission denied",
    "提示词文件不存在",
    "validator timed out",
)

_EVIDENCE_GAP_KEYWORDS = (
    "缺少证据",
    "未实现/无证据",
    "实现摘要缺失",
    "信息缺失",
    "无法确定",
    "missing scenarios_executed",
    "验证结果缺失",
)

_NOISE_KEYWORDS = (
    "node_modules",
    "coverage",
    "dist/",
    "grep:",
    "is a directory",
)


def _normalize_text(*, findings: list[str], evidence: str) -> str:
    return "\n".join(findings + [evidence]).lower()


def classify_validation_result(*, verdict: str, findings: list[str], evidence: str) -> IssueCategory:
    if verdict.upper() == "PASS":
        return "NOISE"

    text = _normalize_text(findings=findings, evidence=evidence)

    if any(keyword in text for keyword in _INFRA_KEYWORDS):
        return "INFRA"
    if any(keyword in text for keyword in _EVIDENCE_GAP_KEYWORDS):
        return "EVIDENCE_GAP"
    if any(keyword in text for keyword in _NOISE_KEYWORDS):
        return "NOISE"
    return "CODE_DEFECT"


def ensure_result_category(result: dict[str, object]) -> IssueCategory:
    category = result.get("category")
    if isinstance(category, str):
        normalized = category.upper()
        if normalized in VALID_ISSUE_CATEGORIES:
            result["category"] = normalized
            return normalized  # type: ignore[return-value]

    verdict = str(result.get("verdict", "")).upper()
    findings = [str(item) for item in result.get("findings", []) if isinstance(item, str)]
    evidence = str(result.get("evidence", ""))
    computed = classify_validation_result(verdict=verdict, findings=findings, evidence=evidence)
    result["category"] = computed
    return computed
