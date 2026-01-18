from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from .config import (
    DEV_PLAN_ALLOWED_STATUSES,
    DEV_PLAN_BANNED_SUBSTRINGS,
    DEV_PLAN_FILE,
    DEV_PLAN_MAX_LINE_LENGTH,
    DEV_PLAN_MAX_TASKS,
    PROJECT_HISTORY_FILE,
    VERIFICATION_POLICY_FILE,
    ACCEPTANCE_SCOPE_FILE,
    REQUIRE_ALL_VERIFIED_FOR_FINISH,
)
from .file_ops import _read_text, _require_file, _atomic_write_text
from .prompt_builder import _task_file_for_agent
from .types import NextAgent


def _validate_dev_plan_text(*, text: str, source: Path) -> None:
    lines = text.splitlines()  # 关键变量：逐行解析 dev_plan 内容
    for idx, line in enumerate(lines, start=1):  # 关键分支：逐行校验 dev_plan
        if len(line) > DEV_PLAN_MAX_LINE_LENGTH:  # 关键分支：行过长直接失败
            raise RuntimeError(
                f"dev_plan line too long: {source}:{idx} len={len(line)} > {DEV_PLAN_MAX_LINE_LENGTH}"
            )
        for banned in DEV_PLAN_BANNED_SUBSTRINGS:  # 关键分支：逐个检查禁用子串
            if banned in line:  # 关键分支：命中禁用子串直接失败
                raise RuntimeError(
                    f"dev_plan contains banned substring {banned!r} at {source}:{idx}"
                )

    task_header_re = re.compile(r"^###\s+([^:]+):\s*(.*)$")
    # NOTE: allow optional leading "-" to reduce brittleness for LLM-written markdown.
    status_re = re.compile(r"^\s*(?:-\s*)?status:\s*([A-Z]+)\s*$")
    acceptance_re = re.compile(r"^\s*(?:-\s*)?acceptance:\s*(.*)$")
    evidence_re = re.compile(r"^\s*(?:-\s*)?evidence:\s*(.*)$")

    tasks: list[dict[str, str | None]] = []  # 关键变量：累计解析出的任务块
    current: dict[str, str | None] | None = None  # 关键变量：当前任务块上下文
    current_has_acceptance = False  # 关键变量：是否出现 acceptance 字段
    current_has_evidence = False  # 关键变量：是否出现 evidence 字段
    current_in_evidence = False  # 关键变量：是否处于 evidence 多行收集
    current_evidence_lines: list[str] = []  # 关键变量：evidence 多行内容缓存

    def finalize(task: dict[str, str | None]) -> None:
        task_id = (task.get("task_id") or "<unknown>").strip()  # 关键变量：任务标识
        status = (task.get("status") or "").strip()  # 关键变量：任务状态
        if status not in DEV_PLAN_ALLOWED_STATUSES:  # 关键分支：状态非法直接失败
            raise RuntimeError(
                f"Invalid dev_plan status for {task_id}: {status!r}, allowed: {sorted(DEV_PLAN_ALLOWED_STATUSES)}"
            )
        if not task.get("has_acceptance"):  # 关键分支：缺 acceptance 字段
            raise RuntimeError(f"dev_plan task {task_id} missing 'acceptance:' field")
        if not task.get("has_evidence"):  # 关键分支：缺 evidence 字段
            raise RuntimeError(f"dev_plan task {task_id} missing 'evidence:' field")
        if status == "VERIFIED":  # 关键分支：VERIFIED 必须有证据
            evidence = (task.get("evidence") or "").strip()  # 关键变量：证据内容
            if not evidence:  # 关键分支：空证据直接失败
                raise RuntimeError(f"dev_plan task {task_id} is VERIFIED but evidence is empty")

    for line in lines:  # 关键分支：逐行解析任务块
        header = task_header_re.match(line)  # 关键变量：任务头匹配结果
        if header:  # 关键分支：命中任务头
            if current is not None:  # 关键分支：结束上一个任务块
                if current_has_evidence:  # 关键分支：尝试补齐 evidence
                    block = "\n".join([l for l in current_evidence_lines if l.strip()]).strip()  # 关键变量：evidence 多行拼接
                    if block and not (current.get("evidence") or "").strip():  # 关键分支：补齐缺失 evidence
                        current["evidence"] = block
                current["has_acceptance"] = "1" if current_has_acceptance else None  # 关键变量：记录 acceptance 是否出现
                current["has_evidence"] = "1" if current_has_evidence else None  # 关键变量：记录 evidence 是否出现
                finalize(current)
                tasks.append(current)
            current = {"task_id": header.group(1).strip(), "title": header.group(2).strip(), "status": None, "evidence": None}  # 关键变量：新任务块
            current_has_acceptance = False  # 关键变量：重置 acceptance 标记
            current_has_evidence = False  # 关键变量：重置 evidence 标记
            current_in_evidence = False  # 关键变量：重置 evidence 解析状态
            current_evidence_lines = []  # 关键变量：清空 evidence 缓存
            continue

        if current is None:  # 关键分支：未进入任务块，忽略
            continue

        m = status_re.match(line)  # 关键变量：status 匹配结果
        if m:  # 关键分支：命中 status 行
            current["status"] = m.group(1).strip()  # 关键变量：写入任务状态
            current_in_evidence = False  # 关键变量：状态行结束 evidence 解析
            continue
        if acceptance_re.match(line):  # 关键分支：命中 acceptance 行
            current_has_acceptance = True  # 关键变量：标记 acceptance 已出现
            current_in_evidence = False  # 关键变量：acceptance 行结束 evidence 解析
            continue
        m = evidence_re.match(line)  # 关键变量：evidence 匹配结果
        if m:  # 关键分支：命中 evidence 行
            current_has_evidence = True  # 关键变量：标记 evidence 已出现
            current["evidence"] = m.group(1)  # 关键变量：首行 evidence 内容
            current_in_evidence = True  # 关键变量：进入 evidence 多行解析
            current_evidence_lines = []  # 关键变量：重置 evidence 缓存
            continue
        if current_in_evidence:  # 关键分支：收集 evidence 多行内容
            current_evidence_lines.append(line)  # 关键变量：追加 evidence 行
            continue

    if current is not None:  # 关键分支：收尾处理最后一个任务块
        if current_has_evidence:  # 关键分支：尝试补齐 evidence
            block = "\n".join([l for l in current_evidence_lines if l.strip()]).strip()  # 关键变量：evidence 多行拼接
            if block and not (current.get("evidence") or "").strip():  # 关键分支：补齐缺失 evidence
                current["evidence"] = block
        current["has_acceptance"] = "1" if current_has_acceptance else None  # 关键变量：记录 acceptance 是否出现
        current["has_evidence"] = "1" if current_has_evidence else None  # 关键变量：记录 evidence 是否出现
        finalize(current)
        tasks.append(current)

    if len(tasks) > DEV_PLAN_MAX_TASKS:  # 关键分支：任务过多直接失败
        raise RuntimeError(
            f"dev_plan has too many tasks: {len(tasks)} > {DEV_PLAN_MAX_TASKS} (keep it to a few dozens)"
        )


