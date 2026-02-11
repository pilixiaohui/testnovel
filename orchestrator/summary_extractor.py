from __future__ import annotations

import json
import re

from datetime import datetime
from pathlib import Path

from .config import REPORT_SUMMARY_CACHE_FILE
from .file_ops import _append_log_line, _atomic_write_text, _read_text, _rel_path, _require_file
from .types import ReportSummary
from .parsing import (
    extract_report_blockers,
    extract_report_iteration,
    extract_report_verdict,
    parse_parsing_rules,
    parse_report_rules,
)

_SUMMARY_SCHEMA_VERSION = 1  # 关键变量：摘要缓存版本
_MAX_EVIDENCE_CHARS = 200  # 关键变量：证据摘要长度上限
_MAX_KEY_CHANGES = 8  # 关键变量：关键变更最大条目数

_FILE_REF_RE = re.compile(r"([\w./-]+:\d+)")
_MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*(.+?)\s*$")
_BOLD_HEADING_RE = re.compile(r"^\s*(?:\*\*|__)(.+?)(?:\*\*|__)\s*$")
_BRACKET_HEADING_RE = re.compile(r"^\s*[【\[](.+?)[】\]]\s*$")
_BULLET_PREFIX_RE = re.compile(r"^[-*+]\s+")
_ORDERED_LIST_PREFIX_RE = re.compile(r"^\d+[.)]\s+")

_EVIDENCE_HEADINGS: dict[str, tuple[str, ...]] = {
    "IMPLEMENTER": ("结果", "自测", "执行命令", "研判"),
    "FINISH_REVIEW": ("问题清单", "差距清单", "证据"),
}


def _load_summary_cache() -> dict[str, object]:
    if not REPORT_SUMMARY_CACHE_FILE.exists():
        return {"schema_version": _SUMMARY_SCHEMA_VERSION, "summaries": {}}
    raw = _read_text(REPORT_SUMMARY_CACHE_FILE).strip()
    if not raw:
        raise ValueError(f"summary cache is empty: {_rel_path(REPORT_SUMMARY_CACHE_FILE)}")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("summary cache must be a JSON object")
    schema_version = payload.get("schema_version")
    if schema_version != _SUMMARY_SCHEMA_VERSION:
        raise ValueError(
            f"summary cache schema_version mismatch: {schema_version!r} != {_SUMMARY_SCHEMA_VERSION}"
        )
    summaries = payload.get("summaries")
    if not isinstance(summaries, dict):
        raise ValueError("summary cache summaries must be an object")
    return payload


def _save_summary_cache(cache: dict[str, object]) -> None:
    REPORT_SUMMARY_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(
        REPORT_SUMMARY_CACHE_FILE,
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
    )


def _get_cached_summary(cache: dict[str, object], *, rel_path: str, mtime: float) -> ReportSummary | None:
    summaries = cache.get("summaries")
    if not isinstance(summaries, dict):
        raise ValueError("summary cache summaries must be an object")
    entry = summaries.get(rel_path)
    if entry is None:
        return None
    if not isinstance(entry, dict):
        raise ValueError(f"summary cache entry invalid for {rel_path}")
    entry_mtime = entry.get("mtime")
    if not isinstance(entry_mtime, (int, float)):
        raise ValueError(f"summary cache entry mtime invalid for {rel_path}")
    if entry_mtime != mtime:
        return None
    summary = entry.get("summary")
    if not isinstance(summary, dict):
        raise ValueError(f"summary cache entry summary invalid for {rel_path}")
    return summary


def _set_cached_summary(
    cache: dict[str, object],
    *,
    rel_path: str,
    mtime: float,
    summary: ReportSummary,
) -> None:
    summaries = cache.get("summaries")
    if not isinstance(summaries, dict):
        raise ValueError("summary cache summaries must be an object")
    summaries[rel_path] = {"mtime": mtime, "summary": summary}


def _extract_key_changes(lines: list[str]) -> list[str]:
    matches: list[str] = []
    for line in lines:
        for match in _FILE_REF_RE.findall(line):
            matches.append(match)
    seen: set[str] = set()
    ordered: list[str] = []
    for item in matches:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
        if len(ordered) >= _MAX_KEY_CHANGES:
            break
    return ordered


def _strip_list_prefix(line: str) -> str:
    stripped = line.strip()
    stripped = _BULLET_PREFIX_RE.sub("", stripped)
    stripped = _ORDERED_LIST_PREFIX_RE.sub("", stripped)
    return stripped


