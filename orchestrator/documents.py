from __future__ import annotations

import base64
import binascii
import json
import re

from datetime import datetime
from pathlib import Path

from .config import FINISH_REVIEW_CONFIG_FILE, PROJECT_ROOT, UPLOADED_DOCS_CATEGORIES, UPLOADED_DOCS_DIR, UPLOADED_DOCS_MAX_BYTES
from .file_ops import _atomic_write_text, _read_text, _require_file
from .types import UploadedDocument

_FILENAME_RE = re.compile(r"^[\w-]+\.md$")


def _ensure_uploaded_dirs() -> None:
    for category in UPLOADED_DOCS_CATEGORIES:
        (UPLOADED_DOCS_DIR / category).mkdir(parents=True, exist_ok=True)


def _validate_category(category: str) -> None:
    if category not in UPLOADED_DOCS_CATEGORIES:
        raise ValueError(f"invalid category: {category!r}")


def _validate_filename(filename: str) -> None:
    if not _FILENAME_RE.fullmatch(filename):
        raise ValueError("filename must match ^[A-Za-z0-9_-]+\\.md$")


def resolve_uploaded_doc_path(doc_path: str) -> Path:
    if not isinstance(doc_path, str) or not doc_path.strip():
        raise ValueError("doc_path is required")
    if "\x00" in doc_path:
        raise ValueError("doc_path contains null byte")
    raw = Path(doc_path)
    if raw.is_absolute():
        raise ValueError("doc_path must be relative")

    base = UPLOADED_DOCS_DIR.resolve()
    resolved = (UPLOADED_DOCS_DIR / raw).resolve()
    try:
        rel = resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError("doc_path is outside uploaded_docs") from exc
    if not rel.parts or rel.parts[0] not in UPLOADED_DOCS_CATEGORIES:
        raise ValueError("doc_path must start with a valid category")
    if resolved.suffix.lower() != ".md":
        raise ValueError("doc_path must end with .md")
    return resolved


def list_uploaded_docs() -> list[UploadedDocument]:
    _ensure_uploaded_dirs()
    docs: list[UploadedDocument] = []
    for category in UPLOADED_DOCS_CATEGORIES:
        root = UPLOADED_DOCS_DIR / category
        for path in sorted(root.glob("*.md")):
            stat = path.stat()
            docs.append(
                {
                    "filename": path.name,
                    "path": f"{category}/{path.name}",
                    "category": category,
                    "size": int(stat.st_size),
                    "upload_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                }
            )
    return docs


def store_uploaded_doc(*, filename: str, content_b64: str, category: str) -> str:
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename is required")
    if not isinstance(content_b64, str) or not content_b64.strip():
        raise ValueError("content is required")
    if not isinstance(category, str) or not category.strip():
        raise ValueError("category is required")

    _validate_category(category.strip())
    _validate_filename(filename.strip())
    _ensure_uploaded_dirs()

    try:
        raw = base64.b64decode(content_b64.encode("utf-8"), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("content is not valid base64") from exc

    if len(raw) > UPLOADED_DOCS_MAX_BYTES:
        raise ValueError(f"file too large: {len(raw)} > {UPLOADED_DOCS_MAX_BYTES}")

    try:
        content_text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("file content must be UTF-8") from exc

    target_dir = UPLOADED_DOCS_DIR / category.strip()
    target_name = filename.strip()
    target_path = target_dir / target_name

    if target_path.exists():
        stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        target_name = f"{Path(target_name).stem}_{stamp}.md"
        target_path = target_dir / target_name
        if target_path.exists():
            raise RuntimeError(f"upload target already exists: {target_path}")

    _atomic_write_text(target_path, content_text)
    return f"{category.strip()}/{target_name}"


def delete_uploaded_doc(doc_path: str) -> None:
    path = resolve_uploaded_doc_path(doc_path)
    if not path.exists():
        raise FileNotFoundError(f"doc not found: {doc_path}")
    path.unlink()


def get_finish_review_docs() -> list[str]:
    _require_file(FINISH_REVIEW_CONFIG_FILE)
    raw = _read_text(FINISH_REVIEW_CONFIG_FILE)
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("finish_review_config must be an object")
    docs = payload.get("docs")
    if not isinstance(docs, list) or not all(isinstance(item, str) for item in docs):
        raise ValueError("finish_review_config.docs must be a list of strings")
    return docs


def add_doc_to_finish_review_config(doc_path: str) -> str:
    path = resolve_uploaded_doc_path(doc_path)
    if not path.exists():
        raise FileNotFoundError(f"doc not found: {doc_path}")

    _require_file(FINISH_REVIEW_CONFIG_FILE)
    raw = _read_text(FINISH_REVIEW_CONFIG_FILE)
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("finish_review_config must be an object")
    docs = payload.get("docs")
    if not isinstance(docs, list) or not all(isinstance(item, str) for item in docs):
        raise ValueError("finish_review_config.docs must be a list of strings")

    rel_path = path.relative_to(PROJECT_ROOT).as_posix()
    if rel_path not in docs:
        docs.append(rel_path)
    payload["docs"] = docs

    _atomic_write_text(
        FINISH_REVIEW_CONFIG_FILE,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    return rel_path


def remove_doc_from_finish_review_config(doc_path: str) -> bool:
    _require_file(FINISH_REVIEW_CONFIG_FILE)
    raw = _read_text(FINISH_REVIEW_CONFIG_FILE)
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("finish_review_config must be an object")
    docs = payload.get("docs")
    if not isinstance(docs, list) or not all(isinstance(item, str) for item in docs):
        raise ValueError("finish_review_config.docs must be a list of strings")

    if doc_path in docs:
        docs.remove(doc_path)
        payload["docs"] = docs
        _atomic_write_text(
            FINISH_REVIEW_CONFIG_FILE,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )
        return True
    return False