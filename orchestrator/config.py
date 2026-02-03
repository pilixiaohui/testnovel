from __future__ import annotations

import os

from pathlib import Path

from project import ProjectConfig, ProjectTemplates

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # 关键变量：项目根目录

# 初始化项目配置
CONFIG = ProjectConfig(PROJECT_ROOT)  # 关键变量：项目配置实例

CODEX_STATE_DIR = PROJECT_ROOT / ".codex"  # 关键变量：Codex 状态目录
MAIN_SESSION_ID_FILE = CODEX_STATE_DIR / "main_session_id.txt"  # 关键变量：MAIN 会话文件
MAIN_ITERATION_FILE = CODEX_STATE_DIR / "main_iteration.txt"  # 关键变量：MAIN 迭代文件
RESUME_STATE_FILE = CODEX_STATE_DIR / "resume_state.json"  # 关键变量：中断续跑状态文件

# 子代理会话文件（用于 resume）- Context-centric 架构
IMPLEMENTER_SESSION_ID_FILE = CODEX_STATE_DIR / "implementer_session_id.txt"  # 关键变量：IMPLEMENTER 会话文件

# 从配置获取路径（保持全局变量兼容性）
MEMORY_DIR = CONFIG.memory_dir  # 关键变量：memory 目录
PROMPTS_DIR = CONFIG.prompts_dir  # 关键变量：prompts 目录
WORKSPACE_DIR = CONFIG.workspace_dir  # 关键变量：workspace 目录
REPORTS_DIR = CONFIG.reports_dir  # 关键变量：reports 目录

PROJECT_HISTORY_FILE = CONFIG.project_history_file  # 关键变量：历史文件
GLOBAL_CONTEXT_FILE = CONFIG.global_context_file  # 关键变量：全局上下文文件
DEV_PLAN_FILE = CONFIG.dev_plan_file  # 关键变量：计划文件
FINISH_REVIEW_CONFIG_FILE = CONFIG.finish_review_config_file  # 关键变量：最终审阅配置文件
VERIFICATION_POLICY_FILE = CONFIG.verification_policy_file  # 关键变量：验证策略配置文件
DEV_PLAN_STAGED_FILE = CONFIG.dev_plan_staged_file  # 关键变量：计划暂存文件

# Context-centric 架构：IMPLEMENTER 工单和报告
IMPLEMENTER_TASK_FILE = WORKSPACE_DIR / "implementer" / "current_task.md"  # 关键变量：IMPLEMENTER 工单
REPORT_IMPLEMENTER_FILE = REPORTS_DIR / "report_implementer.md"  # 关键变量：IMPLEMENTER 报告

# Context-centric 架构：验证器工作区和报告
VALIDATOR_WORKSPACE_DIR = WORKSPACE_DIR / "validators"  # 关键变量：验证器工作区目录
VALIDATOR_REPORTS_DIR = REPORTS_DIR / "report_validators"  # 关键变量：验证器报告目录
SYNTHESIZER_REPORT_FILE = REPORTS_DIR / "report_synthesizer.md"  # 关键变量：SYNTHESIZER 报告
VALIDATION_RESULTS_FILE = REPORTS_DIR / "validation_results.json"  # 关键变量：结构化验证结果

REPORT_FINISH_REVIEW_FILE = CONFIG.report_finish_review_file  # 关键变量：FINISH_REVIEW 报告
REPORT_MAIN_DECISION_FILE = CONFIG.report_main_decision_file  # 关键变量：MAIN 决策输出
REPORT_ITERATION_SUMMARY_FILE = CONFIG.report_iteration_summary_file  # 关键变量：每轮摘要输出
REPORT_ITERATION_SUMMARY_HISTORY_FILE = CONFIG.report_iteration_summary_history_file  # 关键变量：摘要历史输出
ORCHESTRATOR_LOG_FILE = REPORTS_DIR / "orchestrator.log"  # 关键变量：编排器日志

# 监督代理并行化相关文件
ITERATION_METADATA_FILE = REPORTS_DIR / "iteration_metadata.jsonl"  # 关键变量：迭代元数据（主流程写入）
REPORT_SUPERVISOR_FILE = REPORTS_DIR / "report_supervisor.json"  # 关键变量：监督代理输出
REPORT_SUPERVISOR_HISTORY_FILE = REPORTS_DIR / "report_supervisor_history.jsonl"  # 关键变量：监督历史
ORCHESTRATOR_EVENTS_FILE = REPORTS_DIR / "orchestrator_events.jsonl"  # 关键变量：编排器事件日志

