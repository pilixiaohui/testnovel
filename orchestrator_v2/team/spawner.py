"""Docker 容器团队生成器。

对标博客："for each agent, a Docker container is spun up
with the repo mounted to /upstream."
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import (
    AGENT_CONTAINER_PREFIX, AGENT_IMAGE_NAME, DOCKER_NETWORK, UPSTREAM_REPO,
    ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN, ANTHROPIC_API_KEY as CFG_ANTHROPIC_KEY,
    OPENAI_API_KEY as CFG_OPENAI_KEY, OPENAI_BASE_URL,
    CLAUDE_MODEL, WORKSPACES_DIR,
    AGENT_LOG_DIR,
)
from ..scm.sync import setup_upstream

logger = logging.getLogger(__name__)

UPSTREAM_MOUNT_PATH = "/upstream"
WORKSPACE_PATH_IN_CONTAINER = "/home/agent/workspace"
LOG_MOUNT_PATH = "/agent-logs"


@dataclass
class DockerAgent:
    container_id: str
    agent_id: str
    role: str


def _needs_rebuild(project_root: Path) -> bool:
    """检查依赖文件或 orchestrator 代码是否比镜像新，决定是否需要重建。"""
    dep_files = [
        project_root / "project" / "backend" / "pyproject.toml",
        project_root / "project" / "frontend" / "package.json",
    ]
    # orchestrator 全目录变更都需要重建（镜像 COPY orchestrator_v2/，含 prompts/*.md 等）
    orch_dir = project_root / "orchestrator_v2"
    if orch_dir.is_dir():
        dep_files.extend(f for f in orch_dir.rglob("*") if f.is_file())
    max_dep_mtime = max((f.stat().st_mtime for f in dep_files if f.exists()), default=0)

    result = subprocess.run(
        ["docker", "inspect", "--format={{.Created}}", AGENT_IMAGE_NAME],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return True  # 镜像不存在

    from datetime import datetime
    try:
        image_time = datetime.fromisoformat(result.stdout.strip().rstrip("Z"))
        return max_dep_mtime > image_time.timestamp()
    except (ValueError, OSError):
        return True


def build_agent_image(project_root: Path, *, force: bool = False) -> str:
    """构建 agent Docker 镜像。

    镜像即环境：所有依赖在构建时安装，agent 运行时不碰环境。
    使用 Docker 分层缓存：依赖文件不变时秒级构建。
    """
    if not force and not _needs_rebuild(project_root):
        logger.info("image %s is up-to-date, skipping rebuild", AGENT_IMAGE_NAME)
        return AGENT_IMAGE_NAME

    # 生成容器内精简版 codex config
    codex_config_content = """\
model_provider = "codex"
model = "gpt-5.3-codex"
model_reasoning_effort = "xhigh"
disable_response_storage = true

[model_providers.codex]
name = "codex"
base_url = "http://152.53.165.53:3000/v1"
wire_api = "responses"
env_key = "OPENAI_API_KEY"

[projects."/home/agent/workspace"]
trust_level = "trusted"

[sandbox_workspace_write]
network_access = true

[notice]
hide_full_access_warning = true
"""
    codex_dir = project_root / ".codex-agent"
    codex_dir.mkdir(exist_ok=True)
    (codex_dir / "config.toml").write_text(codex_config_content, encoding="utf-8")

    dockerfile_content = """\
FROM node:20-bookworm-slim

