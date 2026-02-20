"""Git 同步协议 — Agent 团队通过 bare upstream repo 同步代码。

对标博客："A new bare git repo is created, and for each agent,
a Docker container is spun up with the repo mounted to /upstream."
"""

from __future__ import annotations

import fnmatch
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# 敏感文件模式 — git add -A 后自动 unstage
_SENSITIVE_PATTERNS = [".env", ".env.*", "*.key", "*.pem", "*.p12", "credentials*", "*secret*"]

# 元数据路径前缀 — 冲突时可程序化解决，跳过 CI 门禁
_METADATA_PREFIXES = ("current_tasks/", "tasks/", "decisions/", "features/", "doc/", "spec_code/", "openspec/")
_METADATA_FILES = ("PROGRESS.md", "PROJECT_CHARTER.md", "SIGNALS.md", "DISCOVERIES.md", ".gitignore")


@dataclass
class GitOpResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    conflict: bool = False
    rejected: bool = False  # e.g. pre-receive hook declined


def _git(args: list[str], *, cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )


def _get_branch(workspace: Path) -> str:
    """检测当前分支名。"""
    r = _git(["branch", "--show-current"], cwd=workspace)
    return r.stdout.strip() or "main"


def _get_local_origin_path(workspace: Path) -> Path | None:
    """获取 origin 的本地文件路径（失败返回 None）。"""
    r = _git(["config", "--get", "remote.origin.url"], cwd=workspace)
    if r.returncode != 0:
        return None

    raw = r.stdout.strip()
    if not raw or raw.startswith("http://") or raw.startswith("https://") or raw.startswith("ssh://") or raw.startswith("git@"):
        return None

    # git 在 local remote 常见形态是裸路径；file:// 需要去掉前缀
    if raw.startswith("file://"):
        raw = raw.removeprefix("file://")

    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (workspace / raw).resolve()
    return candidate


def _fallback_push_with_fetch(workspace: Path, branch: str) -> GitOpResult:
    """当本地 push 走迁移路径报 EXDEV 时，退化为 fetch，保留基本快进校验语义。"""
    upstream = _get_local_origin_path(workspace)
    if upstream is None:
        return GitOpResult(
            ok=False,
            returncode=1,
            stdout="",
            stderr="git_push fallback: origin is not local path",
        )

    r = _git(["--git-dir", str(upstream), "fetch", str(workspace), f"refs/heads/{branch}:refs/heads/{branch}"], cwd=workspace)
    if r.returncode != 0:
        combined = (r.stdout or "") + "\n" + (r.stderr or "")
        return GitOpResult(
            ok=False,
            returncode=r.returncode,
            stdout=r.stdout,
            stderr=r.stderr,
            conflict=_is_non_fast_forward(combined),
            rejected=_is_hook_rejection(combined),
        )
    return GitOpResult(ok=True, returncode=0, stdout=r.stdout, stderr=r.stderr)


def setup_upstream(project_root: Path) -> Path:
    """创建 bare upstream repo，初始推送项目代码。"""
    bare = project_root / ".agent-upstream.git"
    if bare.exists():
        logger.info("upstream repo already exists: %s", bare)
        return bare

    # 用 --bare clone 创建更稳健的镜像副本，避免本地 push 场景下的对象硬链接跨设备问题。
    try:
        subprocess.run(
            ["git", "clone", "--bare", str(project_root), str(bare)],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("created bare upstream: %s", bare)
    except subprocess.CalledProcessError as exc:
        # 兼容老路径：按旧实现 fallback 到 init+push，并在失败时显式报错，避免静默空仓库。
        logger.warning(
            "git clone --bare failed for %s: %s", project_root, (exc.stderr or "").strip()
        )
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True, text=True)
        logger.info("created bare upstream via init: %s", bare)

        branch = _git(["branch", "--show-current"], cwd=project_root).stdout.strip() or "main"
        _git(["remote", "add", "upstream", str(bare)], cwd=project_root)
        push = _git(["push", "upstream", f"HEAD:{branch}"], cwd=project_root)
        if push.returncode != 0:
            raise RuntimeError(f"failed to initialize upstream: {push.stderr.strip()}")
        _git(["remote", "remove", "upstream"], cwd=project_root)
        _git(["symbolic-ref", "HEAD", f"refs/heads/{branch}"], cwd=bare)
        logger.info("pushed project to upstream")
    return bare


