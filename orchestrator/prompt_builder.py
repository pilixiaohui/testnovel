from __future__ import annotations

from pathlib import Path

from .config import CONFIG, PROJECT_HISTORY_FILE, PROMPTS_DIR
from .file_ops import _read_text, _rel_path, _require_file
from .types import NextAgent
from .dev_plan import parse_overall_task_statuses


def _inject_text(*, path: Path, content: str, note: str | None = None) -> str:
    display = _rel_path(path)  # 关键变量：相对路径展示
    label = f"{display} ({note})" if note else display  # 关键变量：显示标签
    header = f"============= Injected File: {label} ============="  # 关键变量：注入头
    footer = f"============= End Injected File: {label} ============="  # 关键变量：注入尾
    return "\n".join([header, content, footer])


def _inject_file(path: Path) -> str:
    """
    将文件内容“注入”到提示词中（黑板模式的可观测快照）。
    - 按用户要求：所有代理注入 global_context；MAIN 额外注入 project_history/dev_plan；REVIEW 注入 dev_plan
    - 不做截断/兜底：缺失即报错（快速失败）
    """
    _require_file(path)  # 关键分支：缺文件直接失败
    return _inject_text(path=path, content=_read_text(path).rstrip())  # 关键变量：注入文件内容


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _inject_project_history_recent(*, last_iterations: int, max_tokens: int | None = None) -> str:
    """
    将 `memory/project_history.md` 以“最近 N 轮 iteration”为窗口注入，避免上下文无限膨胀。
    - N 必须 >= 1
    - 若 history 尚无任何 `## Iteration ` 记录，则注入全量文件
    - 注入内容始终包含文件头部（直到首个 Iteration heading 之前）
    - 可选：根据 max_tokens 动态缩小窗口（近似字符/4）
    """
    if last_iterations < 1:  # 关键分支：窗口必须 >= 1
        raise ValueError("last_iterations must be >= 1")

    _require_file(PROJECT_HISTORY_FILE)
    full_text = _read_text(PROJECT_HISTORY_FILE).rstrip()  # 关键变量：历史全文
    lines = full_text.splitlines()  # 关键变量：历史逐行

    iteration_indices = [idx for idx, line in enumerate(lines) if line.startswith("## Iteration ")]  # 关键变量：迭代分隔行
    if not iteration_indices:  # 关键分支：无迭代则全量注入
        return _inject_text(path=PROJECT_HISTORY_FILE, content=full_text)

    header_end = iteration_indices[0]  # 关键变量：文件头部结束位置
    start_pos = max(0, len(iteration_indices) - last_iterations)

    def build_trimmed(start_at: int) -> str:
        start = iteration_indices[start_at]
        head = lines[:header_end]  # 关键变量：文件头部
        tail = lines[start:]  # 关键变量：窗口内历史
        return "\n".join(head + [""] + tail) if head else "\n".join(tail)

    trimmed = build_trimmed(start_pos)
    if max_tokens is not None and max_tokens > 0:
        while _approx_tokens(trimmed) > max_tokens and start_pos < len(iteration_indices) - 1:
            start_pos += 1
            trimmed = build_trimmed(start_pos)

    selected_iterations = len(iteration_indices) - start_pos
    return _inject_text(
        path=PROJECT_HISTORY_FILE,
        content=trimmed,
        note=f"last {selected_iterations} iterations",
    )


def _load_system_prompt(agent_name: str) -> str:
    path = PROMPTS_DIR / f"subagent_prompt_{agent_name}.md"  # 关键变量：提示词路径
    _require_file(path)  # 关键分支：提示词必须存在
    content = _read_text(path).strip()  # 关键变量：提示词内容
    if not content:  # 关键分支：空提示词直接失败
        raise ValueError(f"Empty prompt file: {path}")
    return content


def _task_file_for_agent(agent: NextAgent) -> Path:
    if agent in {"TEST", "DEV", "REVIEW"}:  # 关键分支：子代理工单
        return CONFIG.get_task_file(agent)
    if agent == "USER":  # 关键分支：USER 无工单
        raise ValueError("USER is not a sub-agent and has no task file")
    if agent == "FINISH":  # 关键分支：FINISH 无工单
        raise ValueError("FINISH is not a sub-agent and has no task file")
    raise ValueError(f"No task file for agent: {agent!r}")


def _summarize_dev_plan_status(dev_plan_text: str) -> str:
    """
    从 dev_plan 中提取任务状态摘要，用于 FINISH_CHECK 场景。
    返回格式：每个任务一行，包含任务 ID 和状态。
    """
    try:
        tasks = parse_overall_task_statuses(dev_plan_text)
    except RuntimeError:
        return "(无法解析任务状态)"
    if not tasks:
        return "(无法解析任务状态)"
    return "\n".join([f"- {task_id}: {status}" for task_id, status in tasks])


def _extract_finish_review_verdict(finish_review_text: str) -> str:
    """
    从 FINISH_REVIEW 报告中提取关键结论和阻塞项，用于 FINISH_CHECK 场景。
    """
    lines = finish_review_text.splitlines()
    extracted: list[str] = []
    in_problem_section = False
    in_blocker_section = False
    problem_lines: list[str] = []
    blocker_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        # 提取结论行
        if stripped.startswith("结论：") or stripped.startswith("结论:"):
            extracted.append(stripped)
        # 提取阻塞行
        elif stripped.startswith("阻塞：") or stripped.startswith("阻塞:"):
            extracted.append(stripped)
        # 提取问题清单标题
        elif stripped.startswith("**问题清单**") or stripped == "问题清单":
            in_problem_section = True
            in_blocker_section = False
        # 提取差距清单标题
        elif stripped.startswith("**差距清单**") or stripped == "差距清单":
            in_problem_section = False
            in_blocker_section = True
        # 其他标题结束当前段落
        elif stripped.startswith("**") and stripped.endswith("**"):
            in_problem_section = False
            in_blocker_section = False
        # 收集问题清单内容（P0/P1 开头的行）
        elif in_problem_section and (stripped.startswith("- P0") or stripped.startswith("- P1")):
            problem_lines.append(stripped)

    # 组装摘要
    result_parts = extracted
    if problem_lines:
        result_parts.append("关键问题：")
        result_parts.extend(problem_lines[:5])  # 最多 5 条
        if len(problem_lines) > 5:
            result_parts.append(f"  ...（共 {len(problem_lines)} 条）")

    if not result_parts:
        return "(无法解析 FINISH_REVIEW 结论)"
    return "\n".join(result_parts)