# Layer 1: 系统依赖（几乎不变）
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv git curl \
    && rm -rf /var/lib/apt/lists/*

# Layer 2: CLI 工具（很少变）
RUN npm install -g @openai/codex@0.101.0 @anthropic-ai/claude-code @fission-ai/openspec
RUN pip3 install --no-cache-dir --break-system-packages anthropic

# Layer 3: 镜像内独立 venv（不依赖宿主机）
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Layer 4: 项目依赖（只有 pyproject.toml / package.json 变化时才重建）
COPY project/backend/pyproject.toml project/backend/setup.cfg* project/backend/
RUN cd project/backend && pip install -e '.[dev]' -q

COPY project/frontend/package.json project/frontend/package-lock.json* project/frontend/
RUN cd project/frontend && npm ci --ignore-scripts --legacy-peer-deps

# Layer 5: orchestrator 代码 + codex config
RUN mkdir -p /home/agent/.codex && chmod -R 777 /home/agent
COPY .codex-agent/config.toml /home/agent/.codex/config.toml
COPY orchestrator_v2/ /opt/orchestrator_v2/

# Layer 6: 冒烟测试 — 构建时就验证环境
RUN python -c "import fastapi, pydantic, pytest; print('Python deps OK')"
RUN node -e "try{require('/home/agent/workspace/project/frontend/node_modules/vitest/dist/node/index.js')}catch(e){console.log('WARN: vitest not importable (will be available after clone)')}"

ENV PYTHONPATH=/opt HOME=/home/agent
ENTRYPOINT ["python", "-m", "orchestrator_v2.harness.entrypoint", "agent"]
"""
    dockerfile = project_root / "Dockerfile.agent"
    dockerfile.write_text(dockerfile_content, encoding="utf-8")

    try:
        result = subprocess.run(
            ["docker", "build", "-t", AGENT_IMAGE_NAME, "-f", str(dockerfile), str(project_root)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"docker build failed: {result.stderr}")
    finally:
        dockerfile.unlink(missing_ok=True)
        import shutil
        shutil.rmtree(codex_dir, ignore_errors=True)

    logger.info("built agent image: %s", AGENT_IMAGE_NAME)
    return AGENT_IMAGE_NAME


def spawn_team(
    *,
    project_root: Path,
    roles: dict[str, int],
    image: str | None = None,
) -> list[DockerAgent]:
    """启动 Docker 容器团队。"""
    upstream = setup_upstream(project_root)
    img = image or AGENT_IMAGE_NAME
    agents: list[DockerAgent] = []

    # 确保 Docker 网络存在
    subprocess.run(
        ["docker", "network", "create", DOCKER_NETWORK],
        capture_output=True, text=True,
    )

    for role, count in roles.items():
        for i in range(1, count + 1):
            agent_id = f"{role}-{i}"
            agent = _spawn_one(
                agent_id=agent_id,
                role=role,
                upstream_path=upstream,
                image=img,
            )
            agents.append(agent)

    logger.info("spawned %d agents", len(agents))
    return agents


def _spawn_one(
    *,
    agent_id: str,
    role: str,
    upstream_path: Path,
    image: str,
) -> DockerAgent:
    """启动单个 agent 容器。"""
    container_name = f"{AGENT_CONTAINER_PREFIX}-{agent_id}"

    # 先清理同名容器
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True, text=True,
    )

    # 确保宿主机 workspace 目录存在，用于持久化日志
    workspace_host = WORKSPACES_DIR / agent_id
    workspace_host.mkdir(parents=True, exist_ok=True)

    # 确保宿主机 log 目录存在
    AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "--network", DOCKER_NETWORK,
        "--user", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{upstream_path}:{UPSTREAM_MOUNT_PATH}:rw",
        "-v", f"{workspace_host}:{WORKSPACE_PATH_IN_CONTAINER}:rw",
        "-v", f"{AGENT_LOG_DIR}:{LOG_MOUNT_PATH}:rw",
        "-e", f"AGENT_ID={agent_id}",
        "-e", f"AGENT_ROLE={role}",
        "-e", f"UPSTREAM_PATH={UPSTREAM_MOUNT_PATH}",
        "-e", f"WORKSPACE_PATH={WORKSPACE_PATH_IN_CONTAINER}",
        "-e", f"AGENT_LOG_DIR={LOG_MOUNT_PATH}",
        "-e", f"OPENAI_API_KEY={CFG_OPENAI_KEY}",
        "-e", f"ANTHROPIC_API_KEY={CFG_ANTHROPIC_KEY}",
        "-e", f"ANTHROPIC_AUTH_TOKEN={ANTHROPIC_AUTH_TOKEN}",
        "-e", "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1",
    ]
    # 第三方代理 base URL
    if ANTHROPIC_BASE_URL:
        cmd += ["-e", f"ANTHROPIC_BASE_URL={ANTHROPIC_BASE_URL}"]
    if OPENAI_BASE_URL:
        cmd += ["-e", f"OPENAI_BASE_URL={OPENAI_BASE_URL}"]
    if CLAUDE_MODEL:
        cmd += ["-e", f"CLAUDE_MODEL={CLAUDE_MODEL}"]
    cmd += [
        image,
        "--role", role,
        "--agent-id", agent_id,
        "--workspace", WORKSPACE_PATH_IN_CONTAINER,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"docker run failed for {agent_id}: {result.stderr}")

    container_id = result.stdout.strip()[:12]
    logger.info("started container %s for %s (%s)", container_id, agent_id, role)

    return DockerAgent(
        container_id=container_id,
        agent_id=agent_id,
        role=role,
    )


def shutdown_team(agents: list[DockerAgent]) -> None:
    """停止并删除所有容器。"""
    for agent in agents:
        container_name = f"{AGENT_CONTAINER_PREFIX}-{agent.agent_id}"
        subprocess.run(["docker", "stop", container_name], capture_output=True, text=True)
        subprocess.run(["docker", "rm", container_name], capture_output=True, text=True)
        logger.info("stopped %s", agent.agent_id)


def restart_agent(agent: DockerAgent, project_root: Path, image: str | None = None) -> DockerAgent:
    """重启崩溃的 agent 容器。"""
    container_name = f"{AGENT_CONTAINER_PREFIX}-{agent.agent_id}"
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, text=True)

    upstream = project_root / ".agent-upstream.git"
    return _spawn_one(
        agent_id=agent.agent_id,
        role=agent.role,
        upstream_path=upstream if upstream.exists() else UPSTREAM_REPO,
        image=image or AGENT_IMAGE_NAME,
    )


def is_agent_alive(agent: DockerAgent) -> bool:
    """检查容器是否在运行。"""
    container_name = f"{AGENT_CONTAINER_PREFIX}-{agent.agent_id}"
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"
