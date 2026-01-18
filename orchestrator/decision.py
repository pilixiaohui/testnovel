from __future__ import annotations

import json
from datetime import datetime
from queue import Empty

from .config import PROJECT_HISTORY_FILE
from .file_ops import _append_log_line
from .state import UiRuntime, UserInterrupted
from .types import MainDecision, MainDecisionUser, MainOutput, UserDecisionOption


def _load_json_object(raw_json: str) -> dict:
    try:  # 关键分支：尝试解析 JSON
        payload = json.loads(raw_json.strip())  # 关键变量：解析 JSON
    except json.JSONDecodeError as exc:  # 关键分支：非 JSON 输出直接失败
        raise ValueError(f"MAIN output must be pure JSON, got: {raw_json!r}") from exc
    if not isinstance(payload, dict):  # 关键分支：必须是 JSON 对象
        raise ValueError(f"MAIN output must be a JSON object, got: {payload!r}")
    return payload


def _parse_main_decision_payload(decision: dict) -> MainDecision:
    """
    MAIN decision payload must be a JSON object containing:
    {"next_agent":"DEV","reason":"..."}
    """

    next_agent = decision.get("next_agent")  # 关键变量：目标代理
    reason = decision.get("reason")  # 关键变量：决策理由

    allowed: set[str] = {"TEST", "DEV", "REVIEW", "FINISH", "USER"}
    if next_agent not in allowed:  # 关键分支：非法代理
        raise ValueError(f"Invalid next_agent: {next_agent!r}, allowed: {sorted(allowed)}")
    if not isinstance(reason, str) or not reason.strip():  # 关键分支：理由缺失
        raise ValueError("Invalid reason: must be a non-empty string")

    if next_agent != "USER":  # 关键分支：非 USER 直接返回最小决策
        return {"next_agent": next_agent, "reason": reason.strip()}  # type: ignore[return-value]

    decision_title = decision.get("decision_title")  # 关键变量：抉择标题
    question = decision.get("question")  # 关键变量：抉择问题
    options = decision.get("options")  # 关键变量：候选项
    recommended_option_id = decision.get("recommended_option_id")  # 关键变量：推荐项

    if not isinstance(decision_title, str) or not decision_title.strip():  # 关键分支：标题缺失
        raise ValueError("Invalid decision_title: must be a non-empty string when next_agent=USER")
    if not isinstance(question, str) or not question.strip():  # 关键分支：问题缺失
        raise ValueError("Invalid question: must be a non-empty string when next_agent=USER")
    if not isinstance(options, list) or len(options) < 2:  # 关键分支：选项不足
        raise ValueError("Invalid options: must be a list with >= 2 items when next_agent=USER")

    parsed_options: list[UserDecisionOption] = []  # 关键变量：解析后的选项
    seen_ids: set[str] = set()  # 关键变量：去重集合
    for idx, opt in enumerate(options, start=1):  # 关键分支：逐条校验选项
        if not isinstance(opt, dict):  # 关键分支：选项必须是对象
            raise ValueError(f"Invalid options[{idx}]: must be an object")
        option_id = opt.get("option_id")  # 关键变量：选项 id
        description = opt.get("description")  # 关键变量：选项描述
        if not isinstance(option_id, str) or not option_id.strip():  # 关键分支：id 缺失
            raise ValueError(f"Invalid options[{idx}].option_id: must be a non-empty string")
        if not isinstance(description, str) or not description.strip():  # 关键分支：描述缺失
            raise ValueError(f"Invalid options[{idx}].description: must be a non-empty string")
        if option_id in seen_ids:  # 关键分支：重复 id
            raise ValueError(f"Duplicate option_id in options: {option_id!r}")
        seen_ids.add(option_id)
        parsed_options.append({"option_id": option_id, "description": description.strip()})

    if recommended_option_id is not None:  # 关键分支：推荐项可选
        if not isinstance(recommended_option_id, str) or not recommended_option_id.strip():  # 关键分支：推荐项非法
            raise ValueError("Invalid recommended_option_id: must be a non-empty string or null")
        if recommended_option_id not in seen_ids:  # 关键分支：推荐项不在选项列表
            raise ValueError(
                "Invalid recommended_option_id: must match one of options[].option_id, "
                f"got {recommended_option_id!r}"
            )

    return {
        "next_agent": "USER",
        "reason": reason.strip(),
        "decision_title": decision_title.strip(),
        "question": question.strip(),
        "options": parsed_options,
        "recommended_option_id": recommended_option_id.strip() if isinstance(recommended_option_id, str) else None,
    }


def _parse_main_decision(raw_json: str) -> MainDecision:
    """
    MAIN 的最后一条消息必须是纯 JSON（无额外文本），形如：
    {"next_agent":"DEV","reason":"..."}
    """
    payload = _load_json_object(raw_json)  # 关键变量：JSON 负载
    return _parse_main_decision_payload(payload)


def _parse_main_output(raw_json: str) -> MainOutput:
    payload = _load_json_object(raw_json)  # 关键变量：JSON 负载
    decision = _parse_main_decision_payload(payload)  # 关键变量：解析决策

    history_append = payload.get("history_append")  # 关键变量：历史追加内容
    if not isinstance(history_append, str) or not history_append.strip():  # 关键分支：历史缺失
        raise ValueError("Invalid history_append: must be a non-empty string")

    dev_plan_next = payload.get("dev_plan_next")  # 关键变量：计划草案（可为空）
    if dev_plan_next is not None:  # 关键分支：存在草案才校验
        if not isinstance(dev_plan_next, str) or not dev_plan_next.strip():  # 关键分支：草案为空
            raise ValueError("Invalid dev_plan_next: must be a non-empty string or null")

    task = payload.get("task")  # 关键变量：工单内容（可为空）
    next_agent = decision["next_agent"]  # 关键变量：目标代理
    if next_agent in {"TEST", "DEV", "REVIEW"}:  # 关键分支：子代理必须有工单
        if not isinstance(task, str) or not task.strip():  # 关键分支：子代理必须有工单
            raise ValueError(f"Invalid task: must be a non-empty string when next_agent={next_agent}")
    else:  # 关键分支：非子代理必须为 null
        if task is not None:  # 关键分支：存在 task 时继续校验
            if not isinstance(task, str) or task.strip():  # 关键分支：非子代理必须为 null
                raise ValueError(f"Invalid task: must be null when next_agent={next_agent}")

    return {
        "decision": decision,
        "history_append": history_append,
        "task": task if isinstance(task, str) else None,
        "dev_plan_next": dev_plan_next if isinstance(dev_plan_next, str) else None,
    }


