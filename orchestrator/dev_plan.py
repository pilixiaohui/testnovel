from __future__ import annotations

import re
from dataclasses import dataclass


_TASK_HEADER_RE = re.compile(r"^###\s+([^:]+):\s*(.*)$")
_MILESTONE_HEADER_RE = re.compile(r"^##\s+Milestone\s+(\S+):\s*(.*)$")
# NOTE: allow optional leading "-" to reduce brittleness for LLM-written markdown.
_STATUS_RE = re.compile(r"^\s*(?:-\s*)?status:\s*([A-Z]+)\s*$")


def parse_overall_task_statuses(dev_plan_text: str) -> list[tuple[str, str]]:
    """
    Parse `dev_plan.md` and return each task's overall status.

    Overall status rule (backward compatible):
    - For a task block, the overall status is the **last** `status:` line found in that block.
      This supports an extended format where each task may contain multiple phase statuses.
    """
    lines = dev_plan_text.splitlines()
    tasks: list[tuple[str, str]] = []

    current_task_id: str | None = None
    current_status: str | None = None

    for line in lines:
        header = _TASK_HEADER_RE.match(line)
        if header:
            if current_task_id is not None:
                if current_status is None:
                    raise RuntimeError(f"dev_plan task {current_task_id} missing status")
                tasks.append((current_task_id, current_status))
            current_task_id = header.group(1).strip()
            current_status = None
            continue

        m = _STATUS_RE.match(line)
        if m and current_task_id is not None:
            current_status = m.group(1).strip()

    if current_task_id is not None:
        if current_status is None:
            raise RuntimeError(f"dev_plan task {current_task_id} missing status")
        tasks.append((current_task_id, current_status))

    return tasks


def count_overall_task_statuses(
    dev_plan_text: str,
    *,
    known_statuses: set[str] | None = None,
) -> dict[str, int]:
    """
    Count task overall statuses.

    If `known_statuses` is provided, ensure these keys exist in the returned dict.
    """
    tasks = parse_overall_task_statuses(dev_plan_text)
    counts: dict[str, int] = {}
    for _, status in tasks:
        counts[status] = counts.get(status, 0) + 1

    if known_statuses:
        for s in known_statuses:
            counts.setdefault(s, 0)

    return counts


VALID_TRANSITIONS: dict[str, set[str]] = {
    "TODO":     {"DOING", "BLOCKED"},
    "DOING":    {"DONE", "BLOCKED", "TODO"},
    "BLOCKED":  {"DOING", "TODO"},
    "DONE":     {"VERIFIED", "DOING", "BLOCKED"},
    "VERIFIED": set(),
}


def validate_status_transitions(
    *, before_text: str, after_text: str,
) -> list[str]:
    """比较 before/after dev_plan，返回非法转换列表（空=全部合法）。"""
    before_map = dict(parse_overall_task_statuses(before_text))
    after_map = dict(parse_overall_task_statuses(after_text))
    violations: list[str] = []

    for task_id, new_status in after_map.items():
        old_status = before_map.get(task_id)
        if old_status is None:
            if new_status != "TODO":
                violations.append(f"{task_id}: 新任务必须以 TODO 开始，当前为 {new_status}")
            continue
        if old_status == new_status:
            continue
        allowed = VALID_TRANSITIONS.get(old_status, set())
        if new_status not in allowed:
            violations.append(
                f"{task_id}: 非法转换 {old_status} → {new_status}"
                f"（{old_status} 允许: {sorted(allowed) if allowed else '终态不可变'}）"
            )

    for task_id in before_map:
        if task_id not in after_map:
            violations.append(f"{task_id}: 任务被删除（原状态 {before_map[task_id]}）")

    return violations