REPORTS_BACKUP_DIR = CONFIG.reports_backup_dir  # 关键变量：报告备份目录
WORKSPACE_BACKUP_DIR = CONFIG.workspace_backup_dir  # 关键变量：工单备份目录
MEMORY_BACKUP_DIR = CONFIG.memory_backup_dir  # 关键变量：memory 备份目录

# 从配置获取验证规则（保持全局变量兼容性）
DEV_PLAN_ALLOWED_STATUSES: set[str] = CONFIG.dev_plan_allowed_statuses  # 关键变量：合法状态集合
DEV_PLAN_MAX_TASKS = CONFIG.dev_plan_max_tasks  # 关键变量：任务最大数量
DEV_PLAN_MAX_LINE_LENGTH = CONFIG.dev_plan_max_line_length  # 关键变量：行长度上限
DEV_PLAN_BANNED_SUBSTRINGS: tuple[str, ...] = CONFIG.dev_plan_banned_substrings  # 关键变量：禁用子串

# 收敛控制参数（新增）
MAX_ITERATIONS = 100  # 关键变量：最大迭代轮数
MAX_FINISH_ATTEMPTS = 3  # 关键变量：最大 FINISH 尝试次数
REQUIRE_ALL_VERIFIED_FOR_FINISH = True  # 关键变量：是否要求所有任务 VERIFIED 才能 FINISH

# 并行验证参数（Context-centric 架构）
PARALLEL_VALIDATORS = ["TEST_RUNNER", "REQUIREMENT_VALIDATOR", "ANTI_CHEAT_DETECTOR", "EDGE_CASE_TESTER"]  # 关键变量：并行验证器列表
MAX_PARALLEL_VALIDATORS = 4  # 关键变量：最大并行验证器数量
VALIDATOR_TIMEOUT_MS = 300000  # 关键变量：验证器超时时间（5分钟）

# 上下文管理参数（新增）
KEEP_RECENT_MILESTONES = 2  # 关键变量：dev_plan 保留最近 N 个 Milestone
MIN_HISTORY_WINDOW = 3  # 关键变量：最小历史窗口（用于 token 裁剪时保护最近 N 轮）

# 阈值参数（新增）
MAX_DEV_PLAN_SIZE = 1000  # 关键变量：dev_plan 最大行数（触发归档）
MAX_PROMPT_SIZE = 800000  # 关键变量：prompt 最大字符数（触发警告）

# 子代理历史上下文参数（新增）
SUBAGENT_HISTORY_LOOKBACK = int(os.getenv("SUBAGENT_HISTORY_LOOKBACK", "1"))  # 关键变量：历史回溯轮数
if SUBAGENT_HISTORY_LOOKBACK < 0:  # 关键分支：回溯轮数非法
    raise ValueError("SUBAGENT_HISTORY_LOOKBACK must be >= 0")

# 新增文件路径
PROJECT_ENV_FILE = MEMORY_DIR / "project_env.json"  # 关键变量：项目环境配置（重置时保留）
ACCEPTANCE_SCOPE_FILE = MEMORY_DIR / "acceptance_scope.json"  # 关键变量：验收范围定义
OUT_OF_SCOPE_ISSUES_FILE = MEMORY_DIR / "out_of_scope_issues.md"  # 关键变量：范围外问题记录
DEV_PLAN_ARCHIVED_FILE = MEMORY_DIR / "dev_plan_archived.md"  # 关键变量：已归档任务
LEGACY_ISSUES_REPORT_FILE = REPORTS_DIR / "legacy_issues_report.md"  # 关键变量：遗留问题报告
LOG_SUMMARY_CONFIG_FILE = MEMORY_DIR / "log_summary_config.json"  # 关键变量：日志摘要 LLM 配置

# 文档管理与进度展示
UPLOADED_DOCS_DIR = MEMORY_DIR / "uploaded_docs"  # 关键变量：上传文档根目录
UPLOADED_DOCS_CATEGORIES = ("requirements", "specs", "references")  # 关键变量：文档分类
UPLOADED_DOCS_MAX_BYTES = 5 * 1024 * 1024  # 关键变量：上传文档大小上限（5MB）

# 新增缓存路径
REPORT_SUMMARY_CACHE_FILE = PROJECT_ROOT / "orchestrator" / "cache" / "report_summaries.json"  # 关键变量：报告摘要缓存

# ============= 用户洞察与决策模式配置 =============
USER_INSIGHT_REPORT_FILE = REPORTS_DIR / "user_insight_report.md"  # 关键变量：用户洞察报告
USER_INSIGHT_HISTORY_FILE = REPORTS_DIR / "user_insight_history.jsonl"  # 关键变量：洞察历史
USER_DECISION_PATTERNS_FILE = MEMORY_DIR / "user_decision_patterns.md"  # 关键变量：用户决策模式

