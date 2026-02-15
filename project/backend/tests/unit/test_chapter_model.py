import importlib.util
import inspect

import pytest
from pydantic import ValidationError

from app.models import Chapter
from tests.unit import schema_contract_helpers as schema_helpers


def _import_module(module_path: str):
    try:
        spec = importlib.util.find_spec(module_path)
    except ModuleNotFoundError as exc:
        pytest.fail(f"{module_path} module is missing: {exc}", pytrace=False)
    if spec is None:
        pytest.fail(f"{module_path} module is missing", pytrace=False)
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def _get_memgraph_storage_class():
    module = _import_module("app.storage.memgraph_storage")
    if not hasattr(module, "MemgraphStorage"):
        pytest.fail("MemgraphStorage class is missing", pytrace=False)
    return module.MemgraphStorage


def _normalize_status(value):
    return value.value if hasattr(value, "value") else value


def _base_chapter_kwargs():
    return {
        "id": "act-1:ch:1",
        "act_id": "act-1",
        "sequence": 1,
        "title": "Chapter 1",
        "focus": "Focus",
        "pov_character_id": None,
        "rendered_content": "Rendered content",
    }


def test_chapter_model_has_rendered_content_and_review_status():
    fields = Chapter.model_fields
    assert "rendered_content" in fields
    assert "review_status" in fields


def test_chapter_review_status_default_pending():
    chapter = Chapter(**_base_chapter_kwargs())
    assert _normalize_status(chapter.review_status) == "pending"


def test_chapter_review_status_rejects_invalid_value():
    kwargs = _base_chapter_kwargs()
    kwargs["review_status"] = "invalid"
    with pytest.raises(ValidationError):
        Chapter(**kwargs)


def test_schema_chapter_fields_include_rendered_content_and_review_status():
    schema = schema_helpers.get_schema_module()
    chapter_cls = schema_helpers.require_class(schema, "Chapter")
    schema_helpers.assert_fields_present(
        chapter_cls,
        {
            "id",
            "act_id",
            "sequence",
            "title",
            "focus",
            "pov_character_id",
            "rendered_content",
            "review_status",
        },
    )


def test_memgraph_create_chapter_accepts_rendered_content_and_review_status():
    storage_cls = _get_memgraph_storage_class()
    signature = inspect.signature(storage_cls.create_chapter)
    params = signature.parameters

    for name in ("rendered_content", "review_status"):
        assert name in params, f"create_chapter missing param: {name}"


def test_memgraph_chapter_props_include_rendered_content_and_review_status():
    storage_cls = _get_memgraph_storage_class()
    storage = storage_cls.__new__(storage_cls)

    chapter = Chapter(**_base_chapter_kwargs(), review_status="approved")
    props = storage._chapter_props(chapter)

    assert props["rendered_content"] == "Rendered content"
    assert props["review_status"] == "approved"


def test_memgraph_get_chapter_returns_rendered_content_and_review_status():
    storage_cls = _get_memgraph_storage_class()

    class DummyNode:
        def __init__(self, props):
            self._properties = props

    class DummyDB:
        def execute_and_fetch(self, *args, **kwargs):
            return iter(
                [
                    {
                        "n": DummyNode(
                            {
                                "id": "act-1:ch:1",
                                "act_id": "act-1",
                                "sequence": 1,
                                "title": "Chapter 1",
                                "focus": "Focus",
                                "pov_character_id": None,
                                "rendered_content": "Rendered content",
                                "review_status": "approved",
                            }
                        )
                    }
                ]
            )

    storage = storage_cls.__new__(storage_cls)
    storage.db = DummyDB()

    chapter = storage.get_chapter("act-1:ch:1")
    assert chapter is not None
    assert chapter.rendered_content == "Rendered content"
    assert _normalize_status(chapter.review_status) == "approved"
