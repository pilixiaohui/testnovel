from __future__ import annotations

import json
import re
from datetime import datetime
from queue import Empty

from .config import (
    PROJECT_HISTORY_FILE,
    USER_DECISION_PATTERNS_FILE,
    ENABLE_DECISION_PATTERNS,
)
from .file_ops import _append_log_line
from .state import UiRuntime, UserInterrupted
from .types import MainDecision, MainDecisionUser, MainOutput, UserDecisionOption


def _extract_json_object(raw_json: str) -> str | None:
    start = raw_json.find("{")
    end = raw_json.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return raw_json[start : end + 1]


_ALLOWED_SPEC_ARTIFACT_FILES = frozenset({
    "proposal.md",
    "design.md",
    "delta_spec.md",
    "tasks.md",
    "validation.md",
    "questions.md",
    "proofs.md",
    "meta.json",
})
_CHANGE_ID_RE = re.compile(r"^CHG-\d{4,}$")


def _validate_artifact_update_file_for_change(*, normalized_file: str, active_change_id: str, idx: int) -> None:
    expected_change_id = active_change_id.strip().upper()
    parts = normalized_file.split("/")
    if len(parts) != 3 or parts[0] != "changes":
        raise ValueError(
            f"Invalid artifact_updates[{idx}].file: must be under changes/{expected_change_id}/"
        )

    if parts[1].upper() != expected_change_id:
        raise ValueError(
            f"Invalid artifact_updates[{idx}].file: must target active change {expected_change_id!r}"
        )

    if parts[2] not in _ALLOWED_SPEC_ARTIFACT_FILES:
        allowed = ", ".join(sorted(_ALLOWED_SPEC_ARTIFACT_FILES))
        raise ValueError(
            f"Invalid artifact_updates[{idx}].file: unsupported artifact {parts[2]!r}, allowed: {allowed}"
        )


def _extract_option_description(opt: dict) -> str | None:
    """从选项对象中提取描述，兼容多种字段格式。

    优先级：description > label + detail > label > detail
    """
    # 优先使用标准字段
    desc = opt.get("description")
    if isinstance(desc, str) and desc.strip():
        return desc.strip()

    # 兼容 label/detail 格式
    label = opt.get("label")
    detail = opt.get("detail")
    label_str = label.strip() if isinstance(label, str) and label.strip() else None
    detail_str = detail.strip() if isinstance(detail, str) and detail.strip() else None

    if label_str and detail_str:
        return f"{label_str} - {detail_str}"
    if label_str:
        return label_str
    if detail_str:
        return detail_str

    return None


def _load_json_object(raw_json: str, *, strict: bool = False) -> dict:
    trimmed = raw_json.strip()
    try:  # 关键分支：尝试解析 JSON
        payload = json.loads(trimmed)  # 关键变量：解析 JSON
    except json.JSONDecodeError as exc:  # 关键分支：严格模式直接失败，非严格模式容忍包裹文本
        if strict:
            raise ValueError(f"MAIN output must be pure JSON, got: {raw_json!r}") from exc
        extracted = _extract_json_object(raw_json)
        if extracted is None:
            raise ValueError(f"MAIN output must be pure JSON, got: {raw_json!r}") from exc
        try:
            payload = json.loads(extracted)
        except json.JSONDecodeError as exc_inner:
            raise ValueError(f"MAIN output must be pure JSON, got: {raw_json!r}") from exc_inner
    if not isinstance(payload, dict):  # 关键分支：必须是 JSON 对象
        raise ValueError(f"MAIN output must be a JSON object, got: {payload!r}")
    return payload


def _parse_main_decision_payload(decision: dict) -> MainDecision:
    """
    MAIN decision payload must be a JSON object containing:
    {"next_agent":"IMPLEMENTER","reason":"..."}
    """

    next_agent = decision.get("next_agent")  # 关键变量：目标代理
    reason = decision.get("reason")  # 关键变量：决策理由

    # Context-centric 架构：IMPLEMENTER 合并 TEST+DEV，VALIDATE 触发并行验证
    allowed: set[str] = {"IMPLEMENTER", "SPEC_ANALYZER", "VALIDATE", "FINISH", "USER"}
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
        # 容错：字符串自动转换为对象格式
        if isinstance(opt, str):
            opt = {"option_id": f"opt{idx}", "description": opt}
        if not isinstance(opt, dict):  # 关键分支：选项必须是对象或字符串
            raise ValueError(f"Invalid options[{idx}]: must be an object or string")
        option_id = opt.get("option_id")  # 关键变量：选项 id
        description = _extract_option_description(opt)  # 关键变量：选项描述（兼容多种格式）
        # 容错：缺少 option_id 时自动生成
        if not isinstance(option_id, str) or not option_id.strip():
            option_id = f"opt{idx}"
        if not description:  # 关键分支：描述缺失
            raise ValueError(f"Invalid options[{idx}]: missing description (or label/detail fallback)")
        if option_id in seen_ids:  # 关键分支：重复 id
            raise ValueError(f"Duplicate option_id in options: {option_id!r}")
        seen_ids.add(option_id)
        parsed_options.append({"option_id": option_id, "description": description})

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
        "doc_patches": None,  # 文档修正在 _parse_main_output 中解析
    }