def clone_workspace(upstream_path: Path, workspace_dir: Path) -> Path:
    """为 agent 克隆独立工作区。"""
    if workspace_dir.exists() and (workspace_dir / ".git").exists():
        logger.info("workspace already exists: %s", workspace_dir)
        return workspace_dir
    # 目录存在但不是 git repo（如 Docker 挂载的空目录）→ 清空内容但保留目录
    if workspace_dir.exists():
        import os, shutil
        os.chdir("/")          # 避免 cwd 被删除导致 git checkout 失败
        # 只删除目录内容，不删除目录本身（避免 Docker volume 挂载点问题）
        for item in workspace_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    workspace_dir.parent.mkdir(parents=True, exist_ok=True)
    # Docker 容器内 uid 可能与宿主不同，需要标记 safe.directory
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", str(upstream_path)],
        capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", str(workspace_dir)],
        capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "clone", str(upstream_path), str(workspace_dir)],
        check=True, capture_output=True, text=True,
    )
    # 容器内可能没有 git user 配置，commit 会失败
    subprocess.run(
        ["git", "config", "user.name", "orchestrator-agent"],
        cwd=str(workspace_dir), capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "agent@orchestrator.local"],
        cwd=str(workspace_dir), capture_output=True, text=True,
    )
    # 快速失败：团队模式必须使用本地 bare upstream repo 作为 origin
    origin_path = _get_local_origin_path(workspace_dir)
    if origin_path is None:
        raise RuntimeError("invalid origin remote: expected local bare repo path")
    if not origin_path.exists():
        raise RuntimeError(f"invalid origin remote: path not found: {origin_path}")
    if not (origin_path / "HEAD").exists() or not (origin_path / "objects").is_dir():
        raise RuntimeError(f"invalid origin remote: not a bare repo: {origin_path}")

    # 设置 push 默认分支
    _git(["config", "push.default", "current"], cwd=workspace_dir)
    logger.info("cloned workspace: %s", workspace_dir)
    return workspace_dir


def _is_rebase_conflict(output: str) -> bool:
    lowered = output.lower()
    hints = (
        "conflict",
        "could not apply",
        "resolve all conflicts",
        "fix conflicts",
        "after resolving the conflicts",
    )
    return any(h in lowered for h in hints)


def _is_non_fast_forward(output: str) -> bool:
    lowered = output.lower()
    hints = (
        "non-fast-forward",
        "fetch first",
        "failed to push some refs",
        "updates were rejected",
    )
    return any(h in lowered for h in hints)


def _is_hook_rejection(output: str) -> bool:
    lowered = output.lower()
    hints = (
        "pre-receive hook declined",
        "remote rejected",
        "hook declined",
        "ci gate failed",
    )
    return any(h in lowered for h in hints)


def git_pull(workspace: Path) -> GitOpResult:
    """从 upstream 拉取最新代码。

    发生 rebase 冲突时不做 reset/abort，留给 agent 解决（对标博客思想）。
    """
    return _git_pull_rebase(workspace)


def _git_pull_rebase(workspace: Path) -> GitOpResult:
    """执行 `git pull --rebase`。

    与 git_pull 保持一致；暴露单独入口主要用于语义清晰以及兼容历史调用点。
    """
    branch = _get_branch(workspace)
    r = _git(["pull", "--rebase", "origin", branch], cwd=workspace)
    if r.returncode != 0:
        combined = (r.stdout or "") + "\n" + (r.stderr or "")
        logger.warning("git pull failed: %s", (r.stderr or "").strip())
        return GitOpResult(
            ok=False,
            returncode=r.returncode,
            stdout=r.stdout,
            stderr=r.stderr,
            conflict=_is_rebase_conflict(combined),
        )
    return GitOpResult(ok=True, returncode=0, stdout=r.stdout, stderr=r.stderr)