def _validate_history_append(*, iteration: int, entry: str) -> str:
    stripped = entry.lstrip()  # 关键变量：去除前导空白便于校验
    expected_header = f"## Iteration {iteration}:"  # 关键变量：本轮历史头部
    if not stripped.startswith(expected_header):  # 关键分支：头部缺失直接失败
        raise RuntimeError(f"history_append must start with {expected_header!r}")
    if "dev_plan:" not in entry:  # 关键分支：必须包含 dev_plan 说明
        raise RuntimeError("history_append missing required 'dev_plan:' line")
    return entry.rstrip()


def _validate_task_content(*, iteration: int, expected_agent: str, task: str) -> str:
    expected_header = f"# Current Task (Iteration {iteration})"  # 关键变量：工单头部
    if not task.startswith(expected_header):  # 关键分支：工单头部不匹配
        raise RuntimeError(f"task must start with {expected_header!r}")

    assigned_agent = None  # 关键变量：解析出的 assigned_agent
    for line in task.splitlines():  # 关键分支：逐行解析工单
        if line.strip().startswith("assigned_agent:"):  # 关键分支：定位 assigned_agent 行
            assigned_agent = line.split(":", 1)[1].strip()  # 关键变量：工单声明代理
            break

    if assigned_agent is None:  # 关键分支：工单缺 assigned_agent
        raise RuntimeError("task missing required 'assigned_agent:' line")
    if assigned_agent != expected_agent:  # 关键分支：工单代理不一致
        raise RuntimeError(f"task assigned_agent mismatch: expected {expected_agent!r}, got {assigned_agent!r}")

    return task.rstrip()



