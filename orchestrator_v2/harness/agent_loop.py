"""Agent 主循环（v2）。

目标：回到博客风格的 while true 循环：sync -> prompt -> LLM -> test -> push -> repeat。

约束：
- 不解析 LLM 输出（元数据由 LLM 直接写文件）。
- 仅在必要点做原子同步（claim/lock 立即 commit+push）。
"""

from __future__ import annotations

import datetime
import json
import logging
import subprocess
import time
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..agents.roles import BUILTIN_ROLES, AgentRole
from ..config import CLI_TIMEOUT_SECONDS, DEFAULT_CLI
from ..core.errors import PermanentError, TemporaryError
from ..scm.sync import (
    auto_resolve_metadata_conflict,
    git_commit,
    git_pull,
    git_pull_rebase,
    git_push,
    git_revert_to_upstream,
)
from ..cli.base import CLIRunResult
from ..testing.runner import check_gate, run_tests
from ..types import Task

from .locks import new_lock, release_lock, try_acquire_lock
from .prompt_builder import build_prompt
from .task_picker import (
    MAX_TASK_ATTEMPTS,
    claim_task,
    load_cross_task_failure_patterns,
    load_failure_history,
    pick_task_for_role,
    scan_available_tasks,
    scan_tasks,
    write_failure_record,
)

logger = logging.getLogger(__name__)

# 环境预检标记（模块级，首次 session 检查一次）
_env_checked = False


