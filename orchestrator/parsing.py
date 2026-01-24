from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import VERIFICATION_POLICY_FILE
from .file_ops import _append_log_line, _read_text, _rel_path, _require_file

_REPORT_ITERATION_RE = re.compile(r"^\s*iteration:\s*(\d+)\s*$", re.IGNORECASE | re.MULTILINE)
_COVERAGE_LINE_RE = re.compile(r"^\s*coverage:\s*([0-9]+(?:\.[0-9]+)?)%\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class ReportRules:
    apply_to: set[str]
    require_verdict: bool
    verdict_prefix: str
    verdict_allowed: set[str]
    blocker_prefix: str
    blocker_clear_value: str


@dataclass(frozen=True)
class ParsingRules:
    critical_fields: set[str]
    optional_fields: set[str]
    use_defaults_on_failure: bool


_DEFAULT_PARSING_RULES = ParsingRules(
    critical_fields={"iteration"},
    optional_fields={"verdict", "blockers"},
    use_defaults_on_failure=True,
)


def _log_parse_warning(*, field: str, detail: str, default: Any, source: Path | None = None) -> None:
    location = _rel_path(source) if source is not None else "(unknown)"
    _append_log_line(
        "orchestrator: WARN - "
        f"parse {field} failed at {location}: {detail}; default={default!r}\n"
    )


def _load_verification_policy() -> dict[str, object]:
    _require_file(VERIFICATION_POLICY_FILE)
    raw = _read_text(VERIFICATION_POLICY_FILE).strip()
    if not raw:
        raise ValueError("verification_policy.json is empty")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("verification_policy.json must be a JSON object")
    return payload


def parse_parsing_rules(*, payload: dict[str, object] | None = None) -> ParsingRules:
    if payload is None:
        payload = _load_verification_policy()
    raw_rules = payload.get("parsing_rules")
    if raw_rules is None:
        return _DEFAULT_PARSING_RULES
    if not isinstance(raw_rules, dict):
        raise ValueError("verification_policy.parsing_rules must be an object")

    def _parse_field_list(name: str) -> set[str]:
        value = raw_rules.get(name)
        if not isinstance(value, list) or not value:
            raise ValueError(f"verification_policy.parsing_rules.{name} must be a non-empty list")
        parsed: set[str] = set()
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"verification_policy.parsing_rules.{name} entries must be non-empty strings")
            parsed.add(item.strip())
        return parsed

    critical_fields = _parse_field_list("critical_fields")
    optional_fields = _parse_field_list("optional_fields")
    use_defaults = raw_rules.get("use_defaults_on_failure")
    if not isinstance(use_defaults, bool):
        raise ValueError("verification_policy.parsing_rules.use_defaults_on_failure must be boolean")

    if "iteration" not in critical_fields:
        raise ValueError("verification_policy.parsing_rules.critical_fields must include 'iteration'")
    overlap = critical_fields & optional_fields
    if overlap:
        raise ValueError(f"verification_policy.parsing_rules fields overlap: {sorted(overlap)}")

    return ParsingRules(
        critical_fields=critical_fields,
        optional_fields=optional_fields,
        use_defaults_on_failure=use_defaults,
    )


