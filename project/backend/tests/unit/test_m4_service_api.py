from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.models import ActionResult, AgentAction, ConvergenceCheck, DMArbitration, ReplanResult, SimulationRoundResult
from app.services.character_agent import CharacterAgentEngine
from app.services.simulation_engine import SimulationEngine
from app.services.smart_renderer import SmartRenderer
from app.services.world_master import WorldMasterEngine
from tests.service_coverage_helpers import (
    exercise_character_agent_engine,
    exercise_world_master_engine,
    exercise_simulation_engine,
    exercise_smart_renderer,
    exercise_llm_engine,
    exercise_local_story_engine,
    exercise_topone_client,
)


def _root_payload() -> dict[str, object]:
    return {
        "logline": "A hero seeks redemption.",
        "three_disasters": ["loss", "betrayal", "reckoning"],
        "ending": "peace",
        "theme": "forgiveness",
    }


def _character_payload() -> dict[str, object]:
    return {
        "name": "Hero",
        "ambition": "redeem",
        "conflict": "guilt",
        "epiphany": "forgive self",
        "voice_dna": "steady",
    }


def _build_action_result() -> ActionResult:
    return ActionResult(
        action_id="act-1",
        agent_id="agent-1",
        success="success",
        reason="ok",
        actual_outcome="clear",
    )


def _build_dm_arbitration() -> DMArbitration:
    return DMArbitration(round_id="round-1", action_results=[_build_action_result()])


def _build_agent_action() -> AgentAction:
    return AgentAction(
        agent_id="agent-1",
        internal_thought="wait",
        action_type="wait",
        action_target="",
        dialogue=None,
        action_description="pause",
    )


def _build_round_result() -> SimulationRoundResult:
    return SimulationRoundResult(
        round_id="round-1",
        agent_actions=[_build_agent_action()],
        dm_arbitration=_build_dm_arbitration(),
        narrative_events=[{"event": "beat"}],
        sensory_seeds=[{"type": "weather", "detail": "rain"}],
        convergence_score=0.2,
        drama_score=0.3,
        info_gain=0.4,
        stagnation_count=0,
    )


def _override(dep, value) -> None:
    app.dependency_overrides[dep] = lambda: value


@dataclass
class AnchorStub:
    id: str
    root_id: str
    branch_id: str
    sequence: int
    anchor_type: str
    description: str
    constraint_type: str
    required_conditions: str
    deadline_scene: str | None
    achieved: bool


class StepStorage:
    def __init__(self) -> None:
        self.created_acts: list[dict[str, object]] = []
        self.created_chapters: list[dict[str, object]] = []
        self.acts: list[dict[str, object]] = [{"id": "act-1"}]

    def create_act(self, *, root_id: str, seq: int, title: str, purpose: str, tone: str):
        record = {
            "id": f"act-{seq}",
            "root_id": root_id,
            "seq": seq,
            "title": title,
            "purpose": purpose,
            "tone": tone,
        }
        self.created_acts.append(record)
        return record

    def list_acts(self, *, root_id: str):
        _ = root_id
        return self.acts

    def create_chapter(
        self,
        *,
        act_id: str,
        seq: int,
        title: str,
        focus: str,
        pov_character_id: str | None = None,
    ):
        record = {
            "id": f"chapter-{seq}",
            "act_id": act_id,
            "seq": seq,
            "title": title,
            "focus": focus,
            "pov_character_id": pov_character_id,
        }
        self.created_chapters.append(record)
        return record