def git_push(workspace: Path, *, remote: str = "origin") -> GitOpResult:
    """推送到 upstream。"""
    branch = _get_branch(workspace)
    r = _git(["push", remote, branch], cwd=workspace)
    if r.returncode != 0:
        combined = (r.stdout or "") + "\n" + (r.stderr or "")
        logger.warning("git push failed: %s", (r.stderr or "").strip())

        # 某些环境下本地仓库与 bare 仓库对象迁移会触发 EXDEV，本地路径迁移走 fetch 可避开该问题。
        if "unable to migrate objects to permanent storage" in combined:
            fallback = _fallback_push_with_fetch(workspace, branch)
            if fallback.ok:
                return fallback
            combined = (fallback.stdout or "") + "\n" + (fallback.stderr or "")
            return GitOpResult(
                ok=False,
                returncode=fallback.returncode,
                stdout=fallback.stdout,
                stderr=fallback.stderr,
                conflict=_is_non_fast_forward(combined),
                rejected=_is_hook_rejection(combined),
            )

        return GitOpResult(
            ok=False,
            returncode=r.returncode,
            stdout=r.stdout,
            stderr=r.stderr,
            conflict=_is_non_fast_forward(combined),
            rejected=_is_hook_rejection(combined),
        )
    return GitOpResult(ok=True, returncode=0, stdout=r.stdout, stderr=r.stderr)


def git_pull_rebase(workspace: Path) -> GitOpResult:
    """执行 `git pull --rebase`。发生冲突时不 abort，留给 agent 解决。"""
    return _git_pull_rebase(workspace)


def git_checkout_clean(workspace: Path) -> None:
    """丢弃所有未提交变更。"""
    _git(["checkout", "--", "."], cwd=workspace)
    _git(["clean", "-fd"], cwd=workspace)


def git_revert_to_upstream(workspace: Path) -> None:
    """重置到 upstream 当前分支。"""
    branch = _get_branch(workspace)
    _git(["fetch", "origin"], cwd=workspace)
    _git(["reset", "--hard", f"origin/{branch}"], cwd=workspace)
    _git(["clean", "-fd"], cwd=workspace)


def git_reset_to_upstream_keep_changes(workspace: Path) -> None:
    """重置分支指针到 upstream，但保留工作区改动（用于 CI/hook 拒绝等失败保留场景）。"""
    branch = _get_branch(workspace)
    _git(["fetch", "origin"], cwd=workspace)
    _git(["reset", "--mixed", f"origin/{branch}"], cwd=workspace)


def git_commit(workspace: Path, message: str, *, paths: list[str] | None = None) -> bool:
    """Add + commit。返回 True 表示有变更被提交。

    paths 为 None 时使用 git add -A（自动过滤敏感文件）；
    paths 提供时只 add 指定路径。
    """
    if paths:
        _git(["add", "--"] + paths, cwd=workspace)
    else:
        _git(["add", "-A"], cwd=workspace)
        # 安全过滤：unstage 匹配敏感模式的文件
        # 使用 -z 避免中文文件名被引号包裹
        staged = _git(["diff", "--cached", "--name-only", "-z"], cwd=workspace)
        if staged.returncode == 0 and staged.stdout.strip("\0").strip():
            for fname in staged.stdout.strip("\0").split("\0"):
                fname = fname.strip()
                if not fname:
                    continue
                basename = Path(fname).name
                if any(fnmatch.fnmatch(basename, pat) for pat in _SENSITIVE_PATTERNS):
                    _git(["reset", "HEAD", "--", fname], cwd=workspace)
                    logger.debug("unstaged sensitive file: %s", fname)
    r = _git(["diff", "--cached", "--quiet"], cwd=workspace)
    if r.returncode == 0:
        return False  # nothing to commit
    r = _git(["commit", "-m", message], cwd=workspace)
    return r.returncode == 0


def _is_metadata_path(filepath: str) -> bool:
    """判断文件路径是否属于元数据（冲突时可程序化解决）。"""
    return (
        any(filepath.startswith(p) for p in _METADATA_PREFIXES)
        or filepath in _METADATA_FILES
    )


