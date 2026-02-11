from __future__ import annotations

import sys
from typing import Literal, TypedDict

if sys.version_info >= (3, 11):
    from typing import NotRequired, Required
else:
    from typing_extensions import NotRequired, Required

NextAgent = Literal["IMPLEMENTER", "VALIDATE", "FINISH", "USER"]  # 关键变量：调度目标枚举（Context-centric 架构）
ResumePhase = Literal["after_main", "after_subagent", "after_main_validate", "awaiting_user"]  # 关键变量：续跑阶段枚举
TaskType = Literal["feature", "bugfix", "refactor", "chore"]  # 关键变量：任务类型标记（dev_plan 可选字段）


class ResumeState(TypedDict):
    schema_version: int  # 关键变量：续跑状态版本
    iteration: int  # 关键变量：迭代号
    phase: ResumePhase  # 关键变量：续跑阶段
    next_agent: Literal["IMPLEMENTER", "VALIDATE", "USER"]  # 关键变量：续跑目标（Context-centric 架构）
    main_session_id: str  # 关键变量：MAIN 会话 id
    subagent_session_id: str | None  # 关键变量：子代理会话 id
    blackboard_digest: str  # 关键变量：黑板摘要
    last_compact_iteration: int  # 关键变量：上次压缩的迭代号（避免重复压缩）


class UserDecisionOption(TypedDict):
    option_id: str  # 关键变量：选项标识
    description: str  # 关键变量：选项描述


class DocPatch(TypedDict, total=False):
    """文档修正项，用于 USER 决策时提供文档修正建议"""
    file: str  # 关键变量：要修改的文档文件路径（相对于项目根目录，如 doc/xxx.md 或 project/docs/xxx.md）
    action: str  # 关键变量：修改类型（append/replace/insert）
    content: str  # 关键变量：修改内容
    reason: str  # 关键变量：修改原因
    old_content: str  # 关键变量：被替换的内容（仅 replace 时需要）
    after_marker: str  # 关键变量：插入位置标记（仅 insert 时需要）


class MainDecisionDispatch(TypedDict):
    next_agent: Literal["IMPLEMENTER", "VALIDATE", "FINISH"]  # 关键变量：下一代理（Context-centric 架构）
    reason: str  # 关键变量：决策理由


class MainDecisionUser(TypedDict):
    next_agent: Literal["USER"]  # 关键变量：用户抉择分支
    reason: str  # 关键变量：抉择理由
    decision_title: str  # 关键变量：抉择标题
    question: str  # 关键变量：抉择问题
    options: list[UserDecisionOption]  # 关键变量：选项列表
    recommended_option_id: str | None  # 关键变量：推荐选项（可空）
    doc_patches: list[DocPatch] | None  # 关键变量：文档修正建议（可空）


MainDecision = MainDecisionDispatch | MainDecisionUser


# ============= 验证结果类型（Context-centric 架构） =============


class ValidationResult(TypedDict):
    """单个验证器的输出结果"""
    validator: str  # 关键变量：验证器名称（TEST_RUNNER/REQUIREMENT_VALIDATOR/ANTI_CHEAT_DETECTOR/EDGE_CASE_TESTER）
    iteration: int  # 关键变量：验证结果对应迭代号
    verdict: Literal["PASS", "FAIL", "BLOCKED"]  # 关键变量：验证结论
    category: Literal["CODE_DEFECT", "INFRA", "NOISE", "EVIDENCE_GAP"]  # 关键变量：问题分类（用于路由）
    confidence: float  # 关键变量：置信度（0.0-1.0）
    findings: list[str]  # 关键变量：发现列表
    evidence: str  # 关键变量：证据摘要
    duration_ms: int  # 关键变量：执行耗时（毫秒）
    scenarios_total: NotRequired[int]  # 关键变量：场景总数（TEST_RUNNER）
    scenarios_passed: NotRequired[int]  # 关键变量：通过场景数（TEST_RUNNER）
    scenarios_executed: NotRequired[int]  # 关键变量：实际执行场景数（TEST_RUNNER）
    commands_total: NotRequired[int]  # 关键变量：执行命令/场景总数（TEST_RUNNER，兼容字段）
    commands_executed: NotRequired[int]  # 关键变量：实际执行命令/场景数（TEST_RUNNER，兼容字段）


