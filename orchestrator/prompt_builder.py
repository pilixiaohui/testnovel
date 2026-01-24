from __future__ import annotations

import re

from pathlib import Path

from .config import CONFIG, MIN_HISTORY_WINDOW, PROJECT_HISTORY_FILE, PROMPTS_DIR
from .documents import resolve_uploaded_doc_path
from .file_ops import _read_text, _rel_path, _require_file
from .types import NextAgent
from .dev_plan import parse_overall_task_statuses
from .summary_extractor import extract_report_summary, format_report_summary


def _inject_text(*, path: Path, content: str, note: str | None = None) -> str:
    display = _rel_path(path)  # 关键变量：相对路径展示
    label = f"{display} ({note})" if note else display  # 关键变量：显示标签
    header = f"============= Injected File: {label} ============="  # 关键变量：注入头
    footer = f"============= End Injected File: {label} ============="  # 关键变量：注入尾
    return "\n".join([header, content, footer])


def _inject_file(
    path: Path,
    *,
    level: int = 3,
    use_summary: bool = False,
    agent: str | None = None,
    label_suffix: str = "",
) -> str:
    """
    将文件内容“注入”到提示词中（黑板模式的可观测快照）。
    - 按用户要求：所有代理注入 global_context；MAIN 额外注入 project_history/dev_plan；REVIEW 注入 dev_plan
    - 不做截断/兜底：缺失即报错（快速失败）
    """
    if use_summary:
        if agent is None:
            raise ValueError("agent is required when use_summary=True")
        return _inject_report_with_level(report_path=path, agent=agent, level=level, label_suffix=label_suffix)
    _require_file(path)  # 关键分支：缺文件直接失败
    note = label_suffix.strip() or None
    return _inject_text(path=path, content=_read_text(path).rstrip(), note=note)  # 关键变量：注入文件内容


def _inject_report_with_level(
    *,
    report_path: Path,
    agent: str,
    level: int,
    label_suffix: str = "",
    force_refresh: bool = False,
) -> str:
    if level not in {1, 2, 3}:
        raise ValueError(f"report injection level invalid: {level}")
    if level == 3:
        return _inject_file(report_path, label_suffix=label_suffix)
    summary = extract_report_summary(
        report_path=report_path,
        agent=agent,
        force_refresh=force_refresh,
    )
    content = format_report_summary(summary=summary, level=level)
    note = f"summary L{level}{label_suffix}".strip()
    return _inject_text(path=report_path, content=content, note=note)


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


_ITERATION_HEADER_RE = re.compile(r"^## Iteration (\d+):")
_MILESTONE_MARKER = "[MILESTONE]"
_COMPRESS_KEEP_PREFIXES = (
    "next_agent:",
    "reason:",
    "blockers:",
    "dev_plan:",
    "finish_review_override:",
)
_DOC_REF_RE = re.compile(r"@doc:([\w/\-]+\.md)")


def _parse_history_entries(lines: list[str]) -> tuple[list[str], list[dict[str, object]]]:
    iteration_indices = [idx for idx, line in enumerate(lines) if line.startswith("## Iteration ")]
    if not iteration_indices:
        return lines, []
    header = lines[:iteration_indices[0]]
    entries: list[dict[str, object]] = []
    for pos, start_idx in enumerate(iteration_indices):
        end_idx = iteration_indices[pos + 1] if pos + 1 < len(iteration_indices) else len(lines)
        header_line = lines[start_idx]
        match = _ITERATION_HEADER_RE.match(header_line)
        if not match:
            raise RuntimeError(f"Invalid iteration header line: {header_line!r}")
        iteration = int(match.group(1))
        entries.append(
            {
                "iteration": iteration,
                "lines": lines[start_idx:end_idx],
            }
        )
    return header, entries


def _identify_milestones(entries: list[dict[str, object]]) -> set[int]:
    milestones: set[int] = set()
    for entry in entries:
        iteration = entry.get("iteration")
        lines = entry.get("lines")
        if not isinstance(iteration, int) or not isinstance(lines, list):
            raise RuntimeError("Invalid history entry structure")
        if any(_MILESTONE_MARKER in line for line in lines):
            milestones.add(iteration)
    return milestones


def _compress_history_entry(entry_lines: list[str]) -> list[str]:
    if not entry_lines:
        raise RuntimeError("Empty history entry")
    header = entry_lines[0]
    kept = [header]
    for line in entry_lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(prefix) for prefix in _COMPRESS_KEEP_PREFIXES):
            kept.append(line)
    if len(kept) == 1:
        raise RuntimeError("History entry missing required fields for compression")
    return kept


def _extract_doc_references(text: str) -> list[str]:
    seen: set[str] = set()
    refs: list[str] = []
    for match in _DOC_REF_RE.finditer(text):
        ref = match.group(1)
        if ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
    return refs


def _inject_doc_references(refs: list[str]) -> list[str]:
    injections: list[str] = []
    for ref in refs:
        path = resolve_uploaded_doc_path(ref)
        injections.append(_inject_file(path, label_suffix=f"doc ref: {ref}"))
    return injections