def auto_resolve_metadata_conflict(workspace: Path) -> bool:
    """尝试程序化解决 rebase 冲突中的元数据文件。

    仅当所有冲突文件都是元数据时才处理；有非元数据冲突则返回 False。
    策略：tasks/、current_tasks/ 用 --ours；PROGRESS.md 用 --theirs（append-only）。
    """
    for _ in range(3):
        # 使用 -z 避免中文文件名被引号包裹
        r = _git(["diff", "--name-only", "--diff-filter=U", "-z"], cwd=workspace)
        if r.returncode != 0:
            return False

        conflicted = [f.strip() for f in r.stdout.strip("\0").split("\0") if f.strip()]
        if not conflicted:
            return True

        for f in conflicted:
            if not _is_metadata_path(f):
                logger.info("non-metadata conflict: %s, cannot auto-resolve", f)
                return False

        for f in conflicted:
            if f.startswith("tasks/") or f.startswith("current_tasks/"):
                _git(["checkout", "--ours", "--", f], cwd=workspace)
            else:
                _git(["checkout", "--theirs", "--", f], cwd=workspace)
            _git(["add", "--", f], cwd=workspace)

        cont = _git(["rebase", "--continue"], cwd=workspace, timeout=30)
        if cont.returncode != 0:
            logger.warning("rebase --continue failed after auto-resolve: %s", cont.stderr.strip()[:300])
            return False

        logger.info("auto-resolved metadata conflict for %d file(s)", len(conflicted))

    logger.warning("auto_resolve_metadata_conflict gave up after retries")
    return False


def git_commit_and_push(workspace: Path, message: str, max_retries: int = 3, *, remote: str = "origin") -> bool:
    """Commit + push，冲突时自动 pull rebase 重试。"""
    if not git_commit(workspace, message):
        return True  # nothing to commit is fine

    for attempt in range(max_retries):
        push = git_push(workspace, remote=remote)
        if push.ok:
            return True
        logger.info("push failed, pull rebase retry %d/%d", attempt + 1, max_retries)
        pull = git_pull_rebase(workspace)
        if not pull.ok:
            # 不做 reset --hard 兜底，交给上层（agent）决定如何处理冲突
            return False
    return False


def install_pre_receive_ci_hook(upstream_bare_repo: Path) -> Path:
    """安装 pre-receive 钩子：push 时在干净工作树中跑 commands.ci。

    - 仅当变更包含非元数据文件时才执行 CI（current_tasks/, tasks/, PROGRESS.md 为元数据）。
    - 失败时拒绝 push，并输出：
      - ERROR: <reason>
      - LOG: <path>
    """
    hooks_dir = upstream_bare_repo / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-receive"

    script = """#!/bin/bash
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/ci_logs"
mkdir -p "$LOG_DIR"

is_metadata_only() {
  local oldrev="$1"
  local newrev="$2"

  # new branch: oldrev is all zeros; treat as non-metadata by default and let CI decide.
  if [[ "$oldrev" =~ ^0+$ ]]; then
    return 1
  fi

  local changed
  # 使用 -z 避免中文文件名被引号包裹；不用 --git-dir 以兼容 quarantine 环境
  changed="$(git diff -z --name-only "$oldrev" "$newrev" 2>/dev/null | tr '\\0' '\\n')" || true
  if [[ -z "$changed" ]]; then
    return 0
  fi

  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    # 去掉可能残留的引号
    f="${f#\\"}"
    f="${f%\\"}"
    if [[ "$f" == current_tasks/* || "$f" == tasks/* || "$f" == decisions/* || "$f" == features/* || "$f" == doc/* || "$f" == spec_code/* || "$f" == openspec/* || "$f" == PROGRESS.md || "$f" == SIGNALS.md || "$f" == DISCOVERIES.md || "$f" == PROJECT_CHARTER.md || "$f" == .gitignore ]]; then
      continue
    fi
    return 1
  done <<< "$changed"
  return 0
}

run_ci_for_rev() {
  local newrev="$1"

  local tmp
  tmp="$(mktemp -d)"

  # 使用 git archive 兼容 quarantine 环境，fallback 到 clone
  git archive "$newrev" | tar -x -C "$tmp" 2>/dev/null || {
    rm -rf "$tmp/repo"
    git clone "$ROOT" "$tmp/repo" >/dev/null 2>&1 || {
      rm -rf "$tmp"
      echo "remote: ERROR: cannot create work tree for CI" >&2
      exit 1
    }
    cd "$tmp/repo"
    git checkout -q "$newrev" 2>/dev/null || {
      rm -rf "$tmp"
      echo "remote: ERROR: cannot checkout $newrev for CI" >&2
      exit 1
    }
  }
  if [[ ! -d "$tmp/repo" ]]; then
    cd "$tmp"
  fi

  local ci_cmd
  ci_cmd="$(python3 - <<'PY'
import json
from pathlib import Path
p = Path("project_env.json")
if not p.exists():
    print("")
    raise SystemExit(0)
env = json.loads(p.read_text(encoding="utf-8"))
cmd = (env.get("commands") or {}).get("ci") or ""
print(cmd)
PY
)"

  if [[ -z "$ci_cmd" ]]; then
    rm -rf "$tmp"
    echo "remote: WARNING: no CI command configured, skipping CI gate" >&2
    exit 0
  fi

  local ts sha log
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  sha="${newrev:0:12}"
  log="$LOG_DIR/ci_${ts}_${sha}.log"

  set +e
  bash -lc "$ci_cmd" >"$log" 2>&1
  local rc=$?
  set -e
  rm -rf "$tmp"

  if [[ $rc -ne 0 ]]; then
    echo "remote: ERROR: CI gate failed (rc=$rc)" >&2
    echo "remote: LOG: $log" >&2
    exit 1
  fi
}

while read -r oldrev newrev refname; do
  # branch deletion
  if [[ "$newrev" =~ ^0+$ ]]; then
    continue
  fi

  if is_metadata_only "$oldrev" "$newrev"; then
    continue
  fi

  run_ci_for_rev "$newrev"
done
"""

    hook_path.write_text(script, encoding="utf-8")
    hook_path.chmod(0o755)
    logger.info("installed pre-receive CI hook at %s", hook_path)
    return hook_path


