from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .config import ORCHESTRATOR_LOG_FILE, PROJECT_HISTORY_FILE, PROJECT_ROOT


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
