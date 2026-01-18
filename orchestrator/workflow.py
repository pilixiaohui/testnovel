from __future__ import annotations

import json
import time

from pathlib import Path
from .backup import _backup_subagent_artifacts, _clear_dev_plan_stage_file, _commit_staged_dev_plan_if_present
from .codex_runner import (
    _clear_saved_main_state,
    _load_saved_main_iteration,
    _load_saved_main_session_id,
    _run_codex_exec,
    _save_main_iteration,
    _save_main_session_id,
)
from .config import (
    CODEX_STATE_DIR,
    RESUME_STATE_FILE,
    CONFIG,
    DEV_PLAN_FILE,
    DEV_PLAN_STAGED_FILE,
    DEV_TASK_FILE,
    FINISH_REVIEW_CONFIG_FILE,
    VERIFICATION_POLICY_FILE,
    GLOBAL_CONTEXT_FILE,
    MEMORY_DIR,
    ORCHESTRATOR_LOG_FILE,
    PROJECT_HISTORY_FILE,
    PROJECT_ROOT,
    PROMPTS_DIR,
    REPORT_DEV_FILE,
    REPORT_MAIN_DECISION_FILE,
    REPORT_ITERATION_SUMMARY_FILE,
    REPORT_ITERATION_SUMMARY_HISTORY_FILE,
    REPORT_REVIEW_FILE,
    REPORT_FINISH_REVIEW_FILE,
    REPORT_TEST_FILE,
    REPORTS_DIR,
    REVIEW_TASK_FILE,
    TEST_TASK_FILE,
    WORKSPACE_DIR,
    ProjectTemplates,
    ACCEPTANCE_SCOPE_FILE,
    OUT_OF_SCOPE_ISSUES_FILE,
    DEV_PLAN_ARCHIVED_FILE,
    MAX_FINISH_ATTEMPTS,
    LEGACY_ISSUES_REPORT_FILE,
    KEEP_RECENT_MILESTONES,
    MAX_DEV_PLAN_SIZE,
    MIN_HISTORY_WINDOW,
    MAX_HISTORY_WINDOW,
    MAX_PROMPT_SIZE,
)
from .decision import _parse_main_output, _prompt_user_for_decision
from .summary import _append_iteration_summary_history, _load_iteration_summary_history, _parse_iteration_summary
from .telemetry import log_event, new_trace_id
from .file_ops import (
    _append_history_entry,
    _append_log_line,
    _assert_files_unchanged,
    _atomic_write_text,
    _read_text,
    _require_file,
    _rel_path,
    _sha256_text,
    _snapshot_files,
    _write_text_if_missing,
)
from .prompt_builder import (
    _extract_finish_review_verdict,
    _inject_file,
    _inject_project_history_recent,
    _load_system_prompt,
    _task_file_for_agent,
)
from .errors import TemporaryError
from .state import RunControl, UiRuntime, UserInterrupted
from .types import MainOutput, ResumeState
from .validation import (
    _assert_main_side_effects,
    _check_finish_readiness,
    _archive_verified_tasks,
    _validate_dev_plan,
    _validate_dev_plan_text,
    _validate_history_append,
    _validate_report_consistency,
    _validate_report_iteration,
    _validate_session_id,
    _validate_task_content,
)


def _ensure_initial_md_files() -> None:
    """
    初始化黑板目录与初始 Markdown 文件（仅在缺失时创建，不覆盖）。
    用户要求：orchestrator/memory/、orchestrator/reports/、orchestrator/workspace/
    内缺失初始 md 文件则新建初始化。
    """
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)  # 关键变量：黑板 memory 目录
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)  # 关键变量：提示词目录
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)  # 关键变量：报告目录
    (WORKSPACE_DIR / "test").mkdir(parents=True, exist_ok=True)  # 关键变量：TEST 工单目录
    (WORKSPACE_DIR / "dev").mkdir(parents=True, exist_ok=True)  # 关键变量：DEV 工单目录
    (WORKSPACE_DIR / "review").mkdir(parents=True, exist_ok=True)  # 关键变量：REVIEW 工单目录
    (WORKSPACE_DIR / "main").mkdir(parents=True, exist_ok=True)  # 关键变量：MAIN 工作区目录
    ORCHESTRATOR_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)  # 关键变量：日志目录
    ORCHESTRATOR_LOG_FILE.touch(exist_ok=True)  # 关键变量：确保日志文件存在

    # 使用模板初始化文件
    _write_text_if_missing(GLOBAL_CONTEXT_FILE, ProjectTemplates.global_context())  # 关键变量：全局上下文模板
    _write_text_if_missing(PROJECT_HISTORY_FILE, ProjectTemplates.project_history())  # 关键变量：历史模板
    _write_text_if_missing(DEV_PLAN_FILE, ProjectTemplates.dev_plan())  # 关键变量：计划模板
    _write_text_if_missing(FINISH_REVIEW_CONFIG_FILE, ProjectTemplates.finish_review_config())  # 关键变量：最终审阅配置模板
    _write_text_if_missing(VERIFICATION_POLICY_FILE, ProjectTemplates.verification_policy())  # 关键变量：验证策略配置模板
    _write_text_if_missing(ACCEPTANCE_SCOPE_FILE, ProjectTemplates.acceptance_scope())  # 关键变量：验收范围定义模板
    _write_text_if_missing(OUT_OF_SCOPE_ISSUES_FILE, ProjectTemplates.out_of_scope_issues())  # 关键变量：范围外问题记录模板
    _write_text_if_missing(DEV_PLAN_ARCHIVED_FILE, ProjectTemplates.dev_plan_archived())  # 关键变量：已归档任务模板

    _write_text_if_missing(TEST_TASK_FILE, ProjectTemplates.task_file("TEST", 0))  # 关键变量：TEST 工单模板
    _write_text_if_missing(DEV_TASK_FILE, ProjectTemplates.task_file("DEV", 0))  # 关键变量：DEV 工单模板
    _write_text_if_missing(REVIEW_TASK_FILE, ProjectTemplates.task_file("REVIEW", 0))  # 关键变量：REVIEW 工单模板

    _write_text_if_missing(REPORT_TEST_FILE, ProjectTemplates.report_file("TEST"))  # 关键变量：TEST 报告模板
    _write_text_if_missing(REPORT_DEV_FILE, ProjectTemplates.report_file("DEV"))  # 关键变量：DEV 报告模板
    _write_text_if_missing(REPORT_REVIEW_FILE, ProjectTemplates.report_file("REVIEW"))  # 关键变量：REVIEW 报告模板
    _write_text_if_missing(REPORT_FINISH_REVIEW_FILE, ProjectTemplates.report_file("FINISH_REVIEW"))  # 关键变量：FINISH_REVIEW 报告模板

    # NOTE: prompts are NOT initialized here.
    # `orchestrator/memory/prompts/subagent_prompt_{main,test,dev,review,summary,finish_review}.md` are the single source of truth and must exist.


def _reset_workspace_task_files(*, iteration: int = 0) -> None:
    """
    new task 时重置各子代理工单（覆盖写入）。
    """
    for agent in CONFIG.agents:  # 关键分支：逐个子代理重置工单
        task_file = CONFIG.get_task_file(agent)  # 关键变量：当前代理工单路径
        task_file.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(
            task_file,
            ProjectTemplates.task_file(agent, iteration),  # 关键变量：工单内容模板
        )


def _reset_report_files() -> None:
    """
    new task 时重置 reports（覆盖写入），避免把旧任务的子代理输出注入到新会话。
    """
    for agent in CONFIG.agents:  # 关键分支：逐个子代理重置报告
        report_file = CONFIG.get_report_file(agent)  # 关键变量：当前代理报告路径
        report_file.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(report_file, ProjectTemplates.report_file(agent))  # 关键变量：报告模板
        REPORT_FINISH_REVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)  # 关键变量：FINISH_REVIEW 报告目录
    _atomic_write_text(
        REPORT_FINISH_REVIEW_FILE,
        ProjectTemplates.report_file("FINISH_REVIEW"),
    )  # 关键变量：FINISH_REVIEW 报告模板
    if REPORT_ITERATION_SUMMARY_FILE.exists():  # 关键分支：清理上轮摘要
        REPORT_ITERATION_SUMMARY_FILE.unlink()
    if REPORT_ITERATION_SUMMARY_HISTORY_FILE.exists():  # 关键分支：清理摘要历史
        REPORT_ITERATION_SUMMARY_HISTORY_FILE.unlink()


def _purge_directory(*, root: Path, keep_dirs: tuple[Path, ...] = ()) -> None:
    if not root.exists():  # 关键分支：目录不存在则创建
        root.mkdir(parents=True, exist_ok=True)
        return
    keep_dirs = tuple(keep_dirs)
    for path in sorted(root.rglob("*"), reverse=True):  # 关键分支：逆序删除，先文件后目录
        if any(path.is_relative_to(keep) for keep in keep_dirs):  # 关键分支：跳过保留目录
            continue
        if path.is_dir():  # 关键分支：目录直接删除
            path.rmdir()
        else:  # 关键分支：文件/链接删除
            path.unlink()


