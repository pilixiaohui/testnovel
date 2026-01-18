from __future__ import annotations

import json
import re

from pathlib import Path

from .decision import _load_json_object, _parse_main_decision_payload
from .file_ops import _rel_path
from .types import IterationSummary, SubagentSummary, SummaryStep

_ALLOWED_ACTORS = {"MAIN", "ORCHESTRATOR", "TEST", "DEV", "REVIEW"}


def _try_extract_steps_from_raw_json(raw_json: str) -> list[dict] | None:
    """
    尝试从原始 JSON 字符串中提取并修复畸形的 steps 数组。

    当 LLM 错误地将多个 step 合并到一个对象时，例如：
    "steps":[{"step":1,"actor":"MAIN","detail":"...","step":2,"actor":"DEV","detail":"..."}]

    我们尝试用正则表达式提取所有 step/actor/detail 组合并重建数组。
    """
    # 查找 steps 数组的位置
    steps_match = re.search(r'"steps"\s*:\s*\[', raw_json)
    if not steps_match:
        return None

    # 从 steps 开始位置提取到对应的 ]
    start = steps_match.end() - 1  # 包含 [
    bracket_count = 0
    end = start
    for i, char in enumerate(raw_json[start:], start):
        if char == '[':
            bracket_count += 1
        elif char == ']':
            bracket_count -= 1
            if bracket_count == 0:
                end = i + 1
                break

    steps_str = raw_json[start:end]

    # 使用正则提取所有 step/actor/detail 组合
    # 匹配模式：找到所有 "step":N,"actor":"...","detail":"..." 的组合
    pattern = r'"step"\s*:\s*(\d+)\s*,\s*"actor"\s*:\s*"([^"]+)"\s*,\s*"detail"\s*:\s*"([^"]*(?:\\.[^"]*)*)"'
    matches = re.findall(pattern, steps_str)

    if len(matches) < 3:
        # 尝试另一种顺序：actor/detail/step
        pattern2 = r'"actor"\s*:\s*"([^"]+)"\s*,\s*"detail"\s*:\s*"([^"]*(?:\\.[^"]*)*)"\s*,\s*"step"\s*:\s*(\d+)'
        matches2 = re.findall(pattern2, steps_str)
        if len(matches2) >= 3:
            matches = [(m[2], m[0], m[1]) for m in matches2]

    if len(matches) < 3:
        # 尝试更宽松的匹配：分别提取 step、actor、detail
        step_pattern = r'"step"\s*:\s*(\d+)'
        actor_pattern = r'"actor"\s*:\s*"([^"]+)"'
        detail_pattern = r'"detail"\s*:\s*"([^"]*(?:\\.[^"]*)*)"'

        steps_nums = re.findall(step_pattern, steps_str)
        actors = re.findall(actor_pattern, steps_str)
        details = re.findall(detail_pattern, steps_str)

        # 如果三者数量相等且 >= 3，则组合
        if len(steps_nums) == len(actors) == len(details) >= 3:
            matches = list(zip(steps_nums, actors, details))

    if len(matches) < 3:
        return None

    # 重建 steps 数组
    fixed_steps = []
    for step_num, actor, detail in matches:
        fixed_steps.append({
            "step": int(step_num),
            "actor": actor,
            "detail": detail,
        })

    # 限制在 3-8 范围内
    if len(fixed_steps) > 8:
        fixed_steps = fixed_steps[:8]

    return fixed_steps if 3 <= len(fixed_steps) <= 8 else None


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
        # 尝试从原始 JSON 中修复畸形的 steps 数组
        fixed_steps = _try_extract_steps_from_raw_json(raw_json)
        if fixed_steps is not None:
            steps_payload = fixed_steps
            # 同时更新 payload 以便后续使用
            payload["steps"] = fixed_steps
        else:
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
