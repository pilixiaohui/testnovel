from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from .config import CODEX_STATE_DIR, MAIN_ITERATION_FILE, MAIN_SESSION_ID_FILE, ORCHESTRATOR_LOG_FILE, PROJECT_ROOT, RESUME_STATE_FILE
from .errors import PermanentError, TemporaryError
from .file_ops import _append_log_line, _atomic_write_text, _read_text, _require_file
from .state import RunControl, UserInterrupted
from .types import CodexRunResult
from .validation import _validate_session_id


def _clear_saved_main_state() -> None:
    """
    new task 时清空 MAIN 的会话与迭代记录。
    - 目的：避免用户触发 new task 但中途打断时，下次仍误恢复旧会话
    - 快速失败：删除失败直接抛错
    """
    for path in (MAIN_SESSION_ID_FILE, MAIN_ITERATION_FILE, RESUME_STATE_FILE):  # 关键分支：逐个清理状态文件
        if path.exists():  # 关键分支：存在才删除，避免无意义报错
            path.unlink()


def _load_saved_main_session_id() -> str | None:
    if not MAIN_SESSION_ID_FILE.exists():  # 关键分支：文件不存在则无会话
        return None
    session_id = _read_text(MAIN_SESSION_ID_FILE).strip()  # 关键变量：读取会话 id
    if not session_id:  # 关键分支：空内容直接失败
        raise ValueError(f"Empty main session id file: {MAIN_SESSION_ID_FILE}")
    _validate_session_id(session_id)
    return session_id


def _save_main_session_id(session_id: str) -> None:
    _validate_session_id(session_id)
    MAIN_SESSION_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(MAIN_SESSION_ID_FILE, f"{session_id}\n")  # 关键变量：持久化会话 id


def _load_saved_main_iteration() -> int:
    """
    返回“最后一次已记录的 iteration”（非下一次）。
    - 文件不存在：返回 0
    - 文件存在但内容非法：快速失败
    """
    if not MAIN_ITERATION_FILE.exists():  # 关键分支：无记录则从 0 开始
        return 0
    raw = _read_text(MAIN_ITERATION_FILE).strip()  # 关键变量：读取迭代值
    if not raw:  # 关键分支：空内容直接失败
        raise ValueError(f"Empty main iteration file: {MAIN_ITERATION_FILE}")
    try:  # 关键分支：尝试解析迭代值
        iteration = int(raw)  # 关键变量：解析迭代数字
    except ValueError as exc:  # 关键分支：非法数值
        raise ValueError(f"Invalid main iteration value: {raw!r} in {MAIN_ITERATION_FILE}") from exc
    if iteration < 0:  # 关键分支：负值非法
        raise ValueError(f"Invalid main iteration value: {iteration} in {MAIN_ITERATION_FILE} (must be >= 0)")
    return iteration


def _save_main_iteration(iteration: int) -> None:
    if iteration < 0:  # 关键分支：负值非法
        raise ValueError(f"Invalid iteration: {iteration} (must be >= 0)")
    MAIN_ITERATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(MAIN_ITERATION_FILE, f"{iteration}\n")  # 关键变量：持久化迭代号


_TEMPORARY_HINTS = (
    "timeout",
    "timed out",
    "rate limit",
    "429",
    "502",
    "503",
    "504",
    "overloaded",
    "temporar",
    "network",
    "connection reset",
    "connection refused",
    "econnreset",
    "econnrefused",
)


def _is_temporary_codex_failure(output: str) -> bool:
    lowered = output.lower()
    return any(hint in lowered for hint in _TEMPORARY_HINTS)


