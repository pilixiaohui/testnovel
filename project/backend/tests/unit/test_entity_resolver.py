import importlib
import importlib.util
import inspect
from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock

import pytest


@dataclass(frozen=True)
class EntityStub:
    id: str
    name: str
    entity_type: str


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


def test_entity_resolver_module_exists():
    _import_module("app.services.entity_resolver")


def test_entity_resolver_has_resolve_mentions():
    resolver_cls = _get_entity_resolver_class()
    if not hasattr(resolver_cls, "resolve_mentions"):
        pytest.fail("EntityResolver.resolve_mentions is missing", pytrace=False)
    method = getattr(resolver_cls, "resolve_mentions")
    if not callable(method):
        pytest.fail("EntityResolver.resolve_mentions must be callable", pytrace=False)
    assert inspect.iscoroutinefunction(method), "EntityResolver.resolve_mentions must be async"


@pytest.fixture
def gateway():
    gateway = Mock()
    gateway.generate_structured = AsyncMock()
    return gateway


@pytest.mark.asyncio
async def test_resolve_mentions_pronoun_resolution(gateway):
    resolver_cls = _get_entity_resolver_class()
    resolver = resolver_cls(gateway)
    gateway.generate_structured.return_value = {"John": "e1", "他": "e1"}

    known_entities = [EntityStub(id="e1", name="John", entity_type="Character")]
    text = "John走进房间。他坐下了。"

    mentions = await resolver.resolve_mentions(text=text, known_entities=known_entities)

    assert mentions["John"] == "e1"
    assert mentions["他"] == "e1"


@pytest.mark.asyncio
async def test_resolve_mentions_duplicate_entity_mapping(gateway):
    resolver_cls = _get_entity_resolver_class()
    resolver = resolver_cls(gateway)
    gateway.generate_structured.return_value = {"Alice#1": "e1", "Alice#2": "e1"}

    known_entities = [EntityStub(id="e1", name="Alice", entity_type="Character")]
    text = "Alice和Alice的朋友见面了。"

    mentions = await resolver.resolve_mentions(text=text, known_entities=known_entities)

    alice_mentions = [key for key in mentions if "Alice" in key]
    assert alice_mentions, "expected at least one Alice mention"
    assert all(mentions[key] == "e1" for key in alice_mentions)


@pytest.mark.asyncio
async def test_resolve_mentions_builds_payload_for_gateway(gateway):
    resolver_cls = _get_entity_resolver_class()
    resolver = resolver_cls(gateway)
    gateway.generate_structured.return_value = {
        "王强": "e1",
        "他": "e1",
        "小雅": "e2",
        "她": "e2",
    }

    known_entities = [
        EntityStub(id="e1", name="王强", entity_type="Character"),
        EntityStub(id="e2", name="小雅", entity_type="Character"),
    ]
    text = "王强进入书店。他和小雅谈话，她点头。"

    mentions = await resolver.resolve_mentions(text=text, known_entities=known_entities)

    expected_payload = {
        "text": text,
        "known_entities": [
            {"id": "e1", "name": "王强", "entity_type": "Character"},
            {"id": "e2", "name": "小雅", "entity_type": "Character"},
        ],
    }
    gateway.generate_structured.assert_awaited_once_with(expected_payload)
    assert mentions == gateway.generate_structured.return_value

@pytest.mark.asyncio
async def test_resolve_incremental_uses_cache_without_gateway_call(gateway):
    resolver_cls = _get_entity_resolver_class()
    resolver = resolver_cls(gateway)
    gateway.generate_structured.side_effect = AssertionError("gateway should not be called")

    mention_cache = {"John": "e1"}
    known_entities = [EntityStub(id="e1", name="John", entity_type="Character")]
    text = "John walks home."

    result = await resolver.resolve_incremental(
        text=text,
        known_entities=known_entities,
        mention_cache=mention_cache,
    )

    assert result == {"John": "e1"}


@pytest.mark.asyncio
async def test_resolve_incremental_updates_cache_on_miss(gateway):
    resolver_cls = _get_entity_resolver_class()
    resolver = resolver_cls(gateway)
    gateway.generate_structured.return_value = {"Mary": "e2"}

    mention_cache = {"John": "e1"}
    known_entities = [
        EntityStub(id="e1", name="John", entity_type="Character"),
        EntityStub(id="e2", name="Mary", entity_type="Character"),
    ]
    text = "John meets Mary."

    result = await resolver.resolve_incremental(
        text=text,
        known_entities=known_entities,
        mention_cache=mention_cache,
    )

    assert result == {"John": "e1", "Mary": "e2"}
    assert mention_cache["Mary"] == "e2"


@pytest.mark.asyncio
async def test_resolve_full_book_merges_results_and_updates_cache(gateway):
    resolver_cls = _get_entity_resolver_class()
    resolver = resolver_cls(gateway)
    gateway.generate_structured.side_effect = [{"Alice": "e1"}, {"Bob": "e2"}]

    mention_cache: dict[str, str] = {}
    known_entities = [
        EntityStub(id="e1", name="Alice", entity_type="Character"),
        EntityStub(id="e2", name="Bob", entity_type="Character"),
    ]
    chunks = ["Alice arrives.", "Bob leaves."]

    result = await resolver.resolve_full_book(
        chunks=chunks,
        known_entities=known_entities,
        mention_cache=mention_cache,
    )

    assert result == {"Alice": "e1", "Bob": "e2"}
    assert mention_cache == result
    assert gateway.generate_structured.await_count == 2
