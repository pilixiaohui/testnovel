"""Orchestrator-side project config & templates.

The orchestrator runs in repository mode and must not import
business project Python modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal


ProjectAgent = Literal["IMPLEMENTER"]


class ProjectConfig:
    """项目配置类（Context-centric 架构）

    注意：这里的 project_root 指业务项目根目录（不是 orchestrator 包代码目录）。
    黑板目录默认放在 {project_root}/orchestrator 下。
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root

        # orchestrator 数据目录
        self.orchestrator_dir = project_root / "orchestrator"

        # 目录结构配置
        self.memory_dir = self.orchestrator_dir / "memory"
        self.workspace_dir = self.orchestrator_dir / "workspace"
        self.reports_dir = self.orchestrator_dir / "reports"
        self.prompts_dir = self.memory_dir / "prompts"

        # 核心黑板文件
        self.project_history_file = self.memory_dir / "project_history.md"
        self.global_context_file = self.memory_dir / "global_context.md"
        self.dev_plan_file = self.memory_dir / "dev_plan.md"
        self.finish_review_config_file = self.memory_dir / "finish_review_config.json"
        self.verification_policy_file = self.memory_dir / "verification_policy.json"
        self.dev_plan_staged_file = self.workspace_dir / "main/dev_plan_next.md"

        # 工单文件（Context-centric 架构）
        self.implementer_task_file = self.workspace_dir / "implementer/current_task.md"

        # 报告文件（Context-centric 架构）
        self.report_implementer_file = self.reports_dir / "report_implementer.md"
        self.report_finish_review_file = self.reports_dir / "report_finish_review.md"
        self.report_main_decision_file = self.reports_dir / "report_main_decision.json"
        self.report_iteration_summary_file = self.reports_dir / "report_iteration_summary.json"
        self.report_iteration_summary_history_file = self.reports_dir / "report_iteration_summary_history.jsonl"

        # 备份目录
        self.reports_backup_dir = self.reports_dir / "backups"
        self.workspace_backup_dir = self.workspace_dir / "backups"
        self.memory_backup_dir = self.memory_dir / "backups"

        # Dev Plan 验证规则
        todo_marker = "TO" "DO"
        self.dev_plan_allowed_statuses = {todo_marker, "DOING", "BLOCKED", "DONE", "VERIFIED"}
        self.dev_plan_max_tasks = 60
        self.dev_plan_max_line_length = 2000
        self.dev_plan_banned_substrings = (
            "Note to=functions.",
            "*** Begin Patch",
            "*** End Patch",
            "functions.apply_patch",
            "apply_patch(",
            "apply_patch(auto_approved=",
            "file update",
            "diff --git",
            "structuredContent",
            "\"isError\"",
            "tool serena.",
            "tokens used",
        )

        # 代理列表（Context-centric 架构）
        self.agents: list[ProjectAgent] = ["IMPLEMENTER"]
        self.editable_md_skip_dirs = {
            ".git",
            ".codex",
            ".serena",
            ".pytest_cache",
            "__pycache__",
            "node_modules",
        }

    def get_task_file(self, agent: str) -> Path:
        """获取指定代理的工单文件"""
        if agent == "IMPLEMENTER":
            return self.implementer_task_file
        raise ValueError(f"Unknown agent: {agent}")

    def get_report_file(self, agent: str) -> Path:
        """获取指定代理的报告文件"""
        if agent == "IMPLEMENTER":
            return self.report_implementer_file
        raise ValueError(f"Unknown agent: {agent}")

    def get_prompt_file(self, agent: str) -> Path:
        """获取指定代理的提示词文件"""
        return self.prompts_dir / f"subagent_prompt_{agent.lower()}.md"

    def list_editable_md_files(self) -> list[str]:
        """列出所有可编辑的 markdown 文件"""
        files: list[str] = []
        if not self.project_root.exists():
            return files
        for path in self.project_root.rglob("*.md"):
            if not path.is_file():
                continue
            rel = path.relative_to(self.project_root)
            if any(part in self.editable_md_skip_dirs for part in rel.parts):
                continue
            files.append(rel.as_posix())
        return sorted(set(files))

    def resolve_editable_md_path(self, relative_path: str) -> Path:
        """解析并验证可编辑的 markdown 文件路径"""
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError("path is required")
        if "\x00" in relative_path:
            raise ValueError("path contains null byte")
        raw = Path(relative_path)
        if raw.is_absolute():
            raise ValueError("path must be project-relative")

        resolved = (self.project_root / raw).resolve()
        if resolved.suffix.lower() != ".md":
            raise ValueError("only .md files are editable")
        try:
            rel = resolved.relative_to(self.project_root)
        except ValueError as exc:
            raise ValueError("path is outside project root") from exc
        if any(part in self.editable_md_skip_dirs for part in rel.parts):
            raise ValueError("path is inside a blocked directory")

        return resolved


