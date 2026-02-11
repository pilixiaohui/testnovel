from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from http.server import ThreadingHTTPServer
from queue import Queue
from threading import Event, RLock, Thread
from typing import Callable

from .types import UiState, UserDecisionResponse


class UiStateStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._version = 0
        self._state: UiState = {
            "phase": "idle",
            "iteration": 0,
            "current_agent": "",
            "version": self._version,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._listeners: list[Callable[[UiState], None]] = []

    def get(self) -> UiState:
        with self._lock:
            return dict(self._state)  # 关键变量：返回状态快照

    def subscribe(self, listener: Callable[[UiState], None]) -> None:
        with self._lock:
            self._listeners.append(listener)  # 关键变量：注册观察者

    def update(self, **kwargs: object) -> None:
        with self._lock:
            for key, value in kwargs.items():  # 关键分支：逐项更新传入字段
                self._state[key] = value  # type: ignore[literal-required]  # 关键变量：更新状态字段
            self._version += 1
            self._state["version"] = self._version  # 关键变量：版本号自增
            self._state["updated_at"] = datetime.now().isoformat(timespec="seconds")  # 关键变量：更新时间戳
            snapshot = dict(self._state)
            listeners = list(self._listeners)
        for listener in listeners:
            listener(dict(snapshot))  # 关键变量：通知观察者


class UserInterrupted(RuntimeError):
    pass


class RunControl:
    def __init__(self) -> None:
        self._lock = RLock()
        self._running = False  # 关键变量：运行态
        self._start_pending = False  # 关键变量：启动中
        self._current_proc: subprocess.Popen[str] | None = None  # 关键变量：当前子进程
        self._start_queue: Queue[tuple[bool, str]] = Queue()  # 关键变量：启动请求队列 (new_task, task_goal)
        self.cancel_event = Event()  # 关键变量：中断信号

    def is_running(self) -> bool:
        with self._lock:
            return self._running  # 关键变量：是否运行中

    def is_busy(self) -> bool:
        with self._lock:
            return self._running or self._start_pending  # 关键变量：是否忙碌（运行或等待启动）

    def request_start(self) -> bool:
        return self.request_start_with_options(new_task=False)  # 关键变量：默认非新任务启动

    def request_start_with_options(
        self,
        *,
        new_task: bool,
        task_goal: str = "",
        before_enqueue: Callable[[], None] | None = None,
    ) -> bool:
        with self._lock:
            if self._running or self._start_pending:  # 关键分支：忙碌时拒绝启动
                return False
            if before_enqueue is not None:  # 关键分支：启动前回调
                before_enqueue()
            self._start_pending = True  # 关键变量：标记启动中
            self.cancel_event.clear()  # 关键变量：清除中断标志
            self._start_queue.put((new_task, task_goal))  # 关键变量：入队启动请求
            return True

    def wait_for_start(self) -> tuple[bool, str]:
        new_task, task_goal = self._start_queue.get()  # 关键变量：阻塞等待启动请求
        with self._lock:
            self._start_pending = False  # 关键变量：清理启动中
            self._running = True  # 关键变量：标记运行中
        return new_task, task_goal

    def mark_finished(self) -> None:
        with self._lock:
            self._running = False  # 关键变量：结束运行
            self._current_proc = None  # 关键变量：清理进程引用

    def set_current_proc(self, proc: subprocess.Popen[str] | None) -> None:
        with self._lock:
            self._current_proc = proc  # 关键变量：登记当前子进程

    def interrupt(self) -> None:
        self.cancel_event.set()  # 关键变量：标记中断
        with self._lock:
            proc = self._current_proc  # 关键变量：当前进程快照
        if proc is not None and proc.poll() is None:  # 关键分支：仅在运行中终止
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


class SSEManager:
    """SSE 连接管理器，支持多客户端广播"""

    def __init__(self, state_store: UiStateStore) -> None:
        self._lock = RLock()
        self._clients: dict[int, Queue[dict]] = {}
        self._next_client_id = 0
        self._log_offsets: dict[int, int] = {}
        state_store.subscribe(self._on_state_change)

    def register_client(self) -> tuple[int, Queue[dict]]:
        with self._lock:
            client_id = self._next_client_id
            self._next_client_id += 1
            queue: Queue[dict] = Queue()
            self._clients[client_id] = queue
            self._log_offsets[client_id] = 0
            return client_id, queue

    def unregister_client(self, client_id: int) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            self._log_offsets.pop(client_id, None)

    def _on_state_change(self, state: UiState) -> None:
        event = {"type": "state", "data": state}
        with self._lock:
            for queue in self._clients.values():
                try:
                    queue.put_nowait(event)
                except Exception:
                    pass

    def push_log_event(self, client_id: int, text: str, next_offset: int) -> None:
        with self._lock:
            if client_id in self._clients:
                self._clients[client_id].put_nowait({
                    "type": "log",
                    "data": {"text": text, "next_offset": next_offset}
                })
                self._log_offsets[client_id] = next_offset

    def get_log_offset(self, client_id: int) -> int:
        with self._lock:
            return self._log_offsets.get(client_id, 0)

    def set_log_offset(self, client_id: int, offset: int) -> None:
        with self._lock:
            self._log_offsets[client_id] = offset

    def get_client_ids(self) -> list[int]:
        with self._lock:
            return list(self._clients.keys())


@dataclass(frozen=True)
class UiRuntime:
    host: str
    port: int
    state: UiStateStore
    decision_queue: Queue[UserDecisionResponse]
    control: RunControl
    server: ThreadingHTTPServer
    thread: Thread