# 功能开关
ENABLE_BEHAVIOR_AUDIT = True  # 关键变量：是否启用行为审计
ENABLE_DECISION_PATTERNS = True  # 关键变量：是否启用决策模式整合

# 上下文压缩配置
COMPACT_INTERVAL = 3  # 每 N 轮压缩一次（0 表示禁用）
COMPACT_INSTRUCTIONS = """侧重保留：
1. 决策推理过程（为什么选择某个 next_agent）
2. 跨轮问题分析（连续 FAIL 的根因判断）
3. 文档修正执行记录（Edit 工具调用）
4. 用户补充说明（user_comment）的关键信息

可丢弃（每轮会重新注入）：
- dev_plan 完整内容
- 子代理报告详情
- 用户决策选项列表
- 项目目录结构
- 全局上下文（压缩后会重新注入）"""

# 子代理压缩指令（针对 IMPLEMENTER）
SUBAGENT_COMPACT_INSTRUCTIONS = """你的任务是/compact当前对话上下文后退出，不需要执行其他的任务。压缩过程侧重保留：
1. 当前任务的关键发现和结论
2. 已执行的命令及其结果摘要
3. 遇到的问题和解决方案
4. TDD 流程中的测试设计思路和实现决策
"""

# ============= CLI 工具配置（Context-centric 架构） =============
# 每个代理可以配置使用不同的 CLI 工具
# 支持的 CLI: codex, claude, opencode
CLI_CONFIG: dict[str, dict[str, str | list[str] | bool]] = {
    "MAIN": {
        "cli": "claude",           # MAIN 使用 claude CLI
        "extra_args": [],         # 额外参数
        "enable_resume": True,    # MAIN 保持 resume 模式
    },
    # Context-centric 架构：IMPLEMENTER（合并 TEST+DEV）
    "IMPLEMENTER": {
        "cli": "codex",
        "extra_args": ["--model", "gpt-5.2-codex"],
        "enable_resume": False,   # 暂时禁用 resume（codex /compact 无效）
    },
    # Context-centric 架构：并行验证器（轻量级）
    "TEST_RUNNER": {
        "cli": "codex",
        "extra_args": ["--model", "gpt-5.2"],
        "enable_resume": False,
    },
    "REQUIREMENT_VALIDATOR": {
        "cli": "codex",
        "extra_args": ["--model", "gpt-5.2"],
        "enable_resume": False,
    },
    "ANTI_CHEAT_DETECTOR": {
        "cli": "codex",
        "extra_args": ["--model", "gpt-5.2"],
        "enable_resume": False,
    },
    "EDGE_CASE_TESTER": {
        "cli": "codex",
        "extra_args": ["--model", "gpt-5.2"],
        "enable_resume": False,
    },
    "SYNTHESIZER": {
        "cli": "codex",
        "extra_args": ["--model", "gpt-5.2"],
        "enable_resume": False,
    },
    "SUMMARY": {
        "cli": "codex",
        "extra_args": ["--model", "gpt-5.2"],
        "enable_resume": False,
    },
}

# ============= MCP 工具注入配置 =============
# 配置哪些代理需要注入 MCP 工具指南
MCP_TOOLS_GUIDE_FILE = PROMPTS_DIR / "mcp_tools_guide.md"  # 关键变量：MCP 工具指南文件

# 需要注入 MCP 工具指南的代理列表（Context-centric 架构）
MCP_TOOLS_INJECT_AGENTS: set[str] = {"IMPLEMENTER", "FINISH_REVIEW"}


def get_cli_for_agent(agent: str) -> str:
    """获取指定代理使用的 CLI 工具名称"""
    agent_config = CLI_CONFIG.get(agent, {})
    return str(agent_config.get("cli", "codex"))


def get_cli_extra_args(agent: str) -> list[str]:
    """获取指定代理的额外 CLI 参数"""
    agent_config = CLI_CONFIG.get(agent, {})
    extra = agent_config.get("extra_args", [])
    return list(extra) if extra else []


def is_resume_enabled(agent: str) -> bool:
    """检查指定代理是否启用 resume 模式

    返回 False 时，子代理每次都新开会话（不使用历史会话 ID）。
    中断重续场景由 workflow 层单独处理，不受此配置影响。
    """
    agent_config = CLI_CONFIG.get(agent, {})
    return bool(agent_config.get("enable_resume", True))


def _list_editable_md_files() -> list[str]:
    return CONFIG.list_editable_md_files()  # 关键变量：可编辑 md 文件列表


def _resolve_editable_md_path(relative_path: str) -> Path:
    return CONFIG.resolve_editable_md_path(relative_path)  # 关键变量：校验并解析 md 路径
