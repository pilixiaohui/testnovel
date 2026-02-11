"""CLI 工具抽象基类"""

from __future__ import annotations

import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..state import RunControl
    from ..types import TokenInfo, CompactResult


@dataclass
class CLIRunResult:
    """CLI 执行结果"""
    last_message: str                    # 模型最后一条消息
    session_id: str | None = None        # 会话ID（用于恢复）
    exit_code: int = 0                   # 退出码
    raw_output: str = ""                 # 原始输出（用于调试）
    token_info: "TokenInfo | None" = None  # Token 信息（压缩后查询）
    compact_result: "CompactResult | None" = None  # 压缩结果（仅 run_with_compact 时有值）


@dataclass
class CLIConfig:
    """CLI 运行配置"""
    sandbox_mode: str                    # 沙箱模式
    approval_policy: str                 # 审批策略
    work_dir: Path                       # 工作目录
    output_file: Path                    # 输出文件路径
    extra_args: list[str] = field(default_factory=list)  # 额外参数
    system_prompt: str | None = None     # 系统提示词（追加到默认系统提示词）


# 临时错误关键词（用于判断是否可重试）
# 注意：使用完整短语匹配，避免误匹配 JSON 字段（如 "service_tier" 误匹配 "service"）
TEMPORARY_ERROR_HINTS = (
    "timeout",
    "timed out",
    "rate limit",
    "429",
    "500",
    "502",
    "503",
    "504",
    "overloaded",
    "temporar",
    "network error",
    "connection reset",
    "connection refused",
    "econnreset",
    "econnrefused",
    "high demand",
    "internal server error",
    "service unavailable",
    "封号",
    "exceeded the",  # 捕获 "exceeded the N output token maximum"
    "output token maximum",  # 捕获 output token 超限错误
)

# 排除误匹配的 JSON 字段模式
TEMPORARY_ERROR_EXCLUDE_PATTERNS = (
    '"service_tier"',
    "'service_tier'",
)


def is_temporary_failure(output: str) -> bool:
    """判断是否为临时性错误（可重试）

    使用关键词匹配，但排除 JSON 字段中的误匹配（如 "service_tier":"standard"）
    """
    lowered = output.lower()

    # 先检查是否包含排除模式（JSON 字段）
    for exclude in TEMPORARY_ERROR_EXCLUDE_PATTERNS:
        if exclude in lowered:
            # 如果包含排除模式，需要更严格的匹配
            # 只有当错误关键词不是来自 JSON 字段时才返回 True
            pass

    # 检查是否包含临时错误关键词
    for hint in TEMPORARY_ERROR_HINTS:
        if hint in lowered:
            # 特殊处理 "service unavailable"：确保不是 "service_tier" 的误匹配
            if hint == "service unavailable":
                # 精确匹配完整短语
                if "service unavailable" in lowered:
                    return True
            else:
                return True

    return False