def _reset_workflow_state() -> None:
    """
    将工作流状态重置为“无进度”的初始态（覆盖写入+清理状态文件）。
    """
    _clear_saved_main_state()  # 关键变量：清空 MAIN 会话与迭代
    _clear_dev_plan_stage_file()  # 关键变量：清理 dev_plan 草案
    _purge_directory(root=WORKSPACE_DIR)  # 关键变量：清理 workspace
    _purge_directory(root=REPORTS_DIR)  # 关键变量：清理 reports
    _purge_directory(root=MEMORY_DIR, keep_dirs=(PROMPTS_DIR,))  # 关键变量：清理 memory（保留提示词）
    _ensure_initial_md_files()  # 关键变量：重建初始黑板文件


def _inject_user_inputs_from_history(*, anchor: str, match_mode: str) -> str:
    _require_file(PROJECT_HISTORY_FILE)  # 关键分支：用户输入历史必须存在
    lines = _read_text(PROJECT_HISTORY_FILE).splitlines()  # 关键变量：历史逐行
    anchor_text = anchor.strip()
    if not anchor_text:  # 关键分支：anchor 不能为空
        raise ValueError("finish_review_config.task_goal_anchor is required")
    if match_mode not in {"exact", "prefix_first", "prefix_latest"}:  # 关键分支：模式非法
        raise ValueError(f"finish_review_config.task_goal_anchor_mode invalid: {match_mode!r}")
    if match_mode == "exact":
        matches = [idx for idx, line in enumerate(lines) if line.strip() == anchor_text]
    else:
        matches = [idx for idx, line in enumerate(lines) if line.strip().startswith(anchor_text)]
    if not matches:  # 关键分支：缺失指定任务目标直接失败
        raise RuntimeError(f"Missing required task goal heading prefix: {anchor_text!r}")
    if match_mode == "exact" and len(matches) > 1:  # 关键分支：精确匹配不允许多条
        raise RuntimeError(f"Multiple task goal headings matched anchor prefix: {anchor_text!r}")
    if match_mode == "prefix_latest":
        start_idx = matches[-1]
    else:
        start_idx = matches[0]
    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):  # 关键分支：查找下一个标题
        if lines[idx].startswith("## "):
            end_idx = idx
            break
    content = "\n".join(lines[start_idx:end_idx]).rstrip()
    label = f"{_rel_path(PROJECT_HISTORY_FILE)} (user_inputs_only)"
    header = f"============= Injected File: {label} ============="
    footer = f"============= End Injected File: {label} ============="
    return "\n".join([header, content, footer])


