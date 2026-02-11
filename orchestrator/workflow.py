from __future__ import annotations

import json
import re
import time

from datetime import datetime

from collections.abc import Callable
from pathlib import Path
from .backup import _backup_iteration_artifacts, _backup_subagent_artifacts, _clear_dev_plan_stage_file, _commit_staged_dev_plan_if_present
from .codex_runner import (
    _clear_saved_main_state,
    _load_saved_main_iteration,
    _load_saved_main_session_id,
    _load_subagent_session_id,
    _run_cli_exec,
    _save_main_iteration,
    _save_main_session_id,
    _save_subagent_session_id,
    _clear_all_subagent_sessions,
)
from .token_info import get_session_token_info, format_token_info
from .config import (
    CODEX_STATE_DIR,
    RESUME_STATE_FILE,
    CONFIG,
    DEV_PLAN_FILE,
    DEV_PLAN_STAGED_FILE,
    FINISH_REVIEW_CONFIG_FILE,
    VERIFICATION_POLICY_FILE,
    GLOBAL_CONTEXT_FILE,
    MEMORY_DIR,
    ORCHESTRATOR_LOG_FILE,
    PROJECT_HISTORY_FILE,
    PROJECT_ROOT,
    PROMPTS_DIR,
    PROJECT_ENV_FILE,
    REPORT_MAIN_DECISION_FILE,
    REPORT_ITERATION_SUMMARY_FILE,
    REPORT_ITERATION_SUMMARY_HISTORY_FILE,
    REPORT_FINISH_REVIEW_FILE,
    REPORTS_DIR,
    REPORT_SUMMARY_CACHE_FILE,
    WORKSPACE_DIR,
    ProjectTemplates,
    ACCEPTANCE_SCOPE_FILE,
    OUT_OF_SCOPE_ISSUES_FILE,
    DEV_PLAN_ARCHIVED_FILE,
    MAX_FINISH_ATTEMPTS,
    LEGACY_ISSUES_REPORT_FILE,
    KEEP_RECENT_MILESTONES,
    MAX_DEV_PLAN_SIZE,
    MAX_PROMPT_SIZE,
    SUBAGENT_HISTORY_LOOKBACK,
    UPLOADED_DOCS_DIR,
    UPLOADED_DOCS_CATEGORIES,
    USER_DECISION_PATTERNS_FILE,
    ITERATION_METADATA_FILE,
    get_cli_for_agent,
    # Context-centric 架构新增
    IMPLEMENTER_TASK_FILE,
    REPORT_IMPLEMENTER_FILE,
    VALIDATOR_WORKSPACE_DIR,
    VALIDATOR_REPORTS_DIR,
    SYNTHESIZER_REPORT_FILE,
    VALIDATION_RESULTS_FILE,
    PARALLEL_VALIDATORS,
    MAX_PARALLEL_VALIDATORS,
    VALIDATOR_TIMEOUT_MS,
)
from .decision import _parse_main_output, _prompt_user_for_decision, _update_user_decision_patterns
from .summary import (
    _append_iteration_summary_history,
    _load_iteration_summary_history,
    _parse_iteration_summary,
    _parse_user_insight,
    _generate_user_insight_report,
    _append_user_insight_history,
)
from .telemetry import log_event, new_trace_id
from .file_ops import (
    _append_history_entry,
    _append_log_line,
    _assert_files_unchanged,
    _atomic_write_text,
    _extract_last_iteration_from_history,
    _extract_latest_task_goal,
    _extract_latest_user_decision,
    _extract_recent_user_decisions,
    _read_text,
    _require_file,
    _rel_path,
    _sha256_text,
    _snapshot_files,
    _write_text_if_missing,
)
from .prompt_builder import (
    _extract_doc_references,
    _inject_file,
    _inject_doc_references,
    _inject_project_history_head,
    _inject_report_with_level,
    _load_system_prompt,
    _task_file_for_agent,
)
from .errors import PermanentError, TemporaryError
from .state import RunControl, UiRuntime, UserInterrupted
from .types import MainOutput, ResumeState, MainDecisionUser, ValidationResult, SynthesizerOutput
from .dev_plan import count_overall_task_statuses, parse_overall_task_statuses
from .parsing import extract_report_verdict, parse_parsing_rules, parse_report_rules
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
    _validate_and_complete_task_fields,
    _inject_execution_environment,
    _build_execution_environment_section,
)
from .runtime_context import RuntimeContext, load_runtime_context
from .blackboard_mirror import assert_project_mirror_unchanged, sync_project_markdown_mirror
from .health_gate import run_pre_validation_health_check
from .issue_classifier import ensure_result_category
from .decision_router import route_validation_results
from .synthesizer_parser import parse_synthesizer_output


def _ensure_initial_md_files() -> None:
    """
    初始化黑板目录与初始 Markdown 文件（仅在缺失时创建，不覆盖）。
    用户要求：orchestrator/memory/、orchestrator/reports/、orchestrator/workspace/
    内缺失初始 md 文件则新建初始化。
    """
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)  # 关键变量：黑板 memory 目录
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)  # 关键变量：提示词目录
    for category in UPLOADED_DOCS_CATEGORIES:  # 关键变量：上传文档目录
        (UPLOADED_DOCS_DIR / category).mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)  # 关键变量：报告目录
    (WORKSPACE_DIR / "implementer").mkdir(parents=True, exist_ok=True)  # 关键变量：IMPLEMENTER 工单目录
    (WORKSPACE_DIR / "validators").mkdir(parents=True, exist_ok=True)  # 关键变量：验证器工单目录
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

    # Context-centric 架构：IMPLEMENTER 工单模板
    _write_text_if_missing(IMPLEMENTER_TASK_FILE, ProjectTemplates.task_file("IMPLEMENTER", 0))  # 关键变量：IMPLEMENTER 工单模板
    _write_text_if_missing(REPORT_IMPLEMENTER_FILE, ProjectTemplates.report_file("IMPLEMENTER"))  # 关键变量：IMPLEMENTER 报告模板
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
    if REPORT_MAIN_DECISION_FILE.exists():  # 关键分支：清理 MAIN 决策文件
        REPORT_MAIN_DECISION_FILE.unlink()
    if REPORT_SUMMARY_CACHE_FILE.exists():  # 关键分支：清理报告摘要缓存
        REPORT_SUMMARY_CACHE_FILE.unlink()
    if SYNTHESIZER_REPORT_FILE.exists():  # 关键分支：清理综合器报告
        SYNTHESIZER_REPORT_FILE.unlink()
    if VALIDATION_RESULTS_FILE.exists():  # 关键分支：清理验证结果
        VALIDATION_RESULTS_FILE.unlink()
    if VALIDATOR_REPORTS_DIR.exists():  # 关键分支：清理验证器报告目录
        for stale_file in VALIDATOR_REPORTS_DIR.iterdir():
            if stale_file.is_file() and stale_file.suffix == ".md" and stale_file.name != ".gitkeep":
                stale_file.unlink()
    if VALIDATOR_WORKSPACE_DIR.exists():  # 关键分支：清理验证器工单目录
        for stale_file in VALIDATOR_WORKSPACE_DIR.iterdir():
            if stale_file.is_file() and stale_file.suffix == ".md" and stale_file.name != ".gitkeep":
                stale_file.unlink()


def _reset_acceptance_scope(user_task: str) -> None:
    """
    新任务开始时重置 acceptance_scope.json，更新 task_goal。
    FINISH_REVIEW 将直接根据 task_goal 判断任务是否完成，无需预定义 acceptance_criteria。
    """
    import json
    scope_data = {
        "schema_version": 1,
        "locked_at_iteration": 0,
        "task_goal": user_task.strip() if user_task else "",
        "acceptance_criteria": [],
        "out_of_scope": [],
        "completion_criteria": {
            "all_tasks_verified": True,
            "all_tests_passing": True,
            "no_p0_blockers": True,
        },
    }
    ACCEPTANCE_SCOPE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(ACCEPTANCE_SCOPE_FILE, json.dumps(scope_data, ensure_ascii=False, indent=2))


def _purge_directory(*, root: Path, keep_dirs: tuple[Path, ...] = (), keep_files: tuple[Path, ...] = ()) -> None:
    if not root.exists():  # 关键分支：目录不存在则创建
        root.mkdir(parents=True, exist_ok=True)
        return
    keep_dirs = tuple(keep_dirs)
    keep_files = tuple(keep_files)
    for path in sorted(root.rglob("*"), reverse=True):  # 关键分支：逆序删除，先文件后目录
        if any(path.is_relative_to(keep) for keep in keep_dirs):  # 关键分支：跳过保留目录
            continue
        if path in keep_files:  # 关键分支：跳过保留文件
            continue
        if path.is_dir():  # 关键分支：目录直接删除
            path.rmdir()
        else:  # 关键分支：文件/链接删除
            path.unlink()


def _reset_workflow_state() -> None:
    """
    将工作流状态重置为"无进度"的初始态（覆盖写入+清理状态文件）。
    """
    _clear_saved_main_state()  # 关键变量：清空 MAIN 会话与迭代
    _clear_all_subagent_sessions()  # 关键变量：清空所有子代理会话
    _clear_dev_plan_stage_file()  # 关键变量：清理 dev_plan 草案
    _purge_directory(root=WORKSPACE_DIR)  # 关键变量：清理 workspace
    _purge_directory(root=REPORTS_DIR)  # 关键变量：清理 reports
    _purge_directory(
        root=MEMORY_DIR,
        keep_dirs=(PROMPTS_DIR, UPLOADED_DOCS_DIR),
        keep_files=(PROJECT_ENV_FILE,),
    )  # 关键变量：清理 memory（保留提示词、已上传文档、项目环境配置）
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


def _resolve_target_project_root() -> Path:
    """解析仓库根目录（来自 project_env.json.project.root）。"""
    context = load_runtime_context(project_env_file=PROJECT_ENV_FILE)
    return context.project_root


def _resolve_target_agent_root() -> Path:
    """解析子代理业务工作根目录。"""
    context = load_runtime_context(project_env_file=PROJECT_ENV_FILE)
    return context.agent_root


def _resolve_finish_review_path(*, value: str, expect_dir: bool) -> Path:
    if not isinstance(value, str) or not value.strip():  # 关键分支：路径不能为空
        raise ValueError("finish_review_config contains empty path")
    raw = Path(value)
    if raw.is_absolute():  # 关键分支：禁止绝对路径
        raise ValueError(f"finish_review_config path must be project-relative: {value!r}")
    target_root = _resolve_target_project_root()
    resolved = (target_root / raw).resolve()
    try:
        resolved.relative_to(target_root)
    except ValueError as exc:  # 关键分支：路径越界
        raise ValueError(f"finish_review_config path is outside project root: {value!r}") from exc
    if expect_dir:
        if not resolved.is_dir():  # 关键分支：目录必须存在
            raise FileNotFoundError(f"Missing code_root directory: {resolved.as_posix()}")
    else:
        if not resolved.is_file():  # 关键分支：文件必须存在
            raise FileNotFoundError(f"Missing doc file: {resolved.as_posix()}")
    return resolved


def _parse_finish_review_config() -> tuple[str, str, list[Path], Path]:
    payload = _load_finish_review_config()
    anchor = payload.get("task_goal_anchor")
    if not isinstance(anchor, str) or not anchor.strip():  # 关键分支：anchor 必须为非空字符串
        raise ValueError("finish_review_config.task_goal_anchor must be a non-empty string")
    match_mode = payload.get("task_goal_anchor_mode", "prefix_latest")
    if not isinstance(match_mode, str) or not match_mode.strip():  # 关键分支：模式必须为非空字符串
        raise ValueError("finish_review_config.task_goal_anchor_mode must be a non-empty string")
    docs = payload.get("docs", [])
    if not isinstance(docs, list):  # 关键分支：docs 必须为列表（可为空）
        raise ValueError("finish_review_config.docs must be a list")
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
        IMPLEMENTER_TASK_FILE,  # 关键变量：IMPLEMENTER 工单
        REPORT_IMPLEMENTER_FILE,  # 关键变量：IMPLEMENTER 报告
        REPORT_FINISH_REVIEW_FILE,  # 关键变量：FINISH_REVIEW 报告
        REPORT_MAIN_DECISION_FILE,  # 关键变量：MAIN 决策输出
        REPORT_ITERATION_SUMMARY_FILE,  # 关键变量：每轮摘要输出
        REPORT_ITERATION_SUMMARY_HISTORY_FILE,  # 关键变量：摘要历史输出
        REPORT_SUMMARY_CACHE_FILE,  # 关键变量：报告摘要缓存
        SYNTHESIZER_REPORT_FILE,  # 关键变量：SYNTHESIZER 报告
        VALIDATION_RESULTS_FILE,  # 关键变量：验证结果
    ]


_RESUME_SCHEMA_VERSION = 1  # 关键变量：续跑状态版本


def _resume_blackboard_paths(*, phase: str, next_agent: str) -> tuple[list[Path], list[Path]]:
    required = [PROJECT_HISTORY_FILE, DEV_PLAN_FILE, REPORT_MAIN_DECISION_FILE]
    if next_agent == "IMPLEMENTER":
        required.append(IMPLEMENTER_TASK_FILE)
        if phase == "after_subagent":
            required.append(REPORT_IMPLEMENTER_FILE)
    elif next_agent == "VALIDATE" and phase != "after_main_validate":
        raise ValueError(f"续跑 phase/next_agent 组合无效：phase={phase!r}, next_agent={next_agent!r}")
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


_RESUME_PHASES = {"after_main", "after_subagent", "after_main_validate", "awaiting_user"}  # 关键变量：可恢复阶段
_RESUME_AGENTS = {"IMPLEMENTER", "VALIDATE", "USER"}  # 关键变量：可恢复代理（Context-centric 架构）

from .config import MAX_STAGE_RETRIES as _MAX_STAGE_RETRIES  # 关键变量：从 config 读取重试次数
from .config import BACKOFF_BASE_SECONDS as _BACKOFF_BASE_SECONDS  # 关键变量：从 config 读取退避基数
from .config import BACKOFF_MAX_SECONDS as _BACKOFF_MAX_SECONDS  # 关键变量：从 config 读取退避上限
from .config import MAIN_MAX_STAGE_RETRIES as _MAIN_MAX_STAGE_RETRIES  # 关键变量：MAIN 专用重试次数
from .config import MAIN_BACKOFF_BASE_SECONDS as _MAIN_BACKOFF_BASE_SECONDS  # 关键变量：MAIN 专用退避基数
from .config import MAIN_BACKOFF_MAX_SECONDS as _MAIN_BACKOFF_MAX_SECONDS  # 关键变量：MAIN 专用退避上限


def _sleep_backoff(
    *,
    label: str,
    attempt: int,
    base_seconds: float = _BACKOFF_BASE_SECONDS,
    max_seconds: float = _BACKOFF_MAX_SECONDS,
) -> None:
    delay = min(base_seconds * (2 ** attempt), max_seconds)
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
    last_compact_iteration: int = 0,
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
    if phase in {"after_main", "after_subagent"} and next_agent != "IMPLEMENTER":  # 关键分支：阶段与代理不一致
        raise ValueError("续跑 after_main/after_subagent 必须搭配 next_agent=IMPLEMENTER")
    if phase == "after_main_validate" and next_agent != "VALIDATE":  # 关键分支：阶段与代理不一致
        raise ValueError("续跑 after_main_validate 必须搭配 next_agent=VALIDATE")
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
        "last_compact_iteration": last_compact_iteration,
    }
    RESUME_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(RESUME_STATE_FILE, json.dumps(payload, ensure_ascii=True) + "\n")


def _clear_resume_state() -> None:
    if RESUME_STATE_FILE.exists():  # 关键分支：存在才删除
        RESUME_STATE_FILE.unlink()


# ========== MAIN checkpoint（崩溃恢复）==========
MAIN_CHECKPOINT_FILE = WORKSPACE_DIR / "main_checkpoint.json"