def _append_user_interaction_to_history(
    *,
    iteration: int,
    decision: MainDecisionUser,
    user_choice: str,
    user_comment: str | None,
) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")  # 关键变量：用户决策时间戳
    lines: list[str] = []  # 关键变量：历史追加内容
    lines.append("")
    lines.append(f"## User Decision (Iteration {iteration}): {decision['decision_title']} - {timestamp}")  # 关键变量：标题
    lines.append(f"- reason: {decision['reason']}")  # 关键变量：理由
    lines.append(f"- question: {decision['question']}")  # 关键变量：问题
    lines.append("- options:")
    for opt in decision["options"]:  # 关键分支：追加选项列表
        lines.append(f"  - {opt['option_id']}: {opt['description']}")  # 关键变量：选项详情
    if decision["recommended_option_id"] is not None:  # 关键分支：有推荐项才写入
        lines.append(f"- recommended_option_id: {decision['recommended_option_id']}")  # 关键变量：推荐项
    lines.append(f"- user_choice: {user_choice}")  # 关键变量：用户选择
    if user_comment is not None and user_comment.strip():  # 关键分支：可选备注
        lines.append(f"- user_comment: {user_comment.strip()}")  # 关键变量：用户补充说明
    lines.append("")

    PROJECT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PROJECT_HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _prompt_user_for_decision(
    *,
    iteration: int,
    decision: MainDecisionUser,
    ui: UiRuntime | None,
) -> None:
    if ui is None:  # 关键分支：CLI 模式
        print("\n========== USER DECISION REQUIRED ==========")
        print(f"title: {decision['decision_title']}")
        print(f"reason: {decision['reason']}")
        print(f"question: {decision['question']}")
        print("options:")
        for idx, opt in enumerate(decision["options"], start=1):  # 关键分支：按序号展示选项
            print(f"  {idx}. {opt['option_id']}: {opt['description']}")
        if decision["recommended_option_id"] is not None:  # 关键分支：显示推荐项
            print(f"recommended_option_id: {decision['recommended_option_id']}")
        raw = input("请选择 option_id 或序号（1..N）: ").strip()  # 关键变量：用户输入
        if not raw:  # 关键分支：输入不能为空
            raise ValueError("User decision input is required")

        options = decision["options"]  # 关键变量：可选项
        valid_ids = {o["option_id"] for o in options}  # 关键变量：合法 id 集合
        if raw.isdigit():  # 关键分支：数字输入按序号解析
            idx = int(raw)  # 关键变量：序号
            if not (1 <= idx <= len(options)):  # 关键分支：序号越界
                raise ValueError(f"Invalid option index: {raw!r}, must be in 1..{len(options)}")
            user_choice = options[idx - 1]["option_id"]  # 关键变量：用户选择 id
        else:  # 关键分支：非数字输入直接按 id 处理
            user_choice = raw  # 关键变量：直接使用 option_id

        if user_choice not in valid_ids:  # 关键分支：非法选项
            raise ValueError(f"Invalid option_id: {user_choice!r}, allowed: {sorted(valid_ids)}")

        user_comment = input("补充说明（可选，直接回车跳过）: ")  # 关键变量：用户备注
        _append_user_interaction_to_history(
            iteration=iteration,
            decision=decision,
            user_choice=user_choice,
            user_comment=user_comment,
        )
        print(f"Recorded user_choice: {user_choice}")
        return

    ui.state.update(phase="awaiting_user", iteration=iteration, current_agent="USER", awaiting_user_decision=decision)  # 关键变量：UI 进入等待态
    _append_log_line(f"\nawaiting_user_decision: {decision['decision_title']}\n")
    while True:  # 关键分支：阻塞等待用户决策
        if ui.control.cancel_event.is_set():  # 关键分支：用户中断等待
            raise UserInterrupted("User interrupted while awaiting decision")
        try:  # 关键分支：尝试读取队列
            resp = ui.decision_queue.get(timeout=0.4)  # 关键变量：UI 决策响应
            break
        except Empty:  # 关键分支：超时则继续轮询
            continue
    user_choice = (resp.get("option_id") or "").strip()  # 关键变量：用户选择
    user_comment = resp.get("comment")  # 关键变量：用户备注
    if not user_choice:  # 关键分支：空选择
        raise ValueError("Missing option_id from UI")

    valid_ids = {o["option_id"] for o in decision["options"]}  # 关键变量：合法 id 集合
    if user_choice not in valid_ids:  # 关键分支：非法选项
        raise ValueError(f"Invalid option_id from UI: {user_choice!r}, allowed: {sorted(valid_ids)}")

    _append_user_interaction_to_history(
        iteration=iteration,
        decision=decision,
        user_choice=user_choice,
        user_comment=user_comment,
    )
    ui.state.update(phase="running", awaiting_user_decision=None)  # 关键变量：UI 回到运行态
    _append_log_line(f"user_choice_recorded: {user_choice}\n")
