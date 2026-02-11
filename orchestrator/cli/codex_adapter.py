"""Codex CLI 适配器"""

from __future__ import annotations

import re
from pathlib import Path

from .base import CLIRunner, CLIConfig


# Codex 压缩配置：resume 时使用较低的 auto_compact_limit 触发自动压缩
CODEX_COMPACT_LIMIT = 5000


class CodexRunner(CLIRunner):
    """Codex CLI 适配器

    使用 `codex exec` 非交互模式执行任务。
    - 通过 stdin 传递 prompt
    - 通过 `--output-last-message` 将最后一条消息写入文件
    - 从输出中解析 session id
    - resume 时通过 auto_compact_limit 触发自动压缩
    """

    # 会话ID正则表达式
    SESSION_ID_RE = re.compile(
        r"\bsession id:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
        re.IGNORECASE,
    )

    @property
    def name(self) -> str:
        return "codex"

    @property
    def supports_compact(self) -> bool:
        """Codex 不支持 /compact 命令

        Codex 的 auto_compact_limit 只是一个配置参数，不是真正的压缩命令。
        /compact 会被当作普通文本发送给模型，不会实际压缩上下文。
        """
        return False

    def build_command(
        self,
        config: CLIConfig,
        resume_session_id: str | None = None,
    ) -> list[str]:
        """构建 codex exec 命令"""
        cmd: list[str] = [
            "codex",
            "-s", config.sandbox_mode,
            "-a", config.approval_policy,
            "exec",
            "--color", "never",
            "-C", str(config.work_dir),
            "--output-last-message", str(config.output_file),
        ]

        # 添加额外参数
        if config.extra_args:
            cmd.extend(config.extra_args)

        # 恢复会话或新会话
        if resume_session_id is not None:
            cmd.extend(["resume", resume_session_id, "-"])
        else:
            cmd.append("-")

        return cmd

    def build_compact_command(
        self,
        config: CLIConfig,
        resume_session_id: str,
    ) -> list[str]:
        """构建带压缩配置的 codex exec resume 命令

        Codex 通过 auto_compact_limit 配置触发自动压缩，
        而不是像 Claude 那样使用 /compact 命令。
        """
        cmd: list[str] = [
            "codex",
            "-s", config.sandbox_mode,
            "-a", config.approval_policy,
            "-c", f"auto_compact_limit={CODEX_COMPACT_LIMIT}",
            "exec",
            "--color", "never",
            "-C", str(config.work_dir),
            "--output-last-message", str(config.output_file),
        ]

        # 添加额外参数
        if config.extra_args:
            cmd.extend(config.extra_args)

        # resume 会话
        cmd.extend(["resume", resume_session_id, "-"])

        return cmd

    def parse_session_id(self, output: str) -> str | None:
        """从输出行解析会话ID"""
        match = self.SESSION_ID_RE.search(output)
        if match:
            return match.group(1)
        return None

    def get_last_message(self, config: CLIConfig, output: str) -> str:
        """从输出文件读取最后一条消息"""
        if not config.output_file.exists():
            return ""
        return config.output_file.read_text(encoding="utf-8").strip()