def _write_main_checkpoint(
    *,
    iteration: int,
    main_output: MainOutput,
    main_session_id: str,
    history_entry: str,
    task_content: str | None,
    dev_plan_next: str | None,
) -> None:
    """在 stage_complete(MAIN) 后立即写入 checkpoint，缩小崩溃窗口。"""
    payload = {
        "schema_version": 1,
        "iteration": iteration,
        "main_session_id": main_session_id,
        "main_output": main_output,
        "history_entry": history_entry,
        "task_content": task_content,
        "dev_plan_next": dev_plan_next,
    }
    MAIN_CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(MAIN_CHECKPOINT_FILE, json.dumps(payload, ensure_ascii=False) + "\n")


def _load_main_checkpoint(iteration: int) -> dict | None:
    """加载 MAIN checkpoint。仅当 iteration 匹配时返回，否则返回 None。"""
    if not MAIN_CHECKPOINT_FILE.exists():
        return None
    try:
        raw = _read_text(MAIN_CHECKPOINT_FILE).strip()
        if not raw:
            return None
        payload = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return None  # 文件损坏时回退到正常执行
    if payload.get("schema_version") != 1:
        return None
    if payload.get("iteration") != iteration:
        return None  # 不同迭代的 checkpoint 无效
    return payload


def _clear_main_checkpoint() -> None:
    """post-MAIN 处理完成后清除 checkpoint。"""
    if MAIN_CHECKPOINT_FILE.exists():
        MAIN_CHECKPOINT_FILE.unlink()


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
    if phase in {"after_main", "after_subagent"} and next_agent != "IMPLEMENTER":
        raise ValueError("续跑 after_main/after_subagent 必须搭配 next_agent=IMPLEMENTER")
    if phase == "after_main_validate" and next_agent != "VALIDATE":
        raise ValueError("续跑 after_main_validate 必须搭配 next_agent=VALIDATE")

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

    # 读取 last_compact_iteration（兼容旧版本状态文件）
    last_compact_iter = payload.get("last_compact_iteration", 0)
    if not isinstance(last_compact_iter, int) or last_compact_iter < 0:
        last_compact_iter = 0

    return {
        "schema_version": schema_version,
        "iteration": iteration,
        "phase": phase,
        "next_agent": next_agent,
        "main_session_id": main_session_id,
        "subagent_session_id": subagent_session_id,
        "blackboard_digest": blackboard_digest,
        "last_compact_iteration": last_compact_iter,
    }


def _history_has_user_decision(*, iteration: int) -> bool:
    _require_file(PROJECT_HISTORY_FILE)  # 关键分支：历史必须存在
    needle = f"## User Decision (Iteration {iteration}):"  # 关键变量：用户决策标识
    return needle in _read_text(PROJECT_HISTORY_FILE)


# ============= 迭代元数据管理（用于监督代理并行化） =============


def _append_iteration_metadata(
    *,
    iteration: int,
    agent: str,
    session_id: str,
    report_file: Path,
) -> None:
    """
    写入轻量级迭代元数据（同步，极快）。

    主流程在每轮子代理完成后调用，记录必要的元数据。
    用于替代从 SUMMARY 历史文件获取信息的依赖。
    """
    record = {
        "iteration": iteration,
        "agent": agent,
        "session_id": session_id,
        "report_file": str(report_file.relative_to(PROJECT_ROOT)),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    ITERATION_METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ITERATION_METADATA_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_iteration_metadata() -> list[dict]:
    """加载所有迭代元数据"""
    if not ITERATION_METADATA_FILE.exists():
        return []
    raw = ITERATION_METADATA_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    records: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            if isinstance(record, dict):
                records.append(record)
        except json.JSONDecodeError:
            continue
    return records


def _get_last_subagent_from_metadata(iteration: int) -> str | None:
    """
    从迭代元数据获取指定迭代的子代理类型。

    优先使用元数据文件，若不存在则回退到摘要历史文件。
    """
    # 优先从元数据文件获取
    metadata = _load_iteration_metadata()
    for record in reversed(metadata):
        if record.get("iteration") == iteration:
            agent = record.get("agent")
            if isinstance(agent, str) and agent in {"IMPLEMENTER", "VALIDATE"}:
                return agent
            break

    # 回退到摘要历史文件（兼容旧数据）
    return _get_last_subagent_from_history(iteration)


def _get_last_subagent_from_history(iteration: int) -> str | None:
    """
    从迭代摘要历史中获取指定迭代运行的子代理类型。
    用于恢复 workflow 时确定上一轮运行的子代理，以便注入正确的报告。
    """
    history = _load_iteration_summary_history(REPORT_ITERATION_SUMMARY_HISTORY_FILE)
    for summary in reversed(history):
        if summary.get("iteration") == iteration:
            subagent = summary.get("subagent")
            if isinstance(subagent, dict):
                agent = subagent.get("agent")
                if isinstance(agent, str) and agent in {"IMPLEMENTER", "VALIDATE"}:
                    return agent
            break
    return None


def _find_recent_reports_from_metadata(*, agent: str, lookback: int) -> list[Path]:
    """
    从迭代元数据查找最近报告。

    优先使用元数据文件，若不存在则回退到摘要历史文件。
    """
    if lookback < 1:
        return []

    # 优先从元数据文件获取
    metadata = _load_iteration_metadata()
    if metadata:
        found: list[Path] = []
        for record in reversed(metadata):
            if record.get("agent") != agent:
                continue
            report_rel = record.get("report_file")
            if not isinstance(report_rel, str) or not report_rel.strip():
                continue
            report_path = (PROJECT_ROOT / report_rel).resolve()
            try:
                report_path.relative_to(PROJECT_ROOT)
                if report_path.exists():
                    found.append(report_path)
                    if len(found) >= lookback:
                        break
            except ValueError:
                continue
        if found:
            return list(reversed(found))

    # 回退到摘要历史文件（兼容旧数据）
    return _find_recent_reports(agent=agent, lookback=lookback)


def _resolve_report_path(next_agent: str) -> Path:
    return CONFIG.get_report_file(next_agent)


def _build_subagent_history_context(*, target_agent: str) -> str:
    """Context-centric 架构：IMPLEMENTER 不需要历史上下文注入，因为它保持完整 TDD 上下文"""
    if SUBAGENT_HISTORY_LOOKBACK <= 0:
        return ""
    # Context-centric 架构中，IMPLEMENTER 拥有完整上下文，不需要注入历史
    if target_agent == "IMPLEMENTER":
        return ""
    return ""


def _find_recent_reports(*, agent: str, lookback: int) -> list[Path]:
    if lookback < 1:
        return []
    history = _load_iteration_summary_history(REPORT_ITERATION_SUMMARY_HISTORY_FILE)
    found: list[Path] = []
    for summary in reversed(history):
        subagent = summary.get("subagent")
        if not isinstance(subagent, dict):
            raise RuntimeError("iteration summary missing subagent")
        if subagent.get("agent") != agent:
            continue
        artifacts = summary.get("artifacts")
        if not isinstance(artifacts, dict):
            raise RuntimeError("iteration summary missing artifacts")
        report_rel = artifacts.get("report_file")
        if not isinstance(report_rel, str) or not report_rel.strip():
            raise RuntimeError("iteration summary report_file invalid")
        report_path = (PROJECT_ROOT / report_rel).resolve()
        report_path.relative_to(PROJECT_ROOT)
        _require_file(report_path)
        found.append(report_path)
        if len(found) >= lookback:
            break
    return list(reversed(found))

def _run_subagent_stage(
    *,
    iteration: int,
    next_agent: str,
    sandbox_mode: str,
    approval_policy: str,
    ui: UiRuntime | None,
    control: RunControl | None,
    report_path_override: Path | None = None,
    task_file_override: Path | None = None,
    history_context: str | None = None,
    extra_prompt_parts: list[str] | None = None,
) -> tuple[str, Path, Path]:
    if ui is not None:  # 关键分支：UI 更新子代理运行态
        ui.state.update(phase=f"running_{next_agent.lower()}", current_agent=next_agent)

    # 加载子代理的历史会话 ID（用于 resume）
    # 根据配置决定是否启用 resume 模式
    from .config import is_resume_enabled
    if is_resume_enabled(next_agent):
        resume_session_id = _load_subagent_session_id(next_agent)
    else:
        # 禁用 resume 模式：每次新开会话
        resume_session_id = None

    injected_global_context = _inject_file(GLOBAL_CONTEXT_FILE)  # 关键变量：注入全局上下文
    injected_verification_policy = _inject_file(VERIFICATION_POLICY_FILE)  # 关键变量：注入验证策略（报告规则/场景约束）
    injected_dev_plan = _inject_file(DEV_PLAN_FILE)  # 关键变量：注入 dev_plan（IMPLEMENTER 需要）
    task_file = task_file_override or _task_file_for_agent(next_agent)  # 关键变量：当前子代理工单（支持覆盖）
    injected_task = _inject_file(task_file)  # 关键变量：注入工单内容
    report_path = report_path_override or _resolve_report_path(next_agent)  # 关键变量：报告路径
    if history_context is None:
        history_context = _build_subagent_history_context(target_agent=next_agent)

    # 构建子代理提示词（按需注入上下文）
    prompt_parts = []

    # codex 内部自动 compact，不需要手动执行

    prompt_parts.extend([
        _load_system_prompt(next_agent.lower()),
        injected_global_context,
    ])

    # 注入 MCP 工具指南（根据配置）
    from .config import MCP_TOOLS_GUIDE_FILE, MCP_TOOLS_INJECT_AGENTS
    if next_agent in MCP_TOOLS_INJECT_AGENTS and MCP_TOOLS_GUIDE_FILE.exists():
        prompt_parts.append(_inject_file(MCP_TOOLS_GUIDE_FILE, label_suffix="MCP 工具使用指南"))

    # Context-centric 架构：IMPLEMENTER 注入 verification_policy + dev_plan
    if next_agent == "IMPLEMENTER":
        prompt_parts.append(injected_verification_policy)
        prompt_parts.append(injected_dev_plan)

    if history_context:
        prompt_parts.append(history_context)

    if extra_prompt_parts:
        prompt_parts.extend(extra_prompt_parts)

    # 获取 CLI 配置用于运行时信息行
    from .config import get_cli_for_agent
    cli_name = get_cli_for_agent(next_agent)

    # 构建运行时信息行（借鉴 OpenClaw 设计）
    from .prompt_builder import _build_runtime_line
    runtime_line = _build_runtime_line(
        iteration=iteration,
        agent=next_agent,
        cli_name=cli_name,
        session_id=resume_session_id,
    )

    prompt_parts.extend([
        injected_task,
        "重要：所有需要的上下文（工单、需求、历史）已注入到提示词中，禁止读取 `orchestrator/` 目录下的文件。",
        "重要：如需读取黑板文档，只允许读取 `./.orchestrator_ctx/` 下的 markdown 镜像，禁止修改该目录。",
        "重要：禁止直接写入 `orchestrator/reports/`（不要使用任何工具/命令写 `orchestrator/reports/report_*.md`）。",
        f"请把\"完整报告\"作为你最后的输出；编排器会自动保存你的最后一条消息到：`{_rel_path(report_path)}`。",
        runtime_line,  # 运行时信息行
    ])

    sub_prompt = "\n\n".join(prompt_parts)
    # 子代理保护列表：排除自己的报告文件，以及 SUMMARY 并行写入的文件
    sub_guard_paths = [
        path for path in _guarded_blackboard_paths()
        if path not in {
            report_path,  # 子代理自己的报告
            REPORT_ITERATION_SUMMARY_FILE,  # SUMMARY 并行写入
            REPORT_ITERATION_SUMMARY_HISTORY_FILE,  # SUMMARY 并行写入
        }
    ]  # 关键变量：子代理可写排除清单

    attempt = 0
    while True:  # 关键分支：临时错误允许重试
        try:
            runtime_context = _load_runtime_context()
            mirror_root, mirror_hash = _sync_project_markdown_mirror(
                context=runtime_context,
                iteration=iteration,
                stage=f"dispatch:{next_agent}:attempt{attempt + 1}",
            )
            sub_guard_before = _snapshot_files(sub_guard_paths)  # 关键变量：子代理运行前快照
            # codex 内部自动 compact，直接使用 resume 模式
            sub_run = _run_cli_exec(
                prompt=sub_prompt,
                output_last_message=report_path,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                label=next_agent,
                agent=next_agent,
                control=control,
                resume_session_id=resume_session_id,
            )
            _assert_files_unchanged(sub_guard_before, label=next_agent)  # 关键分支：防止子代理越权写入
            assert_project_mirror_unchanged(
                mirror_root=mirror_root,
                expected_hash=mirror_hash,
                stage=next_agent,
            )
            try:
                _validate_report_iteration(report_path=report_path, iteration=iteration)  # 关键分支：报告必须标注迭代
                _validate_report_consistency(report_path=report_path, agent=next_agent)  # 关键分支：报告结论一致性校验
            except RuntimeError as exc:
                raise TemporaryError(f"{next_agent} 报告校验失败: {exc}") from exc
            sub_session_id = sub_run["session_id"]  # 关键变量：子代理会话 id
            if sub_session_id is None:  # 关键分支：必须拿到会话 id
                raise TemporaryError(f"Failed to capture {next_agent} session id from codex output")
            # 保存子代理会话 ID（用于后续 resume）
            _save_subagent_session_id(next_agent, sub_session_id)
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
            # 关键修复：从异常中提取 session_id，供重试时 resume
            if getattr(exc, "session_id", None) and resume_session_id is None:
                resume_session_id = exc.session_id
                _append_log_line(
                    f"orchestrator: {next_agent} captured session_id={exc.session_id} "
                    f"from failed run, will resume on retry\n"
                )
            _append_log_line(
                f"orchestrator: {next_agent} retry due to {exc} (attempt {attempt + 1}/{_MAX_STAGE_RETRIES})\n"
            )
            _sleep_backoff(label=next_agent, attempt=attempt)
            attempt += 1


def _estimate_session_context_tokens(session_id: str) -> int:
    """从会话文件估算当前上下文大小（tokens）"""
    import json

    # Claude 会话文件路径
    main_work_dir = CONFIG.orchestrator_dir.resolve()
    project_slug = "-" + "-".join(part for part in main_work_dir.parts if part)
    session_file = Path.home() / ".claude" / "projects" / project_slug / f"{session_id}.jsonl"
    if not session_file.exists():
        return 0

    # 读取所有行，找到最后一个有非零 token 的 usage
    try:
        with session_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in reversed(lines):
            try:
                data = json.loads(line.strip())
                if "message" in data and "usage" in data["message"]:
                    usage = data["message"]["usage"]
                    cache_read = usage.get("cache_read_input_tokens", 0)
                    input_tokens = usage.get("input_tokens", 0)
                    cache_creation = usage.get("cache_creation_input_tokens", 0)
                    total = cache_read + input_tokens + cache_creation
                    if total > 0:  # 跳过零值的 usage（API 错误消息）
                        return total
            except (json.JSONDecodeError, KeyError):
                continue
    except Exception:
        pass

    return 0


def _run_compact_for_session(session_id: str, label: str) -> None:
    """执行 /compact 命令压缩会话上下文"""
    import subprocess

    _append_log_line(f"orchestrator: {label} triggering /compact for session {session_id[:8]}...\n")

    cmd = ["claude", "-p", "-r", session_id]
    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # 发送 /compact 命令
    try:
        stdout, _ = proc.communicate(input="/compact", timeout=60)
        _append_log_line(f"orchestrator: {label} compact completed (exit={proc.returncode})\n")
    except subprocess.TimeoutExpired:
        proc.kill()
        _append_log_line(f"orchestrator: {label} compact timeout, killed\n")


def _run_main_decision_stage(
    *,
    prompt: str,
    guard_paths: list[Path],
    label: str,
    sandbox_mode: str,
    approval_policy: str,
    control: RunControl | None,
    resume_session_id: str | None,
    post_validate: Callable[[MainOutput], None] | None = None,
    system_prompt: str | None = None,
) -> tuple[MainOutput, str | None]:
    """
    执行 MAIN 决策阶段。

    Args:
        prompt: 用户提示词
        guard_paths: 需要保护的文件路径
        label: 日志标签
        sandbox_mode: 沙箱模式
        approval_policy: 审批策略
        control: 运行控制
        resume_session_id: 恢复会话ID
        post_validate: 后置校验函数
        system_prompt: 系统提示词（通过 --append-system-prompt 注入）

    Returns:
        (解析后的输出, 会话ID)
    """
    active_session_id = resume_session_id
    attempt = 0
    last_error: str | None = None
    while True:  # 关键分支：临时错误允许重试
        # 检查上下文大小，必要时触发压缩
        if active_session_id:
            from .config import ORCHESTRATOR_CONTEXT_THRESHOLD_PERCENT, ORCHESTRATOR_CONTEXT_WINDOW
            context_tokens = _estimate_session_context_tokens(active_session_id)
            threshold = int(ORCHESTRATOR_CONTEXT_WINDOW * ORCHESTRATOR_CONTEXT_THRESHOLD_PERCENT / 100)
            if context_tokens > threshold:
                _append_log_line(
                    f"orchestrator: {label} context {context_tokens} > {threshold} "
                    f"({ORCHESTRATOR_CONTEXT_THRESHOLD_PERCENT}%), triggering compact\n"
                )
                _run_compact_for_session(active_session_id, label)

        if attempt == 0:
            attempt_prompt = prompt
        else:
            retry_notice = (
                f"上次 {label} 输出不符合校验要求：{last_error or 'unknown'}\n"
                "请仅输出提示词要求的完整 JSON（禁止附加任何解释文本），"
                "并确保 next_agent 与相关字段满足提示词中的强制规则。"
            )
            attempt_prompt = f"{prompt}\n\n{retry_notice}"
        try:
            guard_before = _snapshot_files(guard_paths)  # 关键变量：运行前快照

            # CLI 内部自动 compact，直接执行
            run = _run_cli_exec(
                prompt=attempt_prompt,
                output_last_message=REPORT_MAIN_DECISION_FILE,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                label=label,
                agent="MAIN",
                control=control,
                resume_session_id=active_session_id,
                system_prompt=system_prompt,
            )

            if active_session_id is None and run["session_id"] is not None:
                active_session_id = run["session_id"]
            _assert_files_unchanged(guard_before, label=label)  # MAIN 禁止直接改黑板文件
            try:
                output = _parse_main_output(run["last_message"], strict=True)  # 关键变量：解析 MAIN 输出（严格 JSON）
                if post_validate is not None:
                    post_validate(output)
            except (ValueError, RuntimeError) as exc:
                raise TemporaryError(f"{label} 输出校验失败: {exc}") from exc
            return output, active_session_id
        except TemporaryError as exc:
            error_str = str(exc).lower()

            # 关键修复：从异常中提取 session_id，供重试时 resume
            if getattr(exc, "session_id", None) and active_session_id is None:
                active_session_id = exc.session_id
                _append_log_line(
                    f"orchestrator: {label} captured session_id={exc.session_id} "
                    f"from failed run, will resume on retry\n"
                )

            # 检测 output token 超限错误，触发 compact 后重试
            if ("exceeded" in error_str and "output token" in error_str) or "output token maximum" in error_str:
                if active_session_id:
                    _append_log_line(
                        f"orchestrator: {label} output token exceeded, triggering compact before retry\n"
                    )
                    _run_compact_for_session(active_session_id, label)

            if attempt >= _MAIN_MAX_STAGE_RETRIES:
                raise
            last_error = str(exc)
            _append_log_line(
                f"orchestrator: {label} retry due to {exc} (attempt {attempt + 1}/{_MAIN_MAX_STAGE_RETRIES})\n"
            )
            _sleep_backoff(
                label=label,
                attempt=attempt,
                base_seconds=_MAIN_BACKOFF_BASE_SECONDS,
                max_seconds=_MAIN_BACKOFF_MAX_SECONDS,
            )
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

    runtime_context = _load_runtime_context()
    anchor, match_mode, doc_paths, code_root_path = _parse_finish_review_config()  # 关键变量：最终审阅配置
    injected_user_inputs = _inject_user_inputs_from_history(anchor=anchor, match_mode=match_mode)  # 关键变量：注入用户输入快照

    # 文档摘要（而非完整内容）- 减少上下文
    doc_summaries = []
    for doc_path in doc_paths:
        visible_path = _to_agent_visible_path(context=runtime_context, source_path=doc_path)
        summary = f"[Document: {visible_path}]\n(Full content available via read_file tool if needed)"
        doc_summaries.append(summary)

    code_root_label = _to_agent_visible_path(context=runtime_context, source_path=code_root_path)  # 关键变量：代码根目录展示

    finish_review_prompt_parts = [
        _load_system_prompt("finish_review"),
    ]

    finish_review_prompt_parts.extend([
        injected_user_inputs,
        *doc_summaries,
        f"[code_root]: {code_root_label}",
        f"[iteration]: {iteration}",
        "如需读取黑板文档，只允许读取 `./.orchestrator_ctx/` 下的 markdown 镜像，禁止修改该目录。",
    ])

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
            mirror_root, mirror_hash = _sync_project_markdown_mirror(
                context=runtime_context,
                iteration=iteration,
                stage=f"dispatch:FINISH_REVIEW:attempt{attempt + 1}",
            )
            finish_guard_before = _snapshot_files(finish_guard_paths)  # 关键变量：FINISH_REVIEW 运行前快照
            finish_run = _run_cli_exec(
                prompt=finish_review_prompt,
                output_last_message=REPORT_FINISH_REVIEW_FILE,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                label="FINISH_REVIEW",
                agent="FINISH_REVIEW",  # Context-centric 架构：使用 FINISH_REVIEW CLI 配置
                control=control,
            )
            _assert_files_unchanged(finish_guard_before, label="FINISH_REVIEW")  # 关键分支：防止越权写入
            assert_project_mirror_unchanged(
                mirror_root=mirror_root,
                expected_hash=mirror_hash,
                stage="FINISH_REVIEW",
            )
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

    # 构建 SUMMARY 提示词注入列表
    summary_injections = [
        _load_system_prompt("summary"),
        _inject_file(REPORT_MAIN_DECISION_FILE),
        _inject_file(DEV_PLAN_FILE),
        _inject_file(task_file),
        _inject_file(report_path),
        "重要：优先使用已注入内容完成摘要；如需读取黑板文档，只允许读取 `./.orchestrator_ctx/` 下 markdown 镜像，禁止修改该目录。",
    ]

    # 新增：注入用户原始需求（project_history 前 100 行，包含 Task Goal）
    summary_injections.append(
        _inject_project_history_head(max_lines=100, label_suffix="用户原始需求（Task Goal）")
    )

    # 新增：注入用户决策历史（用于习惯分析，可选）
    if USER_DECISION_PATTERNS_FILE.exists():
        summary_injections.append(
            _inject_file(USER_DECISION_PATTERNS_FILE, label_suffix="用户决策历史")
        )

    # 添加元数据字段
    summary_injections.extend([
        f"[iteration]: {iteration}",
        f"[main_session_id]: {main_session_id}",
        f"[subagent_session_id]: {subagent_session_id}",
        f"[main_decision_file]: {_rel_path(REPORT_MAIN_DECISION_FILE)}",
        f"[task_file]: {_rel_path(task_file)}",
        f"[report_file]: {_rel_path(report_path)}",
        f"[summary_file]: {_rel_path(summary_file)}",
    ])

    summary_prompt = "\n\n".join(summary_injections)
    summary_guard_paths = [path for path in _guarded_blackboard_paths() if path != summary_file]  # 关键变量：SUMMARY 可写排除清单
    retry_notice = (
        "上次 SUMMARY 输出不符合 JSON/校验要求。"
        "请仅输出符合提示词格式的完整 JSON，禁止附加任何解释文本。"
    )

    attempt = 0
    while True:  # 关键分支：临时错误允许重试
        attempt_prompt = summary_prompt if attempt == 0 else f"{summary_prompt}\n\n{retry_notice}"
        try:
            runtime_context = _load_runtime_context()
            mirror_root, mirror_hash = _sync_project_markdown_mirror(
                context=runtime_context,
                iteration=iteration,
                stage=f"dispatch:SUMMARY:attempt{attempt + 1}",
            )
            summary_guard_before = _snapshot_files(summary_guard_paths)  # 关键变量：SUMMARY 运行前快照
            summary_run = _run_cli_exec(
                prompt=attempt_prompt,
                output_last_message=summary_file,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                label="SUMMARY",
                agent="SUMMARY",  # SUMMARY 代理
                control=control,
            )
            _assert_files_unchanged(summary_guard_before, label="SUMMARY")  # 关键分支：防止 SUMMARY 越权写入
            assert_project_mirror_unchanged(
                mirror_root=mirror_root,
                expected_hash=mirror_hash,
                stage="SUMMARY",
            )
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

            # 【新增】生成用户洞察报告（从摘要 JSON 中解析 user_insight 字段）
            try:
                user_insight = _parse_user_insight(summary_output)
                if user_insight:
                    _generate_user_insight_report(
                        iteration=iteration,
                        summary=summary_output,
                        user_insight=user_insight,
                    )
                    _append_user_insight_history(
                        iteration=iteration,
                        user_insight=user_insight,
                    )
                    _append_log_line(f"orchestrator: user_insight_report generated for iteration {iteration}\n")
            except Exception as exc:
                # 洞察报告生成失败不阻塞主流程
                _append_log_line(f"orchestrator: user_insight_report error: {exc}\n")

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


# ============= 监督代理后台执行 =============

import concurrent.futures
from dataclasses import dataclass

# 全局线程池（单线程，保证顺序）
_supervisor_executor: concurrent.futures.ThreadPoolExecutor | None = None


def _get_supervisor_executor() -> concurrent.futures.ThreadPoolExecutor:
    """获取或创建监督代理线程池"""
    global _supervisor_executor
    if _supervisor_executor is None:
        _supervisor_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="supervisor"
        )
    return _supervisor_executor