class SynthesizerOutput(TypedDict):
    """SYNTHESIZER 汇总输出"""
    overall_verdict: Literal["PASS", "FAIL", "REWORK", "BLOCKED"]  # 关键变量：总体结论
    decision_basis: list[str]  # 关键变量：决策依据摘要（结构化）
    results: list[ValidationResult]  # 关键变量：各验证器结果
    blockers: list[str]  # 关键变量：阻塞项列表
    recommendations: list[str]  # 关键变量：建议列表
    session_id: NotRequired[str | None]  # 关键变量：SYNTHESIZER 会话 id（可选）


class CodexRunResult(TypedDict):
    last_message: str  # 关键变量：最后一条消息
    session_id: str | None  # 关键变量：会话 id（可空）


class MainOutput(TypedDict, total=False):
    decision: Required[MainDecision]  # 关键变量：决策对象
    history_append: Required[str]  # 关键变量：历史追加内容
    task_body: str | None  # 关键变量：工单正文（可空，头部由编排器生成）
    dev_plan_next: str | None  # 关键变量：计划草案（可空）
    doc_patches: list[DocPatch] | None  # 关键变量：文档修正建议（可空，仅 USER 决策时）


class SummaryStep(TypedDict):
    step: int  # 关键变量：步骤序号
    actor: str  # 关键变量：执行者
    detail: str  # 关键变量：步骤详情


class SubagentSummary(TypedDict):
    agent: str  # 关键变量：子代理名称
    task_summary: str  # 关键变量：任务摘要
    report_summary: str  # 关键变量：报告摘要


class MilestoneProgress(TypedDict):
    milestone_id: str  # 关键变量：里程碑编号
    milestone_name: str  # 关键变量：里程碑名称
    total_tasks: int  # 关键变量：里程碑任务总数
    completed_tasks: int  # 关键变量：里程碑完成任务数
    verified_tasks: int  # 关键变量：里程碑已验证任务数
    percentage: float  # 关键变量：里程碑完成百分比


class TaskProgress(TypedDict):
    task_id: str  # 关键变量：任务编号
    title: str  # 关键变量：任务标题
    status: str  # 关键变量：任务状态
    milestone_id: str  # 关键变量：任务所属里程碑


class ProgressInfo(TypedDict):
    total_tasks: int  # 关键变量：任务总数
    completed_tasks: int  # 关键变量：已完成任务数（DONE + VERIFIED）
    verified_tasks: int  # 关键变量：已验证任务数
    in_progress_tasks: int  # 关键变量：进行中任务数
    blocked_tasks: int  # 关键变量：阻塞任务数
    todo_tasks: int  # 关键变量：待办任务数
    completion_percentage: float  # 关键变量：完成百分比
    verification_percentage: float  # 关键变量：验证百分比
    current_milestone: str | None  # 关键变量：当前里程碑
    milestones: list[MilestoneProgress]  # 关键变量：里程碑进度列表
    tasks: list[TaskProgress]  # 关键变量：任务列表


class UploadedDocument(TypedDict):
    filename: str  # 关键变量：文件名
    path: str  # 关键变量：相对路径
    category: str  # 关键变量：分类
    size: int  # 关键变量：文件大小（字节）
    upload_time: str  # 关键变量：上传时间戳


class CodeChanges(TypedDict, total=False):
    files_modified: list[str]  # 关键变量：修改的文件列表
    tests_passed: bool  # 关键变量：自测是否通过
    coverage: float  # 关键变量：覆盖率百分比


class IterationSummary(TypedDict, total=False):
    iteration: Required[int]  # 关键变量：迭代号（必填）
    main_session_id: Required[str | None]  # 关键变量：MAIN 会话 id（必填）
    subagent_session_id: Required[str]  # 关键变量：子代理会话 id（必填）
    main_decision: Required[MainDecision]  # 关键变量：MAIN 决策（必填）
    subagent: Required[SubagentSummary]  # 关键变量：子代理摘要（必填）
    steps: Required[list[SummaryStep]]  # 关键变量：步骤列表（必填）
    summary: Required[str]  # 关键变量：本轮摘要（必填）
    artifacts: Required[dict]  # 关键变量：关键产物路径（必填）
    progress: ProgressInfo | None  # 关键变量：进度信息（可选）
    verdict: str  # 关键变量：本轮结论 PASS/FAIL/BLOCKED（可选）
    key_findings: list[str]  # 关键变量：关键发现列表（可选）
    changes: CodeChanges  # 关键变量：代码变更信息（可选，仅 IMPLEMENTER）
    user_insight: dict  # 关键变量：用户洞察信息（可选）


