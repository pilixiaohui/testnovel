"""
项目特定的初始化模板内容
"""


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
  "task_goal": "根据 doc/graph_refactor_plan.md 结合 doc/长篇小说生成系统设计.md 完成图数据库架构重构测试驱动开发",
  "acceptance_criteria": [
    {
      "id": "AC-1",
      "category": "data_model",
      "description": "Commit/SceneOrigin/SceneVersion/BranchHead 模型与关系建立",
      "priority": "P0",
      "source": "doc/graph_refactor_plan.md"
    },
    {
      "id": "AC-2",
      "category": "core_operations",
      "description": "分支/提交/回溯核心操作实现",
      "priority": "P0",
      "source": "doc/graph_refactor_plan.md"
    },
    {
      "id": "AC-3",
      "category": "migration",
      "description": "旧数据迁移与幂等性保证",
      "priority": "P0",
      "source": "doc/graph_refactor_plan.md"
    },
    {
      "id": "AC-4",
      "category": "testing",
      "description": "TDD 覆盖与性能基准达标",
      "priority": "P0",
      "source": "doc/graph_refactor_plan.md"
    }
  ],
  "out_of_scope": [
    "HTTP API 端点（除非文档明确要求为 P0）",
    "性能优化（除非低于基准阈值）",
    "额外的辅助功能（如 gc/history 详情，除非 P0 要求）",
    "批量提交 API（可作为 P1 后续迭代）",
    "历史查询详情 API（可作为 P1 后续迭代）"
  ],
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

## 说明

- **范围内问题**: 在 `acceptance_scope.json` 中定义的验收标准，必须满足才能 FINISH
- **范围外问题**: 在验收过程中发现的其他问题，记录在此但不阻塞完成
- **优先级**: P0 范围内问题阻塞完成；P1/P2 范围外问题记录供后续参考

---

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
