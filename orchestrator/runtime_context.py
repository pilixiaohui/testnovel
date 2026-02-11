from __future__ import annotations

import json
import os

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .config import PROJECT_ENV_FILE
from .file_ops import _read_text, _require_file


@dataclass(frozen=True)
class RuntimeContext:
    project_root: Path
    agent_root: Path
    code_root: Path
    frontend_root: Path
    python_bin: Path
    backend_base_url: str
    frontend_url: str
    frontend_dev_port: int
    service_startup_wait_seconds: float
    test_timeout_seconds: dict[str, float]
    environment: dict[str, str]
    raw_payload: dict[str, object]


def _require_object(payload: dict[str, object], key: str, *, source: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(f"{source} missing object field: {key}")
    return value


def _require_non_empty_str(payload: dict[str, object], key: str, *, source: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{source} missing non-empty string field: {key}")
    return value.strip()


def _require_positive_int(payload: dict[str, object], key: str, *, source: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or value <= 0:
        raise RuntimeError(f"{source} missing positive integer field: {key}")
    return value


def _require_positive_number(payload: dict[str, object], key: str, *, source: str) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or float(value) <= 0:
        raise RuntimeError(f"{source} missing positive number field: {key}")
    return float(value)


def _parse_absolute_path(value: str, *, field: str, project_root: Path | None = None) -> Path:
    raw = Path(value)
    if not raw.is_absolute():
        raise RuntimeError(f"project_env.json field {field} must be absolute path")
    resolved = raw.resolve()
    if project_root is not None:
        try:
            resolved.relative_to(project_root)
        except ValueError as exc:
            raise RuntimeError(f"project_env.json field {field} must stay under project.root") from exc
    return resolved


def _derive_agent_root(*, project_root: Path, code_root: Path, frontend_root: Path) -> Path:
    """推导子代理业务工作根目录。

    规则：取 code_root 与 frontend_root 的共同祖先目录，要求位于 project_root 内。
    """
    shared_root = Path(os.path.commonpath([code_root.as_posix(), frontend_root.as_posix()])).resolve()
    if not shared_root.is_absolute():
        raise RuntimeError("derived agent_root must be absolute path")
    if not shared_root.is_dir():
        raise RuntimeError("derived agent_root must be an existing directory")
    try:
        shared_root.relative_to(project_root)
    except ValueError as exc:
        raise RuntimeError("derived agent_root must stay under project.root") from exc
    return shared_root


def _validate_http_url(url: str, *, field: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(f"project_env.json field {field} must be valid http/https URL")
    return url.rstrip("/")


def _build_test_timeout_seconds(test_execution: dict[str, object]) -> dict[str, float]:
    timeout_source = "project_env.json.test_execution.test_timeout_seconds"
    timeouts = _require_object(test_execution, "test_timeout_seconds", source="project_env.json.test_execution")
    unit_timeout = _require_positive_number(timeouts, "unit", source=timeout_source)
    integration_timeout = _require_positive_number(timeouts, "integration", source=timeout_source)
    e2e_timeout = _require_positive_number(timeouts, "e2e", source=timeout_source)
    return {
        "unit": unit_timeout,
        "integration": integration_timeout,
        "e2e": e2e_timeout,
    }


def _build_environment_variables(payload: dict[str, object]) -> dict[str, str]:
    raw_environment = payload.get("environment")
    if raw_environment is None:
        return {}
    if not isinstance(raw_environment, dict):
        raise RuntimeError("project_env.json field environment must be an object")

    env: dict[str, str] = {}
    for key, value in raw_environment.items():
        if not isinstance(key, str) or not key.strip():
            raise RuntimeError("project_env.json environment key must be non-empty string")
        if not isinstance(value, str):
            raise RuntimeError(f"project_env.json environment value for {key!r} must be string")
        env[key] = value
    return env


def load_runtime_context(*, project_env_file: Path | None = None) -> RuntimeContext:
    """统一加载运行时环境配置并执行强校验。"""
    env_file = project_env_file or PROJECT_ENV_FILE
    _require_file(env_file)

    try:
        payload = json.loads(_read_text(env_file))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"project_env.json is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("project_env.json must be an object")

    project = _require_object(payload, "project", source="project_env.json")
    python = _require_object(payload, "python", source="project_env.json")
    test_execution = _require_object(payload, "test_execution", source="project_env.json")

    project_root_str = _require_non_empty_str(project, "root", source="project_env.json.project")
    project_root = Path(project_root_str).resolve()
    if not project_root.is_absolute():
        raise RuntimeError("project_env.json field project.root must be absolute path")
    if not project_root.is_dir():
        raise RuntimeError("project_env.json field project.root must be an existing directory")

    code_root = _parse_absolute_path(
        _require_non_empty_str(project, "code_root", source="project_env.json.project"),
        field="project.code_root",
        project_root=project_root,
    )
    frontend_root = _parse_absolute_path(
        _require_non_empty_str(project, "frontend_root", source="project_env.json.project"),
        field="project.frontend_root",
        project_root=project_root,
    )
    python_bin = _parse_absolute_path(
        _require_non_empty_str(python, "python_bin", source="project_env.json.python"),
        field="python.python_bin",
    )
    if not code_root.is_dir():
        raise RuntimeError("project_env.json field project.code_root must be an existing directory")
    if not frontend_root.is_dir():
        raise RuntimeError("project_env.json field project.frontend_root must be an existing directory")
    if not python_bin.is_file():
        raise RuntimeError("project_env.json field python.python_bin must be an existing file path")

    agent_root = _derive_agent_root(project_root=project_root, code_root=code_root, frontend_root=frontend_root)

    frontend_dev_port = _require_positive_int(test_execution, "frontend_dev_port", source="project_env.json.test_execution")
    backend_base_url = _validate_http_url(
        _require_non_empty_str(test_execution, "backend_base_url", source="project_env.json.test_execution"),
        field="test_execution.backend_base_url",
    )
    service_startup_wait_seconds = _require_positive_number(
        test_execution,
        "service_startup_wait_seconds",
        source="project_env.json.test_execution",
    )
    test_timeout_seconds = _build_test_timeout_seconds(test_execution)

    frontend_url = f"http://127.0.0.1:{frontend_dev_port}"
    environment = _build_environment_variables(payload)

    return RuntimeContext(
        project_root=project_root,
        agent_root=agent_root,
        code_root=code_root,
        frontend_root=frontend_root,
        python_bin=python_bin,
        backend_base_url=backend_base_url,
        frontend_url=frontend_url,
        frontend_dev_port=frontend_dev_port,
        service_startup_wait_seconds=service_startup_wait_seconds,
        test_timeout_seconds=test_timeout_seconds,
        environment=environment,
        raw_payload=payload,
    )


def build_execution_environment_section(context: RuntimeContext) -> str:
    lines = [
        "## 执行环境",
        f"- 工作目录: {context.agent_root.as_posix()}",
        f"- 项目根目录: {context.project_root.as_posix()}",
        f"- 业务代理根目录: {context.agent_root.as_posix()}",
        f"- 代码目录: {context.code_root.as_posix()}",
        f"- 前端目录: {context.frontend_root.as_posix()}",
        f"- Python: {context.python_bin.as_posix()}",
        f"- 后端地址: {context.backend_base_url}",
        f"- 前端 URL: {context.frontend_url}",
        "- 测试执行配置:",
        f"  - 前端开发端口: {context.frontend_dev_port}",
        f"  - 服务启动等待: {context.service_startup_wait_seconds}秒",
    ]
    for test_type, timeout in context.test_timeout_seconds.items():
        lines.append(f"  - {test_type}测试超时: {timeout}秒")

    if context.environment:
        lines.append("- 环境变量:")
        for key, value in context.environment.items():
            lines.append(f"  - {key}={value}")

    return "\n".join(lines)
