import base64

from pathlib import Path

import pytest

from orchestrator import documents


def test_store_and_list_uploaded_docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_dir = tmp_path / "uploaded_docs"
    monkeypatch.setattr(documents, "UPLOADED_DOCS_DIR", base_dir)
    monkeypatch.setattr(documents, "UPLOADED_DOCS_CATEGORIES", ("requirements",))
    monkeypatch.setattr(documents, "UPLOADED_DOCS_MAX_BYTES", 1024)

    payload = base64.b64encode("hello".encode("utf-8")).decode("utf-8")
    stored = documents.store_uploaded_doc(filename="sample.md", content_b64=payload, category="requirements")
    assert stored == "requirements/sample.md"

    docs = documents.list_uploaded_docs()
    assert len(docs) == 1
    assert docs[0]["path"] == "requirements/sample.md"

    resolved = documents.resolve_uploaded_doc_path("requirements/sample.md")
    assert resolved.exists()


def test_resolve_uploaded_doc_path_rejects_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_dir = tmp_path / "uploaded_docs"
    monkeypatch.setattr(documents, "UPLOADED_DOCS_DIR", base_dir)
    monkeypatch.setattr(documents, "UPLOADED_DOCS_CATEGORIES", ("requirements",))

    with pytest.raises(ValueError):
        documents.resolve_uploaded_doc_path("../secrets.md")