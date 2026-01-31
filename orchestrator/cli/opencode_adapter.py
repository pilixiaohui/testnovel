"""OpenCode CLI 适配器"""

from __future__ import annotations

import json
import re

from .base import CLIRunner, CLIConfig


class OpenCodeRunner(CLIRunner):
    """OpenCode CLI 适配器

    使用 `opencode run` 非交互模式执行任务。
    - 通过命令行参数传递 prompt（不使用 stdin）
    - 通过 `--format json` 获取 JSON 格式输出
    - 从 JSON 输出中提取 session_id 和结果
    """

    # 会话ID正则表达式（从输出中解析）
    SESSION_ID_RE = re.compile(
        r'"session":\s*"([0-9a-zA-Z_-]+)"',
    )

    # 备用会话ID正则（文本格式）
    SESSION_ID_TEXT_RE = re.compile(
        r"\bsession[_\s]?(?:id)?[:\s]+([0-9a-zA-Z_-]+)\b",
        re.IGNORECASE,
    )

    @property
    def name(self) -> str:
        return "opencode"

    def stdin_input(self) -> bool:
        """opencode run 通过命令行参数传递 prompt，不使用 stdin"""
        return False

    def build_command(
        self,
        config: CLIConfig,
        resume_session_id: str | None = None,
    ) -> list[str]:
        """构建 opencode run 命令

        opencode run [message..] 选项：
        - --format json: JSON 格式输出
        - -s/--session: 恢复指定会话
        - -c/--continue: 继续上一个会话
        - -m/--model: 指定模型
        - --agent: 指定 agent (build/plan)
        """
        cmd: list[str] = [
            "opencode",
            "run",
            "--format", "json",  # JSON 格式输出，便于解析
        ]

        # 恢复会话
        if resume_session_id is not None:
            cmd.extend(["-s", resume_session_id])

        # 添加额外参数（如 --model, --agent 等）
        if config.extra_args:
            cmd.extend(config.extra_args)

        # 注意：prompt 通过命令行参数传递，在 run() 方法中处理
        # opencode run "your prompt here"

        return cmd

    def parse_session_id(self, output: str) -> str | None:
        """从输出行解析会话ID"""
        # 尝试从 JSON 格式解析
        match = self.SESSION_ID_RE.search(output)
        if match:
            return match.group(1)

        # 尝试从文本格式解析
        match = self.SESSION_ID_TEXT_RE.search(output)
        if match:
            return match.group(1)

        return None

    def get_last_message(self, config: CLIConfig, output: str) -> str:
        """从输出中提取最后一条消息

        opencode run --format json 输出 JSON 事件流，
        需要解析最后的 assistant 消息。
        """
        result = ""

        # 尝试解析 JSON 事件流
        lines = output.strip().split('\n')
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                # 查找 assistant 消息
                if event.get("type") == "text" and event.get("role") == "assistant":
                    result = event.get("content", "")
                    break
                # 或者查找 message 类型
                if event.get("type") == "message" and event.get("role") == "assistant":
                    content = event.get("content", [])
                    if isinstance(content, list):
                        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                        result = "\n".join(texts)
                    elif isinstance(content, str):
                        result = content
                    break
            except json.JSONDecodeError:
                continue

        # 如果 JSON 解析失败，尝试提取纯文本
        if not result:
            content_lines = []
            for line in lines:
                # 跳过 JSON 行
                if line.strip().startswith('{'):
                    continue
                # 跳过 session id 行
                if self.SESSION_ID_TEXT_RE.search(line):
                    continue
                if not content_lines and not line.strip():
                    continue
                content_lines.append(line)
            result = '\n'.join(content_lines).strip()

        # 写入 output_file 以保持兼容性
        if result and config.output_file:
            config.output_file.parent.mkdir(parents=True, exist_ok=True)
            config.output_file.write_text(result, encoding="utf-8")

        return result
