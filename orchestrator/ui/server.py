from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from threading import Thread
from urllib.parse import parse_qs, unquote, urlparse

from ..codex_runner import _clear_saved_main_state
from ..config import ORCHESTRATOR_LOG_FILE, PROJECT_ROOT, RESUME_STATE_FILE, _list_editable_md_files, _resolve_editable_md_path
from ..documents import add_doc_to_finish_review_config, delete_uploaded_doc, get_finish_review_docs, list_uploaded_docs, remove_doc_from_finish_review_config, store_uploaded_doc
from ..log_summary import load_log_summary_config, save_log_summary_config, summarize_logs
from ..progress import get_progress_info
from ..file_ops import _append_log_line, _append_new_task_goal_to_history, _append_user_message_to_history, _reset_dev_plan_file, _reset_project_history_file
from ..state import RunControl, UiRuntime, UiStateStore
from ..types import UserDecisionResponse
from ..workflow import _reset_workflow_state

UI_DIST_DIR = Path(__file__).resolve().parent / "frontend" / "dist"  # 关键变量：UI 构建产物目录
UI_INDEX_FILE = UI_DIST_DIR / "index.html"  # 关键变量：UI 入口文件
UI_MIME_TYPES = {  # 关键变量：静态资源类型映射
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def _read_tail_text(*, path: Path, tail_lines: int, block_size: int = 8192) -> tuple[str, int]:
    """
    读取文件末尾的 N 行（用于 UI 初始加载/清空后跳到末尾）。
    返回：(text, end_offset)；其中 end_offset 是文件末尾偏移，可用于后续增量拉取。
    """
    if tail_lines < 0:
        raise ValueError("tail_lines must be >= 0")
    if block_size <= 0:
        raise ValueError("block_size must be > 0")

    with path.open("rb") as f:
        f.seek(0, 2)
        end = f.tell()
        if tail_lines == 0 or end == 0:
            return "", end

        chunks: list[bytes] = []
        pos = end
        lines_found = 0
        # 从文件尾部向前读取，直到拿到足够的换行符。
        while pos > 0 and lines_found <= tail_lines:
            read_size = block_size if pos >= block_size else pos
            pos -= read_size
            f.seek(pos)
            chunk = f.read(read_size)
            chunks.append(chunk)
            lines_found += chunk.count(b"\n")

        data = b"".join(reversed(chunks))
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines(True)
        if len(lines) > tail_lines:
            text = "".join(lines[-tail_lines:])
        return text, end


def _start_ui_server(
    *,
    host: str,
    port: int,
    state: UiStateStore,
    decision_queue: Queue[UserDecisionResponse],
    control: RunControl,
) -> UiRuntime:
    ORCHESTRATOR_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)  # 关键变量：确保日志目录
    ORCHESTRATOR_LOG_FILE.touch(exist_ok=True)  # 关键变量：确保日志文件存在
    if not UI_INDEX_FILE.exists():  # 关键分支：UI 构建产物缺失直接失败
        raise FileNotFoundError(f"UI dist missing: {UI_INDEX_FILE}")

    def read_json_body(handler: BaseHTTPRequestHandler) -> dict:
        length_str = handler.headers.get("Content-Length")  # 关键变量：请求体长度
        if length_str is None:  # 关键分支：缺长度头直接失败
            raise ValueError("Missing Content-Length")
        length = int(length_str)  # 关键变量：请求体长度数值
        raw = handler.rfile.read(length)  # 关键变量：原始请求体
        return json.loads(raw.decode("utf-8"))

    def send_json(handler: BaseHTTPRequestHandler, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")  # 关键变量：JSON 响应体
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def send_text(handler: BaseHTTPRequestHandler, body: str, status: int = 200, content_type: str = "text/plain") -> None:
        data = body.encode("utf-8")  # 关键变量：文本响应体
        handler.send_response(status)
        handler.send_header("Content-Type", f"{content_type}; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def send_bytes(
        handler: BaseHTTPRequestHandler, data: bytes, status: int = 200, content_type: str = "application/octet-stream"
    ) -> None:
        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def _guess_content_type(path: Path) -> str:
        return UI_MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")

    def _send_static_file(handler: BaseHTTPRequestHandler, path: Path) -> None:
        data = path.read_bytes()  # 关键变量：静态资源内容
        send_bytes(handler, data, content_type=_guess_content_type(path))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":  # 关键分支：首页返回 UI 入口
                return _send_static_file(self, UI_INDEX_FILE)
            if parsed.path.startswith("/assets/"):  # 关键分支：静态资源
                rel_path = parsed.path.lstrip("/")
                if ".." in rel_path:
                    return send_text(self, "not found", status=404)
                asset_path = UI_DIST_DIR / rel_path
                if not asset_path.exists() or not asset_path.is_file():
                    return send_text(self, "not found", status=404)
                return _send_static_file(self, asset_path)
            if parsed.path == "/api/state":  # 关键分支：状态查询
                payload = state.get()  # 关键变量：当前状态快照
                payload["run_locked"] = control.is_busy()  # 关键变量：运行锁
                payload["resume_available"] = RESUME_STATE_FILE.exists()  # 关键变量：是否存在续跑状态
                return send_json(self, payload)
            if parsed.path == "/api/md_files":  # 关键分支：可编辑 md 列表
                return send_json(self, _list_editable_md_files())
            if parsed.path == "/api/uploaded_docs":  # 关键分支：已上传文档列表
                return send_json(self, list_uploaded_docs())
            if parsed.path == "/api/finish_review_docs":  # 关键分支：验收文档列表
                try:
                    docs = get_finish_review_docs()
                except Exception as exc:  # noqa: BLE001
                    return send_json(self, {"error": str(exc)}, status=500)
                return send_json(self, {"docs": docs})
            if parsed.path == "/api/progress":  # 关键分支：进度查询
                try:
                    progress = get_progress_info()
                except Exception as exc:  # noqa: BLE001
                    return send_json(self, {"error": str(exc)}, status=500)
                return send_json(self, progress)
            if parsed.path == "/api/log_summary/config":  # 关键分支：日志摘要配置读取
                try:
                    config = load_log_summary_config()
                except FileNotFoundError as exc:
                    return send_json(self, {"error": str(exc)}, status=404)
                except Exception as exc:  # noqa: BLE001
                    return send_json(self, {"error": str(exc)}, status=400)
                return send_json(
                    self,
                    {
                        "base_url": config.base_url,
                        "api_key": config.api_key,
                        "model": config.model,
                    },
                )
            if parsed.path == "/api/file":  # 关键分支：读取指定文件
                qs = parse_qs(parsed.query)
                path_raw = (qs.get("path") or [""])[0]  # 关键变量：请求路径
                try:  # 关键分支：解析并校验路径
                    path = _resolve_editable_md_path(path_raw)
                except Exception as exc:  # noqa: BLE001  # 关键分支：路径非法
                    return send_json(self, {"error": str(exc)}, status=400)
                if not path.exists():  # 关键分支：文件不存在
                    return send_json(self, {"error": "file not found"}, status=404)
                content = path.read_text(encoding="utf-8")  # 关键变量：文件内容
                return send_json(
                    self,
                    {"path": path.relative_to(PROJECT_ROOT).as_posix(), "content": content},
                )
            if parsed.path == "/api/log":  # 关键分支：日志拉取
                qs = parse_qs(parsed.query)
                tail_raw = (qs.get("tail_lines") or [""])[0]  # 关键变量：tail 行数
                if tail_raw.strip() != "":
                    try:  # 关键分支：解析 tail 行数
                        tail_lines = int(tail_raw)  # 关键变量：tail 行数
                    except ValueError:  # 关键分支：tail 行数非法
                        return send_json(self, {"error": "tail_lines must be an integer"}, status=400)
                    if tail_lines < 0:  # 关键分支：tail 行数非法
                        return send_json(self, {"error": "tail_lines must be >= 0"}, status=400)
                    text, next_offset = _read_tail_text(path=ORCHESTRATOR_LOG_FILE, tail_lines=tail_lines)
                    return send_json(self, {"data": text, "next_offset": next_offset})

                offset_raw = (qs.get("offset") or ["0"])[0]  # 关键变量：日志偏移
                try:  # 关键分支：解析偏移值
                    offset = int(offset_raw)  # 关键变量：偏移值
                except ValueError:  # 关键分支：偏移值非法
                    return send_json(self, {"error": "offset must be an integer"}, status=400)
                with ORCHESTRATOR_LOG_FILE.open("rb") as f:
                    f.seek(offset)
                    chunk = f.read(65536)  # 关键变量：日志块
                    next_offset = f.tell()  # 关键变量：下次偏移
                return send_json(
                    self,
                    {"data": chunk.decode("utf-8", errors="replace"), "next_offset": next_offset},
                )
            return send_text(self, "not found", status=404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/log_summary/config":  # 关键分支：日志摘要配置写入
                try:
                    payload = read_json_body(self)
                    config = save_log_summary_config(payload)
                except Exception as exc:  # noqa: BLE001
                    return send_json(self, {"error": str(exc)}, status=400)
                return send_json(
                    self,
                    {
                        "base_url": config.base_url,
                        "api_key": config.api_key,
                        "model": config.model,
                    },
                )
            if parsed.path == "/api/log_summary":  # 关键分支：日志摘要生成
                try:
                    payload = read_json_body(self)
                    logs = payload.get("logs")
                    if not isinstance(logs, str):
                        raise ValueError("logs must be a string")
                    config = load_log_summary_config()
                    summary = summarize_logs(logs=logs, config=config)
                except Exception as exc:  # noqa: BLE001
                    return send_json(self, {"error": str(exc)}, status=400)
                return send_json(self, {"summary": summary})
            if parsed.path == "/api/control/start":  # 关键分支：启动运行
                if not control.request_start_with_options(new_task=False, task_goal=""):  # 关键分支：已有运行/请求
                    return send_json(self, {"error": "already running or start pending"}, status=409)
                state.update(phase="starting", current_agent="orchestrator")  # 关键变量：UI 进入启动态
                _append_log_line("orchestrator: start_requested\n")
                return send_json(self, {"ok": True})
            if parsed.path == "/api/control/new_task":  # 关键分支：新任务启动
                try:  # 关键分支：解析请求体
                    payload = read_json_body(self)  # 关键变量：请求体
                except Exception as exc:  # noqa: BLE001  # 关键分支：请求体解析失败
                    return send_json(self, {"error": str(exc)}, status=400)
                task_goal = payload.get("task_goal")  # 关键变量：任务目标
                if not isinstance(task_goal, str) or not task_goal.strip():  # 关键分支：目标为空
                    return send_json(self, {"error": "task_goal is required"}, status=400)
                goal = task_goal.strip()  # 关键变量：清洗后的目标
                reset_dev_plan = bool(payload.get("reset_dev_plan", False))  # 关键变量：是否重置 dev_plan
                reset_project_history = bool(payload.get("reset_project_history", False))  # 关键变量：是否重置 project_history

                def before_enqueue() -> None:
                    if reset_project_history:  # 关键分支：重置 project_history
                        _reset_project_history_file()
                    _append_new_task_goal_to_history(goal=goal)  # 关键变量：记录新任务目标
                    _clear_saved_main_state()  # 关键变量：清理会话状态
                    if reset_dev_plan:  # 关键分支：重置 dev_plan
                        _reset_dev_plan_file()

                try:  # 关键分支：启动前回调与排队
                    ok = control.request_start_with_options(new_task=True, task_goal=goal, before_enqueue=before_enqueue)  # 关键变量：发起新任务
                except Exception as exc:  # noqa: BLE001  # 关键分支：启动失败
                    return send_json(self, {"error": str(exc)}, status=500)
                if not ok:  # 关键分支：已有运行/请求
                    return send_json(self, {"error": "already running or start pending"}, status=409)
                state.update(phase="starting", current_agent="orchestrator", main_session_id=None, iteration=0)  # 关键变量：UI 重置状态
                _append_log_line("orchestrator: new_task_start_requested\n")
                _append_log_line(f"orchestrator: new_task_goal_appended len={len(goal)}\n")
                if reset_dev_plan:
                    _append_log_line("orchestrator: dev_plan reset by user\n")
                if reset_project_history:
                    _append_log_line("orchestrator: project_history reset by user\n")
                return send_json(self, {"ok": True})
            if parsed.path == "/api/control/interrupt":  # 关键分支：中断运行
                control.interrupt()  # 关键变量：发出中断信号
                state.update(phase="interrupting")  # 关键变量：UI 进入中断态
                _append_log_line("orchestrator: interrupt_requested\n")
                return send_json(self, {"ok": True})
            if parsed.path == "/api/control/reset":  # 关键分支：重置状态
                if control.is_busy():  # 关键分支：运行中拒绝重置
                    return send_json(self, {"error": "running or start pending"}, status=409)
                try:  # 关键分支：执行重置
                    _reset_workflow_state()  # 关键变量：重置工作流状态
                    ORCHESTRATOR_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)  # 关键变量：重置后重建日志目录
                    ORCHESTRATOR_LOG_FILE.touch(exist_ok=True)  # 关键变量：重置后确保日志文件存在
                except Exception as exc:  # noqa: BLE001  # 关键分支：重置失败
                    return send_json(self, {"error": str(exc)}, status=500)
                state.update(
                    phase="idle",
                    current_agent="",
                    main_session_id=None,
                    iteration=0,
                    last_iteration_summary=None,
                    last_summary_path=None,
                    summary_history=None,
                    last_main_decision=None,
                    awaiting_user_decision=None,
                    last_error=None,
                )  # 关键变量：UI 重置状态
                return send_json(self, {"ok": True})

            if parsed.path == "/api/user_message":  # 关键分支：用户消息追加
                try:  # 关键分支：解析请求体
                    payload = read_json_body(self)  # 关键变量：请求体
                except Exception as exc:  # noqa: BLE001  # 关键分支：解析失败
                    return send_json(self, {"error": str(exc)}, status=400)
                message = payload.get("message")  # 关键变量：用户消息
                if not isinstance(message, str) or not message.strip():  # 关键分支：消息为空
                    return send_json(self, {"error": "message is required"}, status=400)
                current_iteration = int(state.get().get("iteration", 0))  # 关键变量：当前迭代
                _append_user_message_to_history(iteration=current_iteration, message=message)  # 关键变量：追加历史
                _append_log_line(f"user: {message.strip()}\n")
                return send_json(self, {"ok": True})

            if parsed.path == "/api/user_decision":  # 关键分支：用户抉择提交
                try:  # 关键分支：解析请求体
                    payload = read_json_body(self)  # 关键变量：请求体
                except Exception as exc:  # noqa: BLE001  # 关键分支：解析失败
                    return send_json(self, {"error": str(exc)}, status=400)
                option_id = payload.get("option_id")  # 关键变量：选项 id
                comment = payload.get("comment", "")  # 关键变量：用户备注
                if not isinstance(option_id, str) or not option_id.strip():  # 关键分支：选项为空
                    return send_json(self, {"error": "option_id is required"}, status=400)
                if not isinstance(comment, str):  # 关键分支：备注必须为字符串
                    return send_json(self, {"error": "comment must be a string"}, status=400)
                decision_queue.put({"option_id": option_id.strip(), "comment": comment})  # 关键变量：投递决策
                _append_log_line(f"user_decision: {option_id.strip()}\n")
                return send_json(self, {"ok": True})

            if parsed.path == "/api/upload_doc":  # 关键分支：上传文档
                try:  # 关键分支：解析请求体
                    payload = read_json_body(self)  # 关键变量：请求体
                except Exception as exc:  # noqa: BLE001
                    return send_json(self, {"error": str(exc)}, status=400)
                filename = payload.get("filename")  # 关键变量：文件名
                content = payload.get("content")  # 关键变量：Base64 内容
                category = payload.get("category")  # 关键变量：分类
                try:  # 关键分支：执行上传
                    stored_path = store_uploaded_doc(filename=filename, content_b64=content, category=category)
                except ValueError as exc:  # 关键分支：输入非法
                    return send_json(self, {"error": str(exc)}, status=400)
                except Exception as exc:  # noqa: BLE001  # 关键分支：服务异常
                    return send_json(self, {"error": str(exc)}, status=500)
                return send_json(self, {"success": True, "path": stored_path})

            if parsed.path == "/api/add_to_finish_review":  # 关键分支：加入验收配置
                try:  # 关键分支：解析请求体
                    payload = read_json_body(self)  # 关键变量：请求体
                except Exception as exc:  # noqa: BLE001
                    return send_json(self, {"error": str(exc)}, status=400)
                doc_path = payload.get("doc_path")  # 关键变量：文档路径
                if not isinstance(doc_path, str) or not doc_path.strip():  # 关键分支：路径为空
                    return send_json(self, {"error": "doc_path is required"}, status=400)
                try:  # 关键分支：写入配置
                    stored = add_doc_to_finish_review_config(doc_path.strip())
                except FileNotFoundError as exc:  # 关键分支：文件不存在
                    return send_json(self, {"error": str(exc)}, status=404)
                except ValueError as exc:  # 关键分支：输入非法
                    return send_json(self, {"error": str(exc)}, status=400)
                except Exception as exc:  # noqa: BLE001
                    return send_json(self, {"error": str(exc)}, status=500)
                return send_json(self, {"success": True, "path": stored})

            if parsed.path == "/api/remove_from_finish_review":  # 关键分支：从验收配置移除
                try:  # 关键分支：解析请求体
                    payload = read_json_body(self)  # 关键变量：请求体
                except Exception as exc:  # noqa: BLE001
                    return send_json(self, {"error": str(exc)}, status=400)
                doc_path = payload.get("doc_path")  # 关键变量：文档路径
                if not isinstance(doc_path, str) or not doc_path.strip():  # 关键分支：路径为空
                    return send_json(self, {"error": "doc_path is required"}, status=400)
                try:  # 关键分支：从配置移除
                    removed = remove_doc_from_finish_review_config(doc_path.strip())
                except ValueError as exc:  # 关键分支：输入非法
                    return send_json(self, {"error": str(exc)}, status=400)
                except Exception as exc:  # noqa: BLE001
                    return send_json(self, {"error": str(exc)}, status=500)
                return send_json(self, {"success": True, "removed": removed})

            if parsed.path == "/api/file":  # 关键分支：保存 md 文件
                if control.is_busy():  # 关键分支：运行中禁止编辑
                    return send_json(
                        self,
                        {"error": "运行中禁止编辑 md 文件，请先 Interrupt"},
                        status=409,
                    )
                try:  # 关键分支：解析请求体
                    payload = read_json_body(self)  # 关键变量：请求体
                except Exception as exc:  # noqa: BLE001  # 关键分支：解析失败
                    return send_json(self, {"error": str(exc)}, status=400)
                path_raw = payload.get("path")  # 关键变量：保存路径
                content = payload.get("content")  # 关键变量：保存内容
                if not isinstance(content, str):  # 关键分支：内容必须是字符串
                    return send_json(self, {"error": "content must be a string"}, status=400)
                try:  # 关键分支：解析并校验路径
                    path = _resolve_editable_md_path(path_raw)  # 关键变量：解析后的路径
                except Exception as exc:  # noqa: BLE001  # 关键分支：路径非法
                    return send_json(self, {"error": str(exc)}, status=400)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")  # 关键变量：落盘内容
                _append_log_line(f"file_saved: {path.relative_to(PROJECT_ROOT).as_posix()}\n")
                return send_json(self, {"ok": True, "path": path.relative_to(PROJECT_ROOT).as_posix()})

            return send_text(self, "not found", status=404)

        def do_DELETE(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/uploaded_docs/"):  # 关键分支：删除已上传文档
                rel_path = parsed.path[len("/api/uploaded_docs/") :]
                rel_path = unquote(rel_path)
                if not rel_path:
                    return send_json(self, {"error": "doc path is required"}, status=400)
                try:
                    delete_uploaded_doc(rel_path)
                except FileNotFoundError as exc:  # 关键分支：文件不存在
                    return send_json(self, {"error": str(exc)}, status=404)
                except ValueError as exc:  # 关键分支：路径非法
                    return send_json(self, {"error": str(exc)}, status=400)
                except Exception as exc:  # noqa: BLE001
                    return send_json(self, {"error": str(exc)}, status=500)
                return send_json(self, {"success": True})
            return send_text(self, "not found", status=404)

    server = ThreadingHTTPServer((host, port), Handler)  # 关键变量：HTTP 服务实例
    thread = Thread(target=server.serve_forever, daemon=True)  # 关键变量：后台线程
    thread.start()
    return UiRuntime(
        host=host,
        port=port,
        state=state,
        decision_queue=decision_queue,
        control=control,
        server=server,
        thread=thread,
    )