def _load_finish_review_config() -> dict[str, object]:
    _require_file(FINISH_REVIEW_CONFIG_FILE)  # 关键分支：配置必须存在
    raw = _read_text(FINISH_REVIEW_CONFIG_FILE).strip()  # 关键变量：配置原文
    if not raw:  # 关键分支：空配置直接失败
        raise RuntimeError(f"Empty finish_review_config: {_rel_path(FINISH_REVIEW_CONFIG_FILE)}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:  # 关键分支：非法 JSON
        raise ValueError(f"finish_review_config JSON 解析失败: {_rel_path(FINISH_REVIEW_CONFIG_FILE)}: {exc}") from exc
    if not isinstance(payload, dict):  # 关键分支：必须为对象
        raise ValueError("finish_review_config must be a JSON object")
    return payload


def _resolve_finish_review_path(*, value: str, expect_dir: bool) -> Path:
    if not isinstance(value, str) or not value.strip():  # 关键分支：路径不能为空
        raise ValueError("finish_review_config contains empty path")
    raw = Path(value)
    if raw.is_absolute():  # 关键分支：禁止绝对路径
        raise ValueError(f"finish_review_config path must be project-relative: {value!r}")
    resolved = (PROJECT_ROOT / raw).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as exc:  # 关键分支：路径越界
        raise ValueError(f"finish_review_config path is outside project root: {value!r}") from exc
    if expect_dir:
        if not resolved.is_dir():  # 关键分支：目录必须存在
            raise FileNotFoundError(f"Missing code_root directory: {_rel_path(resolved)}")
    else:
        if not resolved.is_file():  # 关键分支：文件必须存在
            raise FileNotFoundError(f"Missing doc file: {_rel_path(resolved)}")
    return resolved


def _parse_finish_review_config() -> tuple[str, str, list[Path], Path]:
    payload = _load_finish_review_config()
    anchor = payload.get("task_goal_anchor")
    if not isinstance(anchor, str) or not anchor.strip():  # 关键分支：anchor 必须为非空字符串
        raise ValueError("finish_review_config.task_goal_anchor must be a non-empty string")
    match_mode = payload.get("task_goal_anchor_mode", "prefix_latest")
    if not isinstance(match_mode, str) or not match_mode.strip():  # 关键分支：模式必须为非空字符串
        raise ValueError("finish_review_config.task_goal_anchor_mode must be a non-empty string")
    docs = payload.get("docs")
    if not isinstance(docs, list) or not docs:  # 关键分支：docs 必须为非空列表
        raise ValueError("finish_review_config.docs must be a non-empty list")
    doc_paths: list[Path] = []
    for item in docs:
        if not isinstance(item, str):  # 关键分支：每项必须为字符串
            raise ValueError("finish_review_config.docs entries must be strings")
        doc_paths.append(_resolve_finish_review_path(value=item, expect_dir=False))
    code_root = payload.get("code_root")
    if not isinstance(code_root, str) or not code_root.strip():  # 关键分支：code_root 必须为非空字符串
        raise ValueError("finish_review_config.code_root must be a non-empty string")
    code_root_path = _resolve_finish_review_path(value=code_root, expect_dir=True)
    return anchor.strip(), match_mode.strip(), doc_paths, code_root_path


def _guarded_blackboard_paths() -> list[Path]:
    return [
        GLOBAL_CONTEXT_FILE,  # 关键变量：全局上下文
        PROJECT_HISTORY_FILE,  # 关键变量：历史记录
        DEV_PLAN_FILE,  # 关键变量：开发计划
        ACCEPTANCE_SCOPE_FILE,  # 关键变量：验收范围（范围锁定）
        OUT_OF_SCOPE_ISSUES_FILE,  # 关键变量：范围外问题记录
        DEV_PLAN_ARCHIVED_FILE,  # 关键变量：已归档任务
        FINISH_REVIEW_CONFIG_FILE,  # 关键变量：最终审阅配置
        DEV_PLAN_STAGED_FILE,  # 关键变量：dev_plan 暂存
        TEST_TASK_FILE,  # 关键变量：TEST 工单
        DEV_TASK_FILE,  # 关键变量：DEV 工单
        REVIEW_TASK_FILE,  # 关键变量：REVIEW 工单
        REPORT_TEST_FILE,  # 关键变量：TEST 报告
        REPORT_DEV_FILE,  # 关键变量：DEV 报告
        REPORT_REVIEW_FILE,  # 关键变量：REVIEW 报告
        REPORT_FINISH_REVIEW_FILE,  # 关键变量：FINISH_REVIEW 报告
        REPORT_MAIN_DECISION_FILE,  # 关键变量：MAIN 决策输出
        REPORT_ITERATION_SUMMARY_FILE,  # 关键变量：每轮摘要输出
        REPORT_ITERATION_SUMMARY_HISTORY_FILE,  # 关键变量：摘要历史输出
    ]


_RESUME_SCHEMA_VERSION = 1  # 关键变量：续跑状态版本


def _resume_blackboard_paths(*, phase: str, next_agent: str) -> tuple[list[Path], list[Path]]:
    required = [PROJECT_HISTORY_FILE, DEV_PLAN_FILE, REPORT_MAIN_DECISION_FILE]
    if next_agent in {"TEST", "DEV", "REVIEW"}:
        required.append(_task_file_for_agent(next_agent))
        if phase == "after_subagent":
            required.append(_resolve_report_path(next_agent))
    optional = [DEV_PLAN_STAGED_FILE]
    return required, optional


def _resume_blackboard_digest(*, phase: str, next_agent: str) -> str:
    required, optional = _resume_blackboard_paths(phase=phase, next_agent=next_agent)
    for path in required:
        _require_file(path)
    snapshot = _snapshot_files([*required, *optional])
    parts: list[str] = []
    for path in sorted(snapshot, key=lambda p: str(p)):
        digest = snapshot[path] or "MISSING"
        parts.append(f"{_rel_path(path)}:{digest}")
    return _sha256_text("\n".join(parts))


_RESUME_PHASES = {"after_main", "after_subagent", "awaiting_user"}  # 关键变量：可恢复阶段
_RESUME_AGENTS = {"TEST", "DEV", "REVIEW", "USER"}  # 关键变量：可恢复代理

_MAX_STAGE_RETRIES = 2  # 关键变量：可重试次数
_BACKOFF_BASE_SECONDS = 1.0  # 关键变量：退避基数


def _sleep_backoff(*, label: str, attempt: int) -> None:
    delay = _BACKOFF_BASE_SECONDS * (2 ** attempt)
    _append_log_line(
        f"orchestrator: {label} retry backoff={delay:.1f}s attempt={attempt + 1}\n"
    )
    time.sleep(delay)



def _write_resume_state(
    *,
    iteration: int,
    phase: str,
    next_agent: str,
    main_session_id: str,
    subagent_session_id: str | None,
) -> None:
    if iteration < 1:  # 关键分支：迭代号必须为正
        raise ValueError(f"续跑 iteration 无效：{iteration}")
    if phase not in _RESUME_PHASES:  # 关键分支：非法阶段
        raise ValueError(f"续跑 phase 无效：{phase!r}")
    if next_agent not in _RESUME_AGENTS:  # 关键分支：非法代理
        raise ValueError(f"续跑 next_agent 无效：{next_agent!r}")
    _validate_session_id(main_session_id)
    if phase == "awaiting_user" and next_agent != "USER":  # 关键分支：阶段与代理不一致
        raise ValueError("续跑 awaiting_user 必须搭配 next_agent=USER")
    if phase in {"after_main", "after_subagent"} and next_agent == "USER":  # 关键分支：阶段与代理不一致
        raise ValueError("续跑 after_main/after_subagent 不能使用 next_agent=USER")
    if phase == "after_subagent":  # 关键分支：子代理阶段必须有会话 id
        if not isinstance(subagent_session_id, str) or not subagent_session_id.strip():
            raise ValueError("续跑 after_subagent 需要 subagent_session_id")
        _validate_session_id(subagent_session_id)
    else:
        if subagent_session_id is not None:  # 关键分支：非子代理阶段禁止 subagent_session_id
            raise ValueError("续跑 subagent_session_id 仅允许在 after_subagent 阶段出现")

    blackboard_digest = _resume_blackboard_digest(phase=phase, next_agent=next_agent)
    payload = {
        "schema_version": _RESUME_SCHEMA_VERSION,
        "iteration": iteration,
        "phase": phase,
        "next_agent": next_agent,
        "main_session_id": main_session_id,
        "subagent_session_id": subagent_session_id,
        "blackboard_digest": blackboard_digest,
    }
    RESUME_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(RESUME_STATE_FILE, json.dumps(payload, ensure_ascii=True) + "\n")


def _clear_resume_state() -> None:
    if RESUME_STATE_FILE.exists():  # 关键分支：存在才删除
        RESUME_STATE_FILE.unlink()


def _load_resume_state() -> ResumeState | None:
    if not RESUME_STATE_FILE.exists():  # 关键分支：无文件则直接返回
        return None
    raw = _read_text(RESUME_STATE_FILE).strip()  # 关键变量：状态原文
    if not raw:  # 关键分支：空文件直接失败
        raise ValueError(f"续跑状态文件为空：{_rel_path(RESUME_STATE_FILE)}")
    try:  # 关键分支：解析 JSON
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:  # 关键分支：非法 JSON
        raise ValueError(f"续跑状态 JSON 解析失败: {_rel_path(RESUME_STATE_FILE)}: {exc}") from exc
    if not isinstance(payload, dict):  # 关键分支：必须为对象
        raise ValueError("续跑状态必须是 JSON 对象")

    schema_version = payload.get("schema_version")
    iteration = payload.get("iteration")
    phase = payload.get("phase")
    next_agent = payload.get("next_agent")
    main_session_id = payload.get("main_session_id")
    subagent_session_id = payload.get("subagent_session_id")
    blackboard_digest = payload.get("blackboard_digest")

    if not isinstance(iteration, int) or iteration < 1:
        raise ValueError(f"续跑 iteration 无效：{iteration!r}")
    if phase not in _RESUME_PHASES:
        raise ValueError(f"续跑 phase 无效：{phase!r}")
    if next_agent not in _RESUME_AGENTS:
        raise ValueError(f"续跑 next_agent 无效：{next_agent!r}")
    if schema_version != _RESUME_SCHEMA_VERSION:
        raise ValueError(f"续跑状态版本无效：{schema_version!r}")
    if not isinstance(blackboard_digest, str) or not blackboard_digest.strip():
        raise ValueError("续跑 blackboard_digest 无效")
    if not isinstance(main_session_id, str) or not main_session_id.strip():
        raise ValueError("续跑 main_session_id 必须为非空字符串")
    _validate_session_id(main_session_id)

    if phase == "awaiting_user" and next_agent != "USER":
        raise ValueError("续跑 awaiting_user 必须搭配 next_agent=USER")
    if phase in {"after_main", "after_subagent"} and next_agent == "USER":
        raise ValueError("续跑 after_main/after_subagent 不能使用 next_agent=USER")

    if phase == "after_subagent":
        if not isinstance(subagent_session_id, str) or not subagent_session_id.strip():
            raise ValueError("续跑 after_subagent 需要 subagent_session_id")
        _validate_session_id(subagent_session_id)
    else:
        if subagent_session_id is not None:
            raise ValueError("续跑 subagent_session_id 仅允许在 after_subagent 阶段出现")

    expected_digest = _resume_blackboard_digest(phase=phase, next_agent=next_agent)
    if blackboard_digest != expected_digest:
        raise RuntimeError(
            "续跑状态与黑板不一致："
            f"state={blackboard_digest!r}, current={expected_digest!r}"
        )

    return {
        "schema_version": schema_version,
        "iteration": iteration,
        "phase": phase,
        "next_agent": next_agent,
        "main_session_id": main_session_id,
        "subagent_session_id": subagent_session_id,
        "blackboard_digest": blackboard_digest,
    }


def _history_has_user_decision(*, iteration: int) -> bool:
    _require_file(PROJECT_HISTORY_FILE)  # 关键分支：历史必须存在
    needle = f"## User Decision (Iteration {iteration}):"  # 关键变量：用户决策标识
    return needle in _read_text(PROJECT_HISTORY_FILE)


def _resolve_report_path(next_agent: str) -> Path:
    return CONFIG.get_report_file(next_agent)


def _run_subagent_stage(
    *,
    iteration: int,
    next_agent: str,
    sandbox_mode: str,
    approval_policy: str,
    ui: UiRuntime | None,
    control: RunControl | None,
) -> tuple[str, Path, Path]:
    if ui is not None:  # 关键分支：UI 更新子代理运行态
        ui.state.update(phase=f"running_{next_agent.lower()}", current_agent=next_agent)
    injected_global_context = _inject_file(GLOBAL_CONTEXT_FILE)  # 关键变量：注入全局上下文
    injected_dev_plan = _inject_file(DEV_PLAN_FILE)  # 关键变量：注入 dev_plan（REVIEW 需要）
    injected_report_test = _inject_file(REPORT_TEST_FILE)  # 关键变量：注入 TEST 报告（REVIEW 需要）
    injected_report_dev = _inject_file(REPORT_DEV_FILE)  # 关键变量：注入 DEV 报告（REVIEW 需要）
    task_file = _task_file_for_agent(next_agent)  # 关键变量：当前子代理工单
    injected_task = _inject_file(task_file)  # 关键变量：注入工单内容
    report_path = _resolve_report_path(next_agent)  # 关键变量：报告路径

    sub_prompt = "\n\n".join(
        [
            _load_system_prompt(next_agent.lower()),
            injected_global_context,
            injected_dev_plan if next_agent == "REVIEW" else "",  # 关键分支：仅 REVIEW 注入 dev_plan
            injected_report_test if next_agent == "REVIEW" else "",
            injected_report_dev if next_agent == "REVIEW" else "",
            injected_task,
            f"请读取 `{_rel_path(task_file)}` 获取你的唯一任务指令并严格执行。",
            "重要：禁止直接写入 `orchestrator/reports/`（不要使用任何工具/命令写 `orchestrator/reports/report_*.md`）。",
            f"请把“完整报告”作为你最后的输出；编排器会自动保存你的最后一条消息到：`{_rel_path(report_path)}`。",
        ]
    )
    sub_guard_paths = [path for path in _guarded_blackboard_paths() if path != report_path]  # 关键变量：子代理可写排除清单

    attempt = 0
    while True:  # 关键分支：临时错误允许重试
        try:
            sub_guard_before = _snapshot_files(sub_guard_paths)  # 关键变量：子代理运行前快照
            sub_run = _run_codex_exec(
                prompt=sub_prompt,
                output_last_message=report_path,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                label=next_agent,
                control=control,
            )
            _assert_files_unchanged(sub_guard_before, label=next_agent)  # 关键分支：防止子代理越权写入
            try:
                _validate_report_iteration(report_path=report_path, iteration=iteration)  # 关键分支：报告必须标注迭代
                _validate_report_consistency(report_path=report_path, agent=next_agent)  # 关键分支：报告结论一致性校验
            except RuntimeError as exc:
                raise TemporaryError(f"{next_agent} 报告校验失败: {exc}") from exc
            sub_session_id = sub_run["session_id"]  # 关键变量：子代理会话 id
            if sub_session_id is None:  # 关键分支：必须拿到会话 id
                raise TemporaryError(f"Failed to capture {next_agent} session id from codex output")
            _backup_subagent_artifacts(
                agent=next_agent,
                session_id=sub_session_id,
                report_file=report_path,
                task_file=task_file,
            )
            return sub_session_id, task_file, report_path
        except TemporaryError as exc:
            if attempt >= _MAX_STAGE_RETRIES:
                raise
            _append_log_line(
                f"orchestrator: {next_agent} retry due to {exc} (attempt {attempt + 1}/{_MAX_STAGE_RETRIES})\n"
            )
            _sleep_backoff(label=next_agent, attempt=attempt)
            attempt += 1



def _run_main_decision_stage(
    *,
    prompt: str,
    guard_paths: list[Path],
    label: str,
    sandbox_mode: str,
    approval_policy: str,
    control: RunControl | None,
    resume_session_id: str | None,
) -> tuple[MainOutput, str | None]:
    retry_notice = (
        f"上次 {label} 输出不符合 JSON/校验要求。"
        "请仅输出提示词要求的完整 JSON，禁止附加任何解释文本。"
    )
    active_session_id = resume_session_id
    attempt = 0
    while True:  # 关键分支：临时错误允许重试
        attempt_prompt = prompt if attempt == 0 else f"{prompt}\n\n{retry_notice}"
        try:
            guard_before = _snapshot_files(guard_paths)  # 关键变量：运行前快照
            run = _run_codex_exec(
                prompt=attempt_prompt,
                output_last_message=REPORT_MAIN_DECISION_FILE,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                label=label,
                control=control,
                resume_session_id=active_session_id,
            )
            if active_session_id is None and run["session_id"] is not None:
                active_session_id = run["session_id"]
            _assert_files_unchanged(guard_before, label=label)  # 关键分支：防止越权写入
            try:
                output = _parse_main_output(run["last_message"])  # 关键变量：解析 MAIN 输出
            except ValueError as exc:
                raise TemporaryError(f"{label} JSON 校验失败: {exc}") from exc
            return output, active_session_id
        except TemporaryError as exc:
            if attempt >= _MAX_STAGE_RETRIES:
                raise
            _append_log_line(
                f"orchestrator: {label} retry due to {exc} (attempt {attempt + 1}/{_MAX_STAGE_RETRIES})\n"
            )
            _sleep_backoff(label=label, attempt=attempt)
            attempt += 1



def _run_finish_review_stage(
    *,
    iteration: int,
    sandbox_mode: str,
    approval_policy: str,
    ui: UiRuntime | None,
    control: RunControl | None,
) -> str:
    if ui is not None:  # 关键分支：UI 更新 FINISH_REVIEW 运行态
        ui.state.update(phase="running_finish_review", current_agent="FINISH_REVIEW")

    # 注入 acceptance_scope.json（范围锁定：缺失即快速失败）
    injected_acceptance_scope = _inject_file(ACCEPTANCE_SCOPE_FILE)

    anchor, match_mode, doc_paths, code_root_path = _parse_finish_review_config()  # 关键变量：最终审阅配置
    injected_user_inputs = _inject_user_inputs_from_history(anchor=anchor, match_mode=match_mode)  # 关键变量：注入用户输入快照

    # 文档摘要（而非完整内容）- 减少上下文
    doc_summaries = []
    for doc_path in doc_paths:
        summary = f"[Document: {_rel_path(doc_path)}]\n(Full content available via read_file tool if needed)"
        doc_summaries.append(summary)

    code_root_label = _rel_path(code_root_path)  # 关键变量：代码根目录展示

    finish_review_prompt_parts = [
        _load_system_prompt("finish_review"),
    ]

    finish_review_prompt_parts.append(injected_acceptance_scope)

    finish_review_prompt_parts.extend([
        injected_user_inputs,
        *doc_summaries,
        f"[code_root]: {code_root_label}",
        f"[iteration]: {iteration}",
    ])

    finish_review_prompt_parts.append(
        "重要：只检查 acceptance_scope.json 中定义的验收标准。"
        "范围外问题记录到 out_of_scope_issues 部分，但不影响 PASS/FAIL。"
    )

    finish_review_prompt_parts.append(
        f'请把"完整报告"作为你最后的输出；编排器会自动保存到：`{_rel_path(REPORT_FINISH_REVIEW_FILE)}`。'
    )

    finish_review_prompt = "\n\n".join(finish_review_prompt_parts)

    finish_guard_paths = [
        path for path in _guarded_blackboard_paths() if path != REPORT_FINISH_REVIEW_FILE
    ]  # 关键变量：FINISH_REVIEW 可写排除清单

    attempt = 0
    while True:  # 关键分支：临时错误允许重试
        try:
            finish_guard_before = _snapshot_files(finish_guard_paths)  # 关键变量：FINISH_REVIEW 运行前快照
            finish_run = _run_codex_exec(
                prompt=finish_review_prompt,
                output_last_message=REPORT_FINISH_REVIEW_FILE,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                label="FINISH_REVIEW",
                control=control,
            )
            _assert_files_unchanged(finish_guard_before, label="FINISH_REVIEW")  # 关键分支：防止越权写入
            try:
                _validate_report_iteration(report_path=REPORT_FINISH_REVIEW_FILE, iteration=iteration)  # 关键分支：报告必须标注迭代
                _validate_report_consistency(report_path=REPORT_FINISH_REVIEW_FILE, agent="FINISH_REVIEW")  # 关键分支：报告结论一致性校验
            except RuntimeError as exc:
                raise TemporaryError(f"FINISH_REVIEW 报告校验失败: {exc}") from exc
            finish_session_id = finish_run["session_id"]  # 关键变量：会话 id
            if finish_session_id is None:  # 关键分支：必须拿到会话 id
                raise TemporaryError("Failed to capture FINISH_REVIEW session id from codex output")
            return finish_session_id
        except TemporaryError as exc:
            if attempt >= _MAX_STAGE_RETRIES:
                raise
            _append_log_line(
                f"orchestrator: FINISH_REVIEW retry due to {exc} (attempt {attempt + 1}/{_MAX_STAGE_RETRIES})\n"
            )
            _sleep_backoff(label="FINISH_REVIEW", attempt=attempt)
            attempt += 1



def _run_summary_stage(
    *,
    iteration: int,
    next_agent: str,
    main_session_id: str | None,
    subagent_session_id: str,
    task_file: Path,
    report_path: Path,
    sandbox_mode: str,
    approval_policy: str,
    ui: UiRuntime | None,
    control: RunControl | None,
) -> None:
    if main_session_id is None:  # 关键分支：SUMMARY 必须有 MAIN 会话 id
        raise RuntimeError("Missing MAIN session id before SUMMARY run")
    if ui is not None:  # 关键分支：UI 更新 SUMMARY 运行态
        ui.state.update(phase="running_summary", current_agent="SUMMARY")

    summary_file = REPORT_ITERATION_SUMMARY_FILE  # 关键变量：摘要输出路径
    summary_prompt = "\n\n".join(
        [
            _load_system_prompt("summary"),
            _inject_file(REPORT_MAIN_DECISION_FILE),
            _inject_file(task_file),
            _inject_file(report_path),
            f"[iteration]: {iteration}",
            f"[main_session_id]: {main_session_id}",
            f"[subagent_session_id]: {subagent_session_id}",
            f"[main_decision_file]: {_rel_path(REPORT_MAIN_DECISION_FILE)}",
            f"[task_file]: {_rel_path(task_file)}",
            f"[report_file]: {_rel_path(report_path)}",
            f"[summary_file]: {_rel_path(summary_file)}",
        ]
    )
    summary_guard_paths = [path for path in _guarded_blackboard_paths() if path != summary_file]  # 关键变量：SUMMARY 可写排除清单
    retry_notice = (
        "上次 SUMMARY 输出不符合 JSON/校验要求。"
        "请仅输出符合提示词格式的完整 JSON，禁止附加任何解释文本。"
    )

    attempt = 0
    while True:  # 关键分支：临时错误允许重试
        attempt_prompt = summary_prompt if attempt == 0 else f"{summary_prompt}\n\n{retry_notice}"
        try:
            summary_guard_before = _snapshot_files(summary_guard_paths)  # 关键变量：SUMMARY 运行前快照
            summary_run = _run_codex_exec(
                prompt=attempt_prompt,
                output_last_message=summary_file,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                label="SUMMARY",
                control=control,
            )
            _assert_files_unchanged(summary_guard_before, label="SUMMARY")  # 关键分支：防止 SUMMARY 越权写入
            try:
                summary_output = _parse_iteration_summary(
                    summary_run["last_message"],
                    iteration=iteration,
                    expected_agent=next_agent,
                    main_session_id=main_session_id,
                    subagent_session_id=subagent_session_id,
                    main_decision_file=REPORT_MAIN_DECISION_FILE,
                    task_file=task_file,
                    report_file=report_path,
                    summary_file=summary_file,
                )
            except ValueError as exc:
                raise TemporaryError(f"SUMMARY JSON 校验失败: {exc}") from exc
            summary_history = _append_iteration_summary_history(
                history_file=REPORT_ITERATION_SUMMARY_HISTORY_FILE,
                summary=summary_output,
            )
            _append_log_line(f"orchestrator: summary_written path={_rel_path(summary_file)}\n")
            if ui is not None:  # 关键分支：UI 更新摘要
                ui.state.update(
                    last_iteration_summary=summary_output,
                    last_summary_path=_rel_path(summary_file),
                    summary_history=summary_history,
                )
            return
        except TemporaryError as exc:
            if attempt >= _MAX_STAGE_RETRIES:
                raise
            _append_log_line(
                f"orchestrator: SUMMARY retry due to {exc} (attempt {attempt + 1}/{_MAX_STAGE_RETRIES})\n"
            )
            _sleep_backoff(label="SUMMARY", attempt=attempt)
            attempt += 1



def _resume_pending_iteration(
    *,
    last_iteration: int,
    main_session_id: str | None,
    sandbox_mode: str,
    approval_policy: str,
    ui: UiRuntime | None,
    control: RunControl | None,
) -> None:
    resume_state = _load_resume_state()
    if resume_state is None:  # 关键分支：无恢复状态
        return

    iteration = resume_state["iteration"]
    phase = resume_state["phase"]
    next_agent = resume_state["next_agent"]
    resume_main_session_id = resume_state["main_session_id"]
    subagent_session_id = resume_state["subagent_session_id"]

    if last_iteration != iteration:  # 关键分支：状态不一致直接失败
        raise RuntimeError(f"续跑 iteration 不匹配：state={iteration}, saved={last_iteration}")
    if main_session_id != resume_main_session_id:  # 关键分支：会话不一致直接失败
        raise RuntimeError("续跑 main_session_id 不匹配")

    main_output = _parse_main_output(_read_text(REPORT_MAIN_DECISION_FILE))  # 关键变量：解析 MAIN 输出
    decision = main_output["decision"]  # 关键变量：决策字段
    if decision["next_agent"] != next_agent:  # 关键分支：决策不一致直接失败
        raise RuntimeError(
            f"续跑 next_agent 不匹配：state={next_agent!r}, decision={decision['next_agent']!r}"
        )

    if next_agent == "USER":  # 关键分支：恢复等待用户决策
        if phase != "awaiting_user":
            raise RuntimeError(f"续跑 USER 阶段不匹配：{phase!r}")
        if _history_has_user_decision(iteration=iteration):  # 关键分支：已记录则清理并返回
            _clear_resume_state()
            return
        _append_log_line(f"orchestrator: 续跑等待用户 iter={iteration}\n")
        _prompt_user_for_decision(iteration=iteration, decision=decision, ui=ui)
        _clear_resume_state()
        return

    if phase == "after_main":  # 关键分支：补跑子代理与摘要
        _append_log_line(f"orchestrator: 续跑子代理 iter={iteration} agent={next_agent}\n")
        sub_session_id, task_file, report_path = _run_subagent_stage(
            iteration=iteration,
            next_agent=next_agent,
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
            ui=ui,
            control=control,
        )
        _write_resume_state(
            iteration=iteration,
            phase="after_subagent",
            next_agent=next_agent,
            main_session_id=resume_main_session_id,
            subagent_session_id=sub_session_id,
        )
        _run_summary_stage(
            iteration=iteration,
            next_agent=next_agent,
            main_session_id=resume_main_session_id,
            subagent_session_id=sub_session_id,
            task_file=task_file,
            report_path=report_path,
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
            ui=ui,
            control=control,
        )
        _clear_resume_state()
        return

    if phase != "after_subagent":  # 关键分支：未知阶段
        raise RuntimeError(f"续跑阶段无效：{phase!r}")
    if not isinstance(subagent_session_id, str):
        raise RuntimeError("续跑 after_subagent 缺少 subagent_session_id")

    task_file = _task_file_for_agent(next_agent)
    task_content = _read_text(task_file)
    _validate_task_content(iteration=iteration, expected_agent=next_agent, task=task_content)
    report_path = _resolve_report_path(next_agent)
    _validate_report_iteration(report_path=report_path, iteration=iteration)

    if REPORT_ITERATION_SUMMARY_FILE.exists():  # 关键分支：若已有摘要则先校验
        raw_summary = _read_text(REPORT_ITERATION_SUMMARY_FILE).strip()
        if not raw_summary:
            raise RuntimeError(f"摘要文件为空：{_rel_path(REPORT_ITERATION_SUMMARY_FILE)}")
        try:
            summary_payload = json.loads(raw_summary)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"summary JSON 解析失败: {_rel_path(REPORT_ITERATION_SUMMARY_FILE)}: {exc}"
            ) from exc
        if not isinstance(summary_payload, dict):
            raise RuntimeError("摘要 JSON 必须是对象")
        summary_iteration = summary_payload.get("iteration")
        if isinstance(summary_iteration, int) and summary_iteration == iteration:
            summary_output = _parse_iteration_summary(
                raw_summary,
                iteration=iteration,
                expected_agent=next_agent,
                main_session_id=resume_main_session_id,
                subagent_session_id=subagent_session_id,
                main_decision_file=REPORT_MAIN_DECISION_FILE,
                task_file=task_file,
                report_file=report_path,
                summary_file=REPORT_ITERATION_SUMMARY_FILE,
            )
            summary_history = _load_iteration_summary_history(
                REPORT_ITERATION_SUMMARY_HISTORY_FILE
            )
            if not summary_history or summary_history[-1]["iteration"] != iteration:
                summary_history = _append_iteration_summary_history(
                    history_file=REPORT_ITERATION_SUMMARY_HISTORY_FILE,
                    summary=summary_output,
                )
            if ui is not None:  # 关键分支：UI 更新摘要
                ui.state.update(
                    last_iteration_summary=summary_output,
                    last_summary_path=_rel_path(REPORT_ITERATION_SUMMARY_FILE),
                    summary_history=summary_history,
                )
            _clear_resume_state()
            return

    _append_log_line(f"orchestrator: 续跑摘要 iter={iteration} agent={next_agent}\n")
    _run_summary_stage(
        iteration=iteration,
        next_agent=next_agent,
        main_session_id=resume_main_session_id,
        subagent_session_id=subagent_session_id,
        task_file=task_file,
        report_path=report_path,
        sandbox_mode=sandbox_mode,
        approval_policy=approval_policy,
        ui=ui,
        control=control,
    )
    _clear_resume_state()