def _validate_dev_plan() -> None:
    """
    对 `memory/dev_plan.md` 做最小结构校验（快速失败）：
    - 每个任务块以 `### <TASK_ID>: ...` 开头
    - 任务块内必须包含：`status:`、`acceptance:`、`evidence:`（允许可选的前导 `-`）
    - status 只能是 TODO/DOING/BLOCKED/DONE/VERIFIED
    - VERIFIED 必须包含非空 evidence
    - 任务总数不超过 DEV_PLAN_MAX_TASKS（保持"最多几十条"）
    """
    _require_file(DEV_PLAN_FILE)  # 关键分支：缺 dev_plan 直接失败
    _validate_dev_plan_text(text=_read_text(DEV_PLAN_FILE), source=DEV_PLAN_FILE)  # 关键变量：读取并校验


def _get_non_verified_tasks() -> list[tuple[str, str]]:
    """
    返回 dev_plan 中所有非 VERIFIED 状态的任务列表。
    返回格式：[(task_id, status), ...]
    """
    _require_file(DEV_PLAN_FILE)
    text = _read_text(DEV_PLAN_FILE)
    lines = text.splitlines()

    task_header_re = re.compile(r"^###\s+([^:]+):\s*(.*)$")
    status_re = re.compile(r"^\s*(?:-\s*)?status:\s*([A-Z]+)\s*$")

    non_verified: list[tuple[str, str]] = []
    current_task_id: str | None = None
    current_status: str | None = None

    for line in lines:
        header = task_header_re.match(line)
        if header:
            # 保存上一个任务的状态
            if current_task_id is not None and current_status is not None:
                if current_status != "VERIFIED":
                    non_verified.append((current_task_id, current_status))
            current_task_id = header.group(1).strip()
            current_status = None
            continue

        m = status_re.match(line)
        if m and current_task_id is not None:
            current_status = m.group(1).strip()

    # 处理最后一个任务
    if current_task_id is not None and current_status is not None:
        if current_status != "VERIFIED":
            non_verified.append((current_task_id, current_status))

    return non_verified


def _check_dev_plan_finish_ready() -> tuple[bool, str]:
    """
    检查 dev_plan 是否满足 FINISH 条件。
    返回：(is_ready, message)
    - is_ready: True 表示所有任务都是 VERIFIED，可以 FINISH
    - message: 如果不满足条件，返回详细说明
    """
    non_verified = _get_non_verified_tasks()
    if not non_verified:
        return True, "All tasks are VERIFIED"

    task_list = ", ".join([f"{tid}({status})" for tid, status in non_verified])
    return False, f"dev_plan has {len(non_verified)} non-VERIFIED tasks: {task_list}"


def _check_finish_readiness() -> tuple[bool, str, list[str]]:
    """
    检查是否满足 FINISH 条件（快速失败/无兜底）。

    Returns:
        (is_ready, reason, blockers)
        - is_ready: 是否可以 FINISH
        - reason: 汇总原因（便于日志/提示词）
        - blockers: 阻塞项列表（用于遗留问题报告）
    """
    _require_file(DEV_PLAN_FILE)
    dev_plan_text = _read_text(DEV_PLAN_FILE)
    blockers: list[str] = []

    if "status: BLOCKED" in dev_plan_text:
        blockers.append("存在 BLOCKED 状态任务")
    if "status: DOING" in dev_plan_text:
        blockers.append("存在 DOING 状态任务")

    if REQUIRE_ALL_VERIFIED_FOR_FINISH:
        # TODO 任务可接受（可能是未来计划）；DONE/DOING/BLOCKED 必须先收敛到 VERIFIED。
        non_verified_count = 0
        for line in dev_plan_text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("status:") and not stripped.startswith("- status:"):
                continue
            status = stripped.split(":", 1)[1].strip()
            if status in {"VERIFIED", "TODO"}:
                continue
            if status in {"DONE", "DOING", "BLOCKED"}:
                non_verified_count += 1
                continue
            # 其它值已由 dev_plan 校验兜住；到这里属于 dev_plan 结构异常
            raise RuntimeError(f"Unexpected dev_plan status: {status!r}")

        if non_verified_count > 0:
            blockers.append(f"存在 {non_verified_count} 个非 VERIFIED 任务（DONE/DOING/BLOCKED）")

    is_ready = not blockers
    reason = "; ".join(blockers) if blockers else "所有条件满足"
    return is_ready, reason, blockers