def _parse_main_decision(raw_json: str, *, strict: bool = False) -> MainDecision:
    """
    MAIN 的最后一条消息必须是纯 JSON（无额外文本），形如：
    {"next_agent":"IMPLEMENTER","reason":"..."}
    """
    payload = _load_json_object(raw_json, strict=strict)  # 关键变量：JSON 负载
    return _parse_main_decision_payload(payload)


def _parse_main_output(raw_json: str, *, strict: bool = False) -> MainOutput:
    payload = _load_json_object(raw_json, strict=strict)  # 关键变量：JSON 负载
    decision = _parse_main_decision_payload(payload)  # 关键变量：解析决策

    history_append = payload.get("history_append")  # 关键变量：历史追加内容
    if not isinstance(history_append, str) or not history_append.strip():  # 关键分支：历史缺失
        raise ValueError("Invalid history_append: must be a non-empty string")

    # 硬切旧协议：发现旧字段立即失败，避免旧流程残留继续运行
    for legacy_field in ("task", "dev_plan_next", "spec_anchor_next", "target_reqs"):
        if legacy_field in payload:
            raise ValueError(f"Invalid {legacy_field}: legacy field is not allowed in spec-driven protocol")

    task_body = payload.get("task_body")  # 关键变量：工单正文（可为空）
    if task_body is not None and (not isinstance(task_body, str) or not task_body.strip()):
        raise ValueError("Invalid task_body: must be a non-empty string or null")

    active_change_id = payload.get("active_change_id")  # 关键变量：当前变更单 id
    if active_change_id is not None:
        if not isinstance(active_change_id, str) or not active_change_id.strip():
            raise ValueError("Invalid active_change_id: must be a non-empty string or null")
        active_change_id = active_change_id.strip().upper()
        if not _CHANGE_ID_RE.match(active_change_id):
            raise ValueError("Invalid active_change_id: must match CHG-<digits>")

    implementation_scope_payload = payload.get("implementation_scope")  # 关键变量：任务范围
    implementation_scope: list[str] | None = None
    if implementation_scope_payload is not None:
        if not isinstance(implementation_scope_payload, list):
            raise ValueError("Invalid implementation_scope: must be a list of task ids or null")
        parsed_scope: list[str] = []
        seen_scope: set[str] = set()
        for idx, item in enumerate(implementation_scope_payload, start=1):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(
                    f"Invalid implementation_scope[{idx}]: must be a non-empty string"
                )
            task_id = item.strip().upper()
            if task_id in seen_scope:
                raise ValueError(
                    f"Invalid implementation_scope[{idx}]: duplicated task id {task_id!r}"
                )
            seen_scope.add(task_id)
            parsed_scope.append(task_id)
        implementation_scope = parsed_scope

    change_action = payload.get("change_action")  # 关键变量：变更动作
    if change_action is not None:
        if change_action not in {"create", "update", "archive", "none"}:
            raise ValueError(
                "Invalid change_action: must be create/update/archive/none or null"
            )

    artifact_updates_payload = payload.get("artifact_updates")  # 关键变量：规格工件更新
    artifact_updates = None
    if artifact_updates_payload is not None:
        if not isinstance(artifact_updates_payload, list):
            raise ValueError("Invalid artifact_updates: must be a list or null")
        parsed_updates: list[dict] = []
        for idx, patch in enumerate(artifact_updates_payload, start=1):
            if not isinstance(patch, dict):
                raise ValueError(f"Invalid artifact_updates[{idx}]: must be an object")

            file_path = patch.get("file")
            action = patch.get("action")
            content = patch.get("content")
            reason = patch.get("reason")

            if not isinstance(file_path, str) or not file_path.strip():
                raise ValueError(
                    f"Invalid artifact_updates[{idx}].file: must be a non-empty string"
                )
            normalized_file = file_path.strip().replace('\\', '/')
            if normalized_file.startswith('/') or '..' in normalized_file.split('/'):
                raise ValueError(
                    f"Invalid artifact_updates[{idx}].file: must be a safe relative path"
                )
            if not isinstance(active_change_id, str):
                raise ValueError(
                    f"Invalid artifact_updates[{idx}].file: requires active_change_id"
                )
            _validate_artifact_update_file_for_change(
                normalized_file=normalized_file,
                active_change_id=active_change_id,
                idx=idx,
            )

            if action not in {"append", "replace", "insert"}:
                raise ValueError(
                    f"Invalid artifact_updates[{idx}].action: must be append/replace/insert"
                )
            if not isinstance(content, str) or not content.strip():
                raise ValueError(
                    f"Invalid artifact_updates[{idx}].content: must be a non-empty string"
                )

            parsed_patch = {
                "file": normalized_file,
                "action": action,
                "content": content,
            }

            if reason is not None:
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError(
                        f"Invalid artifact_updates[{idx}].reason: must be a non-empty string"
                    )
                parsed_patch["reason"] = reason.strip()

            if action == "replace":
                old_content = patch.get("old_content")
                if not isinstance(old_content, str) or not old_content:
                    raise ValueError(
                        f"Invalid artifact_updates[{idx}].old_content: replace requires non-empty old_content"
                    )
                parsed_patch["old_content"] = old_content

            if action == "insert":
                after_marker = patch.get("after_marker")
                if not isinstance(after_marker, str) or not after_marker.strip():
                    raise ValueError(
                        f"Invalid artifact_updates[{idx}].after_marker: insert requires non-empty after_marker"
                    )
                parsed_patch["after_marker"] = after_marker

            parsed_updates.append(parsed_patch)
        artifact_updates = parsed_updates

    next_agent = decision["next_agent"]  # 关键变量：目标代理

    # 规格驱动协议：实现类任务必须绑定 change id；FINISH/VALIDATE/USER 禁止 task_body
    if next_agent in {"IMPLEMENTER", "SPEC_ANALYZER"}:
        if not isinstance(task_body, str) or not task_body.strip():
            raise ValueError(f"Invalid task_body: must be a non-empty string when next_agent={next_agent}")
        if not isinstance(active_change_id, str) or not active_change_id.strip():
            raise ValueError(
                f"Invalid active_change_id: must be a non-empty string when next_agent={next_agent}"
            )
    else:
        if task_body is not None:
            raise ValueError(f"Invalid task_body: must be null when next_agent={next_agent}")

    if next_agent == "IMPLEMENTER":
        if not implementation_scope:
            raise ValueError(
                "Invalid implementation_scope: must be a non-empty list when next_agent=IMPLEMENTER"
            )
    elif implementation_scope is not None:
        raise ValueError(
            f"Invalid implementation_scope: must be null when next_agent={next_agent}"
        )

    if change_action in {"create", "update", "archive"} and not active_change_id:
        raise ValueError("Invalid change_action: create/update/archive requires active_change_id")
    if change_action in {None, "none"} and artifact_updates is not None:
        raise ValueError("Invalid artifact_updates: requires change_action=create/update/archive")

    # 解析文档修正建议（仅 USER 决策时）
    doc_patches = None
    if next_agent == "USER":
        raw_patches = payload.get("doc_patches")
        if raw_patches is not None:
            if not isinstance(raw_patches, list):
                raise ValueError("Invalid doc_patches: must be a list or null")
            doc_patches = []
            for idx, patch in enumerate(raw_patches, start=1):
                if not isinstance(patch, dict):
                    raise ValueError(f"Invalid doc_patches[{idx}]: must be an object")
                file_path = patch.get("file")
                action = patch.get("action")
                content = patch.get("content")
                reason = patch.get("reason")
                if not isinstance(file_path, str) or not file_path.strip():
                    raise ValueError(f"Invalid doc_patches[{idx}].file: must be a non-empty string")
                if action not in {"append", "replace", "insert"}:
                    raise ValueError(f"Invalid doc_patches[{idx}].action: must be append/replace/insert")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError(f"Invalid doc_patches[{idx}].content: must be a non-empty string")
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError(f"Invalid doc_patches[{idx}].reason: must be a non-empty string")
                doc_patches.append({
                    "file": file_path.strip(),
                    "action": action,
                    "content": content,
                    "reason": reason.strip(),
                    "old_content": patch.get("old_content", ""),
                    "after_marker": patch.get("after_marker", ""),
                })

    return {
        "decision": decision,
        "history_append": history_append,
        "task_body": task_body if isinstance(task_body, str) else None,
        "active_change_id": active_change_id if isinstance(active_change_id, str) else None,
        "implementation_scope": implementation_scope,
        "artifact_updates": artifact_updates,
        "change_action": change_action if isinstance(change_action, str) else None,
        "doc_patches": doc_patches,
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

    # 记录文档修正建议（若用户选择 accept 且存在 doc_patches）
    doc_patches = decision.get("doc_patches")
    if doc_patches and user_choice == "accept":
        lines.append("- doc_patches_accepted:")
        for idx, patch in enumerate(doc_patches, start=1):
            lines.append(f"  - [{idx}] file: {patch.get('file')}")
            lines.append(f"    action: {patch.get('action')}")
            lines.append(f"    reason: {patch.get('reason')}")
            content = patch.get('content') or ''
            # 内容可能较长，截断显示
            if len(content) > 500:
                content = content[:500] + "...(truncated)"
            lines.append(f"    content: |")
            for line in content.split('\n'):
                lines.append(f"      {line}")
            if patch.get('old_content'):
                lines.append(f"    old_content: {patch.get('old_content')[:100]}...")
            if patch.get('after_marker'):
                lines.append(f"    after_marker: {patch.get('after_marker')}")

    lines.append("")

    PROJECT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PROJECT_HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _prompt_user_for_decision(
    *,
    iteration: int,
    decision: MainDecisionUser,
    ui: UiRuntime | None,
) -> tuple[str, str | None]:
    """返回 (user_choice, user_comment) 元组"""
    # 显示文档修正建议（如果有）
    doc_patches = decision.get("doc_patches")

    if ui is None:  # 关键分支：CLI 模式
        print("\n========== USER DECISION REQUIRED ==========")
        print(f"title: {decision['decision_title']}")
        print(f"reason: {decision['reason']}")
        print(f"question: {decision['question']}")

        # 显示文档修正建议
        if doc_patches:
            print("\n--- 文档修正建议 ---")
            for idx, patch in enumerate(doc_patches, start=1):
                print(f"  [{idx}] 文件: {patch.get('file')}")
                print(f"      操作: {patch.get('action')}")
                print(f"      原因: {patch.get('reason')}")
                content_preview = (patch.get('content') or '')[:100]
                if len(patch.get('content') or '') > 100:
                    content_preview += "..."
                print(f"      内容: {content_preview}")
            print("--- 文档修正建议结束 ---\n")

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
        return user_choice, user_comment if user_comment else None

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
    return user_choice, user_comment


def _update_user_decision_patterns(
    *,
    iteration: int,
    decision: MainDecisionUser,
    user_choice: str,
    user_comment: str | None,
) -> None:
    """
    USER 决策后立即更新决策模式文档。

    此函数在 workflow.py 的 USER 分支中调用，
    因为 USER 决策后直接 continue，不经过 SUMMARY 阶段。
    """
    if not ENABLE_DECISION_PATTERNS:
        return

    timestamp = datetime.now().isoformat(timespec="seconds")

    # 读取现有内容或创建新文件
    if USER_DECISION_PATTERNS_FILE.exists():
        existing = USER_DECISION_PATTERNS_FILE.read_text(encoding="utf-8")
    else:
        existing = _create_decision_patterns_header()

    # 提取决策信息
    decision_title = decision.get("decision_title", "")
    options = decision.get("options", [])
    recommended = decision.get("recommended_option_id")

    # 找到用户选择的选项描述
    choice_desc = ""
    for opt in options:
        if opt.get("option_id") == user_choice:
            choice_desc = opt.get("description", "")
            break

    # 构建新记录
    new_entry = [
        "",
        f"### Iteration {iteration} ({timestamp})",
        "",
        f"**问题**: {decision_title}",
        "",
        f"- **选择**: {user_choice} - {choice_desc}",
    ]

    if recommended:
        was_recommended = "是" if user_choice == recommended else "否"
        new_entry.append(f"- **是否采纳推荐**: {was_recommended}（推荐: {recommended}）")

    if user_comment and user_comment.strip():
        # 截断过长的备注
        comment = user_comment.strip()
        if len(comment) > 200:
            comment = comment[:200] + "..."
        new_entry.append(f"- **用户备注**: {comment}")

    new_entry.append("")

    # 写入文件
    USER_DECISION_PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USER_DECISION_PATTERNS_FILE.write_text(
        existing + "\n".join(new_entry),
        encoding="utf-8"
    )
    _append_log_line(f"decision_patterns: updated for iteration {iteration}\n")


def _create_decision_patterns_header() -> str:
    """创建决策模式文档头部"""
    return """# 用户决策习惯整合

> 此文档记录您在工作流中的决策历史，帮助您了解自己的决策模式。

## 决策记录

"""