def _prepare_main_output(*, iteration: int, output: MainOutput) -> tuple[str, str | None, str | None]:
    decision = output["decision"]  # 关键变量：MAIN 决策对象
    history_entry = _validate_history_append(iteration=iteration, entry=output["history_append"])  # 关键变量：历史追加内容
    dev_plan_next = output.get("dev_plan_next")  # 关键变量：计划草案（可为空）
    if dev_plan_next is not None:  # 关键分支：存在草案则先校验
        _validate_dev_plan_text(text=dev_plan_next, source=DEV_PLAN_STAGED_FILE)  # 关键变量：按规则校验

    task_content = None  # 关键变量：工单内容（可为空）
    next_agent = decision["next_agent"]  # 关键变量：下一步代理
    if next_agent in {"TEST", "DEV", "REVIEW"}:  # 关键分支：子代理必须有工单
        task = output.get("task")  # 关键变量：RAW 工单文本
        if task is None:  # 关键分支：缺工单直接失败
            raise RuntimeError(f"Missing task for next_agent={next_agent}")
        task_content = _validate_task_content(iteration=iteration, expected_agent=next_agent, task=task)  # 关键变量：校验后的工单

    return history_entry, task_content, dev_plan_next


def _build_main_prompt(
    *,
    iteration: int,
    user_task: str,
    history_window_iterations: int,
    history_window_max_tokens: int | None,
    extra_instructions: list[str] | None = None,
) -> str:
    injected_global_context = _inject_file(GLOBAL_CONTEXT_FILE)  # 关键变量：注入全局上下文
    injected_project_history = _inject_project_history_recent(
        last_iterations=history_window_iterations,
        max_tokens=history_window_max_tokens,
    )  # 关键变量：注入历史窗口
    injected_dev_plan = _inject_file(DEV_PLAN_FILE)  # 关键变量：注入 dev_plan
    injected_report_test = _inject_file(REPORT_TEST_FILE)  # 关键变量：注入 TEST 报告
    injected_report_dev = _inject_file(REPORT_DEV_FILE)  # 关键变量：注入 DEV 报告
    injected_report_review = _inject_file(REPORT_REVIEW_FILE)  # 关键变量：注入 REVIEW 报告
    injected_report_finish_review = _inject_file(REPORT_FINISH_REVIEW_FILE)  # 关键变量：注入 FINISH_REVIEW 报告
    parts = [
        _load_system_prompt("main"),
        injected_global_context,
        injected_project_history,
        injected_dev_plan,
        injected_report_test,
        injected_report_dev,
        injected_report_review,
        injected_report_finish_review,
        f"[iteration]: {iteration}",
        f"[user_task]: {user_task}" if user_task else "[user_task]: (use orchestrator/memory/global_context.md)",
    ]
    if extra_instructions:
        parts.extend(extra_instructions)
    parts.append('请严格按提示词中的"必须执行的动作（强制顺序）"完成：生成 history_append/task/dev_plan_next，并最后输出 JSON。')
    return "\n\n".join(parts)


