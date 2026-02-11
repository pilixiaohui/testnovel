from __future__ import annotations

from typing import Literal, TypedDict

IssueCategory = Literal["CODE_DEFECT", "INFRA", "NOISE", "EVIDENCE_GAP"]
ValidationVerdict = Literal["PASS", "FAIL", "BLOCKED"]
OverallVerdict = Literal["PASS", "REWORK", "BLOCKED"]

VALID_ISSUE_CATEGORIES: tuple[IssueCategory, ...] = (
    "CODE_DEFECT",
    "INFRA",
    "NOISE",
    "EVIDENCE_GAP",
)
VALID_VALIDATION_VERDICTS: tuple[ValidationVerdict, ...] = ("PASS", "FAIL", "BLOCKED")
VALID_OVERALL_VERDICTS: tuple[OverallVerdict, ...] = ("PASS", "REWORK", "BLOCKED")


class ValidationResultContract(TypedDict, total=False):
    validator: str
    iteration: int
    verdict: ValidationVerdict
    category: IssueCategory
    confidence: float
    findings: list[str]
    evidence: str
    duration_ms: int


class SynthesizerOutputContract(TypedDict):
    overall_verdict: OverallVerdict
    decision_basis: list[str]
    blockers: list[str]
    recommendations: list[str]


VALIDATION_RESULT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": [
        "validator",
        "iteration",
        "verdict",
        "category",
        "confidence",
        "findings",
        "evidence",
        "duration_ms",
    ],
    "properties": {
        "validator": {"type": "string", "minLength": 1},
        "iteration": {"type": "integer", "minimum": 1},
        "verdict": {"enum": list(VALID_VALIDATION_VERDICTS)},
        "category": {"enum": list(VALID_ISSUE_CATEGORIES)},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "findings": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "string"},
        "duration_ms": {"type": "integer", "minimum": 0},
    },
}

SYNTHESIZER_OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["overall_verdict", "decision_basis", "blockers", "recommendations"],
    "properties": {
        "overall_verdict": {"enum": list(VALID_OVERALL_VERDICTS)},
        "decision_basis": {"type": "array", "items": {"type": "string"}},
        "blockers": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
}
