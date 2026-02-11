"""Token 使用信息查询模块

从 CLI 会话文件中读取 token 使用信息，用于：
1. 监控上下文使用情况
2. 对比压缩前后的 token 变化
3. 在日志/UI 中展示上下文使用率
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import TokenInfo

# Codex 会话目录
CODEX_SESSIONS_DIR = Path.home() / ".codex" / "sessions"
# Claude 会话目录
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def get_codex_session_token_info(session_id: str) -> "TokenInfo | None":
    """从 Codex 会话文件读取 token 信息

    会话文件格式：~/.codex/sessions/YYYY/MM/DD/rollout-*-<session_id>.jsonl
    """
    if not CODEX_SESSIONS_DIR.exists():
        return None

    # 搜索包含 session_id 的文件
    for session_file in CODEX_SESSIONS_DIR.rglob("*.jsonl"):
        if session_id in session_file.name:
            return _parse_codex_session_file(session_file, session_id)
    return None


def _parse_codex_session_file(file_path: Path, session_id: str) -> "TokenInfo | None":
    """解析 Codex 会话文件，提取最新的 token 信息"""
    last_token_info = None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "event_msg":
                        payload = data.get("payload", {})
                        if payload.get("type") == "token_count" and payload.get("info"):
                            last_token_info = payload["info"]
                except json.JSONDecodeError:
                    continue
    except (OSError, IOError):
        return None

    if not last_token_info:
        return None

    last_usage = last_token_info.get("last_token_usage", {})
    total_usage = last_token_info.get("total_token_usage", {})
    context_window = last_token_info.get("model_context_window", 0)
    current_context = last_usage.get("input_tokens", 0)

    return {
        "session_id": session_id,
        "current_context_tokens": current_context,
        "context_window": context_window,
        "usage_percentage": (current_context / context_window * 100) if context_window > 0 else 0,
        "total_usage": total_usage,
        "last_usage": last_usage,
    }


def get_claude_session_token_info(
    session_id: str,
    project_path: Path | None = None,
) -> "TokenInfo | None":
    """从 Claude 会话文件读取 token 信息

    Claude CLI 会话文件格式：~/.claude/projects/<project-hash>/<session_id>.jsonl
    """
    if not CLAUDE_PROJECTS_DIR.exists():
        return None

    # 搜索包含 session_id 的文件
    for session_file in CLAUDE_PROJECTS_DIR.rglob("*.jsonl"):
        if session_id in session_file.name:
            return _parse_claude_session_file(session_file, session_id)
    return None


def _parse_claude_session_file(file_path: Path, session_id: str) -> "TokenInfo | None":
    """解析 Claude 会话文件，提取最新的 token 信息

    Claude 会话文件格式与 Codex 不同，需要查找 usage 信息。

    Claude 的 usage 格式包含：
    - input_tokens: 本次请求新增的 token 数
    - cache_read_input_tokens: 从缓存读取的 token 数
    - cache_creation_input_tokens: 创建缓存的 token 数
    - output_tokens: 输出 token 数

    实际上下文大小 = input_tokens + cache_read_input_tokens
    （cache_creation_input_tokens 是创建缓存时的 token，不计入当前上下文）
    """
    last_usage_info = None
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    # Claude 格式：查找包含 usage 的消息
                    usage = None
                    if "usage" in data:
                        usage = data["usage"]
                    # 也可能在 message 中
                    elif isinstance(data.get("message"), dict):
                        msg = data["message"]
                        if "usage" in msg:
                            usage = msg["usage"]

                    if usage:
                        last_usage_info = usage
                        # 累计 token 使用量
                        total_input_tokens += usage.get("input_tokens", 0)
                        total_input_tokens += usage.get("cache_read_input_tokens", 0)
                        total_output_tokens += usage.get("output_tokens", 0)
                except json.JSONDecodeError:
                    continue
    except (OSError, IOError):
        return None

    if not last_usage_info:
        return None

    # Claude 的 usage 格式 - 计算实际上下文大小
    # 当前上下文 = 本次新增 token + 缓存读取 token
    last_input_tokens = last_usage_info.get("input_tokens", 0)
    last_cache_read = last_usage_info.get("cache_read_input_tokens", 0)
    last_output_tokens = last_usage_info.get("output_tokens", 0)
    current_context = last_input_tokens + last_cache_read

    # Claude 默认上下文窗口（根据模型不同可能变化）
    context_window = 200000  # Claude 3.5 Sonnet / Opus 默认

    return {
        "session_id": session_id,
        "current_context_tokens": current_context,
        "context_window": context_window,
        "usage_percentage": (current_context / context_window * 100) if context_window > 0 else 0,
        "total_usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
        },
        "last_usage": {
            "input_tokens": last_input_tokens,
            "cache_read_input_tokens": last_cache_read,
            "output_tokens": last_output_tokens,
            "total_tokens": last_input_tokens + last_cache_read + last_output_tokens,
        },
    }


def get_session_token_info(
    session_id: str,
    cli_name: str = "codex",
    project_path: Path | None = None,
) -> "TokenInfo | None":
    """统一接口：根据 CLI 类型获取 token 信息

    Args:
        session_id: 会话 ID
        cli_name: CLI 工具名称（codex/claude/opencode）
        project_path: 项目路径（Claude 需要）

    Returns:
        TokenInfo 或 None
    """
    if not session_id:
        return None

    if cli_name == "codex":
        return get_codex_session_token_info(session_id)
    elif cli_name == "claude":
        return get_claude_session_token_info(session_id, project_path)
    elif cli_name == "opencode":
        # OpenCode 暂不支持，返回 None
        return None
    return None


def format_token_info(info: "TokenInfo") -> str:
    """格式化 token 信息为可读字符串"""
    current = info.get("current_context_tokens", 0)
    window = info.get("context_window", 0)
    percentage = info.get("usage_percentage", 0)
    return f"context={current:,} tokens ({percentage:.1f}% of {window:,})"


def format_compact_result(
    before_tokens: int,
    after_tokens: int,
) -> str:
    """格式化压缩结果为可读字符串"""
    reduction = before_tokens - after_tokens
    reduction_pct = (reduction / before_tokens * 100) if before_tokens > 0 else 0
    return f"reduced {reduction:,} tokens ({reduction_pct:.1f}%)"