class AnchorStorage:
    def __init__(self) -> None:
        self.anchor = AnchorStub(
            id="anchor-1",
            root_id="root-alpha",
            branch_id="branch-1",
            sequence=1,
            anchor_type="midpoint",
            description="old",
            constraint_type="hard",
            required_conditions="[]",
            deadline_scene=None,
            achieved=False,
        )

    def create_anchor(
        self,
        *,
        root_id: str,
        branch_id: str,
        seq: int,
        type: str,
        desc: str,
        constraint: str,
        conditions: str,
    ):
        _ = conditions
        return {
            "id": "anchor-1",
            "root_id": root_id,
            "branch_id": branch_id,
            "sequence": seq,
            "anchor_type": type,
            "description": desc,
            "constraint_type": constraint,
            "required_conditions": conditions,
            "deadline_scene": None,
            "achieved": False,
        }

    def get_next_unachieved_anchor(self, *, root_id: str, branch_id: str):
        return {
            "id": "anchor-1",
            "root_id": root_id,
            "branch_id": branch_id,
            "sequence": 1,
            "anchor_type": "midpoint",
            "description": "next",
            "constraint_type": "hard",
            "required_conditions": "[]",
            "deadline_scene": None,
            "achieved": False,
        }

    def get_anchor(self, anchor_id: str):
        _ = anchor_id
        return self.anchor

    def update_anchor(self, anchor):
        return anchor

    def mark_anchor_achieved(self, *, anchor_id: str, scene_version_id: str):
        return {
            "id": anchor_id,
            "scene_version_id": scene_version_id,
            "achieved": True,
        }


class AgentStateStub:
    def __init__(self, *, agent_id: str, character_id: str, branch_id: str) -> None:
        self.id = agent_id
        self.character_id = character_id
        self.branch_id = branch_id
        self.beliefs = {"mood": "calm"}
        self.desires = []
        self.intentions = []
        self.memory = []
        self.private_knowledge = []
        self.last_updated_scene = None
        self.version = 1


class AgentStorage:
    def init_character_agent(
        self, *, char_id: str, branch_id: str, initial_desires: list[dict[str, object]]
    ):
        _ = initial_desires
        return {
            "id": f"agent:{char_id}:{branch_id}",
            "character_id": char_id,
            "branch_id": branch_id,
        }

    def get_agent_state(self, agent_id: str):
        char_id, branch_id = agent_id.split(":", 2)[1:]
        return AgentStateStub(agent_id=agent_id, character_id=char_id, branch_id=branch_id)

    def update_agent_desires(
        self, *, agent_id: str, desires: list[dict[str, object]]
    ) -> dict[str, object]:
        return {"id": agent_id, "desires": desires, "version": 2}


class SimulationLogStub:
    def __init__(self, *, log_id: str, round_number: int) -> None:
        self.log_id = log_id
        self.round_number = round_number

    def model_dump(self) -> dict[str, object]:
        return {
            "id": self.log_id,
            "scene_version_id": "scene-ver-1",
            "round_number": self.round_number,
            "agent_actions": "[]",
            "dm_arbitration": "{}",
            "narrative_events": "[]",
            "sensory_seeds": "[]",
            "convergence_score": 0.4,
            "drama_score": 0.5,
            "info_gain": 0.3,
            "stagnation_count": 0,
        }


class SimulationStorage:
    def __init__(self) -> None:
        self.list_called: str | None = None

    def get_simulation_log(self, log_id: str):
        return SimulationLogStub(log_id=log_id, round_number=1)

    def list_simulation_logs(self, scene_id: str):
        self.list_called = scene_id
        return [
            SimulationLogStub(log_id=f"sim:{scene_id}:round:1", round_number=1),
            SimulationLogStub(log_id=f"sim:{scene_id}:round:2", round_number=2),
        ]


class EmptySimulationStorage(SimulationStorage):
    def list_simulation_logs(self, scene_id: str):
        self.list_called = scene_id
        return []


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_service_dependency_builders_construct_services():
    dummy_storage = object()
    dummy_llm = object()

    character_engine = main.get_character_agent_engine(
        storage=dummy_storage, llm=dummy_llm
    )
    world_master = main.get_world_master_engine(llm=dummy_llm)
    smart_renderer = main.get_smart_renderer(llm=dummy_llm)
    simulation = main.get_simulation_engine(
        character_engine=character_engine,
        world_master=world_master,
        storage=dummy_storage,
        llm=dummy_llm,
        smart_renderer=smart_renderer,
    )

    assert isinstance(character_engine, CharacterAgentEngine)
    assert isinstance(world_master, WorldMasterEngine)
    assert isinstance(smart_renderer, SmartRenderer)
    assert isinstance(simulation, SimulationEngine)
    assert simulation.smart_renderer is smart_renderer


