from __future__ import annotations

from pathlib import Path

from project import ProjectConfig, ProjectTemplates

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # 关键变量：项目根目录

# 初始化项目配置
CONFIG = ProjectConfig(PROJECT_ROOT)  # 关键变量：项目配置实例

CODEX_STATE_DIR = PROJECT_ROOT / ".codex"  # 关键变量：Codex 状态目录
MAIN_SESSION_ID_FILE = CODEX_STATE_DIR / "main_session_id.txt"  # 关键变量：MAIN 会话文件
MAIN_ITERATION_FILE = CODEX_STATE_DIR / "main_iteration.txt"  # 关键变量：MAIN 迭代文件
RESUME_STATE_FILE = CODEX_STATE_DIR / "resume_state.json"  # 关键变量：中断续跑状态文件

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
TEST_TASK_FILE = CONFIG.test_task_file  # 关键变量：TEST 工单
DEV_TASK_FILE = CONFIG.dev_task_file  # 关键变量：DEV 工单
REVIEW_TASK_FILE = CONFIG.review_task_file  # 关键变量：REVIEW 工单

REPORT_TEST_FILE = CONFIG.report_test_file  # 关键变量：TEST 报告
REPORT_DEV_FILE = CONFIG.report_dev_file  # 关键变量：DEV 报告
REPORT_REVIEW_FILE = CONFIG.report_review_file  # 关键变量：REVIEW 报告
REPORT_FINISH_REVIEW_FILE = CONFIG.report_finish_review_file  # 关键变量：FINISH_REVIEW 报告
REPORT_MAIN_DECISION_FILE = CONFIG.report_main_decision_file  # 关键变量：MAIN 决策输出
REPORT_STAGE_CHANGES_FILE = REPORTS_DIR / "report_stage_changes.json"  # 关键变量：子代理阶段代码变更摘要（编排器生成）
REPORT_ITERATION_SUMMARY_FILE = CONFIG.report_iteration_summary_file  # 关键变量：每轮摘要输出
REPORT_ITERATION_SUMMARY_HISTORY_FILE = CONFIG.report_iteration_summary_history_file  # 关键变量：摘要历史输出
ORCHESTRATOR_LOG_FILE = REPORTS_DIR / "orchestrator.log"  # 关键变量：编排器日志
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
MAX_FINISH_ATTEMPTS = 3  # 关键变量：最大 FINISH 尝试次数
REQUIRE_ALL_VERIFIED_FOR_FINISH = True  # 关键变量：是否要求所有任务 VERIFIED 才能 FINISH

# 上下文管理参数（新增）
KEEP_RECENT_MILESTONES = 2  # 关键变量：dev_plan 保留最近 N 个 Milestone
BASE_HISTORY_WINDOW = 10  # 关键变量：基础历史窗口大小
MIN_HISTORY_WINDOW = 3  # 关键变量：最小历史窗口
MAX_HISTORY_WINDOW = 15  # 关键变量：最大历史窗口

# 阈值参数（新增）
MAX_DEV_PLAN_SIZE = 1000  # 关键变量：dev_plan 最大行数（触发归档）
MAX_PROMPT_SIZE = 800000  # 关键变量：prompt 最大字符数（触发警告）

# 新增文件路径
ACCEPTANCE_SCOPE_FILE = MEMORY_DIR / "acceptance_scope.json"  # 关键变量：验收范围定义
OUT_OF_SCOPE_ISSUES_FILE = MEMORY_DIR / "out_of_scope_issues.md"  # 关键变量：范围外问题记录
DEV_PLAN_ARCHIVED_FILE = MEMORY_DIR / "dev_plan_archived.md"  # 关键变量：已归档任务
LEGACY_ISSUES_REPORT_FILE = REPORTS_DIR / "legacy_issues_report.md"  # 关键变量：遗留问题报告


def _list_editable_md_files() -> list[str]:
    return CONFIG.list_editable_md_files()  # 关键变量：可编辑 md 文件列表


def _resolve_editable_md_path(relative_path: str) -> Path:
    return CONFIG.resolve_editable_md_path(relative_path)  # 关键变量：校验并解析 md 路径
