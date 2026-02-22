#!/usr/bin/env python3
"""架构约束 linter — 自动检查文件大小、import 方向、命名规范。

规则：
- Python 文件不超过 500 行
- TypeScript 文件不超过 300 行
- project/ 不能导入 orchestrator_v2/
- Python 文件名必须 snake_case

用法：
  python scripts/lint_arch.py                # 全量扫描
  python scripts/lint_arch.py --changed-only # 只扫描最近变更
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- 规则阈值 ---
MAX_PYTHON_LINES = 500
MAX_TS_LINES = 300

# --- 排除目录 ---
EXCLUDE_DIRS = {
    "__pycache__", "node_modules", ".git", ".venv", "venv",
    "dist", "build", ".agent-upstream.git", ".mypy_cache",
    ".pytest_cache", "data_backup", ".agent-workspaces", "openclaw",
    "spec_code", "openspec",
}

# --- snake_case 正则 ---
_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*\.py$")
_SPECIAL_FILES = {"__init__.py", "__main__.py", "conftest.py", "setup.py"}

# --- import 方向检查正则 ---
_ORCH_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+orchestrator_v2(?:\.|$)", re.MULTILINE
)


def _get_changed_files() -> list[str]:
    """获取最近一次提交的变更文件列表。"""
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"],
            capture_output=True, text=True, timeout=10, cwd=PROJECT_ROOT,
        )
        if r.returncode != 0:
            # fallback: 未提交的变更
            r = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True, text=True, timeout=10, cwd=PROJECT_ROOT,
            )
        return [f.strip() for f in r.stdout.strip().split("\n") if f.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _should_skip(path: Path) -> bool:
    """检查路径是否在排除目录中。"""
    parts = path.relative_to(PROJECT_ROOT).parts
    return any(p in EXCLUDE_DIRS for p in parts)


def _check_file_size(path: Path) -> list[str]:
    """检查文件行数是否超限。"""
    violations = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return violations

    line_count = len(lines)
    suffix = path.suffix.lower()

    if suffix == ".py" and line_count > MAX_PYTHON_LINES:
        violations.append(
            f"{path}:{line_count}: file-size: Python file has {line_count} lines "
            f"(max {MAX_PYTHON_LINES}) "
            f"[fix: 拆分为更小的模块，参见 docs/architecture-constraints.md]"
        )
    elif suffix in (".ts", ".tsx") and line_count > MAX_TS_LINES:
        violations.append(
            f"{path}:{line_count}: file-size: TypeScript file has {line_count} lines "
            f"(max {MAX_TS_LINES}) "
            f"[fix: 拆分为更小的模块，参见 docs/architecture-constraints.md]"
        )

    return violations


def _check_import_direction(path: Path) -> list[str]:
    """检查 project/ 是否导入了 orchestrator_v2/。"""
    violations = []
    rel = path.relative_to(PROJECT_ROOT)
    parts = rel.parts

    if not parts or parts[0] != "project":
        return violations
    if path.suffix != ".py":
        return violations

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return violations

    for i, line in enumerate(content.splitlines(), 1):
        if _ORCH_IMPORT_RE.match(line):
            violations.append(
                f"{path}:{i}: import-direction: project/ 不能导入 orchestrator_v2/ "
                f"[fix: project/ 是业务代码，不应依赖编排层]"
            )

    return violations


def _check_python_naming(path: Path) -> list[str]:
    """检查 Python 文件名是否为 snake_case。"""
    violations = []
    if path.suffix != ".py":
        return violations

    name = path.name
    if name in _SPECIAL_FILES:
        return violations
    if name.startswith("__") and name.endswith("__.py"):
        return violations

    if not _SNAKE_CASE_RE.match(name):
        violations.append(
            f"{path}:1: naming: Python 文件名 '{name}' 不是 snake_case "
            f"[fix: 重命名为 snake_case 格式]"
        )

    return violations


def scan_files(changed_only: bool = False) -> list[Path]:
    """收集需要检查的文件。"""
    if changed_only:
        changed = _get_changed_files()
        files = []
        for f in changed:
            p = PROJECT_ROOT / f
            if p.is_file() and not _should_skip(p):
                files.append(p)
        return files

    files = []
    for suffix in ("*.py", "*.ts", "*.tsx"):
        for p in PROJECT_ROOT.rglob(suffix):
            if not _should_skip(p):
                files.append(p)
    return files


def lint(changed_only: bool = False) -> list[str]:
    """运行所有检查，返回违规列表。"""
    files = scan_files(changed_only)
    violations: list[str] = []

    for path in sorted(files):
        violations.extend(_check_file_size(path))
        violations.extend(_check_import_direction(path))
        violations.extend(_check_python_naming(path))

    return violations


def main() -> None:
    changed_only = "--changed-only" in sys.argv

    violations = lint(changed_only)

    if violations:
        for v in violations:
            print(v)
        sys.exit(1)
    else:
        mode = "changed files" if changed_only else "all files"
        print(f"Architecture lint passed ({mode})")
        sys.exit(0)


if __name__ == "__main__":
    main()
