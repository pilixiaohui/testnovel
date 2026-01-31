"""CLI 工厂函数"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from .codex_adapter import CodexRunner
from .claude_adapter import ClaudeRunner
from .opencode_adapter import OpenCodeRunner

if TYPE_CHECKING:
    from .base import CLIRunner


# 已注册的 CLI 适配器
_CLI_REGISTRY: dict[str, type["CLIRunner"]] = {
    "codex": CodexRunner,
    "claude": ClaudeRunner,
    "opencode": OpenCodeRunner,
}


def get_available_clis() -> list[str]:
    """获取当前系统可用的 CLI 工具列表

    Returns:
        可用的 CLI 名称列表
    """
    available = []
    for name in _CLI_REGISTRY:
        if shutil.which(name):
            available.append(name)
    return available


def is_cli_available(cli_name: str) -> bool:
    """检查指定 CLI 是否可用

    Args:
        cli_name: CLI 名称

    Returns:
        是否可用
    """
    if cli_name not in _CLI_REGISTRY:
        return False
    return shutil.which(cli_name) is not None


def create_cli_runner(cli_name: str, fallback: str = "codex") -> "CLIRunner":
    """创建 CLI 运行器实例

    Args:
        cli_name: CLI 名称（codex、claude、opencode）
        fallback: 不可用时的回退 CLI

    Returns:
        CLI 运行器实例

    Raises:
        ValueError: CLI 名称未注册且无可用回退
    """
    # 检查请求的 CLI 是否可用
    if cli_name in _CLI_REGISTRY and is_cli_available(cli_name):
        return _CLI_REGISTRY[cli_name]()

    # 尝试回退
    if fallback and fallback != cli_name:
        if fallback in _CLI_REGISTRY and is_cli_available(fallback):
            print(f"Warning: {cli_name} not available, falling back to {fallback}")
            return _CLI_REGISTRY[fallback]()

    # 尝试任意可用的 CLI
    available = get_available_clis()
    if available:
        chosen = available[0]
        print(f"Warning: {cli_name} not available, using {chosen}")
        return _CLI_REGISTRY[chosen]()

    raise ValueError(
        f"CLI '{cli_name}' is not available and no fallback found. "
        f"Registered CLIs: {list(_CLI_REGISTRY.keys())}, "
        f"Available on system: {available}"
    )


def register_cli(name: str, runner_class: type["CLIRunner"]) -> None:
    """注册新的 CLI 适配器

    Args:
        name: CLI 名称
        runner_class: CLIRunner 子类
    """
    _CLI_REGISTRY[name] = runner_class
