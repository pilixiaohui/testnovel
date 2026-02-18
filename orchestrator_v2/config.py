"""扁平配置（v2）。

目标：只保留工作流与团队模式必需参数，避免角色级配置与复杂派生逻辑。
"""

from __future__ import annotations

import os

from .infra.paths import PROJECT_ROOT

# ============= 路径（全部相对于 PROJECT_ROOT） =============
VENV_DIR = PROJECT_ROOT / ".venv"          # 宿主机 venv，挂载进容器共享
VENV_MOUNT_PATH = "/home/agent/.venv"      # 容器内挂载点
WORKSPACES_DIR = PROJECT_ROOT / ".agent-workspaces"
UPSTREAM_REPO = PROJECT_ROOT / ".agent-upstream.git"
TASKS_DIR = PROJECT_ROOT / "tasks"
FEATURES_DIR = PROJECT_ROOT / "features"
DECISIONS_DIR = PROJECT_ROOT / "decisions"
CURRENT_TASKS_DIR = PROJECT_ROOT / "current_tasks"
PROGRESS_FILE = PROJECT_ROOT / "PROGRESS.md"
AGENT_LOG_DIR = PROJECT_ROOT / ".agent-logs"
PROJECT_ENV_FILE = PROJECT_ROOT / "project_env.json"

# ============= CLI（所有角色统一使用同一个 CLI） =============
DEFAULT_CLI = "codex"
CLI_TIMEOUT_SECONDS = 10800  # 3 hours

# ============= Docker =============
AGENT_IMAGE_NAME = "orchestrator-agent"
AGENT_CONTAINER_PREFIX = "orch-agent"
DOCKER_NETWORK = "orchestrator-net"

# ============= 监控 =============
TASK_CLAIM_TIMEOUT_MINUTES = 200  # slightly above CLI_TIMEOUT_SECONDS / 60
MONITOR_CHECK_INTERVAL = 60  # seconds

# ============= 重试与退避（供 core.backoff 使用） =============
BACKOFF_FORMAT_ERROR_SECONDS = 2.0
BACKOFF_RATE_LIMIT_SECONDS = 30.0
BACKOFF_NETWORK_ERROR_SECONDS = 10.0
BACKOFF_MAX_SECONDS = 60.0

# ============= API 代理（环境变量，留空则直连官方） =============
API_BASE_URL = os.getenv("API_BASE_URL", "")  # 统一代理地址（如 https://code.ppchat.vip）
API_KEY = os.getenv("API_KEY", "")             # 统一 API 密钥
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", API_BASE_URL)
ANTHROPIC_AUTH_TOKEN = os.getenv("ANTHROPIC_AUTH_TOKEN", API_KEY)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", API_KEY)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", API_KEY)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", f"{API_BASE_URL}/v1" if API_BASE_URL else "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "")  # Claude Code 模型，留空用 CLI 默认

# ============= Feishu（环境变量） =============
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "cli_a9077ddf12389cd5")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "HiHACZjHjjQH8J5UJELtdd1XcRUNBgyV")
FEISHU_CHAT_ID = os.getenv("FEISHU_CHAT_ID", "oc_64d70b5211c692135a9ec1831f2d9d39")
FEISHU_BOT_ENABLED = bool(FEISHU_APP_ID and FEISHU_APP_SECRET and FEISHU_CHAT_ID)

