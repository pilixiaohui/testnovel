from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .config import DEV_PLAN_FILE, ORCHESTRATOR_LOG_FILE, PROJECT_HISTORY_FILE, PROJECT_ROOT

from project import ProjectTemplates


def _require_file(path: Path) -> None:
    if not path.exists():  # 关键分支：缺失即快速失败，保证黑板完整性
        raise FileNotFoundError(f"Missing required file: {path}")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")  # 关键变量：统一以 UTF-8 读取


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def _write_text_if_missing(path: Path, content: str) -> None:
    if path.exists():  # 关键分支：已有文件不覆盖（只做初始化）
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")  # 关键变量：模板落盘


def _append_log_line(line: str) -> None:
    ORCHESTRATOR_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ORCHESTRATOR_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line)  # 关键变量：追加日志文本


def _append_user_message_to_history(*, iteration: int, message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")  # 关键变量：用户消息时间戳
    lines = [
        "",
        f"## User Message (Iteration {iteration}) - {timestamp}",  # 关键变量：迭代与时间定位
        message.rstrip(),  # 关键变量：用户输入正文
        "",
    ]
    PROJECT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PROJECT_HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _append_new_task_goal_to_history(*, goal: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")  # 关键变量：新任务时间戳
    lines = [
        "",
        f"## Task Goal (New Task) - {timestamp}",  # 关键变量：任务目标标识
        goal.rstrip(),  # 关键变量：任务目标正文
        "",
    ]
    PROJECT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PROJECT_HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _append_history_entry(entry: str) -> None:
    if not isinstance(entry, str) or not entry.strip():  # 关键分支：空历史不允许落盘
        raise ValueError("history entry must be a non-empty string")
    PROJECT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PROJECT_HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(entry.rstrip() + "\n")


def _snapshot_files(paths: Iterable[Path]) -> dict[Path, str | None]:
    snapshots: dict[Path, str | None] = {}  # 关键变量：记录文件哈希快照
    for path in paths:  # 关键分支：逐个路径生成快照
        if path.exists():  # 关键分支：存在则记录哈希
            snapshots[path] = _sha256_text(_read_text(path))  # 关键变量：当前内容哈希
        else:  # 关键分支：不存在则记为 None
            snapshots[path] = None  # 关键变量：标记文件缺失
    return snapshots


def _assert_files_unchanged(before: dict[Path, str | None], *, label: str) -> None:
    for path, digest in before.items():  # 关键分支：逐个文件比对变更
        if path.exists():  # 关键分支：文件存在，检查是否被修改
            if digest is None:  # 关键分支：原本不存在却被创建
                raise RuntimeError(f"{label} created forbidden file: {_rel_path(path)}")
            current = _sha256_text(_read_text(path))  # 关键变量：当前哈希
            if current != digest:  # 关键分支：哈希变化即越权修改
                raise RuntimeError(f"{label} modified forbidden file: {_rel_path(path)}")
        else:  # 关键分支：文件消失
            if digest is not None:  # 关键分支：原本存在却被删除
                raise RuntimeError(f"{label} deleted required file: {_rel_path(path)}")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()  # 关键变量：内容哈希


def _rel_path(path: Path) -> str:
    try:  # 关键分支：尝试生成相对路径
        return path.relative_to(PROJECT_ROOT).as_posix()  # 关键变量：项目内相对路径
    except ValueError as exc:  # 关键分支：路径不在项目根内
        raise ValueError(f"Path must be under project root: {path}") from exc


def _extract_latest_task_goal() -> str:
    """
    从 project_history.md 提取最新的 Task Goal。

    查找格式：## Task Goal (New Task) - <timestamp>
    返回该标题下的内容（直到下一个 ## 标题或文件结束）。
    若未找到则返回空字符串。
    """
    if not PROJECT_HISTORY_FILE.exists():  # 关键分支：文件不存在
        return ""
    content = _read_text(PROJECT_HISTORY_FILE)
    lines = content.splitlines()

    # 查找最后一个 Task Goal 标题
    task_goal_start = -1
    for i, line in enumerate(lines):
        if line.startswith("## Task Goal"):  # 关键分支：找到 Task Goal 标题
            task_goal_start = i

    if task_goal_start == -1:  # 关键分支：未找到 Task Goal
        return ""

    # 提取内容（从标题下一行到下一个 ## 标题或文件结束）
    goal_lines: list[str] = []
    for line in lines[task_goal_start + 1 :]:
        if line.startswith("## "):  # 关键分支：遇到下一个标题，停止
            break
        goal_lines.append(line)

    return "\n".join(goal_lines).strip()  # 关键变量：Task Goal 内容


def _extract_latest_user_decision(*, iteration: int) -> str | None:
    """
    从 project_history.md 提取指定迭代的用户决策。

    查找格式：## User Decision (Iteration N): <title> - <timestamp>
    返回该标题下的完整内容（包括 user_choice 和 user_comment）。
    若未找到则返回 None。
    """
    if not PROJECT_HISTORY_FILE.exists():  # 关键分支：文件不存在
        return None
    content = _read_text(PROJECT_HISTORY_FILE)
    lines = content.splitlines()

    # 查找指定迭代的 User Decision 标题
    decision_start = -1
    needle = f"## User Decision (Iteration {iteration}):"
    for i, line in enumerate(lines):
        if line.startswith(needle):  # 关键分支：找到 User Decision 标题
            decision_start = i
            break  # 只取第一个匹配（同一迭代只有一个用户决策）

    if decision_start == -1:  # 关键分支：未找到 User Decision
        return None

    # 提取内容（从标题到下一个 ## 标题或文件结束）
    decision_lines: list[str] = [lines[decision_start]]
    for line in lines[decision_start + 1:]:
        if line.startswith("## "):  # 关键分支：遇到下一个标题，停止
            break
        decision_lines.append(line)

    return "\n".join(decision_lines).strip()  # 关键变量：User Decision 内容


def _reset_project_history_file() -> None:
    """
    重置 project_history.md 为初始模板。
    用于 NewTask 时用户选择清空历史。
    """
    PROJECT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(PROJECT_HISTORY_FILE, ProjectTemplates.project_history())


def _reset_dev_plan_file() -> None:
    """
    重置 dev_plan.md 为初始模板。
    用于 NewTask 时用户选择清空开发计划。
    """
    DEV_PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(DEV_PLAN_FILE, ProjectTemplates.dev_plan())


def _extract_recent_user_decisions(*, lookback: int = 5) -> list[dict[str, str | int | None]]:
    """
    提取最近 N 轮的所有用户决策，供 MAIN 参考以避免重复询问。

    返回格式：
    [
        {
            "iteration": 1,
            "decision_title": "权限操作需要用户介入",
            "user_choice": "user_fix",
            "user_comment": "已经修复了",
        },
        ...
    ]
    """
    import re

    if not PROJECT_HISTORY_FILE.exists():
        return []

    content = _read_text(PROJECT_HISTORY_FILE)
    decisions: list[dict[str, str | int | None]] = []

    # 解析所有 User Decision 块
    # 格式：## User Decision (Iteration N): <title> - <timestamp>
    pattern = r"## User Decision \(Iteration (\d+)\): (.+?) - \d{4}-\d{2}-\d{2}T[\d:]+\n([\s\S]*?)(?=\n## |\Z)"
    for match in re.finditer(pattern, content):
        iteration = int(match.group(1))
        title = match.group(2).strip()
        body = match.group(3)

        # 提取 user_choice 和 user_comment
        choice_match = re.search(r"- user_choice: (.+)", body)
        comment_match = re.search(r"- user_comment: (.+)", body)

        decisions.append({
            "iteration": iteration,
            "decision_title": title,
            "user_choice": choice_match.group(1).strip() if choice_match else None,
            "user_comment": comment_match.group(1).strip() if comment_match else None,
        })

    return decisions[-lookback:] if len(decisions) > lookback else decisions