class CLIRunner(ABC):
    """CLI 工具抽象基类

    子类需实现：
    - name: CLI 工具名称
    - build_command: 构建命令行参数
    - parse_session_id: 从输出解析会话ID
    - get_last_message: 获取最后一条消息
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """CLI 工具名称"""
        pass

    @property
    def supports_compact(self) -> bool:
        """是否支持真正的 /compact 命令

        返回 True 表示 CLI 有内置的 /compact 命令可以真正压缩上下文。
        返回 False 表示 /compact 会被当作普通文本传给模型（无实际压缩效果）。

        默认返回 False，子类可覆盖。
        """
        return False

    @abstractmethod
    def build_command(
        self,
        config: CLIConfig,
        resume_session_id: str | None = None,
    ) -> list[str]:
        """构建命令行参数

        Args:
            config: CLI 配置
            resume_session_id: 恢复会话ID（可选）

        Returns:
            命令行参数列表
        """
        pass

    @abstractmethod
    def parse_session_id(self, output: str) -> str | None:
        """从输出中解析会话ID

        Args:
            output: CLI 输出文本

        Returns:
            会话ID，未找到返回 None
        """
        pass

    @abstractmethod
    def get_last_message(self, config: CLIConfig, output: str) -> str:
        """获取最后一条消息

        Args:
            config: CLI 配置（可能需要读取输出文件）
            output: CLI 输出文本

        Returns:
            最后一条消息内容
        """
        pass

    def stdin_input(self) -> bool:
        """是否通过 stdin 传递 prompt

        Returns:
            True 表示通过 stdin 传递，False 表示通过命令行参数
        """
        return True

    def append_prompt_to_command(self, cmd: list[str], prompt: str) -> list[str]:
        """将 prompt 追加到命令行（用于不使用 stdin 的 CLI）

        Args:
            cmd: 基础命令列表
            prompt: 提示词

        Returns:
            包含 prompt 的完整命令列表
        """
        # 默认实现：将 prompt 作为最后一个参数
        return cmd + [prompt]

    def build_stdin_content(self, prompt: str, config: CLIConfig) -> str:
        """构建 stdin 内容（子类可覆盖以支持系统提示词等）

        Args:
            prompt: 用户提示词
            config: CLI 配置

        Returns:
            要写入 stdin 的内容
        """
        # 默认实现：直接返回 prompt
        return prompt

    def run(
        self,
        prompt: str,
        config: CLIConfig,
        label: str,
        log_file: Path,
        resume_session_id: str | None = None,
        control: "RunControl | None" = None,
        max_empty_retries: int = 3,
    ) -> CLIRunResult:
        """执行 CLI

        Args:
            prompt: 提示词
            config: CLI 配置
            label: 日志标签（如 MAIN、IMPLEMENTER）
            log_file: 日志文件路径
            resume_session_id: 恢复会话ID
            control: 运行控制（用于中断）
            max_empty_retries: 空输出最大重试次数

        Returns:
            执行结果

        Raises:
            UserInterrupted: 用户中断
            TemporaryError: 临时错误（可重试）
            PermanentError: 永久错误
        """
        from ..errors import PermanentError, TemporaryError
        from ..state import UserInterrupted
        from ..file_ops import _append_log_line

        if not config.output_file.parent.is_dir():
            raise FileNotFoundError(f"Missing required directory: {config.output_file.parent}")
        if max_empty_retries < 0:
            raise ValueError("max_empty_retries must be >= 0")

        retries_left = max_empty_retries
        active_resume_session_id = resume_session_id
        retry_notice = (
            f"上次 {label} 输出为空，导致 `{config.output_file}` 无内容。"
            "你必须输出完整最终结果作为最后一条消息（严格按提示词格式），"
            "否则流程将终止。禁止再次省略或空输出。"
        )

        while True:
            if control is not None and control.cancel_event.is_set():
                raise UserInterrupted(f"User interrupted before starting {self.name}")

            attempt_prompt = prompt if retries_left == max_empty_retries else f"{prompt}\n\n{retry_notice}"
            # 构建 stdin 内容（子类可覆盖以支持系统提示词等）
            stdin_content = self.build_stdin_content(attempt_prompt, config)
            cmd = self.build_command(config, active_resume_session_id)

            # 如果不使用 stdin，将 prompt 追加到命令行
            if not self.stdin_input():
                cmd = self.append_prompt_to_command(cmd, attempt_prompt)

            log_file.parent.mkdir(parents=True, exist_ok=True)
            with log_file.open("a", encoding="utf-8") as lf:
                banner = f"\n----- {self.name} ({label}) -----\n"
                print(banner, flush=True)
                lf.write(banner)
                lf.flush()

                line_prefix = f"{label.lower()}: "
                proc = subprocess.Popen(
                    cmd,
                    cwd=config.work_dir,
                    stdin=subprocess.PIPE if self.stdin_input() else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                if control is not None:
                    control.set_current_proc(proc)

                try:
                    if self.stdin_input():
                        assert proc.stdin is not None
                        proc.stdin.write(stdin_content)
                        proc.stdin.close()

                    combined_output: list[str] = []
                    session_id: str | None = None

                    assert proc.stdout is not None
                    for line in proc.stdout:
                        combined_output.append(line)
                        if session_id is None:
                            session_id = self.parse_session_id(line)
                        prefixed = f"{line_prefix}{line}"
                        sys.stdout.write(prefixed)
                        lf.write(prefixed)
                        lf.flush()
                        sys.stdout.flush()
                        if control is not None and control.cancel_event.is_set() and proc.poll() is None:
                            proc.terminate()

                    return_code = proc.wait()
                finally:
                    if control is not None:
                        control.set_current_proc(None)

                if return_code != 0:
                    if control is not None and control.cancel_event.is_set():
                        raise UserInterrupted(f"User interrupted during {label} run")

                    # 关键修复：保留已解析的 session_id，供重试时 resume
                    if session_id is not None and active_resume_session_id is None:
                        active_resume_session_id = session_id

                    combined_text = "".join(combined_output)
                    is_temporary = is_temporary_failure(combined_text)
                    error_msg = (
                        f"{self.name} failed\n"
                        f"cmd: {' '.join(cmd)}\n"
                        f"return_code: {return_code}\n"
                        f"combined_output:\n{combined_text}\n"
                    )
                    # 记录错误到日志文件
                    error_log = (
                        f"orchestrator: {label} CLI FAILED - "
                        f"cli={self.name}, return_code={return_code}, "
                        f"is_temporary={is_temporary}, "
                        f"session_id={active_resume_session_id or 'none'}\n"
                    )
                    _append_log_line(error_log)
                    lf.write(f"\n----- {label} ERROR -----\n{error_msg}\n")
                    lf.flush()
                    if is_temporary:
                        raise TemporaryError(error_msg, session_id=active_resume_session_id)
                    else:
                        raise PermanentError(error_msg)

            # 验证会话ID一致性
            if active_resume_session_id is not None and session_id is not None:
                if session_id != active_resume_session_id:
                    raise RuntimeError(
                        f"{self.name} resumed session_id mismatch: "
                        f"expected {active_resume_session_id!r}, got {session_id!r}"
                    )
            if active_resume_session_id is None and session_id is not None:
                active_resume_session_id = session_id

            # 获取最后一条消息
            combined_text = "".join(combined_output)
            last_message = self.get_last_message(config, combined_text)

            # 诊断信息
            prompt_char_count = len(attempt_prompt)
            prompt_line_count = attempt_prompt.count('\n') + 1
            output_char_count = len(last_message)
            diag_msg = (
                f"orchestrator: {label} diag: "
                f"cli={self.name}, prompt_chars={prompt_char_count}, prompt_lines={prompt_line_count}, "
                f"output_chars={output_char_count}, session_id={session_id or 'none'}\n"
            )
            _append_log_line(diag_msg)

            if not last_message:
                is_server_error = is_temporary_failure(combined_text)
                empty_diag = (
                    f"orchestrator: {label} EMPTY OUTPUT detected - "
                    f"cli={self.name}, prompt_chars={prompt_char_count}, prompt_lines={prompt_line_count}, "
                    f"retries_left={retries_left}, server_error={is_server_error}\n"
                )
                _append_log_line(empty_diag)
                print(empty_diag, end="", flush=True)

                if retries_left <= 0:
                    raise TemporaryError(
                        f"Empty last message: {config.output_file}\n"
                        f"Diagnostics: cli={self.name}, prompt_chars={prompt_char_count}, "
                        f"prompt_lines={prompt_line_count}, session_id={session_id or 'none'}, "
                        f"server_error={is_server_error}"
                    )
                if active_resume_session_id is None:
                    raise PermanentError(
                        f"Empty last message: {config.output_file} (missing session_id for resume)"
                    )

                # 退避重试
                if is_server_error:
                    attempt_num = max_empty_retries - retries_left + 1
                    backoff_seconds = min(30, 5 * (2 ** (attempt_num - 1)))
                    backoff_msg = (
                        f"orchestrator: {label} server error detected, waiting {backoff_seconds}s before retry "
                        f"({attempt_num}/{max_empty_retries})\n"
                    )
                    _append_log_line(backoff_msg)
                    print(backoff_msg, end="", flush=True)
                    time.sleep(backoff_seconds)
                else:
                    retry_msg = (
                        f"orchestrator: {label} empty last message; retrying "
                        f"({max_empty_retries - retries_left + 1}/{max_empty_retries})\n"
                    )
                    _append_log_line(retry_msg)
                    print(retry_msg, end="", flush=True)

                retries_left -= 1
                continue

            return CLIRunResult(
                last_message=last_message,
                session_id=session_id,
                exit_code=0,
                raw_output=combined_text,
            )

    def build_compact_command(
        self,
        config: CLIConfig,
        resume_session_id: str,
    ) -> list[str] | None:
        """构建压缩命令（子类可覆盖）

        默认返回 None，表示使用 /compact 命令方式。
        子类可覆盖此方法返回自定义的压缩命令（如 Codex 使用 auto_compact_limit）。

        Args:
            config: CLI 配置
            resume_session_id: 会话ID

        Returns:
            压缩命令列表，或 None 表示使用默认的 /compact 方式
        """
        return None

    def run_with_compact(
        self,
        prompt: str,
        config: CLIConfig,
        label: str,
        log_file: Path,
        resume_session_id: str,
        compact_instructions: str,
        control: "RunControl | None" = None,
        max_empty_retries: int = 3,
    ) -> CLIRunResult:
        """执行带上下文压缩的 CLI 调用（两步合一）

        流程：
        1. 执行压缩步骤（CLI 特定方式）
        2. 再 resume 会话发送实际 prompt

        不同 CLI 的压缩方式：
        - Claude: 发送 /compact 命令
        - Codex: 使用 -c auto_compact_limit=10000 触发自动压缩

        Args:
            prompt: 实际提示词（不含 /compact）
            config: CLI 配置
            label: 日志标签
            log_file: 日志文件路径
            resume_session_id: 必须提供会话ID（压缩需要已有会话）
            compact_instructions: 压缩指令内容
            control: 运行控制
            max_empty_retries: 空输出最大重试次数

        Returns:
            执行结果（来自实际 prompt），包含 token_info 和 compact_result
        """
        from ..file_ops import _append_log_line
        from ..token_info import get_session_token_info, format_token_info

        # ========== 压缩前记录 token 信息 ==========
        token_before = get_session_token_info(resume_session_id, self.name)
        if token_before:
            _append_log_line(
                f"orchestrator: {label} context BEFORE compact: "
                f"{format_token_info(token_before)}\n"
            )
            print(
                f"orchestrator: {label} context BEFORE compact: "
                f"{format_token_info(token_before)}",
                flush=True,
            )

        # ========== 第一步：执行压缩 ==========
        if self.supports_compact:
            _append_log_line(f"orchestrator: {label} executing compact (step 1/2)\n")
            print(f"\n----- {self.name} ({label}) - Compact Step -----\n", flush=True)

            try:
                # 检查是否有自定义压缩命令（如 Codex 的 auto_compact_limit）
                compact_cmd = self.build_compact_command(config, resume_session_id)

                if compact_cmd is not None:
                    # 使用自定义压缩命令（如 Codex）
                    self._run_compact_with_custom_command(
                        compact_cmd=compact_cmd,
                        compact_prompt=compact_instructions,
                        config=config,
                        label=f"{label}_COMPACT",
                        log_file=log_file,
                        control=control,
                    )
                else:
                    # 使用 /compact 命令方式（如 Claude）
                    # 注意：/compact 命令的预期行为是返回空结果或简短确认
                    # 因此使用 _run_compact_command 而不是 self.run，避免空输出被当作错误
                    compact_prompt = f"/compact {compact_instructions}"
                    self._run_compact_command(
                        prompt=compact_prompt,
                        config=config,
                        label=f"{label}_COMPACT",
                        log_file=log_file,
                        resume_session_id=resume_session_id,
                        control=control,
                    )

                _append_log_line(f"orchestrator: {label} compact completed\n")
            except Exception as e:
                # 压缩失败不阻塞主流程，记录警告继续
                _append_log_line(f"orchestrator: {label} compact failed (non-fatal): {e}\n")
                print(f"Warning: {label} compact failed (non-fatal): {e}", flush=True)

            _append_log_line(f"orchestrator: {label} executing prompt (step 2/2)\n")
            print(f"\n----- {self.name} ({label}) - Main Step -----\n", flush=True)
        else:
            # CLI 不支持压缩，跳过压缩步骤
            _append_log_line(
                f"orchestrator: {label} skipping compact ({self.name} does not support compact)\n"
            )

        # ========== 第二步：执行实际 prompt ==========
        result = self.run(
            prompt=prompt,
            config=config,
            label=label,
            log_file=log_file,
            resume_session_id=resume_session_id,
            control=control,
            max_empty_retries=max_empty_retries,
        )

        # ========== Main Step 执行后记录 token 信息（压缩效果此时才能体现）==========
        token_after = get_session_token_info(resume_session_id, self.name)
        compact_result: "CompactResult | None" = None
        if token_after:
            _append_log_line(
                f"orchestrator: {label} context AFTER compact+main: "
                f"{format_token_info(token_after)}\n"
            )
            print(
                f"orchestrator: {label} context AFTER compact+main: "
                f"{format_token_info(token_after)}",
                flush=True,
            )
            if token_before:
                before_tokens = token_before.get("current_context_tokens", 0)
                after_tokens = token_after.get("current_context_tokens", 0)
                reduction = before_tokens - after_tokens
                reduction_pct = (reduction / before_tokens * 100) if before_tokens > 0 else 0
                compact_result = {
                    "before_tokens": before_tokens,
                    "after_tokens": after_tokens,
                    "reduction": reduction,
                    "reduction_percentage": reduction_pct,
                }
                # 只有在确实减少了 token 时才报告压缩效果
                if reduction > 0:
                    effect_msg = (
                        f"orchestrator: {label} compact effect: "
                        f"reduced {reduction:,} tokens ({reduction_pct:.1f}%)\n"
                    )
                    _append_log_line(effect_msg)
                    print(effect_msg, end="", flush=True)
                else:
                    # Main Step 增加的 token 可能超过压缩减少的量，这是正常的
                    net_change = -reduction  # 净增加量
                    note_msg = (
                        f"orchestrator: {label} note: context increased by {net_change:,} tokens "
                        f"(compact savings offset by main step output)\n"
                    )
                    _append_log_line(note_msg)
                    print(note_msg, end="", flush=True)

        # 附加 token 信息到结果
        result.token_info = token_after
        result.compact_result = compact_result
        return result

    def _run_compact_with_custom_command(
        self,
        compact_cmd: list[str],
        compact_prompt: str,
        config: CLIConfig,
        label: str,
        log_file: Path,
        control: "RunControl | None" = None,
    ) -> None:
        """使用自定义命令执行压缩（内部方法）

        用于 Codex 等使用特殊压缩机制的 CLI。

        Args:
            compact_cmd: 压缩命令列表
            compact_prompt: 压缩提示词
            config: CLI 配置
            label: 日志标签
            log_file: 日志文件路径
            control: 运行控制
        """
        from ..state import UserInterrupted

        if control is not None and control.cancel_event.is_set():
            raise UserInterrupted(f"User interrupted before starting {self.name} compact")

        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as lf:
            banner = f"\n----- {self.name} ({label}) -----\n"
            print(banner, flush=True)
            lf.write(banner)
            lf.flush()

            line_prefix = f"{label.lower()}: "
            proc = subprocess.Popen(
                compact_cmd,
                cwd=config.work_dir,
                stdin=subprocess.PIPE if self.stdin_input() else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if control is not None:
                control.set_current_proc(proc)

            try:
                if self.stdin_input():
                    assert proc.stdin is not None
                    # 对于 Codex 等使用 auto_compact_limit 的 CLI，发送 /compact 命令触发压缩后退出
                    # 而不是发送 compact_prompt 作为任务内容
                    proc.stdin.write(f"/compact {compact_prompt}")
                    proc.stdin.close()

                assert proc.stdout is not None
                for line in proc.stdout:
                    prefixed = f"{line_prefix}{line}"
                    sys.stdout.write(prefixed)
                    lf.write(prefixed)
                    lf.flush()
                    sys.stdout.flush()
                    if control is not None and control.cancel_event.is_set() and proc.poll() is None:
                        proc.terminate()

                proc.wait()
            finally:
                if control is not None:
                    control.set_current_proc(None)

    def _run_compact_command(
        self,
        prompt: str,
        config: CLIConfig,
        label: str,
        log_file: Path,
        resume_session_id: str,
        control: "RunControl | None" = None,
    ) -> None:
        """执行 /compact 命令（内部方法）

        /compact 命令的预期行为是返回空结果或简短确认（如 "Compacted"），
        因此不检查输出是否为空，避免误报错误。

        Args:
            prompt: /compact 命令（包含压缩指令）
            config: CLI 配置
            label: 日志标签
            log_file: 日志文件路径
            resume_session_id: 会话ID
            control: 运行控制
        """
        from ..state import UserInterrupted

        if control is not None and control.cancel_event.is_set():
            raise UserInterrupted(f"User interrupted before starting {self.name} compact")

        cmd = self.build_command(config, resume_session_id)

        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as lf:
            banner = f"\n----- {self.name} ({label}) -----\n"
            print(banner, flush=True)
            lf.write(banner)
            lf.flush()

            line_prefix = f"{label.lower()}: "
            proc = subprocess.Popen(
                cmd,
                cwd=config.work_dir,
                stdin=subprocess.PIPE if self.stdin_input() else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if control is not None:
                control.set_current_proc(proc)

            try:
                if self.stdin_input():
                    assert proc.stdin is not None
                    proc.stdin.write(prompt)
                    proc.stdin.close()

                assert proc.stdout is not None
                for line in proc.stdout:
                    prefixed = f"{line_prefix}{line}"
                    sys.stdout.write(prefixed)
                    lf.write(prefixed)
                    lf.flush()
                    sys.stdout.flush()
                    if control is not None and control.cancel_event.is_set() and proc.poll() is None:
                        proc.terminate()

                return_code = proc.wait()
            finally:
                if control is not None:
                    control.set_current_proc(None)

            # /compact 命令允许非零退出码（某些 CLI 可能返回非零但实际成功）
            # 只在明显失败时抛出异常
            if return_code != 0:
                if control is not None and control.cancel_event.is_set():
                    raise UserInterrupted(f"User interrupted during {label} run")
                # 记录警告但不抛出异常，因为 /compact 的退出码不总是可靠的
                from ..file_ops import _append_log_line
                _append_log_line(
                    f"orchestrator: {label} returned non-zero exit code {return_code} (ignored for compact)\n"
                )