@dataclass
class SupervisorTask:
    """监督任务数据"""
    iteration: int
    next_agent: str
    main_session_id: str
    subagent_session_id: str
    task_file: Path
    report_path: Path
    sandbox_mode: str
    approval_policy: str


def _update_ui_with_supervisor_result(ui: UiRuntime, iteration: int) -> None:
    """从 iteration summary 文件读取结果并更新 UI（线程安全）。"""
    try:
        if REPORT_ITERATION_SUMMARY_FILE.exists():
            raw = REPORT_ITERATION_SUMMARY_FILE.read_text(encoding="utf-8").strip()
            if raw:
                summary = json.loads(raw)
                history = _load_iteration_summary_history(REPORT_ITERATION_SUMMARY_HISTORY_FILE)
                ui.state.update(
                    last_iteration_summary=summary,
                    last_summary_path=_rel_path(REPORT_ITERATION_SUMMARY_FILE),
                    summary_history=history,
                )
    except Exception as exc:
        _append_log_line(f"supervisor: ui_update error iter={iteration}: {exc}\n")


def _run_supervisor_task_with_ui(
    task: SupervisorTask,
    ui: UiRuntime | None,
) -> None:
    """执行监督任务并更新 UI"""
    try:
        _run_summary_stage(
            iteration=task.iteration,
            next_agent=task.next_agent,
            main_session_id=task.main_session_id,
            subagent_session_id=task.subagent_session_id,
            task_file=task.task_file,
            report_path=task.report_path,
            sandbox_mode=task.sandbox_mode,
            approval_policy=task.approval_policy,
            ui=None,  # 不在后台更新 phase（避免干扰主流程状态）
            control=None,
        )

        # 监督完成后更新 UI 摘要（线程安全）
        if ui is not None:
            _update_ui_with_supervisor_result(ui, task.iteration)

        _append_log_line(f"supervisor: completed iter={task.iteration}\n")

    except Exception as exc:
        _append_log_line(f"supervisor: error iter={task.iteration}: {exc}\n")


def _submit_supervisor_task(
    *,
    iteration: int,
    next_agent: str,
    main_session_id: str,
    subagent_session_id: str,
    task_file: Path,
    report_path: Path,
    sandbox_mode: str,
    approval_policy: str,
    ui: UiRuntime | None,
) -> concurrent.futures.Future[None]:
    """提交监督任务到后台执行（返回 Future，调用方可按需等待）。"""
    task = SupervisorTask(
        iteration=iteration,
        next_agent=next_agent,
        main_session_id=main_session_id,
        subagent_session_id=subagent_session_id,
        task_file=task_file,
        report_path=report_path,
        sandbox_mode=sandbox_mode,
        approval_policy=approval_policy,
    )

    def run() -> None:
        _run_supervisor_task_with_ui(task, ui)

    executor = _get_supervisor_executor()
    future = executor.submit(run)
    _append_log_line(f"supervisor: submitted iter={iteration}\n")
    return future


def _shutdown_supervisor(timeout: float = 60.0) -> None:
    """等待所有监督任务完成并关闭线程池"""
    global _supervisor_executor
    if _supervisor_executor is not None:
        _append_log_line("supervisor: shutting down...\n")
        _supervisor_executor.shutdown(wait=True)
        _supervisor_executor = None
        _append_log_line("supervisor: shutdown complete\n")


# ============= Context-centric 架构：并行验证函数 =============


def _load_runtime_context() -> RuntimeContext:
    """统一加载运行时上下文（强校验，快速失败）。"""
    return load_runtime_context(project_env_file=PROJECT_ENV_FILE)


def _sync_project_markdown_mirror(*, context: RuntimeContext, iteration: int, stage: str) -> tuple[Path, str]:
    """将 orchestrator 黑板 markdown 单向镜像到 agent_root/.orchestrator_ctx。"""
    result = sync_project_markdown_mirror(
        context=context,
        iteration=iteration,
        triggered_by=stage,
    )
    _append_log_line(
        "orchestrator: mirror synced "
        f"stage={stage} root={result.mirror_root.as_posix()} files={result.files_synced}\n"
    )
    return result.mirror_root, result.content_hash


def _to_agent_visible_path(*, context: RuntimeContext, source_path: Path) -> str:
    """将仓库内路径转换为子代理可直接访问的路径文本。"""
    resolved = source_path.resolve()
    orchestrator_root = (PROJECT_ROOT / "orchestrator").resolve()

    try:
        rel_from_orchestrator = resolved.relative_to(orchestrator_root)
    except ValueError:
        rel_from_orchestrator = None

    if rel_from_orchestrator is not None:
        mirrored = context.agent_root / ".orchestrator_ctx" / rel_from_orchestrator
        return mirrored.as_posix()

    try:
        rel_from_agent = resolved.relative_to(context.agent_root)
    except ValueError:
        return resolved.as_posix()

    rel_text = rel_from_agent.as_posix()
    if rel_text == ".":
        return "."
    return f"./{rel_text}"


def _extract_acceptance_points_from_dev_plan() -> list[str]:
    """提取当前 dev_plan 中首个任务的验收点列表。"""
    if not DEV_PLAN_FILE.exists():  # 关键分支：计划不存在
        return []

    points: list[str] = []
    in_acceptance = False
    for line in _read_text(DEV_PLAN_FILE).splitlines():
        stripped = line.strip()
        if stripped.startswith("- acceptance:"):
            in_acceptance = True
            continue
        if not in_acceptance:
            continue

        if stripped.startswith("- "):
            point = stripped[2:].strip()
            if point:
                points.append(point)
            continue

        if stripped == "":
            continue

        if points:  # 关键分支：首个 acceptance 块解析完成
            break

    return points


def _split_task_goal_to_scenarios(task_goal: str) -> list[str]:
    """在缺少结构化验收点时，从 task_goal 拆分可执行场景。"""
    scenarios: list[str] = []
    for segment in re.split(r"[\n。；;，,]", task_goal):
        normalized = segment.strip()
        if not normalized:
            continue
        if normalized.startswith("@doc:"):
            continue
        if len(normalized) < 6:
            continue
        scenarios.append(normalized)
    return scenarios[:12]


