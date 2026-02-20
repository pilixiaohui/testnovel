"""团队健康监控 — 检测卡住的 agent、超时任务、完成状态。

通过回调函数解耦通知逻辑，通知失败不影响监控本身。
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .spawner import DockerAgent, is_agent_alive, restart_agent
from .state import get_team_state
from .crash_tracker import CrashTracker
from ..config import TASK_CLAIM_TIMEOUT_MINUTES
from ..types import Task

logger = logging.getLogger(__name__)

# 回调类型
OnAgentCrash = Callable[[str], None]            # (agent_id)
OnCompletion = Callable[[int, int], None]       # (done_count, failed_count)
OnNeedsInput = Callable[[list[Task]], None]     # (new_needs_input_tasks)
OnConvergence = Callable[[], None]              # 所有 agent 空闲且无可做工作
OnBlocked = Callable[[list[Task]], None]        # (new_blocked_tasks)
OnProgress = Callable[[str], None]              # (progress_message)


def _parse_iso8601(s: str) -> datetime | None:
    if not s:
        return None
    raw = s.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _release_lock_in_upstream(upstream_path: Path, lock_rel_path: str, message: str) -> None:
    """从 upstream 克隆并删除锁文件，然后提交推送。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir) / "repo"
        subprocess.run(
            ["git", "clone", str(upstream_path), str(ws)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        subprocess.run(["git", "config", "user.email", "orchestrator-monitor@local"], cwd=ws, check=True)
        subprocess.run(["git", "config", "user.name", "orchestrator-monitor"], cwd=ws, check=True)

        p = ws / lock_rel_path
        if p.exists():
            p.unlink()

        subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ws)
        if diff.returncode == 0:
            return  # nothing to commit

        subprocess.run(["git", "commit", "-m", message], cwd=ws, check=True, capture_output=True, text=True, timeout=60)
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=ws,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip() or "main"
        push = subprocess.run(
            ["git", "push", "origin", branch],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if push.returncode != 0:
            # 可能与 agent 的 push 竞争；下一轮监控会再次尝试，无需中断 monitor
            logger.warning(
                "monitor push failed while releasing stale lock: %s",
                (push.stderr or push.stdout or "").strip()[:500],
            )
            return


def monitor_loop(
    *,
    upstream_path: Path,
    agents: list[DockerAgent],
    project_root: Path,
    image: str | None = None,
    check_interval: int = 60,
    max_checks: int = 0,
    on_agent_crash: OnAgentCrash | None = None,
    on_completion: OnCompletion | None = None,
    on_needs_input: OnNeedsInput | None = None,
    on_convergence: OnConvergence | None = None,
    on_blocked: OnBlocked | None = None,
    on_progress: OnProgress | None = None,
) -> None:
    """监控循环。max_checks=0 表示无限。"""
    # 初始化崩溃追踪器
    crash_tracker = CrashTracker(project_root / ".agent-crash-history.json")

    _idle_rounds = 0  # 连续空闲轮次计数（收敛检测）
    _notified_needs_input: set[str] = set()  # 去重：已通知的 needs_input 任务 ID
    _notified_blocked: set[str] = set()      # 去重：已通知的 blocked 任务 ID
    _prev_claimed: set[str] = set()          # 上一轮 claimed 任务 ID（进度检测）
    _prev_done: set[str] = set()             # 上一轮 done 任务 ID（进度检测）
    _prev_failed: set[str] = set()           # 上一轮 failed 任务 ID（进度检测）
    checks = 0
    while max_checks == 0 or checks < max_checks:
        checks += 1
        try:
            converged = _check_once(
                upstream_path=upstream_path,
                agents=agents,
                project_root=project_root,
                image=image,
                crash_tracker=crash_tracker,
                on_agent_crash=on_agent_crash,
                on_completion=on_completion,
                on_needs_input=on_needs_input,
                on_blocked=on_blocked,
                on_progress=on_progress,
                _notified_needs_input=_notified_needs_input,
                _notified_blocked=_notified_blocked,
                _prev_claimed=_prev_claimed,
                _prev_done=_prev_done,
                _prev_failed=_prev_failed,
            )
            if converged:
                _idle_rounds += 1
                if _idle_rounds >= 3 and on_convergence:
                    on_convergence()
                    _idle_rounds = 0  # 重置，避免重复触发
            else:
                _idle_rounds = 0
        except Exception as e:
            logger.error("monitor error: %s", e)

        time.sleep(check_interval)


def _check_once(
    *,
    upstream_path: Path,
    agents: list[DockerAgent],
    project_root: Path,
    image: str | None,
    crash_tracker: CrashTracker,
    on_agent_crash: OnAgentCrash | None = None,
    on_completion: OnCompletion | None = None,
    on_needs_input: OnNeedsInput | None = None,
    on_blocked: OnBlocked | None = None,
    on_progress: OnProgress | None = None,
    _notified_needs_input: set[str] | None = None,
    _notified_blocked: set[str] | None = None,
    _prev_claimed: set[str] | None = None,
    _prev_done: set[str] | None = None,
    _prev_failed: set[str] | None = None,
) -> bool:
    """单次检查。返回 True 表示团队处于空闲/收敛状态。"""
    # 0. 从 upstream 同步任务状态到主仓库
    from ..scm.sync import sync_from_upstream
    sync_from_upstream(project_root, upstream_path)

    # 1. 检查容器存活
    for i, agent in enumerate(agents):
        if not is_agent_alive(agent):
            # 已暂停的 agent 不再重复处理（避免重复创建 blocked 任务）
            if crash_tracker.should_restart(agent.agent_id) is False and \
               agent.agent_id in crash_tracker.histories and \
               crash_tracker.histories[agent.agent_id].is_suspended:
                continue

            # 读取日志尾部
            log_tail = _read_agent_log_tail(project_root, agent.agent_id)

            # 智能故障分类
            failure_type = _classify_failure(log_tail)

            # 记录崩溃
            crash_tracker.record_crash(
                agent_id=agent.agent_id,
                role=agent.role,
                reason=failure_type,
                log_tail=log_tail,
            )

            # 环境类故障：输出可操作的建议
            if failure_type.startswith("env_") and on_progress:
                on_progress(
                    f"⚠️ Agent {agent.agent_id} failed due to environment issue: {failure_type}\n"
                    f"   Fix: rebuild image with `python -m orchestrator_v2 team --build`"
                )

            # 判断是否应该重启
            if crash_tracker.should_restart(agent.agent_id):
                logger.warning("agent %s is dead (%s), restarting (crash count: %d)",
                             agent.agent_id, failure_type, len(crash_tracker.get_recent_crashes(agent.agent_id)))
                agents[i] = restart_agent(agent, project_root, image)
                if on_agent_crash:
                    on_agent_crash(agent.agent_id)
            else:
                # 达到崩溃阈值，创建 assistant 任务
                logger.error("agent %s crashed too many times, creating assistant task", agent.agent_id)
                task_id = _create_crash_analysis_task(
                    project_root=project_root,
                    agent_id=agent.agent_id,
                    role=agent.role,
                    crashes=crash_tracker.get_recent_crashes(agent.agent_id),
                )
                crash_tracker.suspend_agent(agent.agent_id, task_id)
                if on_progress:
                    on_progress(f"⚠️ Agent {agent.agent_id} suspended after repeated crashes. Created {task_id} for analysis.")

    # 2. 检查团队状态
    state = get_team_state(upstream_path)

    # 2b. 检测超时锁（time blindness 对策）— 使用 heartbeat_at 优先
    now = datetime.now(timezone.utc)
    stale_locks: list[str] = []
    active_lock_count = 0
    for lock in state.locks:
        started = _parse_iso8601(lock.started_at) if lock.started_at else None
        heartbeat = _parse_iso8601(lock.heartbeat_at or "")
        last = heartbeat or started
        if last is None:
            continue

        age_minutes = (now - last).total_seconds() / 60.0
        if age_minutes <= TASK_CLAIM_TIMEOUT_MINUTES:
            active_lock_count += 1
            continue

        stale_locks.append(lock.key)
        logger.warning(
            "stale lock detected: key=%s agent=%s age=%.1fmin (timeout=%dmin) last=%s",
            lock.key,
            lock.agent_id,
            age_minutes,
            TASK_CLAIM_TIMEOUT_MINUTES,
            (lock.heartbeat_at or lock.started_at or "")[:32],
        )

        # 释放锁（允许其他 agent 接手）
        if lock.path:
            _release_lock_in_upstream(
                upstream_path,
                lock.path,
                message=f"monitor: release stale lock {lock.key} ({lock.agent_id})",
            )

        # 记录崩溃并判断是否重启
        log_tail = _read_agent_log_tail(project_root, lock.agent_id)
        crash_tracker.record_crash(
            agent_id=lock.agent_id,
            role="unknown",  # 从 agents 列表中查找
            reason="timeout_lock",
            task_id=lock.key.removeprefix("manual/") if lock.key.startswith("manual/") else None,
            log_tail=log_tail,
        )

        # 重启对应 agent（若存在且未达到阈值）
        for idx, agent in enumerate(agents):
            if agent.agent_id == lock.agent_id:
                if crash_tracker.should_restart(agent.agent_id):
                    logger.warning("restarting agent %s after timeout (crash count: %d)",
                                 agent.agent_id, len(crash_tracker.get_recent_crashes(agent.agent_id)))
                    agents[idx] = restart_agent(agent, project_root, image)
                    if on_agent_crash:
                        on_agent_crash(agent.agent_id)
                else:
                    # 已暂停的 agent 不再重复创建任务
                    if agent.agent_id in crash_tracker.histories and \
                       crash_tracker.histories[agent.agent_id].is_suspended:
                        logger.debug("agent %s already suspended, skipping task creation", agent.agent_id)
                    else:
                        logger.error("agent %s timed out too many times, creating assistant task", agent.agent_id)
                        task_id = _create_crash_analysis_task(
                            project_root=project_root,
                            agent_id=agent.agent_id,
                            role=agent.role,
                            crashes=crash_tracker.get_recent_crashes(agent.agent_id),
                        )
                        crash_tracker.suspend_agent(agent.agent_id, task_id)
                        if on_progress:
                            on_progress(f"⚠️ Agent {agent.agent_id} suspended after repeated timeouts. Created {task_id} for analysis.")
                break

    # 3. 检查是否有需要人工决策的任务（去重：只通知新出现的）
    if _notified_needs_input is not None:
        if state.needs_input_tasks and on_needs_input:
            new_tasks = [t for t in state.needs_input_tasks if t.id not in _notified_needs_input]
            if new_tasks:
                on_needs_input(new_tasks)
                _notified_needs_input.update(t.id for t in new_tasks)
        # 清理已不在 needs_input 的 ID（任务被回复后移走）
        current_ids = {t.id for t in state.needs_input_tasks}
        _notified_needs_input &= current_ids
    elif state.tasks_needs_input > 0 and on_needs_input:
        on_needs_input(state.needs_input_tasks)

    # 3b. 检查是否有 blocked 任务（去重：只通知新出现的）
    if _notified_blocked is not None:
        if state.blocked_tasks and on_blocked:
            new_blocked = [t for t in state.blocked_tasks if t.id not in _notified_blocked]
            if new_blocked:
                on_blocked(new_blocked)
                _notified_blocked.update(t.id for t in new_blocked)
        current_ids = {t.id for t in state.blocked_tasks}
        _notified_blocked &= current_ids
    elif state.tasks_blocked > 0 and on_blocked:
        on_blocked(state.blocked_tasks)

    # 3c. 进度通知：检测新认领和新完成的任务
    if on_progress and _prev_claimed is not None and _prev_done is not None:
        current_claimed_ids: set[str] = set()
        for lock in state.locks:
            if lock.key.startswith("manual/"):
                task_id = lock.key.removeprefix("manual/")
                current_claimed_ids.add(task_id)

        newly_claimed = current_claimed_ids - _prev_claimed
        for tid in sorted(newly_claimed):
            agent = next((l.agent_id for l in state.locks if l.key == f"manual/{tid}"), "?")
            on_progress(f"Task {tid} claimed by {agent}")

        # done 检测：用实际任务列表对比，输出具体任务 ID 和 agent
        current_done_ids = {t.id for t in state.done_tasks}
        newly_done = current_done_ids - _prev_done
        for tid in sorted(newly_done):
            task = next((t for t in state.done_tasks if t.id == tid), None)
            agent = task.agent_id if task and task.agent_id else "?"
            title = task.title if task else ""
            on_progress(
                f"Task {tid} completed by {agent}: {title}\n"
                f"(total: {state.tasks_done} done, {state.tasks_failed} failed, "
                f"{state.tasks_available} remaining)"
            )

        # failed 检测
        current_failed_ids = {t.id for t in state.failed_tasks}
        if _prev_failed is not None:
            newly_failed = current_failed_ids - _prev_failed
            for tid in sorted(newly_failed):
                task = next((t for t in state.failed_tasks if t.id == tid), None)
                agent = task.agent_id if task and task.agent_id else "?"
                title = task.title if task else ""
                on_progress(f"Task {tid} FAILED ({agent}): {title}")
            _prev_failed.clear()
            _prev_failed.update(current_failed_ids)

        _prev_claimed.clear()
        _prev_claimed.update(current_claimed_ids)
        _prev_done.clear()
        _prev_done.update(current_done_ids)

    # 4. 检查是否所有任务完成
    if (
        state.tasks_available == 0
        and state.tasks_claimed == 0
        and state.tasks_needs_input == 0
        and state.tasks_blocked == 0
    ):
        logger.info("All tasks complete! Done: %d, Failed: %d", state.tasks_done, state.tasks_failed)
        if on_completion:
            on_completion(state.tasks_done, state.tasks_failed)

    # 5. 收敛检测：无可用任务、无 claimed，且 TTL 内无活跃心跳锁（stale 锁不算活跃）
    converged = (
        state.tasks_available == 0
        and state.tasks_claimed == 0
        and state.tasks_needs_input == 0
        and state.tasks_blocked == 0
        and active_lock_count == 0
        and not stale_locks
    )

    logger.info(
        "monitor: locks=%d(active=%d stale=%d) available=%d claimed=%d done=%d failed=%d needs_input=%d blocked=%d converged=%s",
        state.locks_active,
        active_lock_count,
        len(stale_locks),
        state.tasks_available, state.tasks_claimed, state.tasks_done,
        state.tasks_failed, state.tasks_needs_input, state.tasks_blocked,
        converged,
    )
    return converged


def _read_agent_log_tail(project_root: Path, agent_id: str, lines: int = 100) -> str:
    """读取 agent 日志的最后N行。"""
    _ = project_root  # 保留参数以保持 API 兼容性
    from ..config import AGENT_LOG_DIR

    log_file = AGENT_LOG_DIR / f"{agent_id}.log"
    if not log_file.exists():
        return "(log file not found)"

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return "".join(tail)
    except Exception as e:
        return f"(failed to read log: {e})"


def _classify_failure(log_tail: str) -> str:
    """从日志尾部识别失败类型。"""
    patterns = [
        ("env_missing_key", "Missing environment variable"),
        ("env_python_not_found", "python: not found"),
        ("env_module_not_found", "ERR_MODULE_NOT_FOUND"),
        ("env_import_error", "ModuleNotFoundError"),
        ("env_npm_error", "npm ERR!"),
        ("timeout_lock", "timeout"),
        ("container_dead", ""),  # 默认
    ]
    for reason, pattern in patterns:
        if pattern and pattern in log_tail:
            return reason
    return "container_dead"


def _create_crash_analysis_task(
    *,
    project_root: Path,
    agent_id: str,
    role: str,
    crashes: list,
) -> str:
    """创建 assistant 任务分析 agent 崩溃原因。"""
    from ..config import TASKS_DIR, UPSTREAM_REPO
    from ..harness.task_picker import next_task_id
    from ..scm.sync import git_commit_and_push
    from ..types import Task

    # 构建崩溃报告
    crash_summary = "\n\n".join([
        f"### 崩溃 #{i+1}\n"
        f"- **时间**: {c.timestamp}\n"
        f"- **原因**: {c.reason}\n"
        f"- **任务**: {c.task_id or 'N/A'}\n"
        f"- **日志尾部**:\n```\n{c.log_tail[-2000:]}\n```"
        for i, c in enumerate(crashes[-3:])  # 最近3次
    ])

    description = f"""# Agent 崩溃诊断报告

**Agent ID**: {agent_id}
**Role**: {role}
**崩溃次数**: {len(crashes)} (最近30分钟内)
**状态**: 已暂停，等待用户修复

## 崩溃记录

{crash_summary}

## Assistant 任务

请分析崩溃日志并创建诊断报告：

1. **识别问题类别**：
   - 代码bug（orchestrator代码）
   - 配置错误
   - 环境问题（Docker、依赖）
   - 任务问题（特定任务导致崩溃）

2. **创建事故报告**：
   - 在 `decisions/incidents/INCIDENT-{{timestamp}}.md` 创建报告
   - 包含：问题摘要、崩溃日志、根因分析、建议修复步骤

3. **通知用户**：
   - 通过飞书发送通知
   - 说明问题类别和建议操作
   - 提供事故报告链接

**重要**: 不要修改 orchestrator_v2/ 下的代码。这些代码由用户维护。

完成分析后，用户将修复问题并运行：
`python -m orchestrator_v2 resume-agent {agent_id}`
"""

    task_id = next_task_id(TASKS_DIR)
    task = Task(
        id=task_id,
        title=f"[系统故障] Agent {agent_id} 反复崩溃 - 需要用户介入",
        description=description,
        role="assistant",
        priority=0,  # 最高优先级
        status="blocked",
    )

    # Write directly to tasks/blocked/ (create_task always writes to available/)
    from ..harness.task_picker import serialize_task
    blocked_dir = TASKS_DIR / "blocked"
    blocked_dir.mkdir(parents=True, exist_ok=True)
    task_path = blocked_dir / f"{task_id}.md"
    task_path.write_text(serialize_task(task), encoding="utf-8")
    git_commit_and_push(project_root, f"monitor: create crash analysis task {task_id}", remote=str(UPSTREAM_REPO))

    logger.info("created crash analysis task %s for agent %s", task_id, agent_id)
    return task_id