def _build_finish_check_prompt(
    *,
    iteration: int,
    user_task: str,
    is_ready: bool,
    check_msg: str,
) -> str:
    """
    构建简化的 FINISH_CHECK 提示词，仅包含决策所需的最小上下文。
    相比完整的 _build_main_prompt，省略了 TEST/DEV/REVIEW 报告和完整的 project_history。
    """
    # 读取 acceptance_scope 摘要（而非完整内容）
    scope = json.loads(_read_text(ACCEPTANCE_SCOPE_FILE))
    if not isinstance(scope, dict):
        raise RuntimeError("acceptance_scope.json must be a JSON object")
    criteria = scope.get("acceptance_criteria")
    if not isinstance(criteria, list):
        raise RuntimeError("acceptance_scope.json.acceptance_criteria must be a list")
    scope_summary = f"验收范围: {len(criteria)} 项标准（详见 acceptance_scope.json）"

    # dev_plan 状态摘要（计数，避免注入过长）
    dev_plan_text = _read_text(DEV_PLAN_FILE)
    status_counts = {
        "VERIFIED": dev_plan_text.count("status: VERIFIED"),
        "DONE": dev_plan_text.count("status: DONE"),
        "DOING": dev_plan_text.count("status: DOING"),
        "BLOCKED": dev_plan_text.count("status: BLOCKED"),
        "TODO": dev_plan_text.count("status: TODO"),
    }
    dev_plan_summary = f"任务状态计数: {status_counts}"

    # 读取并摘要 FINISH_REVIEW 结论
    finish_review_text = _read_text(REPORT_FINISH_REVIEW_FILE)
    finish_review_verdict = _extract_finish_review_verdict(finish_review_text)

    # 构建精简的系统提示（仅保留 FINISH_CHECK 相关规则）
    finish_check_system_prompt = """你是 MAIN 代理，正在执行 FINISH_CHECK 复核。

## 任务
根据 FINISH_REVIEW 的结论，决定是否最终完成任务。

## 决策规则
1. 若 FINISH_REVIEW 结论为 PASS 且满足 readiness（所有非 TODO 任务均 VERIFIED）：输出 `FINISH`
2. 若 FINISH_REVIEW 结论为 FAIL/BLOCKED：
   - 采纳：根据问题类型选择 DEV/TEST/REVIEW 并生成工单
   - 忽略：输出 FINISH 并在 history_append 写明 `finish_review_override: ignore` 与理由
3. 若 readiness 不满足（存在 DONE/DOING/BLOCKED）：禁止 FINISH，必须派发子代理

## 输出格式（必须严格遵守）
输出 **1 行 JSON**（无其它文本）：
- 采纳 FAIL 派发 DEV：`{"next_agent":"DEV","reason":"...","history_append":"## Iteration N:\\n...","task":"# Current Task (Iteration N)\\nassigned_agent: DEV\\n...","dev_plan_next":null}`
- 采纳 FAIL 派发 REVIEW：`{"next_agent":"REVIEW","reason":"...","history_append":"...","task":"...","dev_plan_next":null}`
- 忽略 FAIL 直接完成：`{"next_agent":"FINISH","reason":"...","history_append":"## Iteration N:\\n...\\nfinish_review_override: ignore\\n理由：...","task":null,"dev_plan_next":null}`
- 全部通过直接完成：`{"next_agent":"FINISH","reason":"...","history_append":"...","task":null,"dev_plan_next":null}`

**重要**：你必须输出完整 JSON，禁止空输出。"""

    # 构建上下文部分
    context_parts = [
        f"[iteration]: {iteration}",
        f"[user_task]: {user_task}" if user_task else "[user_task]: (use orchestrator/memory/global_context.md)",
        "",
        "## 验收范围摘要",
        scope_summary,
        "",
        "## Dev Plan 任务状态摘要",
        dev_plan_summary,
        "",
        "## FINISH_REVIEW 结论摘要",
        finish_review_verdict,
    ]

    # 添加警告信息
    if not is_ready:
        context_parts.append("")
        context_parts.append(f"⚠️ 警告：{check_msg}")

    # 组装最终提示词
    parts = [
        finish_check_system_prompt,
        "\n".join(context_parts),
        "请根据以上信息输出 JSON 决策。",
    ]
    return "\n\n".join(parts)


