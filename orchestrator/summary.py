from __future__ import annotations

import json

from pathlib import Path

from .decision import _load_json_object, _parse_main_decision_payload
from .file_ops import _rel_path
from .types import IterationSummary, ProgressInfo, SubagentSummary, SummaryStep

_ALLOWED_ACTORS = {"MAIN", "ORCHESTRATOR", "TEST", "DEV", "REVIEW"}


def _parse_progress(payload: object) -> ProgressInfo | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("摘要 progress 必须是对象或 null")

    def _require_int(name: str) -> int:
        value = payload.get(name)
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"摘要 progress.{name} 必须为非负整数")
        return value

    def _require_float(name: str) -> float:
        value = payload.get(name)
        if not isinstance(value, (int, float)):
            raise ValueError(f"摘要 progress.{name} 必须为数字")
        if not (0 <= float(value) <= 100):
            raise ValueError(f"摘要 progress.{name} 必须在 0-100 之间")
        return float(value)

    total_tasks = _require_int("total_tasks")
    completed_tasks = _require_int("completed_tasks")
    verified_tasks = _require_int("verified_tasks")
    in_progress_tasks = _require_int("in_progress_tasks")
    blocked_tasks = _require_int("blocked_tasks")
    todo_tasks = _require_int("todo_tasks")
    completion_percentage = _require_float("completion_percentage")
    verification_percentage = _require_float("verification_percentage")

    current_milestone = payload.get("current_milestone")
    if current_milestone is not None:
        if not isinstance(current_milestone, str) or not current_milestone.strip():
            raise ValueError("摘要 progress.current_milestone 必须为非空字符串或 null")

    milestones_payload = payload.get("milestones")
    if not isinstance(milestones_payload, list):
        raise ValueError("摘要 progress.milestones 必须是数组")
    milestones = []
    for idx, item in enumerate(milestones_payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"摘要 progress.milestones[{idx}] 必须是对象")
        milestone_id = item.get("milestone_id")
        milestone_name = item.get("milestone_name")
        if not isinstance(milestone_id, str) or not milestone_id.strip():
            raise ValueError(f"摘要 progress.milestones[{idx}].milestone_id 必须为非空字符串")
        if not isinstance(milestone_name, str) or not milestone_name.strip():
            raise ValueError(f"摘要 progress.milestones[{idx}].milestone_name 必须为非空字符串")
        total = item.get("total_tasks")
        completed = item.get("completed_tasks")
        verified = item.get("verified_tasks")
        percentage = item.get("percentage")
        if not isinstance(total, int) or total < 0:
            raise ValueError(f"摘要 progress.milestones[{idx}].total_tasks 必须为非负整数")
        if not isinstance(completed, int) or completed < 0:
            raise ValueError(f"摘要 progress.milestones[{idx}].completed_tasks 必须为非负整数")
        if not isinstance(verified, int) or verified < 0:
            raise ValueError(f"摘要 progress.milestones[{idx}].verified_tasks 必须为非负整数")
        if not isinstance(percentage, (int, float)) or not (0 <= float(percentage) <= 100):
            raise ValueError(f"摘要 progress.milestones[{idx}].percentage 必须在 0-100 之间")
        milestones.append(
            {
                "milestone_id": milestone_id.strip(),
                "milestone_name": milestone_name.strip(),
                "total_tasks": total,
                "completed_tasks": completed,
                "verified_tasks": verified,
                "percentage": float(percentage),
            }
        )

    if total_tasks == 0 and any(
        value != 0
        for value in (completed_tasks, verified_tasks, in_progress_tasks, blocked_tasks, todo_tasks)
    ):
        raise ValueError("摘要 progress total_tasks=0 但其他计数非 0")
    if completed_tasks > total_tasks or verified_tasks > total_tasks:
        raise ValueError("摘要 progress 计数超过 total_tasks")

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "verified_tasks": verified_tasks,
        "in_progress_tasks": in_progress_tasks,
        "blocked_tasks": blocked_tasks,
        "todo_tasks": todo_tasks,
        "completion_percentage": completion_percentage,
        "verification_percentage": verification_percentage,
        "current_milestone": current_milestone.strip() if isinstance(current_milestone, str) else None,
        "milestones": milestones,
    }