def sync_to_upstream(project_root: Path, upstream: Path) -> None:
    """将 PROJECT_ROOT 的当前分支推送到 upstream bare repo，确保二者同步。"""
    branch = _get_branch(project_root)
    r = _git(["push", str(upstream), f"HEAD:{branch}"], cwd=project_root)
    if r.returncode != 0:
        logger.warning("sync to upstream failed: %s", r.stderr.strip()[:200])


def sync_from_upstream(project_root: Path, upstream_path: Path) -> bool:
    """从 upstream 同步任务状态到主仓库。

    仅同步任务元数据目录（tasks/, current_tasks/, .agent-crash-history.json），
    避免同步代码变更导致主仓库被污染。

    返回 True 表示同步成功，False 表示失败。
    """
    if not upstream_path.exists():
        logger.warning("upstream repo not found: %s", upstream_path)
        return False

    # 检查主仓库是否有未提交的变更
    status = _git(["status", "--porcelain"], cwd=project_root)
    if status.stdout.strip():
        logger.debug("project_root has uncommitted changes, skipping sync_from_upstream")
        return True  # 不算失败，只是跳过

    # 添加 upstream 为 remote（如果不存在）
    remotes = _git(["remote"], cwd=project_root)
    if "agent-upstream" not in remotes.stdout:
        _git(["remote", "add", "agent-upstream", str(upstream_path)], cwd=project_root)
        logger.debug("added agent-upstream remote")

    # Fetch upstream 的最新状态
    branch = _get_branch(project_root)
    fetch = _git(["fetch", "agent-upstream", branch], cwd=project_root, timeout=10)
    if fetch.returncode != 0:
        logger.warning("fetch from upstream failed: %s", fetch.stderr.strip()[:200])
        return False

    # 检查是否有需要同步的变更
    diff = _git(["diff", "--name-only", f"HEAD..agent-upstream/{branch}"], cwd=project_root)
    if not diff.stdout.strip():
        return True  # 没有变更，同步成功

    changed_files = [f.strip() for f in diff.stdout.strip().split("\n") if f.strip()]

    # 只同步元数据文件
    metadata_files = [
        f for f in changed_files
        if _is_metadata_path(f) or f == ".agent-crash-history.json"
    ]

    if not metadata_files:
        logger.debug("no metadata changes to sync from upstream")
        return True

    logger.info("syncing %d metadata file(s) from upstream: %s",
                len(metadata_files), ", ".join(metadata_files[:5]))

    # 使用 checkout 逐个同步元数据文件（避免 merge 冲突）
    for f in metadata_files:
        checkout = _git(["checkout", f"agent-upstream/{branch}", "--", f], cwd=project_root)
        if checkout.returncode != 0:
            logger.warning("failed to checkout %s from upstream: %s", f, checkout.stderr.strip()[:100])
            continue

    # 提交同步的变更
    committed = git_commit(project_root, "[monitor] sync task metadata from upstream")
    if committed:
        logger.info("synced metadata from upstream and committed")

    return True
