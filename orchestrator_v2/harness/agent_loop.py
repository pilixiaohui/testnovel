"""Agent 主循环（v2）。

目标：回到博客风格的 while true 循环：sync -> prompt -> LLM -> test -> push -> repeat。

约束：
- 不解析 LLM 输出（元数据由 LLM 直接写文件）。
- 仅在必要点做原子同步（claim/lock 立即 commit+push）。
"""

from __future__ import annotations

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
            # 永久错误：记录日志，跳过当前任务，继续下一轮
            logger.error("agent_loop permanent error for %s (%s): %s", agent_id, role, exc)
            idle_streak += 1
            time.sleep(min(60, 10 * idle_streak))
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
    # 0. 若上次 session 留下未完成的 git 操作（rebase/merge），交给 LLM 处理。
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

    # 4+6. RUN LLM + TEST 迭代循环
    project_env = _load_project_env(workspace)
    max_fix_iters = int(project_env.get("max_fix_iterations", 3))

    # 捕获测试基线（可选，默认开启）
    baseline_result = None
    if agent_role.run_tests_after and project_env.get("baseline_on_session_start", True):
        baseline_result = run_tests(workspace, project_env, fast=True, agent_id=agent_id)

    cli_result = _run_cli(prompt, role=role, workspace=workspace,
                          log_file=log_file, timeout_seconds=CLI_TIMEOUT_SECONDS)

    # 5. CHECK CHANGES（自主模式下无变更 = 空转）
    if work is None and not _has_uncommitted_changes(workspace) and not _has_commits_to_push(workspace):
        return True

    if agent_role.run_tests_after:
        for fix_iter in range(max_fix_iters):
            fast = run_tests(workspace, project_env, fast=True, agent_id=agent_id)
            if not check_gate(fast):
                if fix_iter < max_fix_iters - 1 and cli_result.session_id:
                    follow_up = _build_test_feedback(fast.stdout_tail, fix_iter + 1, max_fix_iters,
                                                     failure_history=(load_failure_history(workspace, work.task.id) if work and work.task else ""))
                    if baseline_result:
                        from ..testing.runner import compare_results, format_regression_info
                        regression = compare_results(baseline_result, fast)
                        regression_text = format_regression_info(regression)
                        if regression_text:
                            follow_up += f"\n\n## 回归分析\n{regression_text}"
                    cli_result = _run_cli(follow_up, role=role, workspace=workspace,
                                          log_file=log_file, timeout_seconds=CLI_TIMEOUT_SECONDS,
                                          resume_session_id=cli_result.session_id)
                    continue
                _handle_test_failure(workspace, work, agent_id, fast.stdout_tail)
                return False

            full = run_tests(workspace, project_env, fast=False, agent_id=agent_id)
            if not check_gate(full):
                if fix_iter < max_fix_iters - 1 and cli_result.session_id:
                    follow_up = _build_test_feedback(full.stdout_tail, fix_iter + 1, max_fix_iters,
                                                     failure_history=(load_failure_history(workspace, work.task.id) if work and work.task else ""))
                    if baseline_result:
                        from ..testing.runner import compare_results, format_regression_info
                        regression = compare_results(baseline_result, full)
                        regression_text = format_regression_info(regression)
                        if regression_text:
                            follow_up += f"\n\n## 回归分析\n{regression_text}"
                    cli_result = _run_cli(follow_up, role=role, workspace=workspace,
                                          log_file=log_file, timeout_seconds=CLI_TIMEOUT_SECONDS,
                                          resume_session_id=cli_result.session_id)
                    continue
                _handle_test_failure(workspace, work, agent_id, full.stdout_tail)
                return False

            break  # 测试全部通过

    # 7. FINALIZE
    if work and work.task:
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


def _build_test_feedback(test_output: str, attempt: int, max_attempts: int, failure_history: str = "") -> str:
    strategy_hints = {
        1: "如果第一次修复没有解决问题，请换一种完全不同的方案，不要在同一方向继续。",
        2: "最后一次机会。请考虑：(1) 是否理解错了需求？(2) 是否改错了文件？(3) 是否需要回滚部分改动？",
    }
    hint = strategy_hints.get(attempt, "")

    parts = [f"## 测试失败（第 {attempt}/{max_attempts} 次修复机会）\n", test_output, ""]
    if hint:
        parts.extend([f"## 策略提示\n\n{hint}", ""])
    if failure_history.strip():
        parts.extend([
            "## 此任务的历史失败记录",
            "以下方法在之前的 session 中已尝试并失败：",
            failure_history[:1500],
            "",
        ])
    parts.append("请根据以上测试结果修复代码。只修复失败的部分，不要做无关改动。")
    return "\n".join(parts)


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

    output_file = log_file.parent / "cli_output.md"
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
