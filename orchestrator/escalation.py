"""
阻塞检测与自动升级模块

设计原则：
1. 普适性：基于配置驱动，不硬编码特定场景
2. 分层检测：编排器层面检测 + MAIN 提示词辅助
3. 快速失败：检测到阻塞立即升级，避免无效循环
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .config import VERIFICATION_POLICY_FILE, REPORT_ITERATION_SUMMARY_HISTORY_FILE, ITERATION_METADATA_FILE
from .file_ops import _read_text, _require_file, _append_log_line
from .parsing import parse_report_rules, extract_report_verdict, extract_report_blockers


@dataclass(frozen=True)
class EscalationRules:
    """升级规则配置"""
    enabled: bool
    max_iterations_same_issue: int
    detect_patterns: list[str]
    permission_keywords: list[str]
    environment_keywords: list[str]
    blocker_types_require_escalation: list[str]


@dataclass
class EscalationResult:
    """升级检测结果"""
    should_escalate: bool
    reason: str
    escalation_type: Literal["permission", "environment", "loop", "none"]
    details: dict


def load_escalation_rules() -> EscalationRules:
    """从 verification_policy.json 加载升级规则"""
    _require_file(VERIFICATION_POLICY_FILE)
    raw = _read_text(VERIFICATION_POLICY_FILE).strip()
    if not raw:
        raise ValueError("verification_policy.json is empty")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("verification_policy.json must be a JSON object")

    rules = payload.get("escalation_rules")
    if rules is None or not rules.get("enabled", False):
        return EscalationRules(
            enabled=False,
            max_iterations_same_issue=3,
            detect_patterns=[],
            permission_keywords=[],
            environment_keywords=[],
            blocker_types_require_escalation=[],
        )

    if not isinstance(rules, dict):
        raise ValueError("verification_policy.escalation_rules must be an object")

    loop_detection = rules.get("loop_detection", {})
    if not isinstance(loop_detection, dict):
        raise ValueError("verification_policy.escalation_rules.loop_detection must be an object")

    return EscalationRules(
        enabled=rules.get("enabled", True),
        max_iterations_same_issue=loop_detection.get("max_iterations_same_issue", 3),
        detect_patterns=loop_detection.get("detect_patterns", []),
        permission_keywords=rules.get("permission_keywords", []),
        environment_keywords=rules.get("environment_keywords", []),
        blocker_types_require_escalation=rules.get("blocker_types_require_escalation", []),
    )


def _check_permission_blocker(
    *,
    report_text: str,
    rules: EscalationRules,
) -> EscalationResult | None:
    """检测权限类阻塞"""
    if not rules.permission_keywords:
        return None

    report_lower = report_text.lower()
    matched_keywords: list[str] = []

    for keyword in rules.permission_keywords:
        if keyword.lower() in report_lower:
            matched_keywords.append(keyword)

    if not matched_keywords:
        return None

    # 检查是否有明确的阻塞类型标注
    blocker_type_match = re.search(r"阻塞类型[：:]\s*(\S+)", report_text)
    if blocker_type_match:
        blocker_type = blocker_type_match.group(1)
        if blocker_type in rules.blocker_types_require_escalation:
            return EscalationResult(
                should_escalate=True,
                reason=f"子代理报告权限阻塞：{blocker_type}",
                escalation_type="permission",
                details={
                    "blocker_type": blocker_type,
                    "matched_keywords": matched_keywords,
                },
            )

    # 即使没有明确标注，关键词匹配也触发升级
    if matched_keywords:
        return EscalationResult(
            should_escalate=True,
            reason=f"检测到权限相关关键词：{', '.join(matched_keywords[:3])}",
            escalation_type="permission",
            details={
                "matched_keywords": matched_keywords,
            },
        )

    return None


def _check_environment_blocker(
    *,
    report_text: str,
    rules: EscalationRules,
) -> EscalationResult | None:
    """检测环境类阻塞"""
    if not rules.environment_keywords:
        return None

    report_lower = report_text.lower()
    matched_keywords: list[str] = []

    for keyword in rules.environment_keywords:
        if keyword.lower() in report_lower:
            matched_keywords.append(keyword)

    if not matched_keywords:
        return None

    # 检查是否有明确的阻塞类型标注
    blocker_type_match = re.search(r"阻塞类型[：:]\s*(\S+)", report_text)
    if blocker_type_match:
        blocker_type = blocker_type_match.group(1)
        if blocker_type in rules.blocker_types_require_escalation:
            return EscalationResult(
                should_escalate=True,
                reason=f"子代理报告环境阻塞：{blocker_type}",
                escalation_type="environment",
                details={
                    "blocker_type": blocker_type,
                    "matched_keywords": matched_keywords,
                },
            )

    return None


def _load_recent_iteration_history(*, lookback: int = 5) -> list[dict]:
    """加载最近的迭代历史（优先使用元数据文件）"""
    # 优先从迭代元数据文件获取
    if ITERATION_METADATA_FILE.exists():
        raw = _read_text(ITERATION_METADATA_FILE).strip()
        if raw:
            history: list[dict] = []
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if isinstance(entry, dict):
                        # 转换元数据格式为摘要历史格式（兼容循环检测逻辑）
                        history.append({
                            "iteration": entry.get("iteration"),
                            "subagent": {"agent": entry.get("agent")},
                        })
                except json.JSONDecodeError:
                    continue
            if history:
                return history[-lookback:] if len(history) > lookback else history

    # 回退到摘要历史文件（兼容旧数据）
    if not REPORT_ITERATION_SUMMARY_HISTORY_FILE.exists():
        return []

    raw = _read_text(REPORT_ITERATION_SUMMARY_HISTORY_FILE).strip()
    if not raw:
        return []

    history = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if isinstance(entry, dict):
                history.append(entry)
        except json.JSONDecodeError:
            continue

    return history[-lookback:] if len(history) > lookback else history


def _check_loop_detection(
    *,
    rules: EscalationRules,
    current_blocker: str | None,
) -> EscalationResult | None:
    """检测循环阻塞（同一问题连续 N 轮未解决）"""
    if rules.max_iterations_same_issue < 2:
        return None

    history = _load_recent_iteration_history(lookback=rules.max_iterations_same_issue + 2)
    if len(history) < rules.max_iterations_same_issue:
        return None

    # 检测代理调度模式循环
    recent_agents = [
        h.get("subagent", {}).get("agent", "")
        for h in history[-rules.max_iterations_same_issue:]
    ]
    agent_pattern = "→".join(recent_agents)

    for pattern in rules.detect_patterns:
        if pattern in agent_pattern:
            return EscalationResult(
                should_escalate=True,
                reason=f"检测到调度循环模式：{agent_pattern}",
                escalation_type="loop",
                details={
                    "pattern": pattern,
                    "recent_agents": recent_agents,
                },
            )

    # 检测相同阻塞原因重复出现
    if current_blocker:
        similar_blockers = 0
        for h in history[-rules.max_iterations_same_issue:]:
            subagent = h.get("subagent", {})
            report_summary = subagent.get("report_summary", "")
            if current_blocker.lower() in report_summary.lower():
                similar_blockers += 1

        if similar_blockers >= rules.max_iterations_same_issue - 1:
            return EscalationResult(
                should_escalate=True,
                reason=f"相同阻塞连续 {similar_blockers + 1} 轮未解决：{current_blocker[:50]}...",
                escalation_type="loop",
                details={
                    "blocker": current_blocker,
                    "occurrences": similar_blockers + 1,
                },
            )

    return None


def check_escalation_needed(
    *,
    report_path: Path,
    agent: str,
) -> EscalationResult:
    """
    检测是否需要升级到用户

    在子代理执行完成后调用，检测报告中的阻塞情况
    """
    rules = load_escalation_rules()

    if not rules.enabled:
        return EscalationResult(
            should_escalate=False,
            reason="升级规则未启用",
            escalation_type="none",
            details={},
        )

    if not report_path.exists():
        return EscalationResult(
            should_escalate=False,
            reason="报告文件不存在",
            escalation_type="none",
            details={},
        )

    report_text = _read_text(report_path)

    # 提取报告结论和阻塞信息
    try:
        report_rules = parse_report_rules()
        verdict = extract_report_verdict(report_text=report_text, report_rules=report_rules)
        blockers = extract_report_blockers(report_text=report_text, report_rules=report_rules)
    except Exception as e:
        _append_log_line(f"orchestrator: escalation check parse error: {e}\n")
        verdict = None
        blockers = []

    current_blocker = blockers[0] if blockers else None

    # 1. 检测权限阻塞（最高优先级）
    permission_result = _check_permission_blocker(report_text=report_text, rules=rules)
    if permission_result and permission_result.should_escalate:
        _append_log_line(
            f"orchestrator: escalation triggered - permission blocker detected: "
            f"{permission_result.reason}\n"
        )
        return permission_result

    # 2. 检测环境阻塞
    env_result = _check_environment_blocker(report_text=report_text, rules=rules)
    if env_result and env_result.should_escalate:
        _append_log_line(
            f"orchestrator: escalation triggered - environment blocker detected: "
            f"{env_result.reason}\n"
        )
        return env_result

    # 3. 检测循环阻塞（仅在有阻塞时检测）
    if verdict in {"FAIL", "BLOCKED"} and current_blocker:
        loop_result = _check_loop_detection(rules=rules, current_blocker=current_blocker)
        if loop_result and loop_result.should_escalate:
            _append_log_line(
                f"orchestrator: escalation triggered - loop detected: "
                f"{loop_result.reason}\n"
            )
            return loop_result

    return EscalationResult(
        should_escalate=False,
        reason="无需升级",
        escalation_type="none",
        details={"verdict": verdict, "blockers": blockers},
    )


def build_escalation_decision(
    *,
    iteration: int,
    escalation: EscalationResult,
    original_agent: str,
) -> dict:
    """
    构建升级到用户的决策 JSON

    当编排器检测到需要升级时，自动生成 USER 决策
    """
    if escalation.escalation_type == "permission":
        title = "权限操作需要用户介入"
        question = f"子代理在执行任务时遇到权限问题：{escalation.reason}\n请选择处理方式："
        options = [
            {"option_id": "user_fix", "description": "用户手动执行所需的权限操作后继续"},
            {"option_id": "skip", "description": "跳过此步骤，尝试替代方案"},
            {"option_id": "abort", "description": "终止当前任务"},
        ]
        recommended = "user_fix"

    elif escalation.escalation_type == "environment":
        title = "环境问题需要用户介入"
        question = f"子代理遇到环境配置问题：{escalation.reason}\n请选择处理方式："
        options = [
            {"option_id": "user_fix", "description": "用户手动修复环境问题后继续"},
            {"option_id": "skip", "description": "跳过此步骤，尝试替代方案"},
            {"option_id": "abort", "description": "终止当前任务"},
        ]
        recommended = "user_fix"

    elif escalation.escalation_type == "loop":
        title = "循环阻塞需要用户决策"
        question = f"检测到任务陷入循环：{escalation.reason}\n请选择处理方式："
        options = [
            {"option_id": "user_guide", "description": "用户提供解决思路或手动修复"},
            {"option_id": "skip_task", "description": "暂时跳过此任务，继续其他工作"},
            {"option_id": "change_approach", "description": "采用替代方案"},
            {"option_id": "abort", "description": "终止当前任务"},
        ]
        recommended = "user_guide"

    else:
        raise ValueError(f"Unknown escalation type: {escalation.escalation_type}")

    history_append = f"""## Iteration {iteration}: [MILESTONE] 自动升级到用户
next_agent: USER
reason: {escalation.reason}
escalation_type: {escalation.escalation_type}
original_agent: {original_agent}
details: {json.dumps(escalation.details, ensure_ascii=False)}"""

    return {
        "next_agent": "USER",
        "reason": escalation.reason,
        "decision_title": title,
        "question": question,
        "options": options,
        "recommended_option_id": recommended,
        "history_append": history_append,
        "task_body": None,
        "dev_plan_next": None,
    }
