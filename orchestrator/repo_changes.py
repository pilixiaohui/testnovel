from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import TypedDict


class GitStatusEntry(TypedDict):
    code: str  # two-letter XY status, e.g. " M", "??", "R "
    path: str  # path (for rename/copy: the NEW path)
    orig_path: str | None  # old path for rename/copy


def _sha256_file_bytes(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_git_status_porcelain_z(*, project_root: Path) -> list[GitStatusEntry]:
    """
    Return `git status --porcelain=v1 -z` entries.

    Notes:
    - With `-z`, records are NUL-separated.
    - For rename/copy, the record contains the **new** path, and the **old** path is the next NUL token.
    """
    proc = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z"],
        cwd=project_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    data = proc.stdout
    if not data:
        return []

    tokens = data.split(b"\0")
    entries: list[GitStatusEntry] = []
    i = 0
    while i < len(tokens):
        raw = tokens[i]
        if not raw:
            break
        line = raw.decode("utf-8", errors="surrogateescape")
        if len(line) < 4 or line[2] != " ":
            raise RuntimeError(f"Unexpected git status porcelain record: {line!r}")
        code = line[:2]
        path = line[3:]
        orig_path: str | None = None
        if "R" in code or "C" in code:
            # rename/copy includes an extra path token (the OLD path); the record path is the NEW path.
            i += 1
            if i >= len(tokens) or not tokens[i]:
                raise RuntimeError(f"Missing old path for rename/copy record: {line!r}")
            orig_path = tokens[i].decode("utf-8", errors="surrogateescape")
        entries.append({"code": code, "path": path, "orig_path": orig_path})
        i += 1
    return entries


def capture_dirty_file_digests(
    *,
    project_root: Path,
    exclude_prefixes: tuple[str, ...] = (),
) -> dict[str, str | None]:
    """
    Capture sha256 digests for files that are currently 'dirty' in git (modified/staged/untracked).

    Returns:
      { "relative/path": "<sha256>" | None } where None means the path is missing on disk (e.g. deleted).
    """
    entries = _run_git_status_porcelain_z(project_root=project_root)
    snapshots: dict[str, str | None] = {}

    for item in entries:
        path = item["path"]
        if any(path.startswith(prefix) for prefix in exclude_prefixes):
            continue
        abs_path = project_root / path
        if abs_path.exists() and abs_path.is_file():
            snapshots[path] = _sha256_file_bytes(abs_path)
        else:
            snapshots[path] = None

    return snapshots


def diff_dirty_file_digests(
    before: dict[str, str | None],
    after: dict[str, str | None],
) -> list[str]:
    """
    Return paths whose digest/presence differs between before/after snapshots.
    """
    changed: list[str] = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path):
            changed.append(path)
    return changed
