from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.models import (
    ActionResult,
    AgentAction,
    CharacterSheet,
    ConvergenceCheck,
    DMArbitration,
    Intention,
    SimulationRoundResult,
    SnowflakeRoot,
)
from app.services.character_agent import CharacterAgentEngine
from app.services.llm_engine import LLMEngine, LocalStoryEngine
from app.services.simulation_engine import SimulationEngine
from app.services.smart_renderer import SmartRenderer
from app.services.topone_client import ToponeClient
from app.services.world_master import WorldMasterEngine


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


def _build_round(info_gain: float, conflict_escalation: float = 0.0) -> SimulationRoundResult:
    return SimulationRoundResult(
        round_id="round-1",
        agent_actions=[_build_agent_action()],
        dm_arbitration=_build_dm_arbitration(),
        narrative_events=[{"event": "beat"}],
        sensory_seeds=[{"type": "weather"}],
        convergence_score=0.2,
        drama_score=0.2,
        info_gain=info_gain,
        stagnation_count=0,
    )


async def exercise_character_agent_engine() -> None:
    llm = SimpleNamespace(
        generate_agent_perception=AsyncMock(return_value={"beliefs": {"loc": "x"}}),
        generate_agent_intentions=AsyncMock(return_value=[]),
        generate_agent_action=AsyncMock(return_value=_build_agent_action()),
    )
    engine = CharacterAgentEngine(storage=object(), llm=llm)
    result = await engine.decide("agent-1", {"scene": "ctx"})
    assert result.action_type == "wait"
    llm.generate_agent_action.assert_not_awaited()

    llm.generate_agent_intentions = AsyncMock(
        return_value=[
            Intention(
                id="intent-1",
                desire_id="desire-1",
                action_type="wait",
                target="",
                expected_outcome="ok",
                risk_assessment=0.2,
            )
        ]
    )
    llm.generate_agent_action = AsyncMock(return_value=_build_agent_action())
    action = await engine.act("agent-1", {"scene": "ctx"})
    assert action.agent_id == "agent-1"
    llm.generate_agent_action.assert_awaited_once()