class ReportSummary(TypedDict):
    iteration: int  # 关键变量：迭代号
    agent: str  # 关键变量：代理名称
    verdict: str  # 关键变量：结论
    blockers: list[str]  # 关键变量：阻塞项
    key_changes: list[str]  # 关键变量：关键变更
    evidence: str  # 关键变量：证据摘要
    timestamp: str  # 关键变量：时间戳


class UiState(TypedDict, total=False):
    phase: str  # 关键变量：运行阶段
    iteration: int  # 关键变量：当前迭代
    current_agent: str  # 关键变量：当前代理
    last_main_decision: object  # 关键变量：最近决策
    last_iteration_summary: IterationSummary | None  # 关键变量：最近迭代摘要
    last_summary_path: str | None  # 关键变量：摘要文件路径
    summary_history: list[IterationSummary] | None  # 关键变量：摘要历史
    resume_available: bool  # 关键变量：是否存在续跑状态
    awaiting_user_decision: object  # 关键变量：等待用户决策
    main_session_id: str | None  # 关键变量：MAIN 会话 id
    last_error: str | None  # 关键变量：最近错误
    updated_at: str  # 关键变量：更新时间戳
    version: int  # 关键变量：状态版本
    main_token_info: object  # 关键变量：MAIN 会话 token 信息
    subagent_token_info: object  # 关键变量：子代理会话 token 信息


class UserDecisionResponse(TypedDict, total=False):
    option_id: str  # 关键变量：用户选择 id
    comment: str  # 关键变量：用户备注


# ============= Token 信息类型 =============


class TokenUsage(TypedDict, total=False):
    """Token 使用量"""
    input_tokens: int           # 关键变量：输入 token 数
    cached_input_tokens: int    # 关键变量：缓存的输入 token 数（Codex 格式）
    cache_read_input_tokens: int  # 关键变量：缓存读取 token 数（Claude 格式）
    output_tokens: int          # 关键变量：输出 token 数
    reasoning_output_tokens: int  # 关键变量：推理输出 token 数
    total_tokens: int           # 关键变量：总 token 数


class TokenInfo(TypedDict, total=False):
    """Token 信息"""
    session_id: str             # 关键变量：会话 ID
    current_context_tokens: int  # 关键变量：当前上下文 token 数
    context_window: int         # 关键变量：上下文窗口大小
    usage_percentage: float     # 关键变量：使用率百分比
    total_usage: TokenUsage     # 关键变量：累计使用量
    last_usage: TokenUsage      # 关键变量：最近一次使用量


class CompactResult(TypedDict, total=False):
    """压缩结果"""
    before_tokens: int          # 关键变量：压缩前 token 数
    after_tokens: int           # 关键变量：压缩后 token 数
    reduction: int              # 关键变量：减少的 token 数
    reduction_percentage: float  # 关键变量：减少百分比


# ============= 验证器配置类型 =============


class ValidatorContextConfig(TypedDict, total=False):
    """验证器上下文配置"""
    validator: str                      # 关键变量：验证器名称
    requires_implementer_report: bool   # 关键变量：是否需要 IMPLEMENTER 报告
    requires_dev_plan: bool             # 关键变量：是否需要 dev_plan
    requires_code_root: bool            # 关键变量：是否需要代码目录
    requires_test_commands: bool        # 关键变量：是否需要测试命令
    requires_api_signatures: bool       # 关键变量：是否需要 API 签名
    requires_modified_files: bool       # 关键变量：是否需要修改文件列表
    custom_context_keys: list[str]      # 关键变量：自定义上下文键


class ExtractedValidationInfo(TypedDict, total=False):
    """提取的验证信息"""
    test_commands: list[str]            # 关键变量：测试命令列表
    api_signatures: list[str]           # 关键变量：API 签名列表
    modified_files: list[str]           # 关键变量：修改文件列表
    raw_yaml: str                       # 关键变量：原始 YAML 内容
    extraction_method: Literal["yaml", "json", "regex", "fallback"]  # 关键变量：提取方法
