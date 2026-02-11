from __future__ import annotations

import json

from datetime import datetime
from pathlib import Path

from .config import (
    USER_INSIGHT_REPORT_FILE,
    USER_INSIGHT_HISTORY_FILE,
    ENABLE_BEHAVIOR_AUDIT,
)
from .decision import _load_json_object, _parse_main_decision_payload
from .file_ops import _rel_path, _append_log_line, _atomic_write_text
from .types import IterationSummary, ProgressInfo, SubagentSummary, SummaryStep

# Context-centric 架构：IMPLEMENTER 合并原 TEST+DEV，FINISH_REVIEW 为最终审阅
_ALLOWED_ACTORS = {"MAIN", "ORCHESTRATOR", "IMPLEMENTER", "FINISH_REVIEW"}


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

    # 解析可选字段：verdict
    verdict = payload.get("verdict")
    if verdict is not None:
        if not isinstance(verdict, str) or verdict not in {"PASS", "FAIL", "BLOCKED"}:
            verdict = None  # 非法值忽略

    # 解析可选字段：key_findings
    key_findings = payload.get("key_findings")
    if key_findings is not None:
        if not isinstance(key_findings, list):
            key_findings = None
        else:
            key_findings = [
                str(item).strip() for item in key_findings
                if isinstance(item, str) and item.strip()
            ][:4]  # 最多 4 条

    # 解析可选字段：changes（仅 IMPLEMENTER 时有意义）
    changes = payload.get("changes")
    if changes is not None:
        if not isinstance(changes, dict):
            changes = None
        else:
            parsed_changes = {}
            files_modified = changes.get("files_modified")
            if isinstance(files_modified, list):
                parsed_changes["files_modified"] = [
                    str(f).strip() for f in files_modified if isinstance(f, str)
                ]
            tests_passed = changes.get("tests_passed")
            if isinstance(tests_passed, bool):
                parsed_changes["tests_passed"] = tests_passed
            coverage = changes.get("coverage")
            if isinstance(coverage, (int, float)) and 0 <= coverage <= 100:
                parsed_changes["coverage"] = float(coverage)
            changes = parsed_changes if parsed_changes else None

    result: dict = {
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

    # 添加可选字段（仅当有值时）
    if verdict is not None:
        result["verdict"] = verdict
    if key_findings:
        result["key_findings"] = key_findings
    if changes:
        result["changes"] = changes

    # 解析并保留 user_insight 字段（可选）
    user_insight = _parse_user_insight(payload)
    if user_insight:
        result["user_insight"] = user_insight

    return result



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
    history_file.parent.mkdir(parents=True, exist_ok=True)

    if history and history[-1]["iteration"] == summary["iteration"]:
        # 同一迭代重试时覆盖最后一条，避免异步重试导致 history 断裂
        history[-1] = summary
        payload = "\n".join(json.dumps(item, ensure_ascii=False) for item in history) + "\n"
        _atomic_write_text(history_file, payload)
        return history

    with history_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    history.append(summary)
    return history


# ============= 用户洞察报告生成 =============


def _generate_user_insight_report(
    *,
    iteration: int,
    summary: IterationSummary,
    user_insight: dict,
) -> None:
    """
    生成面向用户的洞察报告（Markdown 格式）。

    触发时机：SUMMARY 阶段成功完成后
    """
    if not ENABLE_BEHAVIOR_AUDIT:
        return

    timestamp = datetime.now().isoformat(timespec="seconds")
    behavior = user_insight.get("behavior_check", {})
    recommendations = user_insight.get("recommendations", [])

    # 获取代理名称
    subagent_info = summary.get("subagent")
    agent_name = subagent_info.get("agent", "N/A") if isinstance(subagent_info, dict) else "N/A"

    lines = [
        "# 用户洞察报告",
        "",
        f"> 生成时间: {timestamp}",
        f"> 当前迭代: {iteration}",
        f"> 代理: {agent_name}",
        "",
        "## 本轮摘要",
        "",
        str(summary.get("summary", "")),
        "",
        "## 行为合理性检查",
        "",
    ]

    # 任务对齐度
    alignment = behavior.get("task_alignment", {})
    if isinstance(alignment, dict):
        score = alignment.get("score", 0)
        status = alignment.get("status", "unknown")
        detail = alignment.get("detail", "无详情")
        status_icon = "✅" if status == "good" else "⚠️" if status == "attention" else "❌"
        lines.extend([
            f"### 任务对齐度: {status_icon} {status} ({score}%)",
            "",
            f"- {detail}",
            "",
        ])

    # 决策质量
    decision_check = behavior.get("decision_quality", {})
    if isinstance(decision_check, dict):
        status = decision_check.get("status", "unknown")
        status_icon = "✅" if status == "compliant" else "⚠️"
        lines.extend([
            f"### 决策质量: {status_icon} {status}",
            "",
        ])
        issues = decision_check.get("issues", [])
        if issues and isinstance(issues, list):
            for issue in issues:
                lines.append(f"- ⚠️ {issue}")
        else:
            lines.append("- 无问题")
        lines.append("")

    # 范围控制
    scope = behavior.get("scope_control", {})
    if isinstance(scope, dict):
        status = scope.get("status", "unknown")
        detail = scope.get("detail", "无详情")
        status_icon = "✅" if status == "normal" else "⚠️"
        lines.extend([
            f"### 范围控制: {status_icon} {status}",
            "",
            f"- {detail}",
            "",
        ])

    # 效率评估
    efficiency = behavior.get("efficiency", {})
    if isinstance(efficiency, dict):
        status = efficiency.get("status", "unknown")
        repeated_failures = efficiency.get("repeated_failures", 0)
        same_agent_streak = efficiency.get("same_agent_streak", 0)
        status_icon = "✅" if status == "normal" else "⚠️"
        lines.extend([
            f"### 效率评估: {status_icon} {status}",
            "",
            f"- 重复失败: {repeated_failures} 次",
            f"- 连续相同代理: {same_agent_streak} 轮",
            "",
        ])

    # 建议
    if recommendations and isinstance(recommendations, list):
        lines.extend(["## 建议", ""])
        for idx, rec in enumerate(recommendations, 1):
            lines.append(f"{idx}. {rec}")
        lines.append("")

    # 新增：需求对比分析
    requirement_analysis = user_insight.get("requirement_analysis")
    if requirement_analysis and isinstance(requirement_analysis, dict):
        lines.extend(["## 需求对比分析", ""])

        task_goal = requirement_analysis.get("task_goal_summary", "")
        if task_goal:
            lines.extend([f"**用户原始需求**: {task_goal}", ""])

        coverage = requirement_analysis.get("coverage", {})
        if isinstance(coverage, dict):
            completed = coverage.get("completed", [])
            in_progress = coverage.get("in_progress", [])
            not_started = coverage.get("not_started", [])

            if completed:
                lines.append("**已完成**:")
                for item in completed[:5]:
                    lines.append(f"- ✅ {item}")
                lines.append("")

            if in_progress:
                lines.append("**进行中**:")
                for item in in_progress[:3]:
                    lines.append(f"- 🔄 {item}")
                lines.append("")

            if not_started:
                lines.append("**未开始**:")
                for item in not_started[:3]:
                    lines.append(f"- ⏳ {item}")
                lines.append("")

        alignment_score = requirement_analysis.get("alignment_score")
        alignment_status = requirement_analysis.get("alignment_status")
        if alignment_score is not None and alignment_status:
            status_icon = "✅" if alignment_status == "good" else "⚠️" if alignment_status == "attention" else "❌"
            lines.extend([f"**需求对齐度**: {status_icon} {alignment_score}% ({alignment_status})", ""])

        deviation_warning = requirement_analysis.get("deviation_warning")
        if deviation_warning:
            lines.extend([f"**偏离警告**: ⚠️ {deviation_warning}", ""])

    # 新增：决策习惯分析
    decision_habits = user_insight.get("decision_habits")
    if decision_habits and isinstance(decision_habits, dict):
        total_decisions = decision_habits.get("total_decisions", 0)
        if total_decisions >= 2:
            lines.extend(["## 决策习惯分析", ""])

            adoption_rate = decision_habits.get("recommendation_adoption_rate")
            adoption_tendency = decision_habits.get("adoption_tendency")
            decision_style = decision_habits.get("decision_style")
            common_concerns = decision_habits.get("common_concerns", [])

            lines.append(f"**总决策次数**: {total_decisions}")

            if adoption_rate is not None:
                lines.append(f"**推荐采纳率**: {adoption_rate * 100:.0f}%")

            if adoption_tendency:
                tendency_map = {"high": "高采纳", "medium": "中等", "low": "低采纳"}
                lines.append(f"**采纳倾向**: {tendency_map.get(adoption_tendency, adoption_tendency)}")

            if decision_style:
                style_map = {"conservative": "保守型", "progressive": "激进型", "balanced": "平衡型"}
                lines.append(f"**决策风格**: {style_map.get(decision_style, decision_style)}")

            if common_concerns:
                lines.append(f"**常见关注点**: {', '.join(common_concerns)}")

            lines.append("")

    # 进度概览
    progress = summary.get("progress")
    if progress and isinstance(progress, dict):
        milestones = progress.get("milestones", [])
        if milestones and isinstance(milestones, list):
            lines.extend(["## 进度概览", "", "| 里程碑 | 完成度 |", "|--------|--------|"])
            for ms in milestones:
                if isinstance(ms, dict):
                    ms_id = ms.get("milestone_id", "")
                    ms_name = ms.get("milestone_name", "")
                    percentage = ms.get("percentage", 0)
                    lines.append(f"| {ms_id}: {ms_name} | {percentage:.0f}% |")
            lines.append("")

    lines.extend([
        "---",
        "*此报告由总结代理自动生成，仅供参考*",
    ])

    USER_INSIGHT_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    USER_INSIGHT_REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    _append_log_line(f"user_insight_report: written to {_rel_path(USER_INSIGHT_REPORT_FILE)}\n")


def _append_user_insight_history(
    *,
    iteration: int,
    user_insight: dict,
) -> None:
    """追加用户洞察到历史文件（JSONL 格式）"""
    record = {
        "iteration": iteration,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **user_insight,
    }

    USER_INSIGHT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with USER_INSIGHT_HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _parse_user_insight(payload: dict | object) -> dict | None:
    """
    从摘要 JSON 中解析 user_insight 字段（可选）。

    返回 None 表示未提供或格式无效。
    """
    if not isinstance(payload, dict):
        return None
    user_insight = payload.get("user_insight")
    if user_insight is None:
        return None
    if not isinstance(user_insight, dict):
        return None

    # 基本结构校验
    behavior_check = user_insight.get("behavior_check")
    if behavior_check is not None and not isinstance(behavior_check, dict):
        return None

    recommendations = user_insight.get("recommendations")
    if recommendations is not None and not isinstance(recommendations, list):
        return None

    # 解析新增字段：requirement_analysis
    requirement_analysis = _parse_requirement_analysis(user_insight)
    if requirement_analysis:
        user_insight["requirement_analysis"] = requirement_analysis

    # 解析新增字段：decision_habits
    decision_habits = _parse_decision_habits(user_insight)
    if decision_habits:
        user_insight["decision_habits"] = decision_habits

    return user_insight


def _parse_requirement_analysis(user_insight: dict) -> dict | None:
    """
    解析需求对比分析字段（requirement_analysis）。

    返回 None 表示未提供或格式无效。
    """
    req_analysis = user_insight.get("requirement_analysis")
    if req_analysis is None:
        return None
    if not isinstance(req_analysis, dict):
        return None

    # 校验必填字段
    task_goal_summary = req_analysis.get("task_goal_summary")
    if not isinstance(task_goal_summary, str) or not task_goal_summary.strip():
        return None

    coverage = req_analysis.get("coverage")
    if not isinstance(coverage, dict):
        return None

    # 校验 coverage 子字段（允许为空列表）
    for key in ("completed", "in_progress", "not_started"):
        items = coverage.get(key)
        if items is not None and not isinstance(items, list):
            return None

    # 校验评分字段
    alignment_score = req_analysis.get("alignment_score")
    if not isinstance(alignment_score, (int, float)) or not (0 <= alignment_score <= 100):
        alignment_score = None

    alignment_status = req_analysis.get("alignment_status")
    if alignment_status not in ("good", "attention", "warning"):
        alignment_status = None

    deviation_warning = req_analysis.get("deviation_warning")
    if deviation_warning is not None and not isinstance(deviation_warning, str):
        deviation_warning = None

    return {
        "task_goal_summary": task_goal_summary.strip(),
        "coverage": {
            "completed": [str(x).strip() for x in coverage.get("completed", []) if x],
            "in_progress": [str(x).strip() for x in coverage.get("in_progress", []) if x],
            "not_started": [str(x).strip() for x in coverage.get("not_started", []) if x],
        },
        "alignment_score": alignment_score,
        "alignment_status": alignment_status,
        "deviation_warning": deviation_warning.strip() if deviation_warning else None,
    }


def _parse_decision_habits(user_insight: dict) -> dict | None:
    """
    解析用户决策习惯分析字段（decision_habits）。

    返回 None 表示未提供或格式无效。
    """
    habits = user_insight.get("decision_habits")
    if habits is None:
        return None
    if not isinstance(habits, dict):
        return None

    # 校验必填字段
    total_decisions = habits.get("total_decisions")
    if not isinstance(total_decisions, int) or total_decisions < 0:
        return None

    # 如果决策次数不足 2 次，不输出习惯分析
    if total_decisions < 2:
        return None

    adoption_rate = habits.get("recommendation_adoption_rate")
    if not isinstance(adoption_rate, (int, float)) or not (0 <= adoption_rate <= 1):
        adoption_rate = None

    adoption_tendency = habits.get("adoption_tendency")
    if adoption_tendency not in ("high", "medium", "low"):
        adoption_tendency = None

    decision_style = habits.get("decision_style")
    if decision_style not in ("conservative", "progressive", "balanced"):
        decision_style = None

    common_concerns = habits.get("common_concerns")
    if not isinstance(common_concerns, list):
        common_concerns = []
    else:
        common_concerns = [str(x).strip() for x in common_concerns if x][:3]

    return {
        "total_decisions": total_decisions,
        "recommendation_adoption_rate": adoption_rate,
        "adoption_tendency": adoption_tendency,
        "decision_style": decision_style,
        "common_concerns": common_concerns,
    }