def _inject_project_history_recent(
    *, last_iterations: int, max_tokens: int | None = None, include_milestones: bool = True
) -> str:
    """
    将 `memory/project_history.md` 以“最近 N 轮 iteration”为窗口注入，避免上下文无限膨胀。
    - N 必须 >= 1
    - 若 history 尚无任何 `## Iteration ` 记录，则注入全量文件
    - 注入内容始终包含文件头部（直到首个 Iteration heading 之前）
    - 可选：根据 max_tokens 动态缩小窗口（近似字符/4）
    """
    if last_iterations < 1:  # 关键分支：窗口必须 >= 1
        raise ValueError("last_iterations must be >= 1")

    _require_file(PROJECT_HISTORY_FILE)
    full_text = _read_text(PROJECT_HISTORY_FILE).rstrip()  # 关键变量：历史全文
    lines = full_text.splitlines()  # 关键变量：历史逐行

    header_lines, entries = _parse_history_entries(lines)
    if not entries:  # 关键分支：无迭代则全量注入
        return _inject_text(path=PROJECT_HISTORY_FILE, content=full_text)

    total_entries = len(entries)
    start_idx = max(0, total_entries - last_iterations)
    base_indices = list(range(start_idx, total_entries))
    milestone_iterations = _identify_milestones(entries) if include_milestones else set()
    milestone_indices = [
        idx for idx, entry in enumerate(entries) if entry["iteration"] in milestone_iterations
    ]
    selected_indices = sorted(set(base_indices + milestone_indices))

    def build_trimmed(indices: list[int]) -> str:
        parts: list[str] = []
        if header_lines:
            parts.extend(header_lines)
            parts.append("")
        for idx in indices:
            entry_lines = entries[idx]["lines"]
            if not isinstance(entry_lines, list):
                raise RuntimeError("Invalid history entry lines")
            iteration = entries[idx]["iteration"]
            if not isinstance(iteration, int):
                raise RuntimeError("Invalid history entry iteration")
            if iteration in milestone_iterations:
                parts.extend(entry_lines)
            else:
                parts.extend(_compress_history_entry(entry_lines))
            parts.append("")
        return "\n".join(parts).rstrip()

    trimmed = build_trimmed(selected_indices)
    if max_tokens is not None and max_tokens > 0:
        min_keep = min(total_entries, max(MIN_HISTORY_WINDOW, 1))
        protected_recent = set(range(total_entries - min_keep, total_entries))
        while _approx_tokens(trimmed) > max_tokens:
            removable = [
                idx
                for idx in selected_indices
                if idx not in protected_recent and entries[idx]["iteration"] not in milestone_iterations
            ]
            if not removable:
                raise RuntimeError("History window exceeds max_tokens and cannot be reduced further")
            selected_indices.remove(removable[0])
            trimmed = build_trimmed(selected_indices)

    milestone_count = len(milestone_indices) if include_milestones else 0
    note = f"last {len(base_indices)} iterations + {milestone_count} milestones"
    return _inject_text(path=PROJECT_HISTORY_FILE, content=trimmed, note=note)


def _load_system_prompt(agent_name: str) -> str:
    path = PROMPTS_DIR / f"subagent_prompt_{agent_name}.md"  # 关键变量：提示词路径
    _require_file(path)  # 关键分支：提示词必须存在
    content = _read_text(path).strip()  # 关键变量：提示词内容
    if not content:  # 关键分支：空提示词直接失败
        raise ValueError(f"Empty prompt file: {path}")
    return content


def _task_file_for_agent(agent: NextAgent) -> Path:
    if agent in {"TEST", "DEV", "REVIEW"}:  # 关键分支：子代理工单
        return CONFIG.get_task_file(agent)
    if agent == "USER":  # 关键分支：USER 无工单
        raise ValueError("USER is not a sub-agent and has no task file")
    if agent == "FINISH":  # 关键分支：FINISH 无工单
        raise ValueError("FINISH is not a sub-agent and has no task file")
    raise ValueError(f"No task file for agent: {agent!r}")


def _summarize_dev_plan_status(dev_plan_text: str) -> str:
    """
    从 dev_plan 中提取任务状态摘要，用于 FINISH_CHECK 场景。
    返回格式：每个任务一行，包含任务 ID 和状态。
    """
    try:
        tasks = parse_overall_task_statuses(dev_plan_text)
    except RuntimeError:
        return "(无法解析任务状态)"
    if not tasks:
        return "(无法解析任务状态)"
    return "\n".join([f"- {task_id}: {status}" for task_id, status in tasks])


def _extract_finish_review_verdict(finish_review_text: str) -> str:
    """
    从 FINISH_REVIEW 报告中提取关键结论和阻塞项，用于 FINISH_CHECK 场景。
    """
    lines = finish_review_text.splitlines()
    extracted: list[str] = []
    in_problem_section = False
    in_blocker_section = False
    problem_lines: list[str] = []
    blocker_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        # 提取结论行
        if stripped.startswith("结论：") or stripped.startswith("结论:"):
            extracted.append(stripped)
        # 提取阻塞行
        elif stripped.startswith("阻塞：") or stripped.startswith("阻塞:"):
            extracted.append(stripped)
        # 提取问题清单标题
        elif stripped.startswith("**问题清单**") or stripped == "问题清单":
            in_problem_section = True
            in_blocker_section = False
        # 提取差距清单标题
        elif stripped.startswith("**差距清单**") or stripped == "差距清单":
            in_problem_section = False
            in_blocker_section = True
        # 其他标题结束当前段落
        elif stripped.startswith("**") and stripped.endswith("**"):
            in_problem_section = False
            in_blocker_section = False
        # 收集问题清单内容（P0/P1 开头的行）
        elif in_problem_section and (stripped.startswith("- P0") or stripped.startswith("- P1")):
            problem_lines.append(stripped)

    # 组装摘要
    result_parts = extracted
    if problem_lines:
        result_parts.append("关键问题：")
        result_parts.extend(problem_lines[:5])  # 最多 5 条
        if len(problem_lines) > 5:
            result_parts.append(f"  ...（共 {len(problem_lines)} 条）")

    if not result_parts:
        return "(无法解析 FINISH_REVIEW 结论)"
    return "\n".join(result_parts)
