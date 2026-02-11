from __future__ import annotations

import argparse
import json
from queue import Queue

from .codex_runner import _load_saved_main_iteration, _load_saved_main_session_id
from .errors import PermanentError, TemporaryError
from .file_ops import _append_log_line, _append_new_task_goal_to_history, _rel_path
from .config import (
    REPORT_ITERATION_SUMMARY_FILE,
    REPORT_ITERATION_SUMMARY_HISTORY_FILE,
    MAX_ITERATIONS,
)
from .summary import _load_iteration_summary_history
from .state import RunControl, UiStateStore, UserInterrupted
from .types import UserDecisionResponse
from .ui.server import _start_ui_server
from .workflow import _preflight, workflow_loop, _shutdown_supervisor


def main() -> int:
    parser = argparse.ArgumentParser(description="Blackboard-style Codex multi-agent orchestrator")  # 关键变量：CLI 解析器
    parser.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    parser.add_argument("--sandbox-mode", default="workspace-write")
    parser.add_argument("--approval-policy", default="on-request")
    parser.add_argument("--ui", action="store_true", help="Start a local web UI for progress & interaction.")
    parser.add_argument("--ui-host", default="127.0.0.1")
    parser.add_argument("--ui-port", type=int, default=8766)
    parser.add_argument(
        "--new-task",
        action="store_true",
        help="Start a new MAIN session (ignore any saved session id).",
    )
    parser.add_argument(
        "--task",
        default="",
        help="Optional top-level task hint for MAIN; source of truth is still memory/global_context.md",
    )
    args = parser.parse_args()  # 关键变量：解析后的参数

    if not args.ui:  # 关键分支：CLI 模式（无 UI）
        if args.new_task and args.task.strip():  # 关键分支：新任务时写入目标
            _append_new_task_goal_to_history(goal=args.task.strip())
        workflow_loop(
            max_iterations=args.max_iterations,
            sandbox_mode=args.sandbox_mode,
            approval_policy=args.approval_policy,
            user_task=args.task,
            new_task=args.new_task,
            ui=None,
            control=None,
        )
        return 0

    _preflight()  # 关键变量：UI 模式启动前校验
    state = UiStateStore()  # 关键变量：UI 状态存储
    decision_queue: Queue[UserDecisionResponse] = Queue()  # 关键变量：用户决策队列
    control = RunControl()  # 关键变量：运行控制器
    ui_runtime = _start_ui_server(
        host=args.ui_host,
        port=args.ui_port,
        state=state,
        decision_queue=decision_queue,
        control=control,
    )
    url = f"http://{ui_runtime.host}:{ui_runtime.port}/"  # 关键变量：UI 地址
    print(f"UI started: {url}")
    _append_log_line(f"ui: {url}\n")
    ui_runtime.state.update(
        phase="idle",
        current_agent="",
        main_session_id=_load_saved_main_session_id(),
        iteration=_load_saved_main_iteration(),
    )

    if REPORT_ITERATION_SUMMARY_FILE.exists():  # 关键分支：存在摘要文件则恢复到 UI 状态
        raw_summary = REPORT_ITERATION_SUMMARY_FILE.read_text(encoding="utf-8").strip()
        if not raw_summary:  # 关键分支：空摘要文件直接失败
            raise ValueError(f"摘要文件为空：{_rel_path(REPORT_ITERATION_SUMMARY_FILE)}")
        try:  # 关键分支：解析摘要 JSON
            summary_payload = json.loads(raw_summary)
        except json.JSONDecodeError as exc:  # 关键分支：非法 JSON 直接失败
            raise ValueError(
                f"摘要 JSON 解析失败：{_rel_path(REPORT_ITERATION_SUMMARY_FILE)}: {exc}"
            ) from exc
        if not isinstance(summary_payload, dict):  # 关键分支：必须为对象
            raise ValueError("摘要 JSON 必须是对象")
        ui_runtime.state.update(
            last_iteration_summary=summary_payload,
            last_summary_path=_rel_path(REPORT_ITERATION_SUMMARY_FILE),
        )

    if REPORT_ITERATION_SUMMARY_HISTORY_FILE.exists():  # 关键分支：存在摘要历史则恢复到 UI 状态
        summary_history = _load_iteration_summary_history(REPORT_ITERATION_SUMMARY_HISTORY_FILE)
        ui_runtime.state.update(summary_history=summary_history)

    try:  # 关键分支：UI 主循环入口
        force_new_task_once = bool(args.new_task)  # 关键变量：首次强制新任务标记
        while True:  # 关键分支：持续等待启动请求
            requested_new_task, ui_task_goal = control.wait_for_start()  # 关键变量：阻塞等待启动请求
            run_new_task = bool(requested_new_task or force_new_task_once)  # 关键变量：是否新任务
            # 确定本次运行的 user_task：优先使用前端传来的 task_goal，否则使用命令行参数
            effective_user_task = ui_task_goal if ui_task_goal else args.task
            force_new_task_once = False  # 关键变量：仅强制一次
            if run_new_task:  # 关键分支：新任务需要重置状态
                ui_runtime.state.update(
                    main_session_id=None,
                    iteration=0,
                    last_iteration_summary=None,
                    last_summary_path=None,
                    summary_history=None,
                )  # 关键变量：重置 UI 状态
                if args.task.strip() and not requested_new_task:  # 关键分支：CLI 任务提示补写
                    _append_new_task_goal_to_history(goal=args.task.strip())
            ui_runtime.state.update(phase="running", current_agent="orchestrator", awaiting_user_decision=None, last_error=None)  # 关键变量：UI 运行态
            _append_log_line("orchestrator: run_started\n")
            try:  # 关键分支：执行编排主循环
                workflow_loop(
                    max_iterations=args.max_iterations,
                    sandbox_mode=args.sandbox_mode,
                    approval_policy=args.approval_policy,
                    user_task=effective_user_task,
                    new_task=run_new_task,
                    ui=ui_runtime,
                    control=control,
                )
            except UserInterrupted:  # 关键分支：用户中断
                ui_runtime.state.update(phase="idle", current_agent="")
                _append_log_line("orchestrator: interrupted\n")
            except TemporaryError as exc:  # 关键分支：临时故障
                ui_runtime.state.update(
                    phase="error",
                    current_agent="orchestrator",
                    last_error=f"TEMPORARY: {exc}",
                )
                _append_log_line(f"orchestrator: temporary_error: {exc}\n")
            except PermanentError as exc:  # 关键分支：永久故障
                ui_runtime.state.update(
                    phase="error",
                    current_agent="orchestrator",
                    last_error=f"PERMANENT: {exc}",
                )
                _append_log_line(f"orchestrator: permanent_error: {exc}\n")
                raise
            except Exception as exc:  # noqa: BLE001  # 关键分支：异常进入错误态
                ui_runtime.state.update(phase="error", current_agent="orchestrator", last_error=str(exc))
                _append_log_line(f"orchestrator: error: {exc}\n")
                raise
            finally:
                control.mark_finished()  # 关键变量：清理运行状态
    except KeyboardInterrupt:  # 关键分支：UI 模式手动退出
        _append_log_line("orchestrator: ui_shutdown\n")
    finally:
        _shutdown_supervisor()  # 关键变量：等待后台监督任务完成
        ui_runtime.server.shutdown()  # 关键变量：关闭 UI 服务
        ui_runtime.server.server_close()  # 关键变量：释放端口
    return 0