def _extract_inline_evidence(line: str, *, headings: tuple[str, ...]) -> str:
    stripped = _strip_list_prefix(line)
    for sep in ("：", ":"):
        if sep not in stripped:
            continue
        before, after = stripped.split(sep, 1)
        if any(keyword in before for keyword in headings):
            evidence = after.strip()
            if evidence:
                return evidence
    return ""


def _extract_heading_title(line: str, *, headings: tuple[str, ...]) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    match = _MARKDOWN_HEADING_RE.match(stripped)
    if match:
        return match.group(1).strip()
    match = _BOLD_HEADING_RE.match(stripped)
    if match:
        return match.group(1).strip()
    match = _BRACKET_HEADING_RE.match(stripped)
    if match:
        return match.group(1).strip()
    if stripped in headings:
        return stripped
    return None


def _is_heading_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _MARKDOWN_HEADING_RE.match(stripped):
        return True
    if _BOLD_HEADING_RE.match(stripped):
        return True
    if _BRACKET_HEADING_RE.match(stripped):
        return True
    return False


def _extract_evidence(lines: list[str], *, agent: str) -> str:
    headings = _EVIDENCE_HEADINGS.get(agent, ())
    if not headings:
        return ""
    for idx, line in enumerate(lines):
        inline = _extract_inline_evidence(line, headings=headings)
        if inline:
            return inline
        title = _extract_heading_title(line, headings=headings)
        if not title:
            continue
        if not any(keyword in title for keyword in headings):
            continue
        for j in range(idx + 1, len(lines)):
            candidate = lines[j].strip()
            if not candidate:
                continue
            if _is_heading_line(candidate):
                break
            candidate = _strip_list_prefix(candidate)
            if candidate:
                return candidate
    return ""


def extract_report_summary(
    *, report_path: Path, agent: str, force_refresh: bool = False
) -> ReportSummary:
    _require_file(report_path)
    raw = _read_text(report_path)

    cache = _load_summary_cache()
    rel_path = _rel_path(report_path)
    mtime = report_path.stat().st_mtime
    if not force_refresh:
        cached = _get_cached_summary(cache, rel_path=rel_path, mtime=mtime)
        if cached is not None:
            return cached  # type: ignore[return-value]

    parsing_rules = parse_parsing_rules()
    report_rules = parse_report_rules()

    iteration = extract_report_iteration(report_text=raw, parsing_rules=parsing_rules)
    verdict = extract_report_verdict(
        report_text=raw,
        report_rules=report_rules,
        parsing_rules=parsing_rules,
        source=report_path,
    )
    blockers = extract_report_blockers(
        report_text=raw,
        report_rules=report_rules,
        parsing_rules=parsing_rules,
        source=report_path,
    )

    verdict_text = verdict or "N/A"
    lines = raw.splitlines()
    key_changes = _extract_key_changes(lines)
    evidence = _extract_evidence(lines, agent=agent)

    if agent == "FINISH_REVIEW" and not evidence:
        _append_log_line(
            "orchestrator: WARN - "
            f"report missing evidence section for agent {agent} "
            f"at {_rel_path(report_path)}\n"
        )

    timestamp = datetime.fromtimestamp(report_path.stat().st_mtime).isoformat(timespec="seconds")
    summary: ReportSummary = {
        "iteration": iteration,
        "agent": agent,
        "verdict": verdict_text,
        "blockers": blockers,
        "key_changes": key_changes,
        "evidence": evidence,
        "timestamp": timestamp,
    }
    _set_cached_summary(cache, rel_path=rel_path, mtime=mtime, summary=summary)
    _save_summary_cache(cache)
    return summary


def format_report_summary(*, summary: ReportSummary, level: int) -> str:
    if level not in {1, 2}:
        raise ValueError(f"summary level invalid: {level}")
    blockers_text = "无" if not summary["blockers"] else "; ".join(summary["blockers"])
    lines = [
        f"iteration: {summary['iteration']}",
        f"agent: {summary['agent']}",
        f"结论：{summary['verdict']}",
        f"阻塞：{blockers_text}",
    ]

    if level >= 2:
        if summary["key_changes"]:
            lines.append("关键变更：")
            lines.extend([f"- {item}" for item in summary["key_changes"][:_MAX_KEY_CHANGES]])
        if summary["evidence"]:
            lines.append("证据摘要：")
            evidence = summary["evidence"][:_MAX_EVIDENCE_CHARS].rstrip()
            lines.append(evidence)

    return "\n".join(lines)
