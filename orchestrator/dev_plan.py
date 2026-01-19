from __future__ import annotations

import re


_TASK_HEADER_RE = re.compile(r"^###\s+([^:]+):\s*(.*)$")
# NOTE: allow optional leading "-" to reduce brittleness for LLM-written markdown.
_STATUS_RE = re.compile(r"^\s*(?:-\s*)?status:\s*([A-Z]+)\s*$")
_TEST_REQUIRED_RE = re.compile(r"^\s*(?:-\s*)?test_required:\s*(true|false)\s*$", re.IGNORECASE)


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


def find_open_test_required_task_ids(
    dev_plan_text: str,
    *,
    statuses: set[str] | None = None,
) -> list[str]:
    """
    Return task ids that require tests first and are not finished.

    Backward compatible parsing rules:
    - Task blocks start at `### <TASK_ID>: ...`
    - `test_required:` is optional; when present it must be `true|false` (case-insensitive)
    - A task may contain multiple `status:` lines (phase-based format). For deciding whether we still
      need to write tests first, we use the **first** `status:` found in the task block.
      (This matches the extended format where the first phase is typically the test phase.)
    """
    if statuses is None:
        statuses = {"TODO", "DOING", "BLOCKED"}

    lines = dev_plan_text.splitlines()
    matched: list[str] = []

    current_task_id: str | None = None
    first_status: str | None = None
    test_required: bool = False

    def _flush_current() -> None:
        nonlocal current_task_id, first_status, test_required
        if current_task_id is None:
            return
        if first_status is None:
            raise RuntimeError(f"dev_plan task {current_task_id} missing status")
        if test_required and first_status in statuses:
            matched.append(current_task_id)

    for line in lines:
        header = _TASK_HEADER_RE.match(line)
        if header:
            _flush_current()
            current_task_id = header.group(1).strip()
            first_status = None
            test_required = False
            continue

        if current_task_id is None:
            continue

        m_status = _STATUS_RE.match(line)
        if m_status and first_status is None:
            first_status = m_status.group(1).strip()
            continue

        m_req = _TEST_REQUIRED_RE.match(line)
        if m_req:
            test_required = m_req.group(1).lower() == "true"

    _flush_current()
    return matched
