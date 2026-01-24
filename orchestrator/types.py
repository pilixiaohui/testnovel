from __future__ import annotations

from typing import Literal, TypedDict

NextAgent = Literal["TEST", "DEV", "REVIEW", "FINISH", "USER"]  # 关键变量：调度目标枚举
ResumePhase = Literal["after_main", "after_subagent", "awaiting_user"]  # 关键变量：续跑阶段枚举
TaskType = Literal["feature", "bugfix", "refactor", "chore"]  # 关键变量：任务类型标记（dev_plan 可选字段）


class ResumeState(TypedDict):
    schema_version: int  # 关键变量：续跑状态版本
    iteration: int  # 关键变量：迭代号
    phase: ResumePhase  # 关键变量：续跑阶段
    next_agent: Literal["TEST", "DEV", "REVIEW", "USER"]  # 关键变量：续跑目标
    main_session_id: str  # 关键变量：MAIN 会话 id
    subagent_session_id: str | None  # 关键变量：子代理会话 id
    blackboard_digest: str  # 关键变量：黑板摘要


class UserDecisionOption(TypedDict):
    option_id: str  # 关键变量：选项标识
    description: str  # 关键变量：选项描述


class MainDecisionDispatch(TypedDict):
    next_agent: Literal["TEST", "DEV", "REVIEW", "FINISH"]  # 关键变量：下一代理
    reason: str  # 关键变量：决策理由


class MainDecisionUser(TypedDict):
    next_agent: Literal["USER"]  # 关键变量：用户抉择分支
    reason: str  # 关键变量：抉择理由
    decision_title: str  # 关键变量：抉择标题
    question: str  # 关键变量：抉择问题
    options: list[UserDecisionOption]  # 关键变量：选项列表
    recommended_option_id: str | None  # 关键变量：推荐选项（可空）


MainDecision = MainDecisionDispatch | MainDecisionUser


class CodexRunResult(TypedDict):
    last_message: str  # 关键变量：最后一条消息
    session_id: str | None  # 关键变量：会话 id（可空）


class MainOutput(TypedDict):
    decision: MainDecision  # 关键变量：决策对象
    history_append: str  # 关键变量：历史追加内容
    task: str | None  # 关键变量：工单内容（可空）
    dev_plan_next: str | None  # 关键变量：计划草案（可空）


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


class IterationSummary(TypedDict):
    iteration: int  # 关键变量：迭代号
    main_session_id: str | None  # 关键变量：MAIN 会话 id
    subagent_session_id: str  # 关键变量：子代理会话 id
    main_decision: MainDecision  # 关键变量：MAIN 决策
    subagent: SubagentSummary  # 关键变量：子代理摘要
    steps: list[SummaryStep]  # 关键变量：步骤列表
    summary: str  # 关键变量：本轮摘要
    progress: ProgressInfo | None  # 关键变量：进度信息（可选）
    artifacts: dict  # 关键变量：关键产物路径


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


class UserDecisionResponse(TypedDict, total=False):
    option_id: str  # 关键变量：用户选择 id
    comment: str  # 关键变量：用户备注
