"""基础配置与环境变量加载器，支持 .env 文件与系统环境并存."""
from __future__ import annotations

import os
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _load_env_file(path: Path = _ENV_PATH) -> None:
    """读取 .env 文件到 os.environ，不覆盖已存在的环境变量."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        cleaned = value.strip().strip('"').strip("'")
        os.environ[key] = cleaned


_load_env_file()

TOPONE_API_KEY: str | None = os.getenv("TOPONE_API_KEY")
TOPONE_BASE_URL: str = os.getenv("TOPONE_BASE_URL", "https://api.toponeapi.top")
TOPONE_DEFAULT_MODEL: str = os.getenv(
    "TOPONE_DEFAULT_MODEL", "gemini-3-pro-preview-11-2025"
)
TOPONE_SECONDARY_MODEL: str = os.getenv("TOPONE_SECONDARY_MODEL", "gemini-2.5-flash")
try:
    TOPONE_TIMEOUT_SECONDS: float = float(os.getenv("TOPONE_TIMEOUT_SECONDS", "30"))
except ValueError:
    TOPONE_TIMEOUT_SECONDS = 30.0
