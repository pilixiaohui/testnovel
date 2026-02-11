from __future__ import annotations

import hashlib
import json
import shutil

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import PROJECT_ROOT
from .runtime_context import RuntimeContext

MIRROR_DIR_NAME = ".orchestrator_ctx"
MIRROR_MANIFEST_NAME = ".sync_manifest.json"
MIRROR_SUBDIRS: tuple[str, ...] = ("memory", "workspace", "reports")


@dataclass(frozen=True)
class MirrorSyncResult:
    mirror_root: Path
    files_synced: int
    content_hash: str
    triggered_by: str
    synced_at_utc: str


def get_project_mirror_root(context: RuntimeContext) -> Path:
    return context.agent_root / MIRROR_DIR_NAME


def _iter_markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() == ".md":
            files.append(path)
    return sorted(files)


def _compute_markdown_tree_hash(*, mirror_root: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    files_count = 0

    for subdir in MIRROR_SUBDIRS:
        current = mirror_root / subdir
        if not current.is_dir():
            raise RuntimeError(f"Missing mirror subdir: {current.as_posix()}")
        for path in _iter_markdown_files(current):
            rel = path.relative_to(mirror_root).as_posix()
            payload = path.read_bytes()
            files_count += 1
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(payload)
            digest.update(b"\0")

    if files_count == 0:
        raise RuntimeError(f"No markdown files found in mirror root: {mirror_root.as_posix()}")

    return digest.hexdigest(), files_count


def sync_project_markdown_mirror(
    *,
    context: RuntimeContext,
    iteration: int,
    triggered_by: str,
) -> MirrorSyncResult:
    if not triggered_by.strip():
        raise RuntimeError("triggered_by must be non-empty")

    source_root = PROJECT_ROOT / "orchestrator"
    if not source_root.is_dir():
        raise RuntimeError(f"Missing orchestrator source root: {source_root.as_posix()}")

    mirror_root = get_project_mirror_root(context)
    mirror_root.mkdir(parents=True, exist_ok=True)

    for subdir in MIRROR_SUBDIRS:
        src_dir = source_root / subdir
        if not src_dir.is_dir():
            raise RuntimeError(f"Missing orchestrator subdir: {src_dir.as_posix()}")

        dst_dir = mirror_root / subdir
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)

        for source_file in _iter_markdown_files(src_dir):
            rel = source_file.relative_to(src_dir)
            target_file = dst_dir / rel
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(source_file.read_bytes())

    content_hash, files_synced = _compute_markdown_tree_hash(mirror_root=mirror_root)
    synced_at_utc = datetime.now(timezone.utc).isoformat()

    manifest = {
        "schema_version": 1,
        "source_root": source_root.as_posix(),
        "mirror_root": mirror_root.as_posix(),
        "subdirs": list(MIRROR_SUBDIRS),
        "files_synced": files_synced,
        "content_hash": content_hash,
        "iteration": iteration,
        "triggered_by": triggered_by,
        "synced_at_utc": synced_at_utc,
    }
    (mirror_root / MIRROR_MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return MirrorSyncResult(
        mirror_root=mirror_root,
        files_synced=files_synced,
        content_hash=content_hash,
        triggered_by=triggered_by,
        synced_at_utc=synced_at_utc,
    )


def assert_project_mirror_unchanged(*, mirror_root: Path, expected_hash: str, stage: str) -> None:
    current_hash, _ = _compute_markdown_tree_hash(mirror_root=mirror_root)
    if current_hash != expected_hash:
        raise RuntimeError(
            f"project mirror modified during {stage}: {mirror_root.as_posix()} "
            "(mirror is read-only; edits must target orchestrator blackboard)"
        )
