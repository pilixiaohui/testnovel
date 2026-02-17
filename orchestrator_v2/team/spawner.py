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
    CLAUDE_MODEL,
)
from ..scm.sync import setup_upstream

logger = logging.getLogger(__name__)

UPSTREAM_MOUNT_PATH = "/upstream"
WORKSPACE_PATH_IN_CONTAINER = "/home/agent/workspace"


@dataclass
class DockerAgent:
    container_id: str
    agent_id: str
    role: str


def build_agent_image(project_root: Path) -> str:
    """构建 agent Docker 镜像。"""

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
RUN apt-get update && apt-get install -y python3 python3-pip git curl && rm -rf /var/lib/apt/lists/*
RUN npm install -g @openai/codex@0.101.0 @anthropic-ai/claude-code @fission-ai/openspec
RUN pip3 install --no-cache-dir --break-system-packages anthropic
RUN mkdir -p /home/agent/.codex && chmod -R 777 /home/agent
COPY .codex-agent/config.toml /home/agent/.codex/config.toml
COPY orchestrator_v2/ /opt/orchestrator_v2/
ENV PYTHONPATH=/opt HOME=/home/agent
ENTRYPOINT ["python3", "-m", "orchestrator_v2.harness.entrypoint", "agent"]
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

    cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "--network", DOCKER_NETWORK,
        "--user", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{upstream_path}:{UPSTREAM_MOUNT_PATH}:rw",
        "-e", f"AGENT_ID={agent_id}",
        "-e", f"AGENT_ROLE={role}",
        "-e", f"UPSTREAM_PATH={UPSTREAM_MOUNT_PATH}",
        "-e", f"WORKSPACE_PATH={WORKSPACE_PATH_IN_CONTAINER}",
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
