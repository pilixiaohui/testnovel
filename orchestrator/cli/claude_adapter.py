"""Claude Code CLI 适配器"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .base import CLIRunner, CLIConfig


class ClaudeRunner(CLIRunner):
    """Claude Code CLI 适配器

    使用 `claude -p` 非交互模式执行任务。
    - 通过 stdin 传递 prompt
    - 通过 `--output-format json` 获取结构化输出
    - 从 JSON 输出中提取 session_id 和 result
    """

    # 会话ID正则表达式（从 JSON 输出中解析）
    SESSION_ID_JSON_RE = re.compile(
        r'"session_id"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
        re.IGNORECASE,
    )

    # 备用：从文本输出中解析
    SESSION_ID_TEXT_RE = re.compile(
        r"\bsession[_\s]?id[:\s]+([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
        re.IGNORECASE,
    )

    # 权限模式映射：(sandbox_mode, approval_policy) -> claude permission_mode
    PERMISSION_MODE_MAP = {
        ("read-only", "on-request"): "plan",
        ("workspace-write", "on-request"): "default",
        ("workspace-write", "auto-edit"): "acceptEdits",
        ("workspace-write", "full-auto"): "dontAsk",
        ("danger-full-access", "full-auto"): "bypassPermissions",
    }

    @property
    def name(self) -> str:
        return "claude"

    @property
    def supports_compact(self) -> bool:
        """Claude CLI 支持真正的 /compact 命令"""
        return True

    def _map_permission_mode(self, config: CLIConfig) -> str:
        """将 codex 的权限配置映射到 claude 的 permission-mode"""
        key = (config.sandbox_mode, config.approval_policy)
        return self.PERMISSION_MODE_MAP.get(key, "default")

    def build_command(
        self,
        config: CLIConfig,
        resume_session_id: str | None = None,
    ) -> list[str]:
        """构建 claude -p 命令"""
        permission_mode = self._map_permission_mode(config)

        cmd: list[str] = [
            "claude",
            "-p",  # 非交互模式
            "--permission-mode", permission_mode,
            "--output-format", "stream-json",  # 流式 JSON 输出，实时显示且包含 session_id
            "--verbose",  # stream-json 需要 verbose
        ]

        # 追加系统提示词（作为系统消息注入，优先级高于用户消息）
        if config.system_prompt:
            cmd.extend(["--append-system-prompt", config.system_prompt])

        # 恢复会话
        if resume_session_id is not None:
            cmd.extend(["-r", resume_session_id])

        # 添加额外参数
        if config.extra_args:
            cmd.extend(config.extra_args)

        return cmd

    def parse_session_id(self, output: str) -> str | None:
        """从输出行解析会话ID"""
        # 优先从 JSON 格式解析
        match = self.SESSION_ID_JSON_RE.search(output)
        if match:
            return match.group(1)

        # 备用：从文本格式解析
        match = self.SESSION_ID_TEXT_RE.search(output)
        if match:
            return match.group(1)

        return None

    # API 错误关键词（即使返回码为 0，也应该抛出错误）
    API_ERROR_PATTERNS = (
        "api error:",
        "output token maximum",
        "exceeded the",
        "rate limit",
        "overloaded",
    )

    def get_last_message(self, config: CLIConfig, output: str) -> str:
        """从输出中提取最后一条消息

        claude -p --output-format stream-json 输出多行 JSON 事件流，
        最后一行是 type=result 的汇总，包含 result 字段。

        注意：即使返回码为 0，result 中也可能包含 API 错误信息。
        这种情况下需要抛出异常，让上层逻辑处理（如触发 compact）。
        """
        from .base import is_temporary_failure
        from ..errors import TemporaryError

        result = ""
        is_error = False

        # stream-json 输出多行 JSON，查找 type=result 的行
        lines = output.strip().split('\n')
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # 查找 result 类型的事件（最终汇总）
                if data.get("type") == "result" and "result" in data:
                    result = data["result"]
                    # 检查是否标记为错误
                    is_error = data.get("is_error", False)
                    break
            except json.JSONDecodeError:
                continue

        # 如果没找到 result 事件，尝试从 assistant 消息中提取
        if not result:
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "assistant":
                        message = data.get("message", {})
                        content = message.get("content", [])
                        if isinstance(content, list):
                            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                            result = "\n".join(texts)
                        elif isinstance(content, str):
                            result = content
                        if result:
                            break
                except json.JSONDecodeError:
                    continue

        # 写入 output_file 以保持兼容性
        if result and config.output_file:
            config.output_file.parent.mkdir(parents=True, exist_ok=True)
            config.output_file.write_text(result, encoding="utf-8")

        # 检查 result 中是否包含 API 错误（即使返回码为 0）
        # 这种情况下需要抛出异常，让上层逻辑处理（如触发 compact）
        if result and (is_error or self._is_api_error(result)):
            # 使用 is_temporary_failure 判断是否为临时错误
            if is_temporary_failure(result):
                raise TemporaryError(f"Claude API error in result: {result[:500]}")

        return result

    def _is_api_error(self, result: str) -> bool:
        """检查 result 是否包含 API 错误"""
        lowered = result.lower()
        return any(pattern in lowered for pattern in self.API_ERROR_PATTERNS)