def _check_env_or_die(workspace: Path) -> None:
    """轻量级环境检查。失败则抛出 PermanentError，让容器退出。"""
    checks = [
        ("python", ["python", "--version"]),
        ("pytest", ["python", "-c", "import pytest"]),
        ("node", ["node", "--version"]),
    ]
    for name, cmd in checks:
        try:
            subprocess.run(cmd, capture_output=True, timeout=5, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            raise PermanentError(f"Environment check failed: {name} not available. Rebuild image.")


@dataclass(frozen=True)
class WorkItem:
    task: Task | None
    title: str
    description: str
    lock_key: str | None = None


def agent_loop(
    *,
    role: str,
    agent_id: str,
    workspace: Path,
    log_dir: Path,
    max_sessions: int = 0,
) -> None:
    """Agent 主循环。max_sessions=0 表示无限。"""
    if role not in BUILTIN_ROLES:
        raise ValueError(f"unknown role: {role!r}")

    agent_role = BUILTIN_ROLES[role]
    prompts_dir = Path(__file__).resolve().parents[1] / "agents" / "prompts"
    agent_prompt = agent_role.load_prompt(prompts_dir)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{agent_id}.log"

    idle_streak = 0
    sessions = 0
    while max_sessions == 0 or sessions < max_sessions:
        sessions += 1
        try:
            idle = _run_one_session(
                role=role,
                agent_id=agent_id,
                agent_role=agent_role,
                agent_prompt=agent_prompt,
                workspace=workspace,
                log_file=log_file,
            )
            if idle:
                idle_streak += 1
                time.sleep(min(60, 5 * idle_streak))
            else:
                idle_streak = 0
        except TemporaryError as exc:
            # 临时错误（超时、rate limit 等）：退避后重试，不 crash 容器
            logger.warning("agent_loop temporary error for %s (%s): %s", agent_id, role, exc)
            time.sleep(30)
        except PermanentError as exc:
            # 永久错误（环境缺失等）：让容器退出，由 monitor 检测并处理。
            logger.error("agent_loop permanent error for %s (%s): %s", agent_id, role, exc)
            raise
        except Exception as exc:
            # 快速失败：抛出错误，让容器由 monitor 重启。
            raise RuntimeError(f"agent_loop failed for {agent_id} ({role}): {exc}") from exc


def _run_one_session(
    *,
    role: str,
    agent_id: str,
    agent_role: AgentRole,
    agent_prompt: str,
    workspace: Path,
    log_file: Path,
) -> bool:
    """单次 session。返回 True 表示空转。"""
    # 0a. 环境快速检查（首次 session 时执行一次）
    global _env_checked
    if not _env_checked:
        _check_env_or_die(workspace)
        _env_checked = True

    # 0b. 若上次 session 留下未完成的 git 操作（rebase/merge），交给 LLM 处理。
    if _git_operation_in_progress(workspace):
        return _run_conflict_resolution_session(
            role=role,
            agent_id=agent_id,
            agent_role=agent_role,
            agent_prompt=agent_prompt,
            workspace=workspace,
            log_file=log_file,
        )

    # 1. GIT SYNC
    pull = git_pull(workspace)
    if not pull.ok:
        if pull.conflict:
            if auto_resolve_metadata_conflict(workspace):
                return False
            # 代码冲突：不 abort/reset，留给下一轮 LLM 处理（对齐博客做法）。
            logger.warning("git pull conflict detected; leaving repo in conflict state for LLM")
            return False

        # 允许脏工作区（恢复场景）
        if not _has_uncommitted_changes(workspace):
            raise RuntimeError(f"git pull failed: {(pull.stderr or pull.stdout).strip()[:300]}")

    # 2. PICK WORK（已认领 > 新认领 > 自主模式）
    work = _resume_or_pick(role=role, agent_id=agent_id, workspace=workspace)

    # 3. BUILD PROMPT
    cross_patterns = load_cross_task_failure_patterns(workspace)
    prompt = build_prompt(
        agent_prompt=agent_prompt,
        workspace=workspace,
        task_title=work.title if work else "自主模式",
        task_description=work.description if work else "当前没有预分配任务，请自主决定工作内容。",
        agent_id=agent_id,
        failure_history=(load_failure_history(workspace, work.task.id) if work and work.task else ""),
        cross_task_patterns=cross_patterns,
        refs=(work.task.refs if work and work.task else None),
    )

    # 4+6. RUN LLM + TEST gate check
    project_env = _load_project_env(workspace)

    # 捕获测试基线（可选，默认开启）
    if agent_role.run_tests_after and project_env.get("baseline_on_session_start", True):
        run_tests(workspace, project_env, fast=True, agent_id=agent_id)

    _run_cli(prompt, role=role, workspace=workspace,
             log_file=log_file, timeout_seconds=CLI_TIMEOUT_SECONDS)

    # 5. CHECK CHANGES（自主模式下无变更 = 空转）
    if work is None and not _has_uncommitted_changes(workspace) and not _has_commits_to_push(workspace):
        return True

    if agent_role.run_tests_after:
        fast = run_tests(workspace, project_env, fast=True, agent_id=agent_id)
        if not check_gate(fast):
            _handle_test_failure(workspace, work, agent_id, fast.stdout_tail)
            return False

        full = run_tests(workspace, project_env, fast=False, agent_id=agent_id)
        if not check_gate(full):
            _handle_test_failure(workspace, work, agent_id, full.stdout_tail)
            return False

    # 7. FINALIZE
    if work and work.task:
        uat_enabled = project_env.get("uat_enabled", False)

        if uat_enabled and agent_role.run_tests_after and work.task.role != "uat":
            # implementer 完成 → 送 UAT 验收
            from .task_picker import send_task_to_uat
            send_task_to_uat(workspace, work.task, agent_id,
                             test_summary="implementer tests passed")
        elif role == "uat":
            # UAT agent：读取 LLM 写入的验收报告，由 harness 统一做状态流转
            _finalize_uat_task(workspace, work.task, agent_id)
        else:
            from .task_picker import mark_task_done
            mark_task_done(workspace, work.task, agent_id)
    if work and work.lock_key:
        release_lock(workspace, work.lock_key)

    # 8. COMMIT + PUSH（单次推送，所有变更）
    msg = f"[{agent_id}] {work.title if work else 'autonomous'}"
    committed = git_commit(workspace, msg)
    if committed or _has_commits_to_push(workspace):
        pushed = _push_with_retry(workspace, max_retries=3)
        if not pushed:
            return False

    return False


def _run_conflict_resolution_session(
    *,
    role: str,
    agent_id: str,
    agent_role: AgentRole,
    agent_prompt: str,
    workspace: Path,
    log_file: Path,
) -> bool:
    """处理未完成的 git rebase/merge（由 LLM 自行解决）。"""
    work = _resume_or_pick(role=role, agent_id=agent_id, workspace=workspace, allow_claim_new=False)
    title = work.title if work else "GIT 冲突处理"
    description = (
        "当前 workspace 存在未完成的 git 操作（rebase/merge/cherry-pick）。\n"
        "请你自行执行 git status 并解决冲突：\n"
        "1) 打开冲突文件，解决冲突标记\n"
        "2) git add <files>\n"
        "3) git rebase --continue / git merge --continue（按 git status 提示）\n"
        "4) 确认工作区不再处于 rebase/merge 状态\n\n"
        "要求：不要执行 git rebase --abort / reset；我们需要把冲突修复并合并进 upstream。\n"
    )
    if work:
        description = description + "\n---\n\n" + (work.description or "")

    prompt = build_prompt(
        agent_prompt=agent_prompt,
        workspace=workspace,
        task_title=title,
        task_description=description,
        agent_id=agent_id,
        failure_history=(load_failure_history(workspace, work.task.id) if work and work.task else ""),
    )
    _run_cli(prompt, role=role, workspace=workspace, log_file=log_file, timeout_seconds=CLI_TIMEOUT_SECONDS)

    # 若冲突仍未解决，结束本轮，等待下一轮继续。
    if _git_operation_in_progress(workspace):
        logger.warning("git operation still in progress after LLM session")
        return False

    # 冲突解决后：按常规门禁跑测试，然后 push 同步（即使没有新增 commit，rebase 也可能产生 ahead commits）。
    project_env = _load_project_env(workspace)
    if agent_role.run_tests_after and (_has_uncommitted_changes(workspace) or _has_commits_to_push(workspace)):
        fast = run_tests(workspace, project_env, fast=True, agent_id=agent_id)
        if not check_gate(fast):
            _handle_test_failure(workspace, work, agent_id, fast.stdout_tail)
            return False

        full = run_tests(workspace, project_env, fast=False, agent_id=agent_id)
        if not check_gate(full):
            _handle_test_failure(workspace, work, agent_id, full.stdout_tail)
            return False

    if work and work.task:
        project_env = _load_project_env(workspace)
        uat_enabled = project_env.get("uat_enabled", False)

        if uat_enabled and agent_role.run_tests_after and work.task.role != "uat":
            from .task_picker import send_task_to_uat
            send_task_to_uat(workspace, work.task, agent_id,
                             test_summary="conflict-resolution tests passed")
        elif role == "uat":
            _finalize_uat_task(workspace, work.task, agent_id)
        else:
            from .task_picker import mark_task_done
            mark_task_done(workspace, work.task, agent_id)
    if work and work.lock_key:
        release_lock(workspace, work.lock_key)

    msg = f"[{agent_id}] {work.title if work else 'conflict-resolution'}"
    committed = git_commit(workspace, msg)
    if committed or _has_commits_to_push(workspace):
        pushed = _push_with_retry(workspace, max_retries=3)
        if not pushed:
            return False

    return False


def _has_uncommitted_changes(workspace: Path) -> bool:
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git status failed: {(r.stderr or r.stdout).strip()[:300]}")
    return bool(r.stdout.strip())

def _git_operation_in_progress(workspace: Path) -> bool:
    git_dir = workspace / ".git"
    if not git_dir.exists():
        return False
    # rebase-merge/rebase-apply: rebase 中；MERGE_HEAD: merge 中；CHERRY_PICK_HEAD: cherry-pick 中
    return any(
        (git_dir / name).exists()
        for name in ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD")
    )


def _has_commits_to_push(workspace: Path) -> bool:
    """检查本地是否有未推送的提交（ahead origin/<branch>）。"""
    branch_r = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if branch_r.returncode != 0:
        raise RuntimeError(f"git branch failed: {(branch_r.stderr or branch_r.stdout).strip()[:300]}")
    branch = branch_r.stdout.strip() or "main"

    r = subprocess.run(
        ["git", "rev-list", "--left-right", "--count", f"origin/{branch}...HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git rev-list failed: {(r.stderr or r.stdout).strip()[:300]}")
    parts = r.stdout.strip().split()
    if len(parts) != 2:
        raise RuntimeError(f"unexpected git rev-list output: {r.stdout.strip()[:300]}")
    ahead = int(parts[1])
    return ahead > 0


def _load_project_env(workspace: Path) -> dict:
    env_file = workspace / "project_env.json"
    if not env_file.is_file():
        raise FileNotFoundError(f"missing project_env.json at {env_file}")
    return json.loads(env_file.read_text(encoding="utf-8"))


def _push_with_retry(workspace: Path, *, max_retries: int) -> bool:
    for attempt in range(max_retries):
        push = git_push(workspace)
        if push.ok:
            return True

        pull = git_pull_rebase(workspace)
        if pull.ok:
            continue
        if pull.conflict and auto_resolve_metadata_conflict(workspace):
            continue
        if pull.conflict:
            # 代码冲突：保持 rebase 冲突状态，交给下一轮 LLM 处理。
            logger.warning("git push requires manual conflict resolution; leaving repo in rebase state")
            return False
        raise RuntimeError(f"git push failed after retry: {(push.stderr or push.stdout).strip()[:300]}")
    raise RuntimeError(f"git push failed after retry: {(push.stderr or push.stdout).strip()[:300]}")


def _resume_or_pick(*, role: str, agent_id: str, workspace: Path, allow_claim_new: bool = True) -> WorkItem | None:
    tasks_dir = workspace / "tasks"

    # 2.1 resume: claimed by me
    claimed = [t for t in scan_tasks(tasks_dir, "claimed") if t.agent_id == agent_id]
    if claimed:
        claimed.sort(key=lambda t: t.priority)
        t = claimed[0]
        lock_key = f"manual/{t.id}"
        _ensure_manual_lock(workspace, lock_key, agent_id=agent_id, role=role, intent=f"{t.id}: {t.title}")
        return WorkItem(task=t, title=t.title, description=t.description, lock_key=lock_key)

    # 2.2 claim new
    if not allow_claim_new:
        return None
    for _ in range(5):
        available = scan_available_tasks(tasks_dir)
        t = pick_task_for_role(role, available)
        if t is None:
            break
        if claim_task(workspace, t, agent_id):
            lock_key = f"manual/{t.id}"
            _ensure_manual_lock(workspace, lock_key, agent_id=agent_id, role=role, intent=f"{t.id}: {t.title}")
            return WorkItem(task=t, title=t.title, description=t.description, lock_key=lock_key)
        # claim 冲突：继续挑下一个（workspace 已回滚到 upstream）

    return None


def _ensure_manual_lock(workspace: Path, lock_key: str, *, agent_id: str, role: str, intent: str) -> None:
    if (workspace / "current_tasks" / f"{lock_key}.md").exists():
        return
    lock = new_lock(
        key=lock_key,
        agent_id=agent_id,
        role=role,
        source="manual",
        intent=intent,
    )
    try_acquire_lock(workspace, lock)


def _finalize_uat_task(workspace: Path, task: Task, agent_id: str) -> None:
    """UAT agent 完成后，读取验收报告并路由任务状态。"""
    from .task_picker import parse_task_file

    project_env = _load_project_env(workspace)
    max_uat_attempts = int(project_env.get("uat_max_attempts", 2))

    tasks_dir = workspace / "tasks"
    claimed_path = tasks_dir / "claimed" / f"{task.id}.md"

    if not claimed_path.exists():
        logger.warning("UAT task %s not found in claimed/, skipping finalize", task.id)
        return

    # 重新读取任务文件（LLM 已写入验收报告）
    refreshed_task = parse_task_file(claimed_path, "claimed")
    if not refreshed_task:
        logger.error("Failed to parse UAT task %s after LLM session", task.id)
        return

    # 检测验收结果（在任务描述中查找 "**结果**: PASS" 或 "**结果**: FAIL"）
    uat_passed = "**结果**: PASS" in refreshed_task.description or "**结果**: pass" in refreshed_task.description
    uat_failed = "**结果**: FAIL" in refreshed_task.description or "**结果**: fail" in refreshed_task.description

    if uat_passed:
        # 验收通过 → done
        from .task_picker import mark_task_done
        mark_task_done(workspace, refreshed_task, agent_id, test_summary="UAT passed")
        logger.info("UAT task %s passed, moved to done/", task.id)
    elif uat_failed:
        # 验收失败 → 根据重试次数决定
        _uat_fail_or_escalate(workspace, task, refreshed_task, agent_id, max_uat_attempts)
    else:
        # 未检测到明确的 PASS/FAIL → 视为失败，走同样的重试/升级逻辑
        logger.warning("UAT task %s has no clear PASS/FAIL result, treating as failed", task.id)
        _uat_fail_or_escalate(workspace, task, refreshed_task, agent_id, max_uat_attempts)


def _uat_fail_or_escalate(
    workspace: Path, task: Task, refreshed_task: Task, agent_id: str, max_uat_attempts: int,
) -> None:
    """UAT 失败时根据重试次数决定回退 available 还是升级 needs_input。"""
    from .task_picker import move_task, serialize_task

    uat_attempt_count = refreshed_task.uat_attempt_count
    if uat_attempt_count < max_uat_attempts:
        refreshed_task.role = refreshed_task.original_role or "implementer"
        refreshed_task.uat_attempt_count = uat_attempt_count + 1
        refreshed_task.status = "available"
        refreshed_task.agent_id = None
        refreshed_task.claimed_at = None

        dst = move_task(workspace, task.id, "claimed", "available")
        dst.write_text(serialize_task(refreshed_task), encoding="utf-8")
        logger.info("UAT task %s failed (attempt %d), moved back to available/", task.id, uat_attempt_count + 1)
    else:
        refreshed_task.status = "needs_input"
        dst = move_task(workspace, task.id, "claimed", "needs_input")
        dst.write_text(serialize_task(refreshed_task), encoding="utf-8")
        logger.info("UAT task %s escalated to needs_input/ after %d attempts", task.id, uat_attempt_count)


def _handle_test_failure(workspace: Path, work: WorkItem | None, agent_id: str, detail: str) -> None:
    if work is None or work.task is None:
        return

    attempt = write_failure_record(workspace, work.task.id, agent_id, detail)
    if attempt < MAX_TASK_ATTEMPTS:
        return

    # 达到最大次数：标记 failed + 释放 manual lock，并将元数据推送到 upstream。
    tasks_dir = workspace / "tasks"
    claimed_path = tasks_dir / "claimed" / f"{work.task.id}.md"
    if not claimed_path.exists():
        return
    failed_path = tasks_dir / "failed" / f"{work.task.id}.md"
    failed_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(claimed_path), str(failed_path))

    release_lock(workspace, work.lock_key or f"manual/{work.task.id}")

    # 只提交任务/锁元数据，避免把失败的代码改动推到主分支。
    msg = f"[{agent_id}] {work.task.id} -> FAILED (max attempts)"
    committed = git_commit(workspace, msg, paths=["tasks", "current_tasks"])
    if committed:
        pushed = _push_with_retry(workspace, max_retries=3)
        if not pushed:
            # push 触发代码冲突：不要 reset 掉 rebase 状态，留给下一轮 LLM 处理。
            return

    # 丢弃本地失败改动，让 agent 回到干净工作区继续循环。
    git_revert_to_upstream(workspace)


def _run_cli(
    prompt: str,
    *,
    role: str,
    workspace: Path,
    log_file: Path,
    timeout_seconds: int,
    resume_session_id: str | None = None,
) -> CLIRunResult:
    from ..cli.base import CLIConfig
    from ..cli.factory import create_cli_runner

    project_env = _load_project_env(workspace)
    cli_name = project_env.get("cli", DEFAULT_CLI)
    if not isinstance(cli_name, str) or not cli_name.strip():
        raise RuntimeError("project_env.json field 'cli' must be a non-empty string")
    cli_name = cli_name.strip()

    runner = create_cli_runner(cli_name)
    approval_policy = "never" if cli_name == "codex" else "full-auto"

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_file = log_file.parent / f"cli_output_{ts}.md"
    config = CLIConfig(
        sandbox_mode="danger-full-access",
        approval_policy=approval_policy,
        work_dir=workspace,
        output_file=output_file,
        extra_args=[],
        timeout_seconds=timeout_seconds,
    )

    result = runner.run(
        prompt=prompt,
        config=config,
        label=f"AGENT-{role.upper()}",
        log_file=log_file,
        resume_session_id=resume_session_id,
    )
    return result