def _archive_verified_tasks(
    *,
    dev_plan_file: Path,
    archive_file: Path,
    keep_recent_milestones: int = 2,
) -> int:
    """
    将已 VERIFIED 的旧 Milestone 归档到 dev_plan_archived.md，以控制 dev_plan 规模。

    规则：
    - 总是保留最近 N 个 Milestone（即使已 VERIFIED）
    - 仅归档“全部任务 VERIFIED”的旧 Milestone
    - 归档内容追加写入 archive_file，dev_plan_file 中删除对应区块
    """
    if keep_recent_milestones < 0:
        raise ValueError("keep_recent_milestones must be >= 0")

    _require_file(dev_plan_file)
    _require_file(archive_file)

    lines = _read_text(dev_plan_file).splitlines()
    milestone_indices = [idx for idx, line in enumerate(lines) if line.startswith("## Milestone ")]
    if not milestone_indices:
        return 0

    header_end = milestone_indices[0]
    milestones: list[tuple[int, int]] = []
    for i, start in enumerate(milestone_indices):
        end = milestone_indices[i + 1] if i + 1 < len(milestone_indices) else len(lines)
        milestones.append((start, end))

    keep_from = max(0, len(milestones) - keep_recent_milestones)
    to_archive: list[tuple[int, int]] = []

    for idx, (start, end) in enumerate(milestones):
        if idx >= keep_from:
            continue

        block = lines[start:end]
        current_task = None
        statuses: list[str] = []
        for raw in block:
            line = raw.strip()
            if line.startswith("### "):
                current_task = line
                continue
            if current_task is None:
                continue
            if line.startswith("status:") or line.startswith("- status:"):
                statuses.append(line.split(":", 1)[1].strip())
                current_task = None
                continue

        # 无任务的 milestone 不归档（避免误删结构）
        if not statuses:
            continue
        if all(s == "VERIFIED" for s in statuses):
            to_archive.append((start, end))

    if not to_archive:
        return 0

    archive_blocks: list[str] = []
    keep_spans: list[tuple[int, int]] = []

    cursor = header_end
    for start, end in to_archive:
        keep_spans.append((cursor, start))
        archive_blocks.append("\n".join(lines[start:end]).rstrip())
        cursor = end
    keep_spans.append((cursor, len(lines)))

    new_dev_plan_lines: list[str] = []
    for start, end in keep_spans:
        chunk = lines[start:end]
        if not chunk:
            continue
        if new_dev_plan_lines and new_dev_plan_lines[-1].strip():
            new_dev_plan_lines.append("")
        new_dev_plan_lines.extend(chunk)

    # 追加归档内容
    existing_archive = _read_text(archive_file).rstrip()
    appended = "\n\n".join([existing_archive, *archive_blocks]).rstrip() + "\n"

    _atomic_write_text(archive_file, appended)
    _atomic_write_text(dev_plan_file, "\n".join(new_dev_plan_lines).rstrip() + "\n")
    return len(to_archive)


def _load_verification_policy() -> dict[str, object]:
    _require_file(VERIFICATION_POLICY_FILE)  # 关键分支：验证策略必须存在
    raw = _read_text(VERIFICATION_POLICY_FILE).strip()  # 关键变量：配置原文
    if not raw:  # 关键分支：空配置直接失败
        raise RuntimeError(f"Empty verification_policy: {VERIFICATION_POLICY_FILE}")
    try:  # 关键分支：解析 JSON
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:  # 关键分支：非法 JSON 直接失败
        raise ValueError(
            f"verification_policy JSON 解析失败: {VERIFICATION_POLICY_FILE}: {exc}"
        ) from exc
    if not isinstance(payload, dict):  # 关键分支：必须为对象
        raise ValueError("verification_policy must be a JSON object")
    return payload