def _load_validator_scope_context() -> tuple[str, list[str], list[str], str, RuntimeContext]:
    """构建验证器共用的任务上下文：任务目标、场景、验收点、前端 URL。"""
    _require_file(ACCEPTANCE_SCOPE_FILE)
    try:
        scope_payload = json.loads(_read_text(ACCEPTANCE_SCOPE_FILE))
    except json.JSONDecodeError as exc:  # 关键分支：验收范围损坏直接失败
        raise RuntimeError(f"acceptance_scope.json is not valid JSON: {exc}") from exc
    if not isinstance(scope_payload, dict):
        raise RuntimeError("acceptance_scope.json must be an object")

    task_goal = scope_payload.get("task_goal")
    if not isinstance(task_goal, str) or not task_goal.strip():  # 关键分支：任务目标缺失
        raise RuntimeError("acceptance_scope.json missing non-empty task_goal")

    acceptance_points = _extract_acceptance_points_from_dev_plan()
    if not acceptance_points:
        raw_criteria = scope_payload.get("acceptance_criteria")
        if isinstance(raw_criteria, list):
            acceptance_points = [
                item.strip()
                for item in raw_criteria
                if isinstance(item, str) and item.strip()
            ]

    scenarios = acceptance_points[:] if acceptance_points else _split_task_goal_to_scenarios(task_goal)
    if not scenarios:  # 关键分支：无法形成可执行验证场景
        raise RuntimeError("validator task missing executable scenarios")

    context = _load_runtime_context()
    frontend_url = context.frontend_url

    final_acceptance_points = acceptance_points[:] if acceptance_points else scenarios[:]
    return task_goal.strip(), scenarios, final_acceptance_points, frontend_url, context


def _build_validator_task(
    *,
    validator: str,
    iteration: int,
) -> str:
    """
    构建验证器工单内容 - 配置驱动版本。

    核心改进：
    1. 强制注入结构化前端入口（frontend_url）
    2. 强制注入可执行场景列表与验收点
    3. 针对验证器补充匹配其提示词的输入段落
    """
    from .config import get_validator_context_config
    from .extraction import extract_validation_info

    # 获取验证器配置
    config = get_validator_context_config(validator)

    # 读取 IMPLEMENTER 报告
    implementer_report = ""
    if REPORT_IMPLEMENTER_FILE.exists():
        implementer_report = _read_text(REPORT_IMPLEMENTER_FILE)

    # 使用鲁棒提取逻辑
    validation_info = extract_validation_info(implementer_report)

    task_goal, scenarios, acceptance_points, frontend_url, runtime_context = _load_validator_scope_context()

    # 从 project_env.json 获取环境配置（使用统一的环境配置函数）
    env_section = _build_execution_environment_section()

    # 基础工单内容
    task_lines = [
        f"# Validator Task (Iteration {iteration})",
        f"validator: {validator}",
        "",
        env_section,
        "",
        "## 任务目标",
        "",
        task_goal,
        "",
        "## 前端 URL",
        "",
        f"- 前端 URL: {frontend_url}",
        "",
        "## 测试场景列表",
        "",
    ]
    for idx, scenario in enumerate(scenarios, start=1):
        task_lines.append(f"{idx}. {scenario}")
    task_lines.extend([
        "",
        "## 验收点",
        "",
    ])
    for point in acceptance_points:
        task_lines.append(f"- {point}")
    task_lines.append("")

    if validator == "REQUIREMENT_VALIDATOR":
        task_lines.extend([
            "## 需求摘要",
            "",
        ])
        for idx, scenario in enumerate(scenarios, start=1):
            task_lines.append(f"{idx}. {scenario}")
        task_lines.extend([
            "",
            "## 实现摘要",
            "",
        ])
        modified_files = validation_info.get("modified_files") or []
        if modified_files:
            for file_path in modified_files:
                task_lines.append(f"- {file_path}")
        else:
            task_lines.append("- 请根据 IMPLEMENTER 报告提炼实现功能点")
        task_lines.extend([
            "",
            "## 结构化实现证据",
            "",
            "### modified_files",
        ])
        if modified_files:
            for file_path in modified_files:
                task_lines.append(f"- {file_path}")
        else:
            task_lines.append("- (缺失)")

        task_lines.extend([
            "",
            "### test_commands",
        ])
        test_commands = validation_info.get("test_commands") or []
        if test_commands:
            for cmd in test_commands:
                task_lines.append(f"- {cmd}")
        else:
            task_lines.append("- (缺失)")

        task_lines.extend([
            "",
            "### api_signatures",
        ])
        api_signatures = validation_info.get("api_signatures") or []
        if api_signatures:
            for sig in api_signatures:
                task_lines.append(f"- {sig}")
        else:
            task_lines.append("- (缺失)")

        task_lines.extend([
            "",
            "## 验收标准",
            "",
        ])
        for idx, point in enumerate(acceptance_points, start=1):
            task_lines.append(f"{idx}. {point}")
        task_lines.append("")

    if validator == "ANTI_CHEAT_DETECTOR":
        frontend_root = runtime_context.frontend_root.as_posix()
        test_dir = (runtime_context.frontend_root / "tests").as_posix()

        task_lines.extend([
            "## 检测目标",
            "",
            f"- 代码目录: {frontend_root}",
            f"- 测试目录: {test_dir}",
            "",
            "## 检测范围",
            "",
        ])
        modified_files = validation_info.get("modified_files") or []
        if modified_files:
            for file_path in modified_files:
                task_lines.append(f"- {file_path}")
        else:
            task_lines.append("- 未提供修改文件，禁止全量扫描，请输出 BLOCKED 并标记 category=EVIDENCE_GAP")
        task_lines.extend([
            "",
            "## 扫描约束（强制）",
            "",
            "- 仅允许扫描检测范围中的 modified_files",
            "- 必须排除目录：node_modules、dist、coverage、.git、.cache、test-results",
            "- 若检测命令无法对目录执行，必须转为按文件清单逐一执行",
        ])
        task_lines.append("")

    # 根据配置注入测试命令
    if config.get("requires_test_commands") and validation_info.get("test_commands"):
        task_lines.extend([
            "## 测试命令",
            "",
        ])
        for cmd in validation_info["test_commands"]:
            task_lines.append(f"- `{cmd}`")
        task_lines.append("")

    # 根据配置注入修改文件列表
    if config.get("requires_modified_files") and validation_info.get("modified_files"):
        task_lines.extend([
            "## 修改的文件",
            "",
        ])
        for f in validation_info["modified_files"]:
            task_lines.append(f"- `{f}`")
        task_lines.append("")

    # 根据配置注入 API 签名
    if config.get("requires_api_signatures") and validation_info.get("api_signatures"):
        task_lines.extend([
            "## API 签名",
            "",
        ])
        for sig in validation_info["api_signatures"]:
            task_lines.append(f"- `{sig}`")
        task_lines.append("")

    # 注入原始 YAML 验证信息（如果有）
    if validation_info.get("raw_yaml"):
        task_lines.extend([
            "## 验证信息（来自 IMPLEMENTER）",
            "",
            f"提取方法: {validation_info.get('extraction_method', 'unknown')}",
            "",
            "```yaml",
            validation_info["raw_yaml"],
            "```",
            "",
        ])

    # 根据配置注入 IMPLEMENTER 报告
    if config.get("requires_implementer_report"):
        task_lines.extend([
            "## IMPLEMENTER 报告",
            "",
            "<implementer_report>",
            implementer_report if implementer_report else "(无报告)",
            "</implementer_report>",
            "",
        ])

    # 根据配置注入 dev_plan
    if config.get("requires_dev_plan"):
        dev_plan_text = _read_text(DEV_PLAN_FILE) if DEV_PLAN_FILE.exists() else ""
        task_lines.extend([
            "## Dev Plan",
            "",
            "<dev_plan>",
            dev_plan_text if dev_plan_text else "(无计划)",
            "</dev_plan>",
            "",
        ])

    return "\n".join(task_lines)