def _generate_legacy_issues_report(
    *,
    iteration: int,
    blockers: list[str],
    dev_plan_file: Path,
    out_of_scope_file: Path,
) -> None:
    """
    生成遗留问题报告（强制完成时）。
    """
    from datetime import datetime

    timestamp = datetime.now().isoformat(timespec="seconds")
    lines: list[str] = [
        f"# Legacy Issues Report (Iteration {iteration})",
        f"Generated at: {timestamp}",
        "",
        "## 强制完成原因",
        f"已达到最大 FINISH 尝试次数（{MAX_FINISH_ATTEMPTS}），但仍存在阻塞项：",
        "",
    ]

    for idx, blocker in enumerate(blockers, start=1):
        lines.append(f"{idx}. {blocker}")

    lines.extend(["", "## Dev Plan 未完成任务", ""])

    dev_plan_text = _read_text(dev_plan_file)
    current_task: str | None = None
    current_status: str | None = None
    for raw in dev_plan_text.splitlines():
        line = raw.strip()
        if line.startswith("### "):
            current_task = line[4:].strip()
            current_status = None
            continue
        if current_task is None:
            continue
        if line.startswith("status:") or line.startswith("- status:"):
            current_status = line.split(":", 1)[1].strip()
            if current_status != "VERIFIED":
                lines.append(f"- {current_task}: {current_status}")
            current_task = None
            current_status = None

    lines.extend(["", "## 范围外问题", ""])
    _require_file(out_of_scope_file)
    lines.append(_read_text(out_of_scope_file).rstrip())

    lines.extend(
        [
            "",
            "## 建议",
            "",
            "1. 审查未完成任务，评估是否需要在后续迭代补齐并重新验收",
            "2. 审查范围外问题，决定是否纳入下一阶段验收范围（更新 acceptance_scope.json）",
            "3. 如需继续完善，建议创建新任务并重新定义验收范围",
            "",
        ]
    )

    LEGACY_ISSUES_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(LEGACY_ISSUES_REPORT_FILE, "\n".join(lines))
    _append_log_line(
        f"orchestrator: legacy_issues_report written to {_rel_path(LEGACY_ISSUES_REPORT_FILE)}\n"
    )
    print(f"遗留问题报告已生成: {_rel_path(LEGACY_ISSUES_REPORT_FILE)}")


def _calculate_adaptive_history_window(
    *,
    iteration: int,
    dev_plan_size: int,
    base_window: int,
    min_window: int,
    max_window: int,
) -> int:
    """
    根据当前状态动态调整 history_window，避免上下文累积导致 MAIN prompt 过载。
    """
    if base_window < 1:
        raise ValueError("base_window must be >= 1")
    if min_window < 1:
        raise ValueError("min_window must be >= 1")
    if max_window < min_window:
        raise ValueError("max_window must be >= min_window")

    # 规则 1: dev_plan 越大，窗口越小
    if dev_plan_size > 300:
        window = min_window
    elif dev_plan_size > 200:
        window = base_window - 3
    elif dev_plan_size > 150:
        window = base_window - 2
    else:
        window = base_window

    # 规则 2: 迭代越多，窗口越小（防止累积）
    if iteration > 20:
        window = min(window, min_window + 2)
    elif iteration > 15:
        window = min(window, min_window + 4)

    return max(min_window, min(window, max_window))


