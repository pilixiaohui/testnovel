"""CLI 工具统一抽象层

支持多种 CLI 工具（codex、claude、opencode）的统一接口封装。
"""

from .base import CLIRunner, CLIConfig, CLIRunResult
from .factory import create_cli_runner, get_available_clis

__all__ = [
    "CLIRunner",
    "CLIConfig",
    "CLIRunResult",
    "create_cli_runner",
    "get_available_clis",
]