async def exercise_world_master_engine() -> None:
    engine = WorldMasterEngine()

    actions = [
        SimpleNamespace(agent_id="a1", action_type="attack", action_target="a2"),
        SimpleNamespace(agent_id="a2", action_type="attack", action_target="a1"),
    ]
    conflicts = await engine.detect_conflicts(actions)
    assert any(conflict["type"] == "mutual_attack" for conflict in conflicts)

    shared_actions = [
        {"agent_id": "a1", "action_type": "investigate", "action_target": "x"},
        {"agent_id": "a2", "action_type": "investigate", "action_target": "x"},
    ]
    conflicts = await engine.detect_conflicts(shared_actions)
    assert any(conflict["type"] == "shared_target" for conflict in conflicts)

    bad = await engine.check_action_validity(
        {"action_id": "act-1", "agent_id": "a1"},
        {"state": "x"},
        [lambda action, world_state: False],
    )
    assert bad.success == "failure"

    ok = await engine.check_action_validity(
        {"action_id": "act-1", "agent_id": "a1"},
        {"state": "x"},
        [],
    )
    assert ok.success == "success"

    check = await engine.check_convergence({"distance": 0.8}, {"id": "anchor-1"})
    assert check.convergence_needed is True

    for distance, expected in (
        (0.4, "npc_hint"),
        (0.6, "environment_pressure"),
        (0.8, "deus_ex_machina"),
        (0.95, "replan_route"),
    ):
        action = await engine.generate_convergence_action(
            ConvergenceCheck(
                next_anchor_id="anchor-1",
                distance=distance,
                convergence_needed=distance > 0.7,
            ),
            {},
        )
        assert action["type"] == expected

    low_rounds = [
        SimpleNamespace(info_gain=0.05, conflict_escalation=0.1),
        SimpleNamespace(info_gain=0.1, conflict_escalation=0.1),
        SimpleNamespace(info_gain=0.0, conflict_escalation=0.1),
    ]
    pacing = await engine.monitor_pacing(low_rounds)
    assert pacing.type == "inject_incident"

    deescalating = [
        SimpleNamespace(info_gain=0.3, conflict_escalation=0.6),
        SimpleNamespace(info_gain=0.3, conflict_escalation=0.4),
        SimpleNamespace(info_gain=0.3, conflict_escalation=0.2),
    ]
    pacing = await engine.monitor_pacing(deescalating)
    assert pacing.type == "force_escalation"

    stable = [
        SimpleNamespace(info_gain=0.3, conflict_escalation=0.2),
        SimpleNamespace(info_gain=0.3, conflict_escalation=0.2),
        SimpleNamespace(info_gain=0.3, conflict_escalation=0.2),
    ]
    pacing = await engine.monitor_pacing(stable)
    assert pacing.type == "continue"

    engine.analyze_gap = AsyncMock(return_value=SimpleNamespace(severity=0.5))
    engine.generate_bridge_chapters = AsyncMock(return_value=[{"title": "bridge"}])
    recoverable = await engine.replan_route(
        "scene-alpha",
        SimpleNamespace(required_conditions=["x"], constraint_type="hard"),
        {"state": 1},
    )
    assert recoverable.success is True
    assert recoverable.new_chapters == [{"title": "bridge"}]

    engine.analyze_gap = AsyncMock(return_value=SimpleNamespace(severity=0.9))
    engine.soften_anchor = AsyncMock(return_value={"anchor_type": "mid"})
    softened = await engine.replan_route(
        "scene-alpha",
        SimpleNamespace(required_conditions=["x"], constraint_type="soft"),
        {"state": 1},
    )
    assert softened.success is True
    assert softened.modified_anchor == {"anchor_type": "mid"}

    engine.generate_equivalent_anchor = AsyncMock(return_value={"anchor_type": "alt"})
    flexible = await engine.replan_route(
        "scene-alpha",
        SimpleNamespace(required_conditions=["x"], constraint_type="flexible"),
        {"state": 1},
    )
    assert flexible.success is True
    assert flexible.modified_anchor == {"anchor_type": "alt"}

    engine.analyze_gap = AsyncMock(return_value=SimpleNamespace(severity=0.9))
    hard = await engine.replan_route(
        "scene-alpha",
        SimpleNamespace(required_conditions=["x"], constraint_type="hard"),
        {"state": 1},
    )
    assert hard.success is False
    assert hard.reason == "hard_anchor_unreachable"


async def exercise_simulation_engine() -> None:
    action = _build_agent_action()
    agent = SimpleNamespace(agent_id="agent-1", decide=AsyncMock(return_value=action))
    world_master = SimpleNamespace(
        arbitrate=AsyncMock(return_value=_build_dm_arbitration()),
        inject_sensory_seeds=AsyncMock(return_value=[{"type": "weather"}]),
        monitor_pacing=AsyncMock(return_value=SimpleNamespace(type="force_escalation")),
    )
    engine = SimulationEngine(
        character_engine=object(),
        world_master=world_master,
        storage=object(),
        llm=object(),
    )
    engine.calculate_info_gain = AsyncMock(return_value=0.3)
    config = SimpleNamespace(round_id="round-1", max_rounds=1)

    result = await engine.run_round({"scene": "ctx"}, [agent], config)
    assert result.info_gain == 0.3

    engine.run_round = AsyncMock(return_value=_build_round(info_gain=0.3))
    engine.force_conflict_escalation = AsyncMock()
    engine.inject_breaking_incident = AsyncMock()
    engine.smart_render = AsyncMock(return_value="rendered")
    engine.should_end_scene = Mock(return_value=True)
    await engine.run_scene({"scene": "ctx"}, config)
    engine.force_conflict_escalation.assert_awaited_once()

    engine.world_master.monitor_pacing = AsyncMock(
        return_value=SimpleNamespace(type="inject_incident")
    )
    engine.inject_breaking_incident = AsyncMock()
    engine.force_conflict_escalation = AsyncMock()
    engine.smart_render = AsyncMock(return_value="rendered")
    engine.should_end_scene = Mock(return_value=True)
    await engine.run_scene({"scene": "ctx"}, config)
    engine.inject_breaking_incident.assert_awaited_once()

    renderer = SimpleNamespace(render=AsyncMock(return_value="rendered"))
    engine_with_renderer = SimulationEngine(
        character_engine=object(),
        world_master=world_master,
        storage=object(),
        llm=object(),
        smart_renderer=renderer,
    )
    rendered = await engine_with_renderer.smart_render([], {"scene": "ctx"})
    assert rendered == "rendered"

    engine_without_renderer = SimulationEngine(
        character_engine=object(),
        world_master=world_master,
        storage=object(),
        llm=object(),
        smart_renderer=None,
    )
    with pytest.raises(ValueError, match="smart_renderer is required"):
        await engine_without_renderer.smart_render([], {"scene": "ctx"})