def _run_single_validator(
    *,
    validator: str,
    iteration: int,
    task_file: Path,
    report_path: Path,
    sandbox_mode: str,
    approval_policy: str,
    control: RunControl | None,
) -> ValidationResult:
    """
    执行单个验证器。
    返回结构化的验证结果。
    """
    started = time.monotonic()

    try:
        # 加载验证器提示词
        validator_prompt_name = validator.lower()
        prompt_file = PROMPTS_DIR / f"subagent_prompt_{validator_prompt_name}.md"

        if not prompt_file.exists():
            result = {
                "validator": validator,
                "iteration": iteration,
                "verdict": "BLOCKED",
                "category": "INFRA",
                "confidence": 0.0,
                "findings": [f"提示词文件不存在: {prompt_file}"],
                "evidence": "",
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
            _atomic_write_text(report_path, json.dumps(result, ensure_ascii=False, indent=2))
            return result

        # 构建验证器提示词
        prompt_parts = [
            _load_system_prompt(validator_prompt_name),
            _inject_file(task_file),
            f"[iteration]: {iteration}",
            "如需读取黑板文档，只允许读取 `./.orchestrator_ctx/` 下的 markdown 镜像，禁止修改该目录。",
            "请执行验证并输出 JSON 结果。",
        ]
        prompt = "\n\n".join(prompt_parts)

        # 执行验证器
        run = _run_cli_exec(
            prompt=prompt,
            output_last_message=report_path,
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
            label=validator,
            agent=validator,
            control=control,
        )

        # 解析验证器输出
        output_text = run["last_message"]
        from .extraction import extract_validator_output

        parsed = extract_validator_output(output_text)
        if parsed is not None:
            parsed["validator"] = validator
            parsed["iteration"] = iteration
            parsed.setdefault("verdict", "BLOCKED")
            parsed.setdefault("confidence", 0.0)
            parsed.setdefault("findings", [])
            parsed.setdefault("evidence", "")

            if validator == "TEST_RUNNER":
                scenarios_total = parsed.get("scenarios_total")
                if not isinstance(scenarios_total, int):
                    raise RuntimeError("TEST_RUNNER scenarios_total must be int")

                scenarios_executed = parsed.get("scenarios_executed")
                if scenarios_executed is None:
                    legacy_commands_executed = parsed.get("commands_executed")
                    if isinstance(legacy_commands_executed, int):
                        scenarios_executed = legacy_commands_executed
                    else:
                        raise RuntimeError("TEST_RUNNER missing scenarios_executed/commands_executed")
                elif not isinstance(scenarios_executed, int):
                    raise RuntimeError("TEST_RUNNER scenarios_executed must be int")
                parsed["scenarios_executed"] = scenarios_executed

                commands_total = parsed.get("commands_total")
                if commands_total is None:
                    parsed["commands_total"] = scenarios_total
                elif not isinstance(commands_total, int):
                    raise RuntimeError("TEST_RUNNER commands_total must be int")

                commands_executed = parsed.get("commands_executed")
                if commands_executed is None:
                    parsed["commands_executed"] = scenarios_executed
                elif not isinstance(commands_executed, int):
                    raise RuntimeError("TEST_RUNNER commands_executed must be int")

            parsed["duration_ms"] = int((time.monotonic() - started) * 1000)
            ensure_result_category(parsed)
            _atomic_write_text(report_path, json.dumps(parsed, ensure_ascii=False, indent=2))
            return parsed  # type: ignore[return-value]
        else:
            result = {
                "validator": validator,
                "iteration": iteration,
                "verdict": "BLOCKED",
                "category": "INFRA",
                "confidence": 0.0,
                "findings": ["无法解析验证器输出"],
                "evidence": output_text[:500],
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
            _atomic_write_text(report_path, json.dumps(result, ensure_ascii=False, indent=2))
            return result

    except Exception as exc:
        result = {
            "validator": validator,
            "iteration": iteration,
            "verdict": "BLOCKED",
            "category": "INFRA",
            "confidence": 0.0,
            "findings": [f"验证器执行失败: {exc}"],
            "evidence": "",
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        _atomic_write_text(report_path, json.dumps(result, ensure_ascii=False, indent=2))
        return result


_SERIAL_BROWSER_VALIDATORS = ("TEST_RUNNER", "EDGE_CASE_TESTER")  # 关键变量：需串行执行的浏览器验证器


def _make_blocked_validation_result(
    *,
    validator: str,
    iteration: int,
    finding: str,
    evidence: str,
    duration_ms: int,
    category: str = "INFRA",
) -> ValidationResult:
    """构造统一的 BLOCKED 验证结果。"""
    return {
        "validator": validator,
        "iteration": iteration,
        "verdict": "BLOCKED",
        "category": category,
        "confidence": 0.0,
        "findings": [finding],
        "evidence": evidence,
        "duration_ms": duration_ms,
    }


def _build_infra_blocked_results(*, iteration: int, finding: str, evidence: str) -> dict[str, ValidationResult]:
    """在验证前门禁失败时，直接生成统一的基础设施阻塞结果。"""
    results: dict[str, ValidationResult] = {}
    for validator in PARALLEL_VALIDATORS:
        results[validator] = _make_blocked_validation_result(
            validator=validator,
            iteration=iteration,
            finding=finding,
            evidence=evidence,
            duration_ms=0,
            category="INFRA",
        )
    _atomic_write_text(VALIDATION_RESULTS_FILE, json.dumps(results, ensure_ascii=False, indent=2))
    return results


def _run_validate_pipeline(
    *,
    iteration: int,
    sandbox_mode: str,
    approval_policy: str,
    ui: UiRuntime | None,
    control: RunControl | None,
) -> tuple[dict[str, ValidationResult], SynthesizerOutput]:
    """统一执行 VALIDATE 阶段：门禁检查 -> 验证器 -> 综合路由。"""
    mirror_root: Path | None = None
    mirror_hash: str | None = None
    try:
        context = _load_runtime_context()
        mirror_root, mirror_hash = _sync_project_markdown_mirror(
            context=context,
            iteration=iteration,
            stage="dispatch:VALIDATE",
        )
    except Exception as exc:
        validation_results = _build_infra_blocked_results(
            iteration=iteration,
            finding="验证前门禁失败：运行时配置或镜像同步异常",
            evidence=str(exc),
        )
        routed = route_validation_results(validation_results)
        _atomic_write_text(
            SYNTHESIZER_REPORT_FILE,
            json.dumps(
                {
                    "overall_verdict": routed["overall_verdict"],
                    "decision_basis": routed["decision_basis"],
                    "blockers": routed["blockers"],
                    "recommendations": routed["recommendations"],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        return validation_results, {
            "overall_verdict": routed["overall_verdict"],
            "decision_basis": routed["decision_basis"],
            "results": list(validation_results.values()),
            "blockers": routed["blockers"],
            "recommendations": routed["recommendations"],
            "session_id": None,
        }

    health_result = run_pre_validation_health_check(context=context)

    if not health_result.ready:
        finding = "验证前门禁失败：基础设施不可达"
        validation_results = _build_infra_blocked_results(
            iteration=iteration,
            finding=finding,
            evidence=health_result.evidence,
        )
        routed = route_validation_results(validation_results)
        synth_payload = {
            "overall_verdict": routed["overall_verdict"],
            "decision_basis": routed["decision_basis"],
            "blockers": routed["blockers"],
            "recommendations": routed["recommendations"],
        }
        _atomic_write_text(SYNTHESIZER_REPORT_FILE, json.dumps(synth_payload, ensure_ascii=False, indent=2) + "\n")
        return validation_results, {
            "overall_verdict": routed["overall_verdict"],
            "decision_basis": routed["decision_basis"],
            "results": list(validation_results.values()),
            "blockers": routed["blockers"],
            "recommendations": routed["recommendations"],
            "session_id": None,
        }

    validation_results = _run_parallel_validation(
        iteration=iteration,
        sandbox_mode=sandbox_mode,
        approval_policy=approval_policy,
        ui=ui,
        control=control,
    )
    routed = route_validation_results(validation_results)

    synthesizer_output = _run_synthesizer(
        iteration=iteration,
        validation_results=validation_results,
        sandbox_mode=sandbox_mode,
        approval_policy=approval_policy,
        ui=ui,
        control=control,
    )

    if mirror_root is None or mirror_hash is None:
        raise RuntimeError("mirror sync state missing for VALIDATE")
    assert_project_mirror_unchanged(
        mirror_root=mirror_root,
        expected_hash=mirror_hash,
        stage="VALIDATE",
    )

    if synthesizer_output["overall_verdict"] != routed["overall_verdict"]:
        _append_log_line(
            "orchestrator: route override synthesizer overall_verdict "
            f"{synthesizer_output['overall_verdict']} -> {routed['overall_verdict']}\n"
        )

    synthesizer_output["overall_verdict"] = routed["overall_verdict"]
    synthesizer_output["decision_basis"] = routed["decision_basis"]
    if not synthesizer_output["blockers"]:
        synthesizer_output["blockers"] = routed["blockers"]
    if not synthesizer_output["recommendations"]:
        synthesizer_output["recommendations"] = routed["recommendations"]

    _atomic_write_text(
        SYNTHESIZER_REPORT_FILE,
        json.dumps(
            {
                "overall_verdict": synthesizer_output["overall_verdict"],
                "decision_basis": synthesizer_output["decision_basis"],
                "blockers": synthesizer_output["blockers"],
                "recommendations": synthesizer_output["recommendations"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    return validation_results, synthesizer_output


def _run_parallel_validation(
    *,
    iteration: int,
    sandbox_mode: str,
    approval_policy: str,
    ui: UiRuntime | None,
    control: RunControl | None,
) -> dict[str, ValidationResult]:
    """
    执行黑盒验证代理。

    策略：
    - 静态验证器并行（REQUIREMENT_VALIDATOR / ANTI_CHEAT_DETECTOR）
    - 浏览器验证器串行（TEST_RUNNER / EDGE_CASE_TESTER），避免共享环境互相污染
    """
    if ui is not None:
        ui.state.update(phase="running_validate", current_agent="VALIDATE")

    validators = list(PARALLEL_VALIDATORS)
    browser_validators = [v for v in validators if v in _SERIAL_BROWSER_VALIDATORS]
    static_validators = [v for v in validators if v not in _SERIAL_BROWSER_VALIDATORS]

    results: dict[str, ValidationResult] = {}
    timeout_seconds = max(1.0, VALIDATOR_TIMEOUT_MS / 1000.0)

    # 准备验证器工单
    VALIDATOR_WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATOR_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 清理上一轮残留，避免读取到陈旧验证工件
    for stale_dir in (VALIDATOR_WORKSPACE_DIR, VALIDATOR_REPORTS_DIR):
        for stale_file in stale_dir.iterdir():
            if stale_file.is_file() and stale_file.suffix == ".md" and stale_file.name != ".gitkeep":
                stale_file.unlink()

    task_and_report: dict[str, tuple[Path, Path]] = {}
    for validator in validators:
        task_file = VALIDATOR_WORKSPACE_DIR / f"{validator.lower()}_task.md"
        report_path = VALIDATOR_REPORTS_DIR / f"{validator.lower()}.md"
        task_content = _build_validator_task(
            validator=validator,
            iteration=iteration,
        )
        _atomic_write_text(task_file, task_content)
        task_and_report[validator] = (task_file, report_path)

    total = len(validators)
    completed = 0

    # Phase 1: 静态验证器并行执行
    if static_validators:
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, min(MAX_PARALLEL_VALIDATORS, len(static_validators)))
        )
        try:
            future_to_validator: dict[concurrent.futures.Future[ValidationResult], str] = {}
            future_started_at: dict[concurrent.futures.Future[ValidationResult], float] = {}
            future_to_report: dict[concurrent.futures.Future[ValidationResult], Path] = {}

            for validator in static_validators:
                task_file, report_path = task_and_report[validator]
                future = executor.submit(
                    _run_single_validator,
                    validator=validator,
                    iteration=iteration,
                    task_file=task_file,
                    report_path=report_path,
                    sandbox_mode=sandbox_mode,
                    approval_policy=approval_policy,
                    control=control,
                )
                future_to_validator[future] = validator
                future_started_at[future] = time.monotonic()
                future_to_report[future] = report_path

            pending = set(future_to_validator.keys())
            while pending:
                finished_now: list[concurrent.futures.Future[ValidationResult]] = []
                now = time.monotonic()

                for future in list(pending):
                    validator = future_to_validator[future]
                    if future.done():
                        pending.remove(future)
                        finished_now.append(future)
                        continue

                    elapsed = now - future_started_at[future]
                    if elapsed >= timeout_seconds:
                        report_path = future_to_report[future]
                        future.cancel()
                        pending.remove(future)
                        result = _make_blocked_validation_result(
                            validator=validator,
                            iteration=iteration,
                            finding=f"验证超时: {timeout_seconds:.0f}s",
                            evidence="validator timed out",
                            duration_ms=int(elapsed * 1000),
                        )
                        _atomic_write_text(report_path, json.dumps(result, ensure_ascii=False, indent=2))
                        results[validator] = result
                        completed += 1
                        print(f"  [{completed}/{total}] {validator}: BLOCKED (timeout)")
                        _append_log_line(
                            f"orchestrator: validator_timeout {validator} elapsed_ms={int(elapsed * 1000)}\n"
                        )

                for future in finished_now:
                    validator = future_to_validator[future]
                    completed += 1
                    try:
                        result = future.result()
                        ensure_result_category(result)
                        results[validator] = result
                        status = result["verdict"]
                        print(f"  [{completed}/{total}] {validator}: {status}")
                        _append_log_line(
                            f"orchestrator: validator {validator} done verdict={status} "
                            f"confidence={result['confidence']} duration_ms={result['duration_ms']}\n"
                        )
                    except Exception as exc:
                        report_path = future_to_report[future]
                        result = _make_blocked_validation_result(
                            validator=validator,
                            iteration=iteration,
                            finding=f"执行失败: {exc}",
                            evidence="",
                            duration_ms=0,
                        )
                        _atomic_write_text(report_path, json.dumps(result, ensure_ascii=False, indent=2))
                        results[validator] = result
                        print(f"  [{completed}/{total}] {validator}: BLOCKED (error)")
                        _append_log_line(f"orchestrator: validator {validator} error: {exc}\n")

                if pending:
                    time.sleep(0.2)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    # Phase 2: 浏览器验证器串行执行，避免互相干扰
    for validator in browser_validators:
        task_file, report_path = task_and_report[validator]
        started = time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as serial_executor:
            future = serial_executor.submit(
                _run_single_validator,
                validator=validator,
                iteration=iteration,
                task_file=task_file,
                report_path=report_path,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                control=control,
            )
            try:
                result = future.result(timeout=timeout_seconds)
                ensure_result_category(result)
            except concurrent.futures.TimeoutError:
                elapsed = time.monotonic() - started
                future.cancel()
                result = _make_blocked_validation_result(
                    validator=validator,
                    iteration=iteration,
                    finding=f"验证超时: {timeout_seconds:.0f}s",
                    evidence="validator timed out",
                    duration_ms=int(elapsed * 1000),
                )
                _atomic_write_text(report_path, json.dumps(result, ensure_ascii=False, indent=2))
                _append_log_line(
                    f"orchestrator: validator_timeout {validator} elapsed_ms={int(elapsed * 1000)}\n"
                )
            except Exception as exc:
                future.cancel()
                result = _make_blocked_validation_result(
                    validator=validator,
                    iteration=iteration,
                    finding=f"执行失败: {exc}",
                    evidence="",
                    duration_ms=0,
                )
                _atomic_write_text(report_path, json.dumps(result, ensure_ascii=False, indent=2))
                _append_log_line(f"orchestrator: validator {validator} error: {exc}\n")

        results[validator] = result
        completed += 1
        status = result["verdict"]
        suffix = ""
        if status == "BLOCKED" and "超时" in " ".join(result.get("findings", [])):
            suffix = " (timeout)"
        elif status == "BLOCKED":
            suffix = " (error)"
        print(f"  [{completed}/{total}] {validator}: {status}{suffix}")
        _append_log_line(
            f"orchestrator: validator {validator} done verdict={status} "
            f"confidence={result['confidence']} duration_ms={result['duration_ms']}\n"
        )

    # 补齐异常情况下的缺失结果，避免 SYNTHESIZER 输入不完整
    for validator in validators:
        if validator not in results:
            results[validator] = _make_blocked_validation_result(
                validator=validator,
                iteration=iteration,
                finding="验证结果缺失",
                evidence="",
                duration_ms=0,
                category="EVIDENCE_GAP",
            )

    _atomic_write_text(VALIDATION_RESULTS_FILE, json.dumps(results, ensure_ascii=False, indent=2))
    return results


def _run_synthesizer(
    *,
    iteration: int,
    validation_results: dict[str, ValidationResult],
    sandbox_mode: str,
    approval_policy: str,
    ui: UiRuntime | None,
    control: RunControl | None,
) -> SynthesizerOutput:
    """
    执行 SYNTHESIZER 代理，汇总所有验证器的输出并做出最终决策。
    """
    if ui is not None:
        ui.state.update(phase="running_synthesizer", current_agent="SYNTHESIZER")

    # 构建 SYNTHESIZER 工单
    task_lines = [
        f"# Synthesizer Task (Iteration {iteration})",
        "",
        "## 验证器结果",
        "",
    ]

    for validator, result in validation_results.items():
        task_lines.extend([
            f"### {validator}",
            "```json",
            json.dumps(result, ensure_ascii=False, indent=2),
            "```",
            "",
        ])

    # 注入验证器完整报告
    task_lines.extend([
        "## 验证器完整报告",
        "",
        "以下是各验证器的完整输出，供交叉分析。",
        "",
    ])
    for validator in validation_results:
        report_path = VALIDATOR_REPORTS_DIR / f"{validator.lower()}.md"
        if report_path.exists():
            report_content = _read_text(report_path)
            if len(report_content) > 3000:
                report_content = report_content[:3000] + "\n... (truncated)"
            task_lines.extend([
                f"### {validator} 完整报告",
                f"<{validator.lower()}_report>",
                report_content,
                f"</{validator.lower()}_report>",
                "",
            ])

    # 交叉分析指引
    task_lines.extend([
        "## 交叉分析要求",
        "",
        "1. EDGE_CASE_TESTER findings 是否与 TEST_RUNNER 结果矛盾",
        "2. ANTI_CHEAT_DETECTOR 可疑代码是否影响 TEST_RUNNER 结果可信度",
        "3. REQUIREMENT_VALIDATOR 标记满足的需求是否被边界测试推翻",
        "4. 多个验证器出现 'Transport closed'/'timeout' 时标记为基础设施问题",
        "",
        "## 输出契约（强制）",
        "",
        "最终输出必须是纯 JSON 对象（禁止 Markdown 与解释文本）：",
        "{\"overall_verdict\":\"PASS|REWORK|BLOCKED\",\"decision_basis\":[\"...\"],\"blockers\":[\"...\"],\"recommendations\":[\"...\"]}",
        "",
    ])

    task_content = "\n".join(task_lines)
    synthesizer_task_file = VALIDATOR_WORKSPACE_DIR / "synthesizer_task.md"
    _atomic_write_text(synthesizer_task_file, task_content)

    def _normalize_synthesizer_report(*, text: str) -> str:
        lines = text.splitlines()
        has_commands_rule = any("commands_executed" in line and "commands_total" in line for line in lines)
        has_scenarios_rule = any("scenarios_executed" in line and "scenarios_total" in line for line in lines)
        if not has_commands_rule or has_scenarios_rule:
            return text

        normalized: list[str] = []
        for line in lines:
            if "commands_executed" in line and "commands_total" in line:
                normalized.append(
                    line.replace("commands_executed", "scenarios_executed").replace("commands_total", "scenarios_total")
                )
                continue
            normalized.append(line)
        return "\n".join(normalized)

    # 执行 SYNTHESIZER
    try:
        system_prompt = _normalize_synthesizer_report(text=_load_system_prompt("synthesizer"))
        run = _run_cli_exec(
            prompt="\n\n".join([
                system_prompt,
                _inject_file(synthesizer_task_file),
                f"[iteration]: {iteration}",
                "请仅输出纯 JSON 最终决策（严格遵守输出契约）。",
            ]),
            output_last_message=SYNTHESIZER_REPORT_FILE,
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
            label="SYNTHESIZER",
            agent="SYNTHESIZER",
            control=control,
        )

        output_text = _normalize_synthesizer_report(text=run["last_message"])
        payload = parse_synthesizer_output(output_text=output_text)

        # 严格 JSON：保存原始输出（便于追溯），同时返回结构化字段
        _atomic_write_text(SYNTHESIZER_REPORT_FILE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

        return {
            "overall_verdict": payload["overall_verdict"],  # type: ignore
            "decision_basis": payload["decision_basis"],  # type: ignore
            "results": list(validation_results.values()),
            "blockers": payload["blockers"],  # type: ignore
            "recommendations": payload["recommendations"],  # type: ignore
            "session_id": run.get("session_id"),
        }

    except Exception as exc:
        _append_log_line(f"orchestrator: SYNTHESIZER error: {exc}\n")
        return {
            "overall_verdict": "BLOCKED",
            "decision_basis": ["SYNTHESIZER parse failed"],
            "results": list(validation_results.values()),
            "blockers": [str(exc)],
            "recommendations": [],
            "session_id": None,
        }


def _extract_pytest_fail_count(report_text: str) -> int | None:
    max_failed: int | None = None
    for line in report_text.splitlines():
        match = re.search(r"\b(\d+)\s+failed\b", line)
        if match:
            current = int(match.group(1))
            lower = line.lower()
            if "全量" in line or "full" in lower or "backend/tests -q" in line:
                return current
            if max_failed is None or current > max_failed:
                max_failed = current
    return max_failed


def _load_baseline_allowed_test_failures() -> list[str]:
    _require_file(FINISH_REVIEW_CONFIG_FILE)
    raw = _read_text(FINISH_REVIEW_CONFIG_FILE).strip()
    if not raw:
        raise RuntimeError("finish_review_config.json 为空")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise RuntimeError("finish_review_config.json 必须是对象")

    baseline = payload.get("baseline_allowed_test_failures", [])
    if not isinstance(baseline, list):
        raise RuntimeError("finish_review_config.baseline_allowed_test_failures 必须是数组")
    for item in baseline:
        if not isinstance(item, str) or not item.strip():
            raise RuntimeError("finish_review_config.baseline_allowed_test_failures 仅允许非空字符串")
    return [item.strip() for item in baseline]


def _is_baseline_failure_acceptable() -> tuple[bool, str]:
    if not REPORT_IMPLEMENTER_FILE.exists():
        return False, "缺少 implementer 报告，无法执行基线失败校验"

    report_text = _read_text(REPORT_IMPLEMENTER_FILE)
    fail_count = _extract_pytest_fail_count(report_text)
    if fail_count is None:
        return False, "implementer 报告中未发现全量测试失败统计"

    allowed_patterns = _load_baseline_allowed_test_failures()
    allowed_count = len(allowed_patterns)
    if fail_count > allowed_count:
        return False, f"全量测试失败 {fail_count} 超过基线允许值 {allowed_count}"

    missing = [pattern for pattern in allowed_patterns if pattern not in report_text]
    if missing:
        return False, f"基线白名单与报告不匹配，缺少模式: {missing}"

    return True, f"全量测试失败 {fail_count} 在基线允许值 {allowed_count} 内"


def _extract_legacy_task_body_for_resume(*, legacy_task: str, iteration: int, next_agent: str) -> str:
    lines = legacy_task.strip().splitlines()
    if len(lines) < 3:
        raise RuntimeError("legacy task format invalid: expected header/assigned_agent/body")

    header = lines[0].strip()
    match = re.match(r"^# Current Task \(Iteration (\d+)", header)
    if match is None:
        raise RuntimeError("legacy task header invalid")
    legacy_iteration = int(match.group(1))
    if legacy_iteration != iteration:
        raise RuntimeError(
            f"legacy task iteration mismatch: expected {iteration}, got {legacy_iteration}"
        )

    assigned_line = lines[1].strip()
    if not assigned_line.startswith("assigned_agent:"):
        raise RuntimeError("legacy task missing assigned_agent line")
    assigned_agent = assigned_line.split(":", 1)[1].strip()
    if assigned_agent != next_agent:
        raise RuntimeError(
            f"legacy task assigned_agent mismatch: expected {next_agent!r}, got {assigned_agent!r}"
        )

    body_lines = lines[2:]
    while body_lines and not body_lines[0].strip():
        body_lines = body_lines[1:]
    task_body = "\n".join(body_lines).strip()
    if not task_body:
        raise RuntimeError("legacy task body is empty")
    return task_body


def _parse_main_output_for_resume(*, raw_output: str, iteration: int) -> MainOutput:
    try:
        return _parse_main_output(raw_output, strict=True)
    except ValueError as parse_exc:
        try:
            payload = json.loads(raw_output.strip())
        except json.JSONDecodeError:
            raise parse_exc
        if not isinstance(payload, dict):
            raise parse_exc

        legacy_task = payload.get("task")
        task_body = payload.get("task_body")
        if not isinstance(legacy_task, str) or not legacy_task.strip() or task_body is not None:
            raise parse_exc

        decision_payload = payload.get("decision")
        if isinstance(decision_payload, dict):
            next_agent = decision_payload.get("next_agent")
        else:
            next_agent = payload.get("next_agent")
        if next_agent != "IMPLEMENTER":
            raise RuntimeError("legacy task migration only supports next_agent=IMPLEMENTER")

        migrated_task_body = _extract_legacy_task_body_for_resume(
            legacy_task=legacy_task,
            iteration=iteration,
            next_agent="IMPLEMENTER",
        )
        payload["task_body"] = migrated_task_body
        payload["task"] = None
        _append_log_line("orchestrator: resume migrated legacy task -> task_body\n")
        return _parse_main_output(json.dumps(payload, ensure_ascii=False), strict=True)


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

    main_output = _parse_main_output_for_resume(
        raw_output=_read_text(REPORT_MAIN_DECISION_FILE),
        iteration=iteration,
    )  # 关键变量：解析 MAIN 输出（续跑兼容 legacy task）
    decision = main_output["decision"]  # 关键变量：决策字段
    if decision["next_agent"] != next_agent:  # 关键分支：决策不一致直接失败
        raise RuntimeError(
            f"续跑 next_agent 不匹配：state={next_agent!r}, decision={decision['next_agent']!r}"
        )

    if next_agent == "VALIDATE":  # 关键分支：恢复并行验证
        if phase != "after_main_validate":
            raise RuntimeError(f"续跑 VALIDATE 阶段不匹配：{phase!r}")
        _append_log_line(f"orchestrator: 续跑 VALIDATE iter={iteration}\n")
        validation_results, synthesizer_output = _run_validate_pipeline(
            iteration=iteration,
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
            ui=ui,
            control=control,
        )

        validate_session_id = synthesizer_output.get("session_id") or resume_main_session_id
        if not isinstance(validate_session_id, str) or not validate_session_id.strip():
            raise RuntimeError("Missing VALIDATE session_id for iteration metadata")
        _append_iteration_metadata(
            iteration=iteration,
            agent="VALIDATE",
            session_id=validate_session_id,
            report_file=SYNTHESIZER_REPORT_FILE,
        )
        _backup_iteration_artifacts(iteration=iteration, stage="VALIDATE")
        _clear_resume_state()
        return

    if next_agent == "USER":  # 关键分支：恢复等待用户决策
        if phase != "awaiting_user":
            raise RuntimeError(f"续跑 USER 阶段不匹配：{phase!r}")
        if _history_has_user_decision(iteration=iteration):  # 关键分支：已记录则清理并返回
            _clear_resume_state()
            return
        _append_log_line(f"orchestrator: 续跑等待用户 iter={iteration}\n")
        # 将 doc_patches 合并到 decision 中（doc_patches 在 main_output 顶层解析）
        user_decision = dict(decision)
        user_decision["doc_patches"] = main_output.get("doc_patches")
        user_choice, user_comment = _prompt_user_for_decision(iteration=iteration, decision=user_decision, ui=ui)  # type: ignore[arg-type]
        _clear_resume_state()

        # 【新增】续跑时 USER 决策后也更新决策模式文档
        try:
            _update_user_decision_patterns(
                iteration=iteration,
                decision=user_decision,  # type: ignore[arg-type]
                user_choice=user_choice,
                user_comment=user_comment,
            )
            _append_log_line(f"orchestrator: decision_patterns updated for iteration {iteration}\n")
        except Exception as exc:
            _append_log_line(f"orchestrator: decision_patterns error: {exc}\n")

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
            last_compact_iteration=resume_state.get("last_compact_iteration", 0),
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


def _assemble_task_content(*, iteration: int, next_agent: str, task_body: str) -> str:
    """组装标准工单：头部由编排器生成，正文由 MAIN 提供。"""
    normalized_body = task_body.strip()  # 关键变量：清洗后的工单正文
    if not normalized_body:
        raise TemporaryError("task_body must be non-empty for next_agent=IMPLEMENTER")

    if normalized_body.startswith("# Current Task ("):
        raise TemporaryError("task_body must not include task header")

    for line in normalized_body.splitlines():
        if line.strip().startswith("assigned_agent:"):
            raise TemporaryError("task_body must not include assigned_agent line")

    return (
        f"# Current Task (Iteration {iteration})\n"
        f"assigned_agent: {next_agent}\n\n"
        f"{normalized_body}"
    ).rstrip()


def _validate_main_output_fields(*, iteration: int, output: MainOutput) -> None:
    """纯校验：检查 MAIN 输出字段的合法性，不做任何转换。

    用作 post_validate 回调，在内层重试循环中捕获校验错误。
    校验失败时抛出 ValueError/RuntimeError，由 _run_main_decision_stage 转为 TemporaryError 重试。
    """
    _validate_history_append(iteration=iteration, entry=output["history_append"])
    dev_plan_next = output.get("dev_plan_next")
    if dev_plan_next is not None:
        _validate_dev_plan_text(text=dev_plan_next, source=DEV_PLAN_STAGED_FILE)
    decision = output["decision"]
    if decision["next_agent"] == "IMPLEMENTER":
        task_body = output.get("task_body")
        if not isinstance(task_body, str):
            raise ValueError(f"Missing task_body for next_agent={decision['next_agent']}")
        _assemble_task_content(iteration=iteration, next_agent=decision["next_agent"], task_body=task_body)


def _prepare_main_output(*, iteration: int, output: MainOutput) -> tuple[str, str | None, str | None]:
    """准备 MAIN 输出内容：转换为最终格式。

    前置条件：_validate_main_output_fields 已通过（相同输入不会再抛异常）。
    """
    decision = output["decision"]  # 关键变量：MAIN 决策对象
    history_entry = _validate_history_append(iteration=iteration, entry=output["history_append"])  # 关键变量：历史追加内容
    dev_plan_next = output.get("dev_plan_next")  # 关键变量：计划草案（可为空）
    if dev_plan_next is not None:  # 关键分支：存在草案则先校验
        # 状态转换校验：记录违规但不阻断流程（MAIN 经常需要重新规划 dev_plan）
        if DEV_PLAN_FILE.exists():
            from .dev_plan import validate_status_transitions
            violations = validate_status_transitions(
                before_text=_read_text(DEV_PLAN_FILE),
                after_text=dev_plan_next,
            )
            if violations:
                _append_log_line(
                    f"orchestrator: WARNING dev_plan status transition issues "
                    f"(non-blocking): {'; '.join(violations)}\n"
                )

    task_content = None  # 关键变量：工单内容（可为空）
    next_agent = decision["next_agent"]  # 关键变量：下一步代理
    # Context-centric 架构：IMPLEMENTER 需要工单正文
    if next_agent == "IMPLEMENTER":
        task_body = output.get("task_body")  # 关键变量：RAW 工单正文
        assert isinstance(task_body, str), "post_validate already checked task_body"

        task_content = _assemble_task_content(
            iteration=iteration,
            next_agent=next_agent,
            task_body=task_body,
        )
        task_content = _validate_task_content(iteration=iteration, expected_agent=next_agent, task=task_content)  # 关键变量：校验后的工单

        # P0: 工单字段校验与自动补全
        task_content, field_warnings = _validate_and_complete_task_fields(
            task=task_content, agent=next_agent
        )
        for warning in field_warnings:
            _append_log_line(f"orchestrator: task_field_autocomplete: {warning}\n")

        # P0: 自动注入执行环境（MAIN 无需手动填写）
        task_content = _inject_execution_environment(task_content)

    return history_entry, task_content, dev_plan_next


def _validate_main_finish_decision(*, output: MainOutput, iteration: int) -> None:
    decision = output["decision"]
    if decision["next_agent"] != "FINISH":
        return

    verdict = extract_report_verdict(
        report_text=_read_text(REPORT_FINISH_REVIEW_FILE),
        report_rules=parse_report_rules(),
        parsing_rules=parse_parsing_rules(),
        source=REPORT_FINISH_REVIEW_FILE,
    )
    if verdict == "PASS":
        return

    history_append = output.get("history_append", "") or ""
    if "finish_review_override: ignore" in history_append:
        return

    raise RuntimeError(
        f"FINISH_REVIEW verdict={verdict!r} 时必须使用 finish_review_override: ignore 才能 FINISH"
    )


def _count_dev_plan_status_changes(*, before: str, after: str) -> int:
    before_map = dict(parse_overall_task_statuses(before))
    after_map = dict(parse_overall_task_statuses(after))
    all_task_ids = set(before_map) | set(after_map)
    return sum(1 for task_id in all_task_ids if before_map.get(task_id) != after_map.get(task_id))


def _history_has_milestone_tag(tag: str) -> bool:
    _require_file(PROJECT_HISTORY_FILE)
    return tag in _read_text(PROJECT_HISTORY_FILE)


def _mark_history_entry_milestone(*, iteration: int, entry: str, labels: list[str]) -> str:
    if not labels:
        return entry
    lines = entry.splitlines()
    header_prefix = f"## Iteration {iteration}:"
    for idx, line in enumerate(lines):
        if line.strip().startswith(header_prefix):
            if "[MILESTONE]" in line:
                return entry
            suffix = " / ".join(labels)
            lines[idx] = f"{line} [MILESTONE] {suffix}".rstrip()
            return "\n".join(lines)
    raise RuntimeError("history entry missing iteration header for milestone tagging")


def _detect_milestone_change(last_subagent: str | None) -> bool:
    """
    检测是否发生里程碑变更（用于触发上下文压缩）。

    Context-centric 架构：
    里程碑变更条件：
    1. 上一轮是 VALIDATE 且 SYNTHESIZER 报告结论为 PASS
    2. project_history 中最近一条记录包含 [MILESTONE] 标记
    """
    if last_subagent != "VALIDATE":
        return False

    # 检查 SYNTHESIZER 报告是否为 PASS
    if not SYNTHESIZER_REPORT_FILE.exists():
        return False

    try:
        synthesizer_text = _read_text(SYNTHESIZER_REPORT_FILE)
        # 检查报告结论
        for line in synthesizer_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("结论:") or stripped.startswith("结论：") or "overall_verdict" in stripped:
                if "PASS" in stripped.upper():
                    return True
                break
    except Exception:
        pass

    return False


def _build_project_tree(project_dir: Path) -> str:
    """
    构建 project 目录的文件树结构（排除环境文件夹）。
    返回精简的目录结构，帮助 MAIN 了解项目布局。
    """
    exclude_dirs = {
        "node_modules", "__pycache__", ".venv", "venv", "dist", ".git",
        ".tmp", "tmp", "data_backup", ".pytest_cache", ".mypy_cache",
        "htmlcov", "coverage", "test-results", "data", ".serena",
        ".vscode", "gqlalchemy",
    }
    exclude_extensions = {".pyc", ".pyo", ".db", ".log", ".coverage"}

    lines: list[str] = []

    def walk_dir(path: Path, prefix: str = "", depth: int = 0) -> None:
        if depth > 4:  # 限制深度
            return
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        dirs = [e for e in entries if e.is_dir() and e.name not in exclude_dirs]
        files = [e for e in entries if e.is_file() and e.suffix not in exclude_extensions]

        # 只显示源码文件
        source_files = [f for f in files if f.suffix in {".py", ".ts", ".vue", ".json", ".md"}]

        for i, d in enumerate(dirs):
            is_last_dir = (i == len(dirs) - 1) and not source_files
            connector = "└── " if is_last_dir else "├── "
            lines.append(f"{prefix}{connector}{d.name}/")
            new_prefix = prefix + ("    " if is_last_dir else "│   ")
            walk_dir(d, new_prefix, depth + 1)

        for i, f in enumerate(source_files):
            is_last = i == len(source_files) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{f.name}")

    lines.append(f"{project_dir.name}/")
    walk_dir(project_dir, "", 0)

    return "\n".join(lines)


def _build_main_prompt(
    *,
    iteration: int,
    user_task: str,
    extra_instructions: list[str] | None = None,
    last_user_decision_iteration: int | None = None,
    last_subagent: str | None = None,
    is_resume: bool = False,
    last_compact_iteration: int = 0,
    milestone_changed: bool = False,
) -> tuple[str, str, bool]:
    """
    构建 MAIN 代理提示词。

    设计原则：
    - MAIN 代理使用 resume 模式，拥有完整对话历史
    - 系统提示词通过 --append-system-prompt 注入，优先级高于用户消息
    - 用户提示词包含动态上下文（dev_plan、报告等）
    - 强制注入上一轮子代理报告，避免 MAIN 使用过期记忆
    - 注入所有最近的用户决策，避免重复询问已解决的问题
    - 定期压缩上下文，避免超过 token 限制

    Returns:
        tuple[str, str, bool]: (系统提示词, 用户提示词, 是否触发了压缩)
    """
    effective_task = user_task.strip() if user_task else ""
    if not effective_task:
        effective_task = _extract_latest_task_goal()
    if not effective_task:
        effective_task = "(未找到任务目标，请检查 project_history.md)"

    did_compact = False

    # ========== 上下文压缩判断（实际压缩在调用处执行）==========
    from .config import COMPACT_INTERVAL
    if is_resume and iteration > 1 and COMPACT_INTERVAL > 0:
        if last_user_decision_iteration is not None:
            pass
        else:
            iterations_since_compact = iteration - last_compact_iteration
            should_compact = milestone_changed or iterations_since_compact >= COMPACT_INTERVAL
            if should_compact:
                did_compact = True

    # ========== 系统提示词（静态行为规范）==========
    system_prompt = _load_system_prompt("main")

    # ========== 用户提示词（动态上下文）==========
    user_parts = [
        f"[iteration]: {iteration}",
        f"[user_task]: {effective_task}",
    ]

    # 注入 task goal 中 @doc: 引用的文档，避免 MAIN 再次探索路径
    doc_refs = _extract_doc_references(effective_task)
    if doc_refs:
        user_parts.extend(_inject_doc_references(doc_refs))

    # 始终注入 dev_plan
    user_parts.append(_inject_file(DEV_PLAN_FILE, label_suffix="开发计划"))

    # 注入 global_context（首轮或压缩后）
    if iteration == 1 or did_compact:
        user_parts.append(_inject_file(GLOBAL_CONTEXT_FILE, label_suffix="全局上下文"))
        if PROJECT_ENV_FILE.exists():
            user_parts.append(_inject_file(PROJECT_ENV_FILE, label_suffix="项目环境配置"))

    # 每轮注入业务项目目录结构（来自 project_env 的 agent_root）
    project_dir = _resolve_target_agent_root()
    project_tree = _build_project_tree(project_dir)
    user_parts.append(f"[项目目录结构]:\n```\n{project_tree}\n```")

    # ========== 注入用户决策历史 ==========
    recent_decisions = _extract_recent_user_decisions(lookback=5)
    if recent_decisions:
        decisions_lines = []
        for d in recent_decisions:
            line = f"- Iteration {d['iteration']}: {d['decision_title']} → 用户选择 {d['user_choice']}"
            if d.get('user_comment'):
                line += f"，说明：{d['user_comment']}"
            decisions_lines.append(line)
        decisions_text = "\n".join(decisions_lines)
        user_parts.append(f"[历史用户决策（防重复询问）]:\n{decisions_text}")

    if last_user_decision_iteration is not None:
        user_decision = _extract_latest_user_decision(iteration=last_user_decision_iteration)
        if user_decision:
            user_parts.append(f"[上一轮用户决策结果]:\n{user_decision}")
            user_parts.append(
                "重要：用户已在上一轮做出决策，请根据用户的选择（user_choice）和补充说明（user_comment）继续推进任务。"
                "不要再次询问相同的问题。"
            )

    # ========== 注入上一轮子代理报告 ==========
    if last_subagent == "IMPLEMENTER" and REPORT_IMPLEMENTER_FILE.exists():
        user_parts.append(
            f"[上一轮 IMPLEMENTER 报告（强制注入，请基于此做决策）]:\n"
            f"{_inject_file(REPORT_IMPLEMENTER_FILE, label_suffix='上一轮 IMPLEMENTER 报告')}"
        )
    elif last_subagent == "VALIDATE" and SYNTHESIZER_REPORT_FILE.exists():
        user_parts.append(
            f"[上一轮验证结果（强制注入，请基于此做决策）]:\n"
            f"{_inject_file(SYNTHESIZER_REPORT_FILE, label_suffix='上一轮验证结果')}"
        )

    # ========== 额外指令和输出要求 ==========
    if extra_instructions:
        user_parts.extend(extra_instructions)
    user_parts.append(
        '[强制输出要求]\n'
        '禁止调用任何工具（Read/Write/Edit/Bash/Glob 等）；MAIN 只做决策，不做执行。\n'
        '你的最终输出必须且只能是 1 行纯 JSON（无 Markdown 代码块、无额外文本）。\n'
        "格式：{\"next_agent\":\"IMPLEMENTER|VALIDATE|USER|FINISH\",\"reason\":\"...\",\"history_append\":\"...\",\"task_body\":\"...\",\"dev_plan_next\":null}\\n"
        "（当 next_agent=IMPLEMENTER 时仅输出 task_body 正文，禁止输出 # Current Task 与 assigned_agent 行）\\n"
        '禁止无限探索文件而不输出 JSON。立即完成分析并输出决策。'
    )

    user_prompt = "\n\n".join(user_parts)
    return system_prompt, user_prompt, did_compact


def _build_finish_check_prompt(
    *,
    iteration: int,
    user_task: str,
    is_ready: bool,
    check_msg: str,
) -> str:
    """
    构建 FINISH_CHECK 提示词，默认注入完整报告并支持超限降级。
    """
    # 确保 user_task 始终有值：优先使用参数，否则从 project_history.md 提取
    effective_task = user_task.strip() if user_task else ""
    if not effective_task:  # 关键分支：参数为空时从历史提取
        effective_task = _extract_latest_task_goal()
    if not effective_task:  # 关键分支：仍为空则使用占位提示
        effective_task = "(未找到任务目标，请检查 project_history.md)"

    # dev_plan 状态摘要（计数，避免注入过长）
    dev_plan_text = _read_text(DEV_PLAN_FILE)
    status_counts = count_overall_task_statuses(
        dev_plan_text,
        known_statuses={"VERIFIED", "DONE", "DOING", "BLOCKED", "TODO"},
    )
    dev_plan_summary = f"任务状态计数: {status_counts}"

    # 构建精简的系统提示（仅保留 FINISH_CHECK 相关规则）
    # Context-centric 架构：使用 IMPLEMENTER 替代 TEST/DEV/REVIEW
    finish_check_system_prompt = f"""你是 MAIN 代理，正在执行 FINISH_CHECK 复核。

## 任务
根据 FINISH_REVIEW 的结论，决定是否最终完成任务。

## 决策规则
1. 若 FINISH_REVIEW 结论为 PASS 且满足 readiness（所有非 TODO 任务均 VERIFIED）：输出 `FINISH`
2. 若 FINISH_REVIEW 结论为 FAIL/BLOCKED：
   - 采纳：选择 IMPLEMENTER/USER 并生成工单
   - 忽略：输出 FINISH 并在 history_append 写明 `finish_review_override: ignore` 与理由
3. 若 readiness 不满足（存在 DONE/DOING/BLOCKED）：禁止 FINISH，必须派发 IMPLEMENTER

## 迭代号规则（重要）
- 当前 FINISH 尝试的迭代号是 {iteration}
- 若输出 FINISH：history_append 使用 `## Iteration {iteration}:`
- 若输出非 FINISH（IMPLEMENTER/USER）：history_append 使用 `## Iteration {iteration + 1}:`（下一轮迭代号）

## 输出格式（必须严格遵守）
输出 **1 行 JSON**（无其它文本）：
- 采纳 FAIL 派发 IMPLEMENTER：`{{"next_agent":"IMPLEMENTER","reason":"...","history_append":"## Iteration {iteration + 1}:\n...","task_body":"## 任务目标\n...","dev_plan_next":null}}`
- 忽略 FAIL 直接完成：`{{"next_agent":"FINISH","reason":"...","history_append":"## Iteration {iteration}:\n...\nfinish_review_override: ignore\n理由：...","task_body":null,"dev_plan_next":null}}`
- 全部通过直接完成：`{{"next_agent":"FINISH","reason":"...","history_append":"## Iteration {iteration}:\n...","task_body":null,"dev_plan_next":null}}`
- 需要用户决策：`{{"next_agent":"USER","reason":"...","decision_title":"简短标题","question":"详细问题描述","options":[{{"option_id":"opt1","description":"选项1说明"}},{{"option_id":"opt2","description":"选项2说明"}}],"recommended_option_id":"opt1","history_append":"## Iteration {iteration + 1}:\n...","task_body":null,"dev_plan_next":null}}`

**重要**：
1. 必须输出完整 JSON，禁止空输出
2. USER 决策时字段名必须是 `options`（不是 `decision_options`），且至少包含 2 个选项
3. 非 FINISH 决策的 history_append 必须使用迭代号 {iteration + 1}"""

    # 构建上下文部分
    context_parts = [
        f"[iteration]: {iteration}",
        f"[user_task]: {effective_task}",
        "",
        "## Dev Plan 任务状态摘要",
        dev_plan_summary,
        "",
    ]

    # 添加警告信息
    if not is_ready:
        context_parts.append("")
        context_parts.append(f"⚠️ 警告：{check_msg}")

    def build_prompt(*, implementer_level: int) -> str:
        # Context-centric 架构：注入 IMPLEMENTER 和 SYNTHESIZER 报告
        injected_implementer = _inject_report_with_level(
            report_path=REPORT_IMPLEMENTER_FILE,
            agent="IMPLEMENTER",
            level=implementer_level,
            label_suffix=" - FINISH_CHECK",
        )
        injected_synthesizer = _inject_report_with_level(
            report_path=SYNTHESIZER_REPORT_FILE,
            agent="SYNTHESIZER",
            level=3,
            label_suffix=" - FINISH_CHECK",
        )
        injected_finish_review = _inject_report_with_level(
            report_path=REPORT_FINISH_REVIEW_FILE,
            agent="FINISH_REVIEW",
            level=3,
            label_suffix=" - FINISH_CHECK",
        )
        return "\n\n".join(
            [
                finish_check_system_prompt,
                injected_implementer,
                injected_synthesizer,
                injected_finish_review,
                "\n".join(context_parts),
                "请根据以上信息输出 JSON 决策。",
            ]
        )

    implementer_level = 3
    prompt = build_prompt(implementer_level=implementer_level)

    if len(prompt) > MAX_PROMPT_SIZE:
        implementer_level = 1
        _append_log_line(
            "orchestrator: finish_check_prompt downgrade implementer to summary due to size\n"
        )
        prompt = build_prompt(implementer_level=implementer_level)

    if len(prompt) > MAX_PROMPT_SIZE:
        raise RuntimeError(
            f"FINISH_CHECK prompt too large len={len(prompt)} > {MAX_PROMPT_SIZE}"
        )

    _append_log_line(
        "orchestrator: finish_check_prompt_size "
        f"len={len(prompt)} implementer_level={implementer_level}\n"
    )
    return prompt


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
            "2. 审查范围外问题，决定是否纳入下一阶段任务",
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
    _require_file(IMPLEMENTER_TASK_FILE)  # 关键变量：IMPLEMENTER 工单必须存在
    _require_file(REPORT_IMPLEMENTER_FILE)  # 关键变量：IMPLEMENTER 报告必须存在
    _require_file(REPORT_FINISH_REVIEW_FILE)  # 关键变量：FINISH_REVIEW 报告必须存在

    # Context-centric 架构：检查新提示词文件
    for agent in ("main", "implementer", "test_runner", "requirement_validator", "anti_cheat_detector", "edge_case_tester", "synthesizer", "summary", "finish_review"):
        _require_file(PROMPTS_DIR / f"subagent_prompt_{agent}.md")  # 关键变量：提示词必须存在

    _validate_dev_plan()  # 关键变量：计划结构校验


def workflow_loop(
    *,
    max_iterations: int,
    sandbox_mode: str,
    approval_policy: str,
    user_task: str,
    new_task: bool,
    ui: UiRuntime | None,
    control: RunControl | None = None,
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
        user_task_len=len(user_task or ""),
    )
    if new_task:  # 关键分支：新任务需要清理旧状态
        _clear_saved_main_state()  # 关键变量：清空 MAIN 会话与迭代
        _clear_all_subagent_sessions()  # 关键变量：清空所有子代理会话
        _clear_dev_plan_stage_file()  # 关键变量：清理 dev_plan 草案
        _reset_workspace_task_files(iteration=0)  # 关键变量：重置工单
        _reset_report_files()  # 关键变量：重置报告
        _reset_acceptance_scope(user_task or "")  # 关键变量：重置验收范围

    main_session_id = None if new_task else _load_saved_main_session_id()  # 关键变量：MAIN 会话 id
    if main_session_id is not None:  # 关键分支：恢复旧会话
        print(f"Loaded MAIN session id: {main_session_id}")
        if ui is not None:  # 关键分支：UI 同步会话 id
            ui.state.update(main_session_id=main_session_id)

    # 关键变量：上次迭代号
    # new_task 时从 project_history.md 提取（支持保留历史但重启会话的场景）
    if new_task:
        last_iteration = _extract_last_iteration_from_history()
        if last_iteration > 0:
            print(f"Extracted last iteration from project_history.md: {last_iteration}")
    else:
        last_iteration = _load_saved_main_iteration()
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

    # 加载 resume_state 用于恢复 last_compact_iteration
    resume_state = _load_resume_state()

    start_iteration = last_iteration + 1  # 关键变量：本轮起始迭代
    end_iteration = start_iteration + max_iterations - 1  # 关键变量：本轮结束迭代

    finish_attempts = 0  # 关键变量：FINISH 尝试计数（用于强制收敛）
    max_finish_attempts = MAX_FINISH_ATTEMPTS  # 关键变量：最大 FINISH 尝试次数
    last_compact_iteration = 0  # 关键变量：上次压缩上下文的迭代号
    # 从 resume_state 恢复 last_compact_iteration（避免重复压缩）
    if resume_state is not None:
        last_compact_iteration = resume_state.get("last_compact_iteration", 0)
        if last_compact_iteration > 0:
            print(f"Restored last_compact_iteration: {last_compact_iteration}")
    # 关键变量：上一轮用户决策的迭代号
    # 若 workflow 重启且上一轮是用户决策，需要恢复该状态以便注入用户选择
    last_user_decision_iteration: int | None = None
    if last_iteration > 0 and _history_has_user_decision(iteration=last_iteration):
        last_user_decision_iteration = last_iteration
        print(f"Restored user decision from iteration {last_iteration}")
    # 关键变量：上一轮运行的子代理（用于注入报告到 MAIN 提示词）
    last_subagent: str | None = None
    if last_iteration > 0:
        # 从元数据或摘要历史恢复上一轮子代理信息
        last_subagent = _get_last_subagent_from_metadata(last_iteration)
        if last_subagent:
            print(f"Restored last subagent: {last_subagent}")

    for iteration in range(start_iteration, end_iteration + 1):  # 关键分支：迭代循环
        if control is not None and control.cancel_event.is_set():  # 关键分支：用户中断优先
            raise UserInterrupted("User interrupted before starting iteration")
        banner = f"\n========== Iteration {iteration} ==========\n"  # 关键变量：迭代日志分隔
        print(banner, end="")
        _append_log_line(banner)
        log_event("iteration_start", trace_id=trace_id, iteration=iteration)
        finish_attempted = False  # 关键变量：本轮是否触发 FINISH 尝试

        # ========== 检查 MAIN checkpoint（崩溃恢复）==========
        main_checkpoint = _load_main_checkpoint(iteration)
        if main_checkpoint is not None:
            print(f"Resuming from MAIN checkpoint for iteration {iteration}")
            _append_log_line(f"orchestrator: resuming from MAIN checkpoint iter={iteration}\n")
            main_output = main_checkpoint["main_output"]
            main_session_id = main_checkpoint["main_session_id"]
            decision = main_output["decision"]
            history_entry = main_checkpoint["history_entry"]
            task_content = main_checkpoint["task_content"]
            dev_plan_next = main_checkpoint["dev_plan_next"]
            effective_iteration = iteration
            dev_plan_text = _read_text(DEV_PLAN_FILE)
            dev_plan_before_hash = _sha256_text(dev_plan_text)
            # FINISH 分支需要 main_guard_paths
            main_guard_paths = [
                path for path in _guarded_blackboard_paths()
                if path not in {
                    REPORT_MAIN_DECISION_FILE,
                    REPORT_ITERATION_SUMMARY_FILE,
                    REPORT_ITERATION_SUMMARY_HISTORY_FILE,
                }
            ]
            # 跳过 MAIN 执行，直接进入 post-MAIN 处理
        else:

            # ========== 记录 MAIN 会话 token 使用情况 ==========
            if main_session_id:
                cli_name = get_cli_for_agent("MAIN")
                main_token_info = get_session_token_info(main_session_id, cli_name)
                if main_token_info:
                    token_msg = f"orchestrator: iteration {iteration} MAIN context: {format_token_info(main_token_info)}\n"
                    _append_log_line(token_msg)
                    print(token_msg, end="", flush=True)
                    if ui is not None:
                        ui.state.update(main_token_info=main_token_info)

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

            # 1) MAIN：输出包含 history/task_body/dev_plan_next 的调度 JSON
            _clear_dev_plan_stage_file()  # 关键变量：清理上轮 dev_plan 草案
            dev_plan_text = _read_text(DEV_PLAN_FILE)
            dev_plan_before_hash = _sha256_text(dev_plan_text)  # 关键变量：dev_plan 运行前哈希
            extra_instructions: list[str] = []
            # 判断是否为 resume 模式（用于决定是否压缩上下文）
            is_main_resume = main_session_id is not None
            # 检测里程碑变更（用于触发上下文压缩）
            milestone_changed = _detect_milestone_change(last_subagent)
            main_system_prompt, main_user_prompt, did_compact = _build_main_prompt(
                iteration=iteration,
                user_task=user_task,
                extra_instructions=extra_instructions,
                last_user_decision_iteration=last_user_decision_iteration,
                last_subagent=last_subagent,
                is_resume=is_main_resume,
                last_compact_iteration=last_compact_iteration,
                milestone_changed=milestone_changed,
            )
            # ========== 上下文压缩判断 ==========
            # CLI 内部自动 compact，只需记录日志
            if did_compact and main_session_id is not None:
                compact_reason = "里程碑进度变更" if milestone_changed else f"距上次压缩已 {iteration - last_compact_iteration} 轮"
                _append_log_line(f"orchestrator: context will auto-compact (reason: {compact_reason})\n")
                last_compact_iteration = iteration

            # 重置用户决策迭代号（仅在紧接用户决策后的第一轮注入）
            last_user_decision_iteration = None
            prompt_len = len(main_user_prompt)
            # 精简版 prompt 不再需要动态缩减逻辑，但保留超限检查
            if prompt_len > MAX_PROMPT_SIZE:
                raise RuntimeError(
                    f"MAIN prompt too large len={prompt_len} > {MAX_PROMPT_SIZE}. "
                    "This should not happen with simplified prompt."
                )
            log_event(
                "main_prompt_size",
                trace_id=trace_id,
                iteration=iteration,
                prompt_len=prompt_len,
            )
            # MAIN 的文件保护列表：排除 MAIN 自己写的文件，以及 SUMMARY 并行写的文件
            # SUMMARY 在后台线程运行，可能在 MAIN 运行期间写入摘要文件，不应触发误报
            main_guard_paths = [
                path for path in _guarded_blackboard_paths()
                if path not in {
                    REPORT_MAIN_DECISION_FILE,  # MAIN 自己的输出
                    REPORT_ITERATION_SUMMARY_FILE,  # SUMMARY 并行写入
                    REPORT_ITERATION_SUMMARY_HISTORY_FILE,  # SUMMARY 并行写入
                }
            ]  # 关键变量：MAIN 可写排除清单
            main_started = time.monotonic()

            # ========== MAIN 决策阶段 ==========
            # 校验逻辑通过 post_validate 下沉到内层重试循环，消除外层重试
            def _main_post_validate(output: MainOutput) -> None:
                _validate_main_output_fields(iteration=iteration, output=output)

            effective_iteration = iteration
            history_entry: str
            task_content: str | None
            dev_plan_next: str | None

            main_output, captured_session_id = _run_main_decision_stage(
                prompt=main_user_prompt,
                guard_paths=main_guard_paths,
                label="MAIN",
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                control=control,
                resume_session_id=main_session_id,
                post_validate=_main_post_validate,
                system_prompt=main_system_prompt,
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

            decision = main_output["decision"]  # 关键变量：决策字段
            history_entry, task_content, dev_plan_next = _prepare_main_output(
                iteration=iteration,
                output=main_output,
            )
            effective_iteration = iteration

            log_event(
                "stage_complete",
                trace_id=trace_id,
                iteration=iteration,
                stage="MAIN",
                duration_ms=int((time.monotonic() - main_started) * 1000),
            )

            # 立即写入 checkpoint，缩小崩溃窗口（stage_complete 到 resume_state 之间）
            _write_main_checkpoint(
                iteration=iteration,
                main_output=main_output,
                main_session_id=main_session_id,
                history_entry=history_entry,
                task_content=task_content,
                dev_plan_next=dev_plan_next,
            )

        if decision["next_agent"] == "FINISH":  # 关键分支：触发最终审阅
            finish_attempts += 1
            finish_attempted = True
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

            # 提前提交 dev_plan_next，确保 FINISH 检查读取最新状态
            early_dev_plan_next = main_output.get("dev_plan_next")
            if early_dev_plan_next is not None:
                _validate_dev_plan_text(text=early_dev_plan_next, source=DEV_PLAN_STAGED_FILE)
                DEV_PLAN_STAGED_FILE.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write_text(DEV_PLAN_STAGED_FILE, early_dev_plan_next.rstrip() + "\n")
                _commit_staged_dev_plan_if_present(
                    iteration=iteration,
                    main_session_id=main_session_id,
                    dev_plan_before_hash=dev_plan_before_hash,
                )
                dev_plan_before_hash = _sha256_text(_read_text(DEV_PLAN_FILE))  # 更新哈希

            is_ready, check_msg, blockers = _check_finish_readiness()
            baseline_ok, baseline_msg = _is_baseline_failure_acceptable()
            if not baseline_ok:
                is_ready = False
                blockers.append(baseline_msg)
                check_msg = f"{check_msg}; {baseline_msg}" if check_msg else baseline_msg
                _append_log_line(
                    f"orchestrator: FINISH baseline failure check failed: {baseline_msg}\n"
                )
            else:
                _append_log_line(
                    f"orchestrator: FINISH baseline failure check passed: {baseline_msg}\n"
                )
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

            # MAIN_FINISH_CHECK 独立重试循环，避免异常传播导致 FINISH_REVIEW 重复运行
            finish_check_retry_attempt = 0
            max_finish_check_retries = 3
            last_finish_check_error: str | None = None

            while True:
                if finish_check_retry_attempt > 0:
                    # 构建重试提示词，告知 MAIN 上次输出的错误
                    retry_prompt = (
                        f"你上次的输出校验失败：{last_finish_check_error}\n\n"
                        "请重新输出完整的 JSON，确保：\n"
                        "1. USER 决策时必须包含 `decision_title`、`question`、`options` 字段\n"
                        "2. `options` 字段名必须是 `options`（不是 `decision_options`）\n"
                        "3. 所有必填字段都存在且格式正确\n\n"
                        "请仅输出 JSON，不要附加任何解释。"
                    )
                    main_output, _ = _run_main_decision_stage(
                        prompt=retry_prompt,
                        guard_paths=main_guard_paths,
                        label="MAIN_FINISH_CHECK_RETRY",
                        sandbox_mode=sandbox_mode,
                        approval_policy=approval_policy,
                        control=control,
                        resume_session_id=main_session_id,
                        post_validate=None,
                    )
                else:
                    parsing_rules = parse_parsing_rules()
                    has_strict_verdict = "verdict" in parsing_rules.critical_fields
                    main_output, _ = _run_main_decision_stage(
                        prompt=main_prompt,
                        guard_paths=main_guard_paths,
                        label="MAIN_FINISH_CHECK",
                        sandbox_mode=sandbox_mode,
                        approval_policy=approval_policy,
                        control=control,
                        resume_session_id=main_session_id,
                        post_validate=(
                            (lambda output: _validate_main_finish_decision(output=output, iteration=iteration))
                            if has_strict_verdict
                            else None
                        ),
                    )

                try:
                    # 直接编辑 dev_plan 已在 tolerant guard 中容忍，由 backup.py 统一处理
                    decision = main_output["decision"]
                    candidate_iteration = iteration if decision["next_agent"] == "FINISH" else iteration + 1
                    history_entry, task_content, dev_plan_next = _prepare_main_output(
                        iteration=candidate_iteration,
                        output=main_output,
                    )
                    effective_iteration = candidate_iteration
                    break  # 校验通过，退出重试循环
                except (TemporaryError, RuntimeError) as exc:
                    finish_check_retry_attempt += 1
                    if finish_check_retry_attempt >= max_finish_check_retries:
                        # 重试耗尽，降级为直接 FINISH（忽略 FINISH_REVIEW 结果）
                        _append_log_line(
                            f"orchestrator: MAIN_FINISH_CHECK 重试耗尽，降级为直接 FINISH: {exc}\n"
                        )
                        decision = {"next_agent": "FINISH", "reason": f"FINISH_CHECK 重试耗尽: {exc}"}
                        main_output = {
                            "decision": decision,
                            "history_append": f"## Iteration {iteration}:\nnext_agent: FINISH\nreason: FINISH_CHECK 重试耗尽，降级完成\nfinish_review_override: retry_exhausted",
                            "task_body": None,
                            "dev_plan_next": None,
                        }
                        history_entry, task_content, dev_plan_next = _prepare_main_output(
                            iteration=iteration,
                            output=main_output,
                        )
                        effective_iteration = iteration
                        break
                    last_finish_check_error = str(exc)
                    _append_log_line(
                        f"orchestrator: MAIN_FINISH_CHECK 输出校验失败，重试 "
                        f"({finish_check_retry_attempt}/{max_finish_check_retries}): {exc}\n"
                    )
                    print(f"Warning: MAIN_FINISH_CHECK 输出校验失败，重试: {exc}")
                    continue

            log_event(
                "stage_complete",
                trace_id=trace_id,
                iteration=iteration,
                stage="MAIN_FINISH_CHECK",
                duration_ms=int((time.monotonic() - main_finish_started) * 1000),
            )

        # effective_iteration 与结构化输出已在 MAIN/MAIN_FINISH_CHECK 重试循环内校验完成
        milestone_labels: list[str] = []
        if decision["next_agent"] == "USER":
            milestone_labels.append("用户决策")
        if finish_attempted:
            milestone_labels.append(f"FINISH 尝试 #{finish_attempts}")
        if dev_plan_next is not None:
            changed = _count_dev_plan_status_changes(before=dev_plan_text, after=dev_plan_next)
            if changed > 5:
                milestone_labels.append(f"dev_plan 重大更新({changed})")
        # 提取 IMPLEMENTER 报告的 verdict 用于里程碑标记
        last_implementer_verdict: str | None = None
        if REPORT_IMPLEMENTER_FILE.exists():
            try:
                implementer_report_text = _read_text(REPORT_IMPLEMENTER_FILE)
                last_implementer_verdict = extract_report_verdict(
                    report_text=implementer_report_text,
                    report_rules=parse_report_rules(),
                )
            except Exception:
                pass  # 提取失败时忽略，不影响主流程
        if last_implementer_verdict == "PASS" and not _history_has_milestone_tag("首次测试通过"):
            milestone_labels.append("首次测试通过")
        history_entry = _mark_history_entry_milestone(
            iteration=effective_iteration,  # 使用 effective_iteration 与 history_append 中的迭代号一致
            entry=history_entry,
            labels=milestone_labels,
        )
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
        # checkpoint 恢复时可能已追加过 history，检查避免重复
        last_history_iter = _extract_last_iteration_from_history()
        if last_history_iter < effective_iteration:
            _append_history_entry(history_entry)  # 关键变量：追加历史
        elif main_checkpoint is not None:
            _append_log_line(
                f"orchestrator: skipping history append for iter={effective_iteration} "
                f"(already present, checkpoint recovery)\n"
            )

        print(f"MAIN => {decision['next_agent']} ({decision['reason']})")
        _append_log_line(f"orchestrator: MAIN => {decision['next_agent']} ({decision['reason']})\n")
        if ui is not None:  # 关键分支：UI 更新最近决策
            ui.state.update(last_main_decision=decision)

        _assert_main_side_effects(iteration=effective_iteration, expected_next_agent=decision["next_agent"])  # 关键变量：黑板契约校验（使用 effective_iteration 与 history_append 一致）
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
                last_compact_iteration=last_compact_iteration,
            )
        elif decision["next_agent"] == "VALIDATE":  # 关键分支：并行验证可续跑
            _write_resume_state(
                iteration=iteration,
                phase="after_main_validate",
                next_agent="VALIDATE",
                main_session_id=main_session_id,
                subagent_session_id=None,
                last_compact_iteration=last_compact_iteration,
            )
        else:  # 关键分支：子代理阶段
            _write_resume_state(
                iteration=iteration,
                phase="after_main",
                next_agent=decision["next_agent"],
                main_session_id=main_session_id,
                subagent_session_id=None,
                last_compact_iteration=last_compact_iteration,
            )

        _clear_main_checkpoint()  # post-MAIN 处理完成，清除 checkpoint

        if decision["next_agent"] == "FINISH":  # 关键分支：终止流程
            print("Finished.")
            _append_log_line("orchestrator: Finished.\n")
            if ui is not None:  # 关键分支：UI 标记已完成
                ui.state.update(phase="finished", current_agent="FINISH")
            return
        if decision["next_agent"] == "USER":  # 关键分支：等待用户抉择
            # 将 doc_patches 合并到 decision 中（doc_patches 在 main_output 顶层解析）
            user_decision = dict(decision)
            user_decision["doc_patches"] = main_output.get("doc_patches")
            user_choice, user_comment = _prompt_user_for_decision(iteration=iteration, decision=user_decision, ui=ui)  # type: ignore[arg-type]
            _clear_resume_state()

            # 【新增】USER 决策后立即更新决策模式文档
            try:
                _update_user_decision_patterns(
                    iteration=iteration,
                    decision=user_decision,  # type: ignore[arg-type]
                    user_choice=user_choice,
                    user_comment=user_comment,
                )
                _append_log_line(f"orchestrator: decision_patterns updated for iteration {iteration}\n")
            except Exception as exc:
                _append_log_line(f"orchestrator: decision_patterns error: {exc}\n")

            last_user_decision_iteration = iteration  # 关键变量：记录用户决策迭代号，供下一轮注入
            continue

        # Context-centric 架构：处理 VALIDATE 决策（并行验证）
        if decision["next_agent"] == "VALIDATE":
            print(f"MAIN => VALIDATE (并行验证)")
            _append_log_line(f"orchestrator: VALIDATE start, validators={PARALLEL_VALIDATORS}\n")

            validation_results, synthesizer_output = _run_validate_pipeline(
                iteration=iteration,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                ui=ui,
                control=control,
            )

            # 记录 VALIDATE 元数据，避免恢复/审计仅依赖 IMPLEMENTER 记录
            validate_session_id = synthesizer_output.get("session_id") or main_session_id
            if not isinstance(validate_session_id, str) or not validate_session_id.strip():
                raise RuntimeError("Missing VALIDATE session_id for iteration metadata")
            _append_iteration_metadata(
                iteration=iteration,
                agent="VALIDATE",
                session_id=validate_session_id,
                report_file=SYNTHESIZER_REPORT_FILE,
            )

            _clear_resume_state()
            # VALIDATE 阶段不生成 iteration_summary，归档时显式跳过 summary，防止混入上一轮摘要
            log_event("artifact_archive_start", trace_id=trace_id, iteration=iteration, stage="VALIDATE")
            archive_dir = _backup_iteration_artifacts(iteration=iteration, stage="VALIDATE")
            log_event(
                "artifact_archive_end",
                trace_id=trace_id,
                iteration=iteration,
                stage="VALIDATE",
                archived=archive_dir is not None,
            )
            last_subagent = "VALIDATE"
            continue

        # Context-centric 架构：处理 IMPLEMENTER 决策
        if decision["next_agent"] == "IMPLEMENTER":
            # 2) 子代理：只读工单并输出报告（报告由 --output-last-message 落盘）
            sub_started = time.monotonic()
            sub_session_id, task_file, report_path = _run_subagent_stage(
                iteration=iteration,
                next_agent="IMPLEMENTER",
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                ui=ui,
                control=control,
            )

            # ========== 记录子代理会话 token 使用情况 ==========
            if sub_session_id:
                sub_cli_name = get_cli_for_agent("IMPLEMENTER")
                sub_token_info = get_session_token_info(sub_session_id, sub_cli_name)
                if sub_token_info:
                    sub_token_msg = (
                        f"orchestrator: iteration {iteration} IMPLEMENTER context: "
                        f"{format_token_info(sub_token_info)}\n"
                    )
                    _append_log_line(sub_token_msg)
                    print(sub_token_msg, end="", flush=True)
                    if ui is not None:
                        ui.state.update(subagent_token_info=sub_token_info)

            log_event(
                "stage_complete",
                trace_id=trace_id,
                iteration=iteration,
                stage="IMPLEMENTER",
                duration_ms=int((time.monotonic() - sub_started) * 1000),
            )

            _write_resume_state(
                iteration=iteration,
                phase="after_subagent",
                next_agent="IMPLEMENTER",
                main_session_id=main_session_id,
                subagent_session_id=sub_session_id,
                last_compact_iteration=last_compact_iteration,
            )

            # 写入迭代元数据（同步，极快）- 用于替代 SUMMARY 历史的依赖
            _append_iteration_metadata(
                iteration=iteration,
                agent="IMPLEMENTER",
                session_id=sub_session_id,
                report_file=report_path,
            )

            # SUMMARY 改为后台执行后主流程等待，保证归档只包含本轮完整产物
            supervisor_future = _submit_supervisor_task(
                iteration=iteration,
                next_agent="IMPLEMENTER",
                main_session_id=main_session_id,
                subagent_session_id=sub_session_id,
                task_file=task_file,
                report_path=report_path,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
                ui=ui,
            )
            log_event("summary_wait_start", trace_id=trace_id, iteration=iteration, stage="IMPLEMENTER")
            supervisor_future.result()
            log_event("summary_wait_end", trace_id=trace_id, iteration=iteration, stage="IMPLEMENTER")
            log_event("artifact_archive_start", trace_id=trace_id, iteration=iteration, stage="IMPLEMENTER")
            archive_dir = _backup_iteration_artifacts(iteration=iteration, stage="IMPLEMENTER")
            log_event(
                "artifact_archive_end",
                trace_id=trace_id,
                iteration=iteration,
                stage="IMPLEMENTER",
                archived=archive_dir is not None,
            )

            _clear_resume_state()
            last_subagent = "IMPLEMENTER"
            continue

        # 未知的 next_agent
        raise RuntimeError(f"Unknown next_agent: {decision['next_agent']}")

    # 等待所有后台监督任务完成
    _shutdown_supervisor()
    raise RuntimeError(f"Reached max_iterations={max_iterations} without FINISH")
