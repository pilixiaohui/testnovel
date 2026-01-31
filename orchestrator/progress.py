from __future__ import annotations

import re
from pathlib import Path

from .config import DEV_PLAN_FILE
from .file_ops import _read_text, _require_file
from .types import MilestoneProgress, ProgressInfo, TaskProgress

_TASK_HEADER_RE = re.compile(r"^###\s+([^:]+):\s*(.*)$")
_TASK_ID_RE = re.compile(r"^(M\d+)-T\d+$")
_STATUS_RE = re.compile(r"^\s*(?:-\s*)?status:\s*([A-Z]+)\s*$")
# 支持两种格式：
# - "## Milestone M1: 标题" (完整格式)
# - "## M1: 标题" (简写格式)
_MILESTONE_HEADER_RE = re.compile(r"^##\s+(?:Milestone\s+)?(M\d+):\s*(.*)$")
_ALLOWED_STATUSES = {"TODO", "DOING", "BLOCKED", "DONE", "VERIFIED"}


def _parse_dev_plan_progress(*, text: str) -> ProgressInfo:
    lines = text.splitlines()
    milestone_names: dict[str, str] = {}
    milestone_order: list[str] = []

    task_items: list[TaskProgress] = []

    current_task_id: str | None = None
    current_status: str | None = None
    current_milestone: str | None = None
    current_task_title: str | None = None

    for line in lines:
        milestone_match = _MILESTONE_HEADER_RE.match(line)
        if milestone_match:
            milestone_id = milestone_match.group(1).strip()
            milestone_name = milestone_match.group(2).strip()
            milestone_names[milestone_id] = milestone_name
            if milestone_id not in milestone_order:
                milestone_order.append(milestone_id)
            continue

        header = _TASK_HEADER_RE.match(line)
        if header:
            if current_task_id is not None:
                if current_status is None:
                    raise RuntimeError(f"dev_plan task {current_task_id} missing status")
                if current_milestone is None:
                    raise RuntimeError(f"dev_plan task {current_task_id} missing milestone")
                if current_task_title is None or not current_task_title.strip():
                    raise RuntimeError(f"dev_plan task {current_task_id} missing title")
                task_items.append(
                    {
                        "task_id": current_task_id,
                        "title": current_task_title.strip(),
                        "status": current_status,
                        "milestone_id": current_milestone,
                    }
                )

            current_task_id = header.group(1).strip()
            current_status = None
            if current_task_id is None:
                raise RuntimeError("dev_plan task id is None")
            id_match = _TASK_ID_RE.match(current_task_id)
            if not id_match:
                raise RuntimeError(f"dev_plan task id invalid: {current_task_id}")
            current_milestone = id_match.group(1)
            current_task_title = header.group(2).strip()
            if not current_task_title:
                raise RuntimeError(f"dev_plan task {current_task_id} missing title")
            continue

        status_match = _STATUS_RE.match(line)
        if status_match and current_task_id is not None:
            status = status_match.group(1).strip()
            if status not in _ALLOWED_STATUSES:
                raise RuntimeError(f"dev_plan task {current_task_id} status invalid: {status}")
            current_status = status

    if current_task_id is not None:
        if current_status is None:
            raise RuntimeError(f"dev_plan task {current_task_id} missing status")
        if current_milestone is None:
            raise RuntimeError(f"dev_plan task {current_task_id} missing milestone")
        if current_task_title is None or not current_task_title.strip():
            raise RuntimeError(f"dev_plan task {current_task_id} missing title")
        task_items.append(
            {
                "task_id": current_task_id,
                "title": current_task_title.strip(),
                "status": current_status,
                "milestone_id": current_milestone,
            }
        )

    counts = {"TODO": 0, "DOING": 0, "BLOCKED": 0, "DONE": 0, "VERIFIED": 0}
    for item in task_items:
        counts[item["status"]] += 1

    total_tasks = sum(counts.values())
    completed_tasks = counts["DONE"] + counts["VERIFIED"]
    verified_tasks = counts["VERIFIED"]
    in_progress_tasks = counts["DOING"]
    blocked_tasks = counts["BLOCKED"]
    todo_tasks = counts["TODO"]

    completion_percentage = 0.0
    verification_percentage = 0.0
    if total_tasks > 0:
        completion_percentage = completed_tasks / total_tasks * 100
        verification_percentage = verified_tasks / total_tasks * 100

    milestone_stats: dict[str, dict[str, int]] = {}
    for item in task_items:
        milestone_id = item["milestone_id"]
        milestone_stats.setdefault(
            milestone_id,
            {"total": 0, "completed": 0, "verified": 0},
        )
        milestone_stats[milestone_id]["total"] += 1
        if item["status"] in {"DONE", "VERIFIED"}:
            milestone_stats[milestone_id]["completed"] += 1
        if item["status"] == "VERIFIED":
            milestone_stats[milestone_id]["verified"] += 1

    milestones: list[MilestoneProgress] = []
    for milestone_id in milestone_order:
        if milestone_id not in milestone_names:
            raise RuntimeError(f"dev_plan milestone missing header: {milestone_id}")
        stats = milestone_stats.get(milestone_id, {"total": 0, "completed": 0, "verified": 0})
        total = stats["total"]
        percentage = (stats["completed"] / total * 100) if total > 0 else 0.0
        milestones.append(
            {
                "milestone_id": milestone_id,
                "milestone_name": milestone_names[milestone_id],
                "total_tasks": total,
                "completed_tasks": stats["completed"],
                "verified_tasks": stats["verified"],
                "percentage": percentage,
            }
        )

    current_milestone = None
    for milestone in milestones:
        if milestone["total_tasks"] == 0:
            continue
        if milestone["percentage"] < 100:
            current_milestone = milestone["milestone_id"]
            break

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "verified_tasks": verified_tasks,
        "in_progress_tasks": in_progress_tasks,
        "blocked_tasks": blocked_tasks,
        "todo_tasks": todo_tasks,
        "completion_percentage": round(completion_percentage, 1),
        "verification_percentage": round(verification_percentage, 1),
        "current_milestone": current_milestone,
        "milestones": milestones,
        "tasks": task_items,
    }


def get_progress_info(*, dev_plan_path: Path = DEV_PLAN_FILE) -> ProgressInfo:
    _require_file(dev_plan_path)
    text = _read_text(dev_plan_path)
    return _parse_dev_plan_progress(text=text)