def _parse_iteration_summary(
    raw_json: str,
    *,
    iteration: int,
    expected_agent: str,
    main_session_id: str | None,
    subagent_session_id: str,
    main_decision_file: Path,
    task_file: Path,
    report_file: Path,
    summary_file: Path,
) -> IterationSummary:
    payload = _load_json_object(raw_json)  # 关键变量：解析 JSON

    summary_iteration = payload.get("iteration")
    if not isinstance(summary_iteration, int) or summary_iteration != iteration:
        raise ValueError(f"摘要 iteration 无效：期望 {iteration}，实际 {summary_iteration!r}")

    summary_main_session_id = payload.get("main_session_id")
    if main_session_id is None:
        if summary_main_session_id is not None:
            raise ValueError("当 main_session_id 未知时，摘要 main_session_id 必须为 null")
    else:
        if summary_main_session_id != main_session_id:
            raise ValueError(
                "摘要 main_session_id 不匹配："
                f"期望 {main_session_id!r}，实际 {summary_main_session_id!r}"
            )

    summary_sub_session_id = payload.get("subagent_session_id")
    if summary_sub_session_id != subagent_session_id:
        raise ValueError(
            "摘要 subagent_session_id 不匹配："
            f"期望 {subagent_session_id!r}，实际 {summary_sub_session_id!r}"
        )

    decision_payload = payload.get("main_decision")
    if not isinstance(decision_payload, dict):
        raise ValueError("摘要 main_decision 必须是对象")
    main_decision = _parse_main_decision_payload(decision_payload)
    if main_decision["next_agent"] != expected_agent:
        raise ValueError(
            "摘要 main_decision.next_agent 不匹配："
            f"期望 {expected_agent!r}，实际 {main_decision['next_agent']!r}"
        )

    subagent_payload = payload.get("subagent")
    if not isinstance(subagent_payload, dict):
        raise ValueError("摘要 subagent 必须是对象")
    subagent_name = subagent_payload.get("agent")
    if not isinstance(subagent_name, str) or not subagent_name.strip():
        raise ValueError("摘要 subagent.agent 必须为非空字符串")
    if subagent_name != expected_agent:
        raise ValueError(
            "摘要 subagent.agent 不匹配："
            f"期望 {expected_agent!r}，实际 {subagent_name!r}"
        )
    task_summary = subagent_payload.get("task_summary")
    if not isinstance(task_summary, str) or not task_summary.strip():
        raise ValueError("摘要 subagent.task_summary 必须为非空字符串")
    report_summary = subagent_payload.get("report_summary")
    if not isinstance(report_summary, str) or not report_summary.strip():
        raise ValueError("摘要 subagent.report_summary 必须为非空字符串")
    subagent: SubagentSummary = {
        "agent": subagent_name,
        "task_summary": task_summary.strip(),
        "report_summary": report_summary.strip(),
    }

    steps_payload = payload.get("steps")
    if not isinstance(steps_payload, list) or not (3 <= len(steps_payload) <= 8):
        actual_len = len(steps_payload) if isinstance(steps_payload, list) else "非列表"
        raise ValueError(
            f"摘要 steps 必须是长度 3-8 的列表（实际长度：{actual_len}）。"
            "请确保 steps 是独立对象组成的数组，例如：[{\"step\":1,...},{\"step\":2,...}]，"
            "而不是将多个 step 合并到一个对象中。"
        )
    steps: list[SummaryStep] = []
    for idx, item in enumerate(steps_payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"摘要 steps[{idx}] 必须是对象")
        step_no = item.get("step")
        actor = item.get("actor")
        detail = item.get("detail")
        if not isinstance(step_no, int) or step_no < 1:
            raise ValueError(f"摘要 steps[{idx}].step 必须为正整数")
        if not isinstance(actor, str) or actor not in _ALLOWED_ACTORS:
            raise ValueError(f"摘要 steps[{idx}].actor 非法：{actor!r}")
        if not isinstance(detail, str) or not detail.strip():
            raise ValueError(f"摘要 steps[{idx}].detail 必须为非空字符串")
        steps.append({"step": step_no, "actor": actor, "detail": detail.strip()})

    summary_text = payload.get("summary")
    if not isinstance(summary_text, str) or not summary_text.strip():
        raise ValueError("摘要 summary 必须为非空字符串")

    progress = _parse_progress(payload.get("progress"))

    artifacts_payload = payload.get("artifacts")
    if not isinstance(artifacts_payload, dict):
        raise ValueError("摘要 artifacts 必须是对象")

    expected_artifacts = {
        "main_decision_file": _rel_path(main_decision_file),
        "task_file": _rel_path(task_file),
        "report_file": _rel_path(report_file),
        "summary_file": _rel_path(summary_file),
    }
    for key, expected in expected_artifacts.items():
        actual = artifacts_payload.get(key)
        if actual != expected:
            raise ValueError(f"摘要 artifacts.{key} 不匹配：期望 {expected!r}，实际 {actual!r}")

    return {
        "iteration": summary_iteration,
        "main_session_id": summary_main_session_id,
        "subagent_session_id": summary_sub_session_id,
        "main_decision": main_decision,
        "subagent": subagent,
        "steps": steps,
        "summary": summary_text.strip(),
        "progress": progress,
        "artifacts": expected_artifacts,
    }



def _load_iteration_summary_history(history_file: Path) -> list[IterationSummary]:
    if not history_file.exists():  # 关键分支：文件不存在视为无历史
        return []
    raw = history_file.read_text(encoding="utf-8")  # 关键变量：历史文件内容
    if not raw.strip():  # 关键分支：空文件直接失败
        raise ValueError(f"摘要历史文件为空：{_rel_path(history_file)}")

    history: list[IterationSummary] = []  # 关键变量：摘要历史列表
    for idx, line in enumerate(raw.splitlines(), start=1):  # 关键分支：逐行解析 JSONL
        if not line.strip():  # 关键分支：空行直接失败
            raise ValueError(f"摘要历史第 {idx} 行为空：{_rel_path(history_file)}")
        try:  # 关键分支：解析 JSON
            payload = json.loads(line)
        except json.JSONDecodeError as exc:  # 关键分支：非法 JSON
            raise ValueError(
                f"摘要历史 JSON 解析失败：{_rel_path(history_file)} line={idx}: {exc}"
            ) from exc
        if not isinstance(payload, dict):  # 关键分支：必须为对象
            raise ValueError(f"摘要历史第 {idx} 行必须是对象")
        iteration = payload.get("iteration")
        if not isinstance(iteration, int):  # 关键分支：缺少 iteration 直接失败
            raise ValueError(f"摘要历史第 {idx} 行缺少 iteration")
        history.append(payload)
    return history


def _append_iteration_summary_history(
    *,
    history_file: Path,
    summary: IterationSummary,
) -> list[IterationSummary]:
    history = _load_iteration_summary_history(history_file)  # 关键变量：现有历史
    if history:  # 关键分支：避免重复迭代写入
        last_iteration = history[-1]["iteration"]
        if last_iteration == summary["iteration"]:
            raise ValueError(f"摘要历史已包含 iteration {summary['iteration']}")
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with history_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    history.append(summary)
    return history