def _run_codex_exec(
    *,
    prompt: str,
    output_last_message: Path,
    sandbox_mode: str,
    approval_policy: str,
    label: str,
    control: RunControl | None = None,
    resume_session_id: str | None = None,
    max_empty_last_message_retries: int = 3,
) -> CodexRunResult:
    """
    以非交互方式调用 `codex exec`：
    - prompt 通过 stdin 传递（使用 '-'），避免命令行长度与转义问题
    - 通过 `--output-last-message` 将模型最后一条消息落盘到指定文件
    """
    if not output_last_message.parent.is_dir():  # 关键分支：输出目录必须存在
        raise FileNotFoundError(f"Missing required directory: {output_last_message.parent}")
    if max_empty_last_message_retries < 0:  # 关键分支：重试次数非法
        raise ValueError("max_empty_last_message_retries must be >= 0")

    retries_left = max_empty_last_message_retries
    active_resume_session_id = resume_session_id
    retry_notice = (
        f"上次 {label} 输出为空，导致 `{output_last_message}` 无内容。"
        "你必须输出完整最终结果作为最后一条消息（严格按提示词格式），"
        "否则流程将终止。禁止再次省略或空输出。"
    )
    while True:
        if control is not None and control.cancel_event.is_set():  # 关键分支：运行前检查中断
            raise UserInterrupted("User interrupted before starting codex exec")

        attempt_prompt = prompt if retries_left == max_empty_last_message_retries else f"{prompt}\n\n{retry_notice}"
        cmd: list[str] = [  # 关键变量：codex 命令参数
            "codex",
            "-s",
            sandbox_mode,
            "-a",
            approval_policy,
            "exec",
            "--color",
            "never",
            "-C",
            str(PROJECT_ROOT),
            "--output-last-message",
            str(output_last_message),
        ]
        if active_resume_session_id is None:  # 关键分支：新会话直接读 stdin
            cmd.append("-")
        else:  # 关键分支：恢复会话模式
            _validate_session_id(active_resume_session_id)
            cmd.extend(["resume", active_resume_session_id, "-"])  # 关键变量：恢复会话参数

        ORCHESTRATOR_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ORCHESTRATOR_LOG_FILE.open("a", encoding="utf-8") as log_file:
            banner = f"\n----- codex exec ({label}) -----\n"
            print(banner, flush=True)
            log_file.write(banner)
            log_file.flush()

            line_prefix = f"{label.lower()}: "  # 关键变量：输出前缀
            proc = subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if control is not None:  # 关键分支：记录当前进程
                control.set_current_proc(proc)  # 关键变量：登记当前进程

            try:  # 关键分支：执行并收集输出
                assert proc.stdin is not None
                proc.stdin.write(attempt_prompt)  # 关键变量：写入提示词
                proc.stdin.close()

                combined_output: list[str] = []  # 关键变量：合并输出缓存（用于失败诊断）
                session_id: str | None = None  # 关键变量：从输出中抓取会话 id
                session_id_re = re.compile(
                    r"\bsession id:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
                    re.IGNORECASE,
                )
                assert proc.stdout is not None
                for line in proc.stdout:  # 关键分支：逐行读取输出
                    combined_output.append(line)
                    if session_id is None:  # 关键分支：仅首次匹配会话 id
                        match = session_id_re.search(line)
                        if match:  # 关键分支：命中会话 id
                            session_id = match.group(1)
                    prefixed = f"{line_prefix}{line}"  # 关键变量：日志前缀化
                    sys.stdout.write(prefixed)
                    log_file.write(prefixed)
                    log_file.flush()
                    sys.stdout.flush()
                    if control is not None and control.cancel_event.is_set() and proc.poll() is None:  # 关键分支：中断时终止进程
                        proc.terminate()

                return_code = proc.wait()  # 关键变量：进程退出码
            finally:
                if control is not None:  # 关键分支：清理进程引用
                    control.set_current_proc(None)  # 关键变量：清理进程引用

            if return_code != 0:  # 关键分支：非零退出码
                if control is not None and control.cancel_event.is_set():  # 关键分支：中断导致
                    raise UserInterrupted(f"User interrupted during {label} run")
                combined_text = "".join(combined_output)
                err_cls = TemporaryError if _is_temporary_codex_failure(combined_text) else PermanentError
                raise err_cls(
                    "codex exec failed\n"
                    f"cmd: {' '.join(cmd)}\n"
                    f"return_code: {return_code}\n"
                    f"combined_output:\n{combined_text}\n"
                )

        if active_resume_session_id is not None and session_id is not None and session_id != active_resume_session_id:
            raise RuntimeError(
                "Codex resumed session_id mismatch: "
                f"expected {active_resume_session_id!r}, got {session_id!r}"
            )
        if active_resume_session_id is None and session_id is not None:
            active_resume_session_id = session_id
        _require_file(output_last_message)  # 关键分支：输出文件必须存在
        last_message = _read_text(output_last_message).strip()  # 关键变量：最后一条消息

        # 诊断信息：记录 prompt 长度与输出状态
        prompt_char_count = len(attempt_prompt)
        prompt_line_count = attempt_prompt.count('\n') + 1
        output_char_count = len(last_message)
        diag_msg = (
            f"orchestrator: {label} diag: "
            f"prompt_chars={prompt_char_count}, prompt_lines={prompt_line_count}, "
            f"output_chars={output_char_count}, session_id={session_id or 'none'}\n"
        )
        _append_log_line(diag_msg)

        if not last_message:  # 关键分支：空输出则重试或失败
            empty_diag = (
                f"orchestrator: {label} EMPTY OUTPUT detected - "
                f"prompt_chars={prompt_char_count}, prompt_lines={prompt_line_count}, "
                f"retries_left={retries_left}\n"
            )
            _append_log_line(empty_diag)
            print(empty_diag, end="", flush=True)

            if retries_left <= 0:
                raise TemporaryError(
                    f"Empty last message: {output_last_message}\n"
                    f"Diagnostics: prompt_chars={prompt_char_count}, prompt_lines={prompt_line_count}, "
                    f"session_id={session_id or 'none'}"
                )
            if active_resume_session_id is None:
                raise PermanentError(
                    f"Empty last message: {output_last_message} (missing session_id for resume)"
                )
            retry_msg = (
                f"orchestrator: {label} empty last message; retrying "
                f"({max_empty_last_message_retries - retries_left + 1}/{max_empty_last_message_retries})\n"
            )
            _append_log_line(retry_msg)
            print(retry_msg, end="", flush=True)
            retries_left -= 1
            continue
        return {"last_message": last_message, "session_id": session_id}