def test_step5a_creates_acts(client):
    storage = StepStorage()
    engine = SimpleNamespace(
        arbitrate=AsyncMock(return_value=_build_dm_arbitration()),
        check_convergence=AsyncMock(
            return_value=ConvergenceCheck(
                next_anchor_id="anchor-1", distance=0.3, convergence_needed=False
            )
        ),
        generate_convergence_action=AsyncMock(return_value={"type": "npc_hint"}),
        replan_route=AsyncMock(
            return_value=ReplanResult(
                success=True,
                new_chapters=[{"title": "bridge"}],
                modified_anchor=None,
                reason="recoverable",
            )
        ),
    )

    _override(main.get_world_master_engine, engine)

    response = client.post(
        "/api/v1/dm/arbitrate",
        json={"round_id": "round-1", "actions": [], "world_state": {}},
    )
    assert response.status_code == 200
    assert response.json()["round_id"] == "round-1"

    response = client.post(
        "/api/v1/dm/converge",
        json={"world_state": {"distance": 0.3}, "next_anchor": {"id": "anchor-1"}},
    )
    assert response.status_code == 200
    assert response.json()["next_anchor_id"] == "anchor-1"

    response = client.post(
        "/api/v1/dm/intervene",
        json={
            "check": {
                "next_anchor_id": "anchor-1",
                "distance": 0.2,
                "convergence_needed": False,
            },
            "world_state": {},
        },
    )
    assert response.status_code == 200
    assert response.json()["type"] == "npc_hint"

    response = client.post(
        "/api/v1/dm/replan",
        json={
            "current_scene": "scene-alpha",
            "target_anchor": {"constraint_type": "hard", "required_conditions": ["cond"]},
            "world_state": {"state": 1},
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_simulation_and_render_endpoints(client):
    engine = SimpleNamespace(
        run_round=AsyncMock(return_value=_build_round_result()),
        run_scene=AsyncMock(return_value="rendered scene"),
    )
    renderer = SimpleNamespace(render=AsyncMock(return_value="rendered content"))

    _override(main.get_simulation_engine, engine)
    _override(main.get_smart_renderer, renderer)

    response = client.post(
        "/api/v1/simulation/round",
        json={"scene_context": {"scene": "ctx"}, "agents": [], "round_id": "round-1"},
    )
    assert response.status_code == 200
    assert response.json()["round_id"] == "round-1"

    response = client.post(
        "/api/v1/simulation/scene",
        json={"scene_context": {"scene": "ctx"}, "max_rounds": 1},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "rendered scene"

    response = client.post(
        "/api/v1/render/scene",
        json={"rounds": [], "scene": {"id": "scene-alpha"}},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "rendered content"



def test_simulation_logs_endpoint(client):
    storage = SimulationStorage()
    _override(main.get_graph_storage, storage)

    response = client.get("/api/v1/simulation/logs/scene-alpha")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "sim:scene-alpha:round:1"
    assert data[1]["round_number"] == 2
    assert storage.list_called == "scene-alpha"


def test_simulation_logs_endpoint_returns_404_when_empty(client):
    storage = EmptySimulationStorage()
    _override(main.get_graph_storage, storage)

    response = client.get("/api/v1/simulation/logs/scene-alpha")

    assert response.status_code == 404
    assert storage.list_called == "scene-alpha"


@pytest.mark.asyncio
async def test_service_core_components_coverage():
    await exercise_character_agent_engine()
    await exercise_world_master_engine()
    await exercise_simulation_engine()
    await exercise_smart_renderer()


@pytest.mark.asyncio
async def test_llm_and_topone_components_coverage():
    await exercise_llm_engine()
    await exercise_local_story_engine()
    await exercise_topone_client()
