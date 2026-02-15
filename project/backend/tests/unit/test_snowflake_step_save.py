import pytest
from fastapi.testclient import TestClient

from app.constants import DEFAULT_BRANCH_ID
from app.main import app, get_graph_storage
from app.models import Entity, Root


class DummyStorage:
    def __init__(self) -> None:
        self.root = Root(
            id="root-alpha",
            logline="Old logline",
            theme="Old theme",
            ending="Old ending",
        )
        self.entities = [
            {
                "entity_id": "char-alpha",
                "entity_type": "Character",
                "tags": ["core"],
                "arc_status": "active",
            }
        ]
        self.updated_entities: list[Entity] = []

    def get_root_snapshot(self, *, root_id: str, branch_id: str):
        return {
            "root_id": root_id,
            "branch_id": branch_id,
            "logline": self.root.logline,
            "theme": self.root.theme,
            "ending": self.root.ending,
            "characters": [],
            "scenes": [],
        }

    def update_root(self, root: Root):
        self.root = root
        return root

    def list_entities(self, *, root_id: str, branch_id: str):
        _ = (root_id, branch_id)
        return list(self.entities)

    def update_entity(self, entity: Entity):
        self.updated_entities.append(entity)
        return entity

    def create_entity(self, **kwargs):
        raise AssertionError(f"unexpected create_entity: {kwargs}")


def test_save_snowflake_step_updates_root():
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage
    client = TestClient(app)

    response = client.post(
        f"/api/v1/roots/{storage.root.id}/snowflake/steps",
        json={
            "step": "step2",
            "data": {
                "root": {
                    "logline": "New logline",
                    "theme": "New theme",
                    "ending": "New ending",
                    "three_disasters": ["A", "B", "C"],
                }
            },
        },
    )

    assert response.status_code == 200
    assert storage.root.logline == "New logline"
    assert storage.root.theme == "New theme"
    assert storage.root.ending == "New ending"

    app.dependency_overrides.clear()


def test_save_snowflake_step_updates_characters():
    storage = DummyStorage()
    app.dependency_overrides[get_graph_storage] = lambda: storage
    client = TestClient(app)

    response = client.post(
        f"/api/v1/roots/{storage.root.id}/snowflake/steps",
        json={
            "step": "step3",
            "data": {
                "characters": [
                    {
                        "id": "char-alpha",
                        "name": "Nova",
                        "ambition": "Find the signal",
                        "conflict": "Memory decay",
                        "epiphany": "Trust the crew",
                        "voice_dna": "calm",
                    }
                ]
            },
        },
    )

    assert response.status_code == 200
    assert len(storage.updated_entities) == 1
    updated = storage.updated_entities[0]
    assert updated.id == "char-alpha"
    assert updated.name == "Nova"
    assert updated.semantic_states["ambition"] == "Find the signal"
    assert updated.semantic_states["conflict"] == "Memory decay"
    assert updated.semantic_states["epiphany"] == "Trust the crew"
    assert updated.semantic_states["voice_dna"] == "calm"
    assert updated.arc_status == "active"
    assert updated.root_id == storage.root.id
    assert updated.branch_id == DEFAULT_BRANCH_ID

    app.dependency_overrides.clear()