def _parse_report_rules() -> tuple[set[str], bool, str, set[str], str, str]:
    payload = _load_verification_policy()
    rules = payload.get("report_rules")
    if not isinstance(rules, dict):
        raise ValueError("verification_policy.report_rules must be an object")
    apply_to = rules.get("apply_to")
    if not isinstance(apply_to, list) or not apply_to:
        raise ValueError("verification_policy.report_rules.apply_to must be a non-empty list")
    apply_to_set: set[str] = set()
    for item in apply_to:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("verification_policy.report_rules.apply_to entries must be strings")
        apply_to_set.add(item.strip())
    require_verdict = rules.get("require_verdict")
    if not isinstance(require_verdict, bool):
        raise ValueError("verification_policy.report_rules.require_verdict must be boolean")
    verdict_prefix = rules.get("verdict_prefix")
    if not isinstance(verdict_prefix, str) or not verdict_prefix.strip():
        raise ValueError("verification_policy.report_rules.verdict_prefix must be a non-empty string")
    verdict_allowed = rules.get("verdict_allowed")
    if not isinstance(verdict_allowed, list) or not verdict_allowed:
        raise ValueError("verification_policy.report_rules.verdict_allowed must be a non-empty list")
    verdict_allowed_set: set[str] = set()
    for item in verdict_allowed:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("verification_policy.report_rules.verdict_allowed entries must be strings")
        verdict_allowed_set.add(item.strip())
    blocker_prefix = rules.get("blocker_prefix")
    if not isinstance(blocker_prefix, str) or not blocker_prefix.strip():
        raise ValueError("verification_policy.report_rules.blocker_prefix must be a non-empty string")
    blocker_clear_value = rules.get("blocker_clear_value")
    if not isinstance(blocker_clear_value, str) or not blocker_clear_value.strip():
        raise ValueError("verification_policy.report_rules.blocker_clear_value must be a non-empty string")
    return (
        apply_to_set,
        require_verdict,
        verdict_prefix.strip(),
        verdict_allowed_set,
        blocker_prefix.strip(),
        blocker_clear_value.strip(),
    )


def _validate_report_consistency(*, report_path: Path, agent: str) -> None:
    apply_to, require_verdict, verdict_prefix, verdict_allowed, blocker_prefix, blocker_clear_value = _parse_report_rules()
    if agent not in apply_to:  # 关键分支：不在范围内则跳过
        return
    if not require_verdict:  # 关键分支：未要求 verdict 则跳过
        return
    content = _read_text(report_path)  # 关键变量：报告全文
    lines = content.splitlines()
    verdict_line = next((line.strip() for line in lines if line.strip().startswith(verdict_prefix)), None)
    if verdict_line is None:
        raise RuntimeError(f"Report missing verdict line {verdict_prefix!r}: {report_path}")
    verdict = verdict_line.split(verdict_prefix, 1)[1].strip()
    if verdict not in verdict_allowed:
        raise RuntimeError(f"Invalid verdict {verdict!r} in {report_path}, allowed: {sorted(verdict_allowed)}")
    blocker_line = next((line.strip() for line in lines if line.strip().startswith(blocker_prefix)), None)
    if blocker_line is None:
        raise RuntimeError(f"Report missing blocker line {blocker_prefix!r}: {report_path}")
    blocker = blocker_line.split(blocker_prefix, 1)[1].strip()
    if verdict == "PASS" and blocker != blocker_clear_value:
        raise RuntimeError(
            f"Report verdict PASS but blockers not cleared ({blocker!r}) in {report_path}"
        )
    if verdict in {"FAIL", "BLOCKED"} and blocker == blocker_clear_value:
        raise RuntimeError(
            f"Report verdict {verdict} but blockers marked clear in {report_path}"
        )


def _validate_report_iteration(*, report_path: Path, iteration: int) -> None:
    _require_file(report_path)  # 关键分支：报告必须存在
    needle = f"iteration: {iteration}"  # 关键变量：本轮迭代标识
    content = _read_text(report_path)  # 关键变量：报告全文
    if needle not in content:  # 关键分支：报告未标注迭代
        raise RuntimeError(f"Report missing iteration marker {needle!r}: {report_path}")


