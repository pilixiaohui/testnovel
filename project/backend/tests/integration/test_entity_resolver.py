import importlib
import importlib.util
import inspect

import pytest


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
    except ImportError as exc:
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def _get_entity_resolver_class():
    module = _import_module("app.services.entity_resolver")
    if not hasattr(module, "EntityResolver"):
        pytest.fail("EntityResolver class is missing", pytrace=False)
    resolver_cls = module.EntityResolver
    if not inspect.isclass(resolver_cls):
        pytest.fail("EntityResolver must be a class", pytrace=False)
    return resolver_cls


def _get_entity_model():
    module = _import_module("app.storage.schema")
    if not hasattr(module, "Entity"):
        pytest.fail("schema.Entity is missing", pytrace=False)
    return module.Entity


class RecordingGateway:
    def __init__(self, result: dict[str, str]):
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def generate_structured(self, payload: dict[str, object]):
        self.calls.append(payload)
        return self.result


@pytest.mark.asyncio
async def test_entity_resolver_builds_payload_from_schema_entities():
    resolver_cls = _get_entity_resolver_class()
    entity_cls = _get_entity_model()

    gateway = RecordingGateway({"John": "e1", "Park": "e2"})
    resolver = resolver_cls(gateway)
    entities = [
        entity_cls(
            id="e1",
            root_id="root-alpha",
            branch_id="main",
            entity_type="Character",
            name="John",
            tags=[],
            semantic_states={},
            arc_status="active",
        ),
        entity_cls(
            id="e2",
            root_id="root-alpha",
            branch_id="main",
            entity_type="Location",
            name="Park",
            tags=[],
            semantic_states={},
            arc_status="active",
        ),
    ]
    text = "John walks to the Park."

    result = await resolver.resolve_mentions(text=text, known_entities=entities)

    expected_payload = {
        "text": text,
        "known_entities": [
            {"id": "e1", "name": "John", "entity_type": "Character"},
            {"id": "e2", "name": "Park", "entity_type": "Location"},
        ],
    }
    assert gateway.calls == [expected_payload]
    assert result == gateway.result


@pytest.mark.asyncio
async def test_entity_resolver_handles_empty_known_entities():
    resolver_cls = _get_entity_resolver_class()

    gateway = RecordingGateway({})
    resolver = resolver_cls(gateway)
    text = "No known entities here."

    result = await resolver.resolve_mentions(text=text, known_entities=[])

    assert gateway.calls == [{"text": text, "known_entities": []}]
    assert result == {}

class QueueGateway:
    def __init__(self, results: list[dict[str, str]]):
        self._results = list(results)
        self.calls: list[dict[str, object]] = []

    async def generate_structured(self, payload: dict[str, object]):
        self.calls.append(payload)
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_entity_resolver_incremental_uses_cache_for_schema_entities():
    resolver_cls = _get_entity_resolver_class()
    entity_cls = _get_entity_model()

    gateway = RecordingGateway({"ignored": "e1"})
    resolver = resolver_cls(gateway)
    entities = [
        entity_cls(
            id="e1",
            root_id="root-alpha",
            branch_id="main",
            entity_type="Character",
            name="John",
            tags=[],
            semantic_states={},
            arc_status="active",
        )
    ]
    mention_cache = {"John": "e1"}
    text = "John walks home."

    result = await resolver.resolve_incremental(
        text=text,
        known_entities=entities,
        mention_cache=mention_cache,
    )

    assert result == {"John": "e1"}
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_entity_resolver_full_book_merges_chunks():
    resolver_cls = _get_entity_resolver_class()
    entity_cls = _get_entity_model()

    gateway = QueueGateway([{"Alice": "e1"}, {"Bob": "e2"}])
    resolver = resolver_cls(gateway)
    entities = [
        entity_cls(
            id="e1",
            root_id="root-alpha",
            branch_id="main",
            entity_type="Character",
            name="Alice",
            tags=[],
            semantic_states={},
            arc_status="active",
        ),
        entity_cls(
            id="e2",
            root_id="root-alpha",
            branch_id="main",
            entity_type="Character",
            name="Bob",
            tags=[],
            semantic_states={},
            arc_status="active",
        ),
    ]
    mention_cache: dict[str, str] = {}
    chunks = ["Alice arrives.", "Bob leaves."]

    result = await resolver.resolve_full_book(
        chunks=chunks,
        known_entities=entities,
        mention_cache=mention_cache,
    )

    assert result == {"Alice": "e1", "Bob": "e2"}
    assert mention_cache == result
    assert len(gateway.calls) == 2