def _preflight() -> None:
    CODEX_STATE_DIR.mkdir(parents=True, exist_ok=True)  # 关键变量：Codex 状态目录
    legacy_roots = [PROJECT_ROOT / "memory", PROJECT_ROOT / "workspace", PROJECT_ROOT / "reports"]  # 关键变量：旧黑板路径
    for legacy in legacy_roots:  # 关键分支：逐个检查旧目录
        if legacy.exists():  # 关键分支：发现旧目录直接失败
            raise RuntimeError(
                "Legacy blackboard directory detected at "
                f"{legacy}. Blackboard root is `orchestrator/`; remove or migrate this directory."
            )
    _ensure_initial_md_files()

    # 黑板协议校验：创建后仍需满足"可运行"的最低要求，否则快速失败。
    _require_file(GLOBAL_CONTEXT_FILE)  # 关键变量：全局上下文必须存在
    _require_file(PROJECT_HISTORY_FILE)  # 关键变量：历史必须存在
    _require_file(DEV_PLAN_FILE)  # 关键变量：计划必须存在
    _require_file(DEV_PLAN_ARCHIVED_FILE)  # 关键变量：归档计划必须存在
    _require_file(FINISH_REVIEW_CONFIG_FILE)  # 关键变量：最终审阅配置必须存在
    _require_file(VERIFICATION_POLICY_FILE)  # 关键变量：验证策略配置必须存在
    _require_file(OUT_OF_SCOPE_ISSUES_FILE)  # 关键变量：范围外问题记录必须存在
    _require_file(TEST_TASK_FILE)  # 关键变量：TEST 工单必须存在
    _require_file(DEV_TASK_FILE)  # 关键变量：DEV 工单必须存在
    _require_file(REVIEW_TASK_FILE)  # 关键变量：REVIEW 工单必须存在
    _require_file(REPORT_TEST_FILE)  # 关键变量：TEST 报告必须存在
    _require_file(REPORT_DEV_FILE)  # 关键变量：DEV 报告必须存在
    _require_file(REPORT_REVIEW_FILE)  # 关键变量：REVIEW 报告必须存在
    _require_file(REPORT_FINISH_REVIEW_FILE)  # 关键变量：FINISH_REVIEW 报告必须存在

    for agent in ("main", "test", "dev", "review", "summary", "finish_review"):  # 关键分支：逐个检查提示词
        _require_file(PROMPTS_DIR / f"subagent_prompt_{agent}.md")  # 关键变量：提示词必须存在

    _validate_dev_plan()  # 关键变量：计划结构校验

    # 新增：校验 acceptance_scope.json（范围锁定：缺失/格式不对直接失败）
    _require_file(ACCEPTANCE_SCOPE_FILE)
    try:
        scope = json.loads(ACCEPTANCE_SCOPE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid {_rel_path(ACCEPTANCE_SCOPE_FILE)}: {exc}") from exc
    if not isinstance(scope, dict):
        raise RuntimeError(f"Invalid {_rel_path(ACCEPTANCE_SCOPE_FILE)}: root must be a JSON object")
    required_fields = ["schema_version", "locked_at_iteration", "acceptance_criteria", "completion_criteria"]
    for field in required_fields:
        if field not in scope:
            raise RuntimeError(f"Invalid {_rel_path(ACCEPTANCE_SCOPE_FILE)}: missing required field {field!r}")
    criteria = scope.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria:
        raise RuntimeError(f"Invalid {_rel_path(ACCEPTANCE_SCOPE_FILE)}: acceptance_criteria must be a non-empty list")
    _append_log_line(
        f"orchestrator: acceptance_scope validated - {len(criteria)} criteria\n"
    )


def workflow_loop(
    *,
    max_iterations: int,
    sandbox_mode: str,
    approval_policy: str,
    user_task: str,
    new_task: bool,
    ui: UiRuntime | None,
    control: RunControl | None = None,
    history_window_iterations: int = 20,
    history_window_max_tokens: int | None = None,
) -> None:
    _preflight()  # 关键变量：启动前必须通过黑板校验
    trace_id = new_trace_id()  # 关键变量：本次运行 trace
    log_event(
        "run_start",
        trace_id=trace_id,
        new_task=new_task,
        max_iterations=max_iterations,
        sandbox_mode=sandbox_mode,
        approval_policy=approval_policy,
        history_window_iterations=history_window_iterations,
        history_window_max_tokens=history_window_max_tokens,
        user_task_len=len(user_task or ""),
    )
    if new_task:  # 关键分支：新任务需要清理旧状态
        _clear_saved_main_state()  # 关键变量：清空 MAIN 会话与迭代
        _reset_workspace_task_files(iteration=0)  # 关键变量：重置工单
        _reset_report_files()  # 关键变量：重置报告

    main_session_id = None if new_task else _load_saved_main_session_id()  # 关键变量：MAIN 会话 id
    if main_session_id is not None:  # 关键分支：恢复旧会话
        print(f"Loaded MAIN session id: {main_session_id}")
        if ui is not None:  # 关键分支：UI 同步会话 id
            ui.state.update(main_session_id=main_session_id)

    last_iteration = 0 if new_task else _load_saved_main_iteration()  # 关键变量：上次迭代号
    if last_iteration:  # 关键分支：仅在非零时打印
        print(f"Loaded MAIN iteration: {last_iteration}")
    if ui is not None:  # 关键分支：UI 同步迭代号
        ui.state.update(iteration=last_iteration)

    _resume_pending_iteration(
        last_iteration=last_iteration,
        main_session_id=main_session_id,
        sandbox_mode=sandbox_mode,
        approval_policy=approval_policy,
        ui=ui,
        control=control,
    )

    start_iteration = last_iteration + 1  # 关键变量：本轮起始迭代
    end_iteration = start_iteration + max_iterations - 1  # 关键变量：本轮结束迭代

    finish_attempts = 0  # 关键变量：FINISH 尝试计数（用于强制收敛）
    max_finish_attempts = MAX_FINISH_ATTEMPTS  # 关键变量：最大 FINISH 尝试次数
    for iteration in range(start_iteration, end_iteration + 1):  # 关键分支：迭代循环
        if control is not None and control.cancel_event.is_set():  # 关键分支：用户中断优先
            raise UserInterrupted("User interrupted before starting iteration")
        banner = f"\n========== Iteration {iteration} ==========\n"  # 关键变量：迭代日志分隔
        print(banner, end="")
        _append_log_line(banner)
        log_event("iteration_start", trace_id=trace_id, iteration=iteration)
        if ui is not None:  # 关键分支：UI 同步 MAIN 运行态
            ui.state.update(phase="running_main", iteration=iteration, current_agent="MAIN")

        # Phase 3: dev_plan 归档（控制体积，避免上下文过载）
        dev_plan_size = len(_read_text(DEV_PLAN_FILE).splitlines())
        if dev_plan_size > MAX_DEV_PLAN_SIZE:
            archived = _archive_verified_tasks(
                dev_plan_file=DEV_PLAN_FILE,
                archive_file=DEV_PLAN_ARCHIVED_FILE,
                keep_recent_milestones=KEEP_RECENT_MILESTONES,
            )
            if archived:
                dev_plan_size = len(_read_text(DEV_PLAN_FILE).splitlines())
                _append_log_line(
                    f"orchestrator: archived {archived} milestones to {_rel_path(DEV_PLAN_ARCHIVED_FILE)}\n"
                )
                log_event(
                    "dev_plan_archived",
                    trace_id=trace_id,
                    iteration=iteration,
                    archived_milestones=archived,
                    dev_plan_size=dev_plan_size,
                )

        # Phase 3: 动态调整 history_window
        adaptive_window = _calculate_adaptive_history_window(
            iteration=iteration,
            dev_plan_size=dev_plan_size,
            base_window=history_window_iterations,
            min_window=MIN_HISTORY_WINDOW,
            max_window=MAX_HISTORY_WINDOW,
        )
        log_event(
            "adaptive_history_window",
            trace_id=trace_id,
            iteration=iteration,
            dev_plan_size=dev_plan_size,
            history_window_iterations=adaptive_window,
        )

        # 1) MAIN：输出包含 history/task/dev_plan_next 的调度 JSON
        _clear_dev_plan_stage_file()  # 关键变量：清理上轮 dev_plan 草案
        dev_plan_before_hash = _sha256_text(_read_text(DEV_PLAN_FILE))  # 关键变量：dev_plan 运行前哈希
        main_prompt = _build_main_prompt(
            iteration=iteration,
            user_task=user_task,
            history_window_iterations=adaptive_window,
            history_window_max_tokens=history_window_max_tokens,
        )
        prompt_len = len(main_prompt)
        if prompt_len > MAX_PROMPT_SIZE:
            _append_log_line(
                f"orchestrator: WARNING - MAIN prompt too large len={prompt_len} > {MAX_PROMPT_SIZE}\n"
            )
            # 再次尝试用最小窗口缩减历史注入（仍过大则直接失败，避免空输出崩溃）
            if adaptive_window != MIN_HISTORY_WINDOW:
                adaptive_window = MIN_HISTORY_WINDOW
                main_prompt = _build_main_prompt(
                    iteration=iteration,
                    user_task=user_task,
                    history_window_iterations=adaptive_window,
                    history_window_max_tokens=history_window_max_tokens,
                )
                prompt_len = len(main_prompt)
            if prompt_len > MAX_PROMPT_SIZE:
                raise RuntimeError(
                    f"MAIN prompt too large len={prompt_len} > {MAX_PROMPT_SIZE}. "
                    "Please archive dev_plan and/or reduce injected history."
                )
        log_event(
            "main_prompt_size",
            trace_id=trace_id,
            iteration=iteration,
            prompt_len=prompt_len,
            history_window_iterations=adaptive_window,
        )
        main_guard_paths = [path for path in _guarded_blackboard_paths() if path != REPORT_MAIN_DECISION_FILE]  # 关键变量：MAIN 可写排除清单
        main_started = time.monotonic()
        main_output, captured_session_id = _run_main_decision_stage(
            prompt=main_prompt,
            guard_paths=main_guard_paths,
            label="MAIN",
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
            control=control,
            resume_session_id=main_session_id,
        )
        if main_session_id is None:  # 关键分支：首次运行需要保存会话 id
            session_id = captured_session_id  # 关键变量：首次会话 id
            if session_id is None:  # 关键分支：必须拿到会话 id
                raise RuntimeError("Failed to capture MAIN session id from codex output")
            _save_main_session_id(session_id)
            main_session_id = session_id
            print(f"Saved MAIN session id: {main_session_id}")
            if ui is not None:  # 关键分支：UI 更新会话 id
                ui.state.update(main_session_id=main_session_id)

        log_event(
            "stage_complete",
            trace_id=trace_id,
            iteration=iteration,
            stage="MAIN",
            duration_ms=int((time.monotonic() - main_started) * 1000),
        )
        if _sha256_text(_read_text(DEV_PLAN_FILE)) != dev_plan_before_hash:  # 关键分支：禁止直接改 dev_plan
            raise RuntimeError(
                "MAIN must not modify `memory/dev_plan.md` directly. "
                f"Write the full next dev_plan to `{_rel_path(DEV_PLAN_STAGED_FILE)}` instead."
            )
        decision = main_output["decision"]  # 关键变量：决策字段

        if decision["next_agent"] == "FINISH":  # 关键分支：触发最终审阅
            finish_attempts += 1
            _append_log_line(
                f"orchestrator: FINISH attempt {finish_attempts}/{max_finish_attempts}\n"
            )
            log_event(
                "finish_attempt",
                trace_id=trace_id,
                iteration=iteration,
                finish_attempts=finish_attempts,
                max_finish_attempts=max_finish_attempts,
            )

            is_ready, check_msg, blockers = _check_finish_readiness()
            if not is_ready:
                _append_log_line(f"orchestrator: FINISH readiness check failed: {check_msg}\n")
                print(f"Warning: FINISH requested but {check_msg}")

            _append_log_line("orchestrator: FINISH requested, running final review\n")
            finish_started = time.monotonic()
            _run_finish_review_stage(
                iteration=iteration,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                ui=ui,
                control=control,
            )
            log_event(
                "stage_complete",
                trace_id=trace_id,
                iteration=iteration,
                stage="FINISH_REVIEW",
                duration_ms=int((time.monotonic() - finish_started) * 1000),
            )
            if ui is not None:  # 关键分支：UI 更新 MAIN 复核运行态
                ui.state.update(phase="running_main", iteration=iteration, current_agent="MAIN")
            dev_plan_before_hash = _sha256_text(_read_text(DEV_PLAN_FILE))  # 关键变量：复核前哈希

            if not is_ready and finish_attempts >= max_finish_attempts:
                _append_log_line(
                    f"orchestrator: FORCE FINISH after {finish_attempts} attempts. blockers={blockers}\n"
                )
                log_event(
                    "force_finish",
                    trace_id=trace_id,
                    iteration=iteration,
                    finish_attempts=finish_attempts,
                    blockers=blockers,
                )
                print(f"WARNING: 强制完成: 已尝试 {finish_attempts} 次 FINISH，仍有阻塞项: {check_msg}")
                _generate_legacy_issues_report(
                    iteration=iteration,
                    blockers=blockers,
                    dev_plan_file=DEV_PLAN_FILE,
                    out_of_scope_file=OUT_OF_SCOPE_ISSUES_FILE,
                )
                if ui is not None:
                    ui.state.update(phase="finished", current_agent="FINISH")
                return

            # 使用简化的 FINISH_CHECK 提示词，减少上下文长度
            main_prompt = _build_finish_check_prompt(
                iteration=iteration,
                user_task=user_task,
                is_ready=is_ready,
                check_msg=check_msg,
            )
            main_finish_started = time.monotonic()
            main_output, _ = _run_main_decision_stage(
                prompt=main_prompt,
                guard_paths=main_guard_paths,
                label="MAIN_FINISH_CHECK",
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                control=control,
                resume_session_id=main_session_id,
            )
            log_event(
                "stage_complete",
                trace_id=trace_id,
                iteration=iteration,
                stage="MAIN_FINISH_CHECK",
                duration_ms=int((time.monotonic() - main_finish_started) * 1000),
            )
            if _sha256_text(_read_text(DEV_PLAN_FILE)) != dev_plan_before_hash:  # 关键分支：禁止直接改 dev_plan
                raise RuntimeError(
                    "MAIN must not modify `memory/dev_plan.md` directly. "
                    f"Write the full next dev_plan to `{_rel_path(DEV_PLAN_STAGED_FILE)}` instead."
                )
            decision = main_output["decision"]  # 关键变量：最终决策字段

        history_entry, task_content, dev_plan_next = _prepare_main_output(iteration=iteration, output=main_output)  # 关键变量：结构化输出
        if dev_plan_next is not None:  # 关键分支：有计划草案才落盘
            DEV_PLAN_STAGED_FILE.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(
                DEV_PLAN_STAGED_FILE,
                dev_plan_next.rstrip() + "\n",
            )  # 关键变量：暂存 dev_plan
        _commit_staged_dev_plan_if_present(
            iteration=iteration,
            main_session_id=main_session_id,
            dev_plan_before_hash=dev_plan_before_hash,
        )
        if task_content is not None:  # 关键分支：子代理才需要写工单
            task_file = _task_file_for_agent(decision["next_agent"])  # 关键变量：目标工单路径
            task_file.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(task_file, task_content + "\n")  # 关键变量：写入工单内容
        _append_history_entry(history_entry)  # 关键变量：追加历史

        print(f"MAIN => {decision['next_agent']} ({decision['reason']})")
        _append_log_line(f"orchestrator: MAIN => {decision['next_agent']} ({decision['reason']})\n")
        if ui is not None:  # 关键分支：UI 更新最近决策
            ui.state.update(last_main_decision=decision)

        _assert_main_side_effects(iteration=iteration, expected_next_agent=decision["next_agent"])  # 关键变量：黑板契约校验
        _save_main_iteration(iteration)  # 关键变量：记录已完成迭代

        if decision["next_agent"] == "FINISH":  # 关键分支：结束则清理续跑状态
            _clear_resume_state()
        elif decision["next_agent"] == "USER":  # 关键分支：等待用户决策
            _write_resume_state(
                iteration=iteration,
                phase="awaiting_user",
                next_agent="USER",
                main_session_id=main_session_id,
                subagent_session_id=None,
            )
        else:  # 关键分支：子代理阶段
            _write_resume_state(
                iteration=iteration,
                phase="after_main",
                next_agent=decision["next_agent"],
                main_session_id=main_session_id,
                subagent_session_id=None,
            )

        if decision["next_agent"] == "FINISH":  # 关键分支：终止流程
            print("Finished.")
            _append_log_line("orchestrator: Finished.\n")
            if ui is not None:  # 关键分支：UI 标记已完成
                ui.state.update(phase="finished", current_agent="FINISH")
            return
        if decision["next_agent"] == "USER":  # 关键分支：等待用户抉择
            _prompt_user_for_decision(iteration=iteration, decision=decision, ui=ui)
            _clear_resume_state()
            continue

        # 2) 子代理：只读工单并输出报告（报告由 --output-last-message 落盘）
        sub_started = time.monotonic()
        sub_session_id, task_file, report_path = _run_subagent_stage(
            iteration=iteration,
            next_agent=decision["next_agent"],
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
            ui=ui,
            control=control,
        )
        log_event(
            "stage_complete",
            trace_id=trace_id,
            iteration=iteration,
            stage=decision["next_agent"],
            duration_ms=int((time.monotonic() - sub_started) * 1000),
        )
        _write_resume_state(
            iteration=iteration,
            phase="after_subagent",
            next_agent=decision["next_agent"],
            main_session_id=main_session_id,
            subagent_session_id=sub_session_id,
        )
        summary_started = time.monotonic()
        _run_summary_stage(
            iteration=iteration,
            next_agent=decision["next_agent"],
            main_session_id=main_session_id,
            subagent_session_id=sub_session_id,
            task_file=task_file,
            report_path=report_path,
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
            ui=ui,
            control=control,
        )
        log_event(
            "stage_complete",
            trace_id=trace_id,
            iteration=iteration,
            stage="SUMMARY",
            duration_ms=int((time.monotonic() - summary_started) * 1000),
        )
        _clear_resume_state()

    raise RuntimeError(f"Reached max_iterations={max_iterations} without FINISH")
