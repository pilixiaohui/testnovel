import json
from uuid import uuid4

import pytest

from tests.integration import storage_test_helpers as helpers


def _seed_root(memgraph_storage):
    root_id = f"root-{uuid4()}"
    branch_id = helpers.get_default_branch_id()
    commit_id = f"{root_id}:{branch_id}:{uuid4()}"
    helpers.seed_root_with_branch(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
        commit_id=commit_id,
    )
    return root_id, branch_id


def _create_character(memgraph_storage, *, root_id: str, branch_id: str) -> str:
    return memgraph_storage.create_entity(
        root_id=root_id,
        branch_id=branch_id,
        name="Alice",
        entity_type="Character",
        tags=["hero"],
        arc_status="active",
        semantic_states={"hp": "100%"},
    )


def _fetch_agent(memgraph_storage, *, character_id: str):
    return helpers.fetch_one(
        memgraph_storage,
        "MATCH (a:CharacterAgentState {character_id: $char_id}) "
        "RETURN a.id AS id, a.version AS version, a.beliefs AS beliefs, a.memory AS memory;",
        {"char_id": character_id},
    )


def test_init_character_agent_creates_state_and_relation(memgraph_storage):
    root_id, branch_id = _seed_root(memgraph_storage)
    entity_id = _create_character(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
    )

    memgraph_storage.init_character_agent(
        char_id=entity_id,
        branch_id=branch_id,
        initial_desires=[{"id": "d1", "type": "short_term"}],
    )

    agent = _fetch_agent(memgraph_storage, character_id=entity_id)
    assert agent is not None
    assert agent["version"] == 1

    entity = memgraph_storage.get_entity(entity_id)
    assert entity is not None
    assert entity.has_agent is True
    assert entity.agent_state_id == agent["id"]

    edge = helpers.fetch_one(
        memgraph_storage,
        "MATCH (a:CharacterAgentState {id: $agent_id})-[:AGENT_OF]->(e:Entity {id: $entity_id}) "
        "RETURN count(*) AS count;",
        {"agent_id": agent["id"], "entity_id": entity_id},
    )
    assert edge is not None
    assert edge["count"] == 1


def test_init_character_agent_requires_entity(memgraph_storage):
    _root_id, branch_id = _seed_root(memgraph_storage)
    with pytest.raises(KeyError):
        memgraph_storage.init_character_agent(
            char_id="missing-entity",
            branch_id=branch_id,
            initial_desires=[],
        )


def test_init_character_agent_rejects_duplicate(memgraph_storage):
    root_id, branch_id = _seed_root(memgraph_storage)
    entity_id = _create_character(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
    )

    memgraph_storage.init_character_agent(
        char_id=entity_id,
        branch_id=branch_id,
        initial_desires=[{"id": "d1", "type": "short_term"}],
    )

    with pytest.raises(ValueError):
        memgraph_storage.init_character_agent(
            char_id=entity_id,
            branch_id=branch_id,
            initial_desires=[{"id": "d1", "type": "short_term"}],
        )


def test_update_agent_beliefs_deep_merge_and_version(memgraph_storage):
    root_id, branch_id = _seed_root(memgraph_storage)
    entity_id = _create_character(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
    )

    memgraph_storage.init_character_agent(
        char_id=entity_id,
        branch_id=branch_id,
        initial_desires=[{"id": "d1", "type": "short_term"}],
    )

    agent = _fetch_agent(memgraph_storage, character_id=entity_id)
    assert agent is not None

    memgraph_storage.db.execute(
        "MATCH (a:CharacterAgentState {id: $agent_id}) SET a.beliefs = $beliefs;",
        {"agent_id": agent["id"], "beliefs": json.dumps({"world": {"location": "town"}})},
    )

    memgraph_storage.update_agent_beliefs(
        agent_id=agent["id"],
        beliefs_patch={"world": {"weather": "rain"}},
    )

    updated = helpers.fetch_one(
        memgraph_storage,
        "MATCH (a:CharacterAgentState {id: $agent_id}) RETURN a.beliefs AS beliefs, a.version AS version;",
        {"agent_id": agent["id"]},
    )
    assert updated is not None
    assert updated["version"] == 2

    beliefs = json.loads(updated["beliefs"])
    assert beliefs["world"]["location"] == "town"
    assert beliefs["world"]["weather"] == "rain"


def test_add_agent_memory_trims_to_top_80_by_importance(memgraph_storage):
    root_id, branch_id = _seed_root(memgraph_storage)
    entity_id = _create_character(
        memgraph_storage,
        root_id=root_id,
        branch_id=branch_id,
    )

    memgraph_storage.init_character_agent(
        char_id=entity_id,
        branch_id=branch_id,
        initial_desires=[{"id": "d1", "type": "short_term"}],
    )

    agent = _fetch_agent(memgraph_storage, character_id=entity_id)
    assert agent is not None

    memory_entries = [
        {"content": f"m{i}", "importance": i} for i in range(100)
    ]
    memgraph_storage.db.execute(
        "MATCH (a:CharacterAgentState {id: $agent_id}) SET a.memory = $memory;",
        {"agent_id": agent["id"], "memory": json.dumps(memory_entries)},
    )

    memgraph_storage.add_agent_memory(
        agent_id=agent["id"],
        entry={"content": "m100", "importance": 999},
    )

    updated = helpers.fetch_one(
        memgraph_storage,
        "MATCH (a:CharacterAgentState {id: $agent_id}) RETURN a.memory AS memory;",
        {"agent_id": agent["id"]},
    )
    assert updated is not None

    memory = json.loads(updated["memory"])
    importances = sorted(item["importance"] for item in memory)
    assert len(importances) == 80
    assert importances[0] == 21
    assert importances[-1] == 999