def parse_report_rules(*, payload: dict[str, object] | None = None) -> ReportRules:
    if payload is None:
        payload = _load_verification_policy()
    rules = payload.get("report_rules")
    if not isinstance(rules, dict):
        raise ValueError("verification_policy.report_rules must be an object")
    apply_to = rules.get("apply_to")
    if not isinstance(apply_to, list) or not apply_to:
        raise ValueError("verification_policy.report_rules.apply_to must be a non-empty list")
    apply_to_set: set[str] = set()
    for item in apply_to:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("verification_policy.report_rules.apply_to entries must be strings")
        apply_to_set.add(item.strip())
    require_verdict = rules.get("require_verdict")
    if not isinstance(require_verdict, bool):
        raise ValueError("verification_policy.report_rules.require_verdict must be boolean")
    verdict_prefix = rules.get("verdict_prefix")
    if not isinstance(verdict_prefix, str) or not verdict_prefix.strip():
        raise ValueError("verification_policy.report_rules.verdict_prefix must be a non-empty string")
    verdict_allowed = rules.get("verdict_allowed")
    if not isinstance(verdict_allowed, list) or not verdict_allowed:
        raise ValueError("verification_policy.report_rules.verdict_allowed must be a non-empty list")
    verdict_allowed_set: set[str] = set()
    for item in verdict_allowed:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("verification_policy.report_rules.verdict_allowed entries must be strings")
        verdict_allowed_set.add(item.strip())
    blocker_prefix = rules.get("blocker_prefix")
    if not isinstance(blocker_prefix, str) or not blocker_prefix.strip():
        raise ValueError("verification_policy.report_rules.blocker_prefix must be a non-empty string")
    blocker_clear_value = rules.get("blocker_clear_value")
    if not isinstance(blocker_clear_value, str) or not blocker_clear_value.strip():
        raise ValueError("verification_policy.report_rules.blocker_clear_value must be a non-empty string")
    return ReportRules(
        apply_to=apply_to_set,
        require_verdict=require_verdict,
        verdict_prefix=verdict_prefix.strip(),
        verdict_allowed=verdict_allowed_set,
        blocker_prefix=blocker_prefix.strip(),
        blocker_clear_value=blocker_clear_value.strip(),
    )


def _is_required(field_name: str, parsing_rules: ParsingRules) -> bool:
    if field_name in parsing_rules.critical_fields:
        return True
    if field_name in parsing_rules.optional_fields:
        return not parsing_rules.use_defaults_on_failure
    raise ValueError(f"Unknown parsing field: {field_name!r}")


def extract_report_iteration(
    *,
    report_text: str,
    parsing_rules: ParsingRules | None = None,
) -> int:
    if parsing_rules is None:
        parsing_rules = parse_parsing_rules()
    if not _is_required("iteration", parsing_rules):
        raise ValueError("iteration must be a critical parsing field")
    match = _REPORT_ITERATION_RE.search(report_text)
    if not match:
        raise RuntimeError("report missing iteration line")
    return int(match.group(1))


def extract_report_verdict(
    *,
    report_text: str,
    report_rules: ReportRules | None = None,
    parsing_rules: ParsingRules | None = None,
    source: Path | None = None,
) -> str | None:
    if report_rules is None:
        report_rules = parse_report_rules()
    if not report_rules.require_verdict:
        return None
    if parsing_rules is None:
        parsing_rules = parse_parsing_rules()
    required = _is_required("verdict", parsing_rules)

    for line in report_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(report_rules.verdict_prefix):
            verdict = stripped.split(report_rules.verdict_prefix, 1)[1].strip()
            if verdict not in report_rules.verdict_allowed:
                if required:
                    raise RuntimeError(f"Invalid verdict {verdict!r} in report")
                _log_parse_warning(
                    field="verdict",
                    detail=f"invalid value {verdict!r}",
                    default=None,
                    source=source,
                )
                return None
            return verdict

    if required:
        raise RuntimeError(f"report missing verdict line {report_rules.verdict_prefix!r}")
    _log_parse_warning(
        field="verdict",
        detail=f"missing prefix {report_rules.verdict_prefix!r}",
        default=None,
        source=source,
    )
    return None


def extract_report_blockers(
    *,
    report_text: str,
    report_rules: ReportRules | None = None,
    parsing_rules: ParsingRules | None = None,
    source: Path | None = None,
) -> list[str]:
    if report_rules is None:
        report_rules = parse_report_rules()
    if parsing_rules is None:
        parsing_rules = parse_parsing_rules()
    required = _is_required("blockers", parsing_rules)

    for line in report_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(report_rules.blocker_prefix):
            blocker_text = stripped.split(report_rules.blocker_prefix, 1)[1].strip()
            if blocker_text == report_rules.blocker_clear_value:
                return []
            return [blocker_text]

    if required:
        raise RuntimeError(f"report missing blocker line {report_rules.blocker_prefix!r}")
    _log_parse_warning(
        field="blockers",
        detail=f"missing prefix {report_rules.blocker_prefix!r}",
        default=[],
        source=source,
    )
    return []


def extract_report_coverage_percent(*, report_text: str) -> float | None:
    for line in report_text.splitlines():
        match = _COVERAGE_LINE_RE.match(line)
        if match:
            return float(match.group(1))
    return None