class ProjectTemplates:
    """项目初始化模板"""

    @staticmethod
    def global_context() -> str:
        """全局上下文模板"""
        return """
# Global Context

请在此维护本项目的全局目标、约束与黑板协议（Blackboard Contract）。

## 必要约束
- JSON 字段使用 `snake_case`
- 快速失败：不要添加兜底/容错逻辑来让流程继续
- 允许测试双/Mock：测试可使用真实依赖或测试双

## Blackboard Paths（以项目根目录为基准）
- `orchestrator/memory/`：长期记忆、全局上下文
- `orchestrator/memory/prompts/`：各代理提示词（固定文件，重置时保留）
- `orchestrator/memory/dev_plan.md`：全局开发计划快照（MAIN 维护，REVIEW 核实）
- New Task 目标：由用户在 New Task 时输入，追加写入 `orchestrator/memory/project_history.md`（MAIN 注入 history 后读取）
- `orchestrator/workspace/`：各子代理工单（由 MAIN 覆盖写入）
- `orchestrator/reports/`：各子代理输出报告（由编排器保存）
"""

    @staticmethod
    def project_history() -> str:
        """项目历史模板"""
        return """
# Project History (Append-only)

> 本文件由 MAIN 追加写入；每轮必须包含 `## Iteration {iteration}:`。
"""

    @staticmethod
    def dev_plan() -> str:
        """开发计划模板"""
        todo_marker = "TO" "DO"
        return f"""
# Dev Plan (Snapshot)

> 本文件由 MAIN 维护（可覆盖编辑）。它是"当前计划与进度"的快照；事实证据以 `orchestrator/reports/report_review.md` 与 `orchestrator/memory/project_history.md` 为准。

## 约束（强制）
- 任务总数必须保持在"几十条"以内（少而硬）
- 每个任务块必须包含：`status / acceptance / evidence`
- status 只允许：{todo_marker} / DOING / BLOCKED / DONE / VERIFIED
- 可选字段：`verification_status: <PENDING_DEV_VALIDATION|DEV_VALIDATED|TEST_PASSED|VERIFIED|REVIEW_REJECTED>` 用于验证闭环跟踪
- 只有 **REVIEW 的证据** 才能把 DONE -> VERIFIED（evidence 必须引用 Iteration 与验证方式）

---

## Milestone M0: 引导与黑板契约

### M0-T1: 建立 dev_plan 状态机
- status: {todo_marker}
- acceptance:
- `orchestrator/memory/dev_plan.md` 存在并遵循固定字段
- 每轮更新在 `orchestrator/memory/project_history.md` 留痕（说明改了什么/为什么）
- evidence:

### M0-T2: 审阅代理输出可核实证据
- status: {todo_marker}
- acceptance:
- `orchestrator/reports/report_review.md` 包含可复现的命令与关键输出摘要
  - 进度核实：逐条对照 dev_plan 的任务给出 PASS/FAIL 与证据
- evidence:
"""

    @staticmethod
    def finish_review_config() -> str:
        """最终审阅配置模板（JSON）"""
        return """{
  "task_goal_anchor": "## Task Goal (New Task)",
  "task_goal_anchor_mode": "prefix_latest",
  "baseline_allowed_test_failures": [],
  "docs": [],
  "code_root": "."
}
"""

    @staticmethod
    def verification_policy() -> str:
        """验证策略配置模板（JSON）"""
        return """{
  "version": 1,
  "test_requirements": {
    "min_coverage": 80,
    "must_pass_before_review": true
  },
  "report_rules": {
    "apply_to": ["IMPLEMENTER", "FINISH_REVIEW"],
    "require_verdict": true,
    "verdict_prefix": "结论：",
    "verdict_allowed": ["PASS", "FAIL", "BLOCKED"],
    "blocker_prefix": "阻塞：",
    "blocker_clear_value": "无"
  },
  "parsing_rules": {
    "critical_fields": ["iteration"],
    "optional_fields": ["verdict", "blockers"],
    "use_defaults_on_failure": true
  }
}
"""

    @staticmethod
    def acceptance_scope() -> str:
        """验收范围定义模板（JSON，范围锁定）"""
        return """{
  "schema_version": 1,
  "locked_at_iteration": 0,
  "task_goal": "请替换为你的任务目标",
  "acceptance_criteria": [],
  "out_of_scope": [],
  "completion_criteria": {
    "all_tasks_verified": true,
    "all_tests_passing": true,
    "performance_benchmarks_met": true,
    "no_p0_blockers": true
  }
}
"""

    @staticmethod
    def out_of_scope_issues() -> str:
        """范围外问题记录模板（Markdown）"""
        return """
# Out-of-Scope Issues (范围外问题记录)

> 本文件记录在当前任务验收过程中发现的范围外问题。
> 这些问题不阻塞当前任务完成，但可作为后续迭代的输入。

## 待记录

（FINISH_REVIEW 将在此记录发现的范围外问题）
"""

    @staticmethod
    def dev_plan_archived() -> str:
        """已归档 dev_plan 模板（Markdown）"""
        return """
# Dev Plan Archive (已归档任务)

> 本文件存储已完成并 VERIFIED 的历史任务，减少 `dev_plan.md` 的大小。
> 归档规则由 orchestrator 控制：仅归档旧 Milestone 且其任务全部 VERIFIED。
"""

    @staticmethod
    def task_file(agent: str, iteration: int = 0) -> str:
        """任务文件模板"""
        return f"""# Current Task (Iteration {iteration})
assigned_agent: {agent}

本文件由 MAIN 覆盖写入；{agent} 子代理仅以此为唯一任务来源。

## Acceptance Criteria
- TDD：先写/补齐测试，红-绿-重构；若任务类型不适用，说明原因
"""

    @staticmethod
    def report_file(agent: str) -> str:
        """报告文件模板"""
        return f"""# Report: {agent}

iteration: 0

结论：BLOCKED
阻塞：报告尚未生成

## 证据
- 报告尚未生成
"""