def _validate_session_id(session_id: str) -> None:
    try:  # 关键分支：校验 UUID 格式
        uuid.UUID(session_id)  # 关键变量：校验会话 UUID 格式
    except (ValueError, AttributeError) as exc:  # 关键分支：非法 UUID 直接失败
        raise ValueError(f"Invalid Codex session_id: {session_id!r}") from exc


def _assert_main_side_effects(*, iteration: int, expected_next_agent: NextAgent) -> None:
    """
    黑板契约校验：每轮必须完成两件事（由 MAIN 输出、编排器落盘）：
    1) 追加 memory/project_history.md（包含 `## Iteration N:`）
    2) 覆盖对应子代理工单文件（包含当前 iteration 与 assigned_agent）
    """
    _require_file(PROJECT_HISTORY_FILE)  # 关键分支：历史必须存在
    history = _read_text(PROJECT_HISTORY_FILE)  # 关键变量：历史全文
    history_needle = f"## Iteration {iteration}:"  # 关键变量：本轮历史定位
    if history_needle not in history:  # 关键分支：历史未追加
        raise RuntimeError(
            f"MAIN did not append history entry {history_needle!r} in {PROJECT_HISTORY_FILE}"
        )
    lines = history.splitlines()  # 关键变量：历史逐行
    start_idx = None  # 关键变量：本轮起始行
    for idx, line in enumerate(lines):  # 关键分支：定位本轮历史起点
        if line.strip().startswith(history_needle):  # 关键分支：命中起点
            start_idx = idx  # 关键变量：命中本轮起点
            break
    if start_idx is None:  # 关键分支：未找到本轮起点
        raise RuntimeError(
            f"MAIN did not append history entry {history_needle!r} in {PROJECT_HISTORY_FILE}"
        )
    end_idx = len(lines)  # 关键变量：本轮末尾默认到文件末尾
    for idx in range(start_idx + 1, len(lines)):  # 关键分支：查找下一轮起点
        if lines[idx].startswith("## Iteration "):  # 关键分支：命中下一轮
            end_idx = idx  # 关键变量：下一轮开始即本轮结束
            break
    section = "\n".join(lines[start_idx:end_idx])  # 关键变量：本轮历史片段
    if "dev_plan:" not in section:  # 关键分支：必须包含 dev_plan 说明
        raise RuntimeError(
            "MAIN history entry must include a 'dev_plan:' change note "
            f"(either change summary or 'no change') in {PROJECT_HISTORY_FILE} for Iteration {iteration}"
        )

    if expected_next_agent in {"FINISH", "USER"}:  # 关键分支：结束/用户交互仅校验 dev_plan
        _validate_dev_plan()
        return

    task_file = _task_file_for_agent(expected_next_agent)  # 关键变量：目标子代理工单
    _require_file(task_file)  # 关键分支：工单必须存在
    task = _read_text(task_file).strip()  # 关键变量：工单内容
    expected_header = f"# Current Task (Iteration {iteration})"  # 关键变量：工单头部
    if not task.startswith(expected_header):  # 关键分支：工单头部不匹配
        raise RuntimeError(
            f"MAIN did not write expected task header {expected_header!r} in {task_file}"
        )

    assigned_agent = None  # 关键变量：工单声明的代理
    for line in task.splitlines():  # 关键分支：逐行解析工单
        if line.strip().startswith("assigned_agent:"):  # 关键分支：定位 assigned_agent 行
            assigned_agent = line.split(":", 1)[1].strip()  # 关键变量：解析 assigned_agent
            break

    if assigned_agent is None:  # 关键分支：工单缺 assigned_agent
        raise RuntimeError(f"MAIN task missing 'assigned_agent:' in {task_file}")

    if assigned_agent != expected_next_agent:  # 关键分支：工单代理不匹配
        raise RuntimeError(
            "MAIN task assigned_agent mismatch: "
            f"expected {expected_next_agent!r}, got {assigned_agent!r} in {task_file}"
        )

    _validate_dev_plan()  # 关键变量：确保 dev_plan 结构合法