async def exercise_smart_renderer() -> None:
    renderer = SmartRenderer()
    rounds = [_build_round(info_gain=0.05), _build_round(info_gain=0.2)]

    beats = await renderer.extract_narrative_beats(rounds)
    assert len(beats) == 1

    rendered = await renderer.render(rounds, {"scene": "ctx"})
    assert rendered == "beats:1"

    ok = await renderer.check_continuity_errors("content", {"scene": "ctx"})
    assert ok is False


class _DummyLLM(LLMEngine):
    def __init__(self):
        super().__init__(client="dummy")
        self.calls: list[tuple[object, list[dict[str, str]]]] = []

    async def _call_model(self, *, response_model, messages):
        self.calls.append((response_model, messages))
        return "ok"


async def exercise_llm_engine() -> None:
    engine = _DummyLLM()
    root = SnowflakeRoot(
        logline="logline",
        three_disasters=["a", "b", "c"],
        ending="end",
        theme="theme",
    )
    characters = [
        CharacterSheet(
            name="hero",
            ambition="goal",
            conflict="conflict",
            epiphany="epiphany",
            voice_dna="steady",
        )
    ]

    await engine.generate_act_list(root, characters)
    await engine.generate_chapter_list(root, {"id": "act-1"}, characters)
    await engine.generate_story_anchors(root, characters, [{"id": "act-1"}])
    await engine.generate_agent_perception({"agent": "a"}, "scene")
    await engine.generate_agent_intentions({"agent": "a"}, "scene")
    await engine.generate_agent_action({"agent": "a"}, "scene", [{"intent": "x"}])
    await engine.generate_dm_arbitration("round-1", [], {"state": 1}, {"scene": 1})
    await engine.check_convergence({"distance": 0.1}, {"id": "anchor-1"})
    await engine.render_scene({"scene": "ctx"}, [], [], {"style": "none"})

    assert len(engine.calls) == 9


async def exercise_local_story_engine() -> None:
    engine = LocalStoryEngine()

    loglines = await engine.generate_logline_options("idea")
    assert len(loglines) == 10

    with pytest.raises(ValueError, match="idea must not be empty"):
        await engine.generate_logline_options(" ")

    root = await engine.generate_root_structure("logline")
    characters = await engine.generate_characters(root)
    assert len(characters) == 3

    validation = await engine.validate_characters(root, characters)
    assert validation.valid is True

    with pytest.raises(ValueError, match="characters must not be empty"):
        await engine.generate_scene_list(root, [])

    scenes = await engine.generate_scene_list(root, characters)
    assert len(scenes) == 50


async def exercise_topone_client() -> None:
    client = ToponeClient(
        api_key="key",
        base_url="https://example.com",
        allowed_models=["model-1"],
    )

    payload = client._build_payload(
        messages=[{"role": "user", "text": "hi"}],
        system_instruction="sys",
        generation_config={"temperature": 0.1},
    )
    assert payload["systemInstruction"]["parts"][0]["text"] == "sys"
    assert payload["contents"][0]["parts"][0]["text"] == "hi"

    with pytest.raises(ValueError, match="Unsupported model"):
        client._validate_model("bad")

    with pytest.raises(ValueError, match="TOPONE_API_KEY"):
        ToponeClient(api_key="", allowed_models=["model-1"])._ensure_key()

    stripped = client._strip_thoughts(
        {
            "candidates": [
                {"content": {"parts": [{"text": "ok"}, {"text": "t", "thought": True}]}}
            ]
        }
    )
    assert stripped["candidates"][0]["content"]["parts"] == [{"text": "ok"}]

    async def handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "ok"}, {"text": "t", "thought": True}]}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    result = await client.generate_content(
        messages=[{"role": "user", "text": "hi"}],
        model="model-1",
        transport=transport,
    )
    assert result["candidates"][0]["content"]["parts"] == [{"text": "ok"}]
