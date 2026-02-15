from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.models import (
    ActionResult,
    AgentAction,
    DMArbitration,
    SimulationRoundResult,
)

from .service_contract_helpers import (
    build_instance,
    load_module,
    require_async_method,
    require_class,
    require_init_params,
)


class AttrDict(dict):
    def __getattr__(self, item):
        return self[item]


class RoundStub:
    def __init__(self, info_gain: float, conflict_escalation: float = 0.0):
        self.info_gain = info_gain
        self.conflict_escalation = conflict_escalation


def _build_action_result():
    return ActionResult(
        action_id="a1",
        agent_id="agent-1",
        success="success",
        reason="ok",
        actual_outcome="outcome",
    )


def _build_dm_arbitration():
    return DMArbitration(round_id="r1", action_results=[_build_action_result()])


def _build_agent_action():
    return AgentAction(
        agent_id="agent-1",
        internal_thought="think",
        action_type="wait",
        action_target="",
        dialogue=None,
        action_description="desc",
    )


def _build_round(info_gain: float = 0.2):
    return SimulationRoundResult(
        round_id="r1",
        agent_actions=[_build_agent_action()],
        dm_arbitration=_build_dm_arbitration(),
        narrative_events=[{"event": "beat"}],
        sensory_seeds=[{"type": "weather", "detail": "rain"}],
        convergence_score=0.2,
        drama_score=0.2,
        info_gain=info_gain,
        stagnation_count=0,
    )


def _build_character_engine_class():
    module = load_module("app.services.character_agent")
    engine_cls = require_class(module, "CharacterAgentEngine")
    require_init_params(engine_cls, {"storage", "llm"})
    for name in ("perceive", "deliberate", "act", "decide"):
        require_async_method(engine_cls, name)
    return engine_cls


def _build_world_master_class():
    module = load_module("app.services.world_master")
    engine_cls = require_class(module, "WorldMasterEngine")
    for name in (
        "arbitrate",
        "detect_conflicts",
        "check_action_validity",
        "check_convergence",
        "generate_convergence_action",
        "inject_sensory_seeds",
        "monitor_pacing",
        "replan_route",
    ):
        require_async_method(engine_cls, name)
    return engine_cls


def _build_simulation_engine_class():
    module = load_module("app.services.simulation_engine")
    engine_cls = require_class(module, "SimulationEngine")
    require_init_params(engine_cls, {"character_engine", "world_master", "storage", "llm"})
    for name in ("run_round", "run_scene", "calculate_info_gain"):
        require_async_method(engine_cls, name)
    return engine_cls


def _build_smart_renderer_class():
    module = load_module("app.services.smart_renderer")
    engine_cls = require_class(module, "SmartRenderer")
    for name in ("render", "extract_narrative_beats", "check_continuity_errors"):
        require_async_method(engine_cls, name)
    return engine_cls


def test_service_modules_present():
    load_module("app.services.character_agent")
    load_module("app.services.world_master")
    load_module("app.services.simulation_engine")
    load_module("app.services.smart_renderer")


def test_character_agent_engine_contract():
    _build_character_engine_class()


def test_world_master_engine_contract():
    _build_world_master_class()


def test_simulation_engine_contract():
    _build_simulation_engine_class()


def test_smart_renderer_contract():
    _build_smart_renderer_class()


@pytest.mark.asyncio
async def test_character_agent_decide_calls_flow():
    engine_cls = _build_character_engine_class()
    engine = build_instance(engine_cls)

    engine.perceive = AsyncMock(return_value={"beliefs": {"loc": "x"}})
    engine.deliberate = AsyncMock(return_value=[])
    action = _build_agent_action()
    engine.act = AsyncMock(return_value=action)

    result = await engine.decide("agent-1", {"scene": "ctx"})

    assert result == action
    engine.perceive.assert_awaited_once()
    engine.deliberate.assert_awaited_once()
    engine.act.assert_awaited_once()


@pytest.mark.asyncio
async def test_world_master_detect_conflicts_mutual_attack():
    engine_cls = _build_world_master_class()
    engine = build_instance(engine_cls)

    actions = [
        AttrDict(agent_id="a1", action_type="attack", action_target="a2"),
        AttrDict(agent_id="a2", action_type="attack", action_target="a1"),
    ]

    conflicts = await engine.detect_conflicts(actions)

    assert isinstance(conflicts, list)
    assert len(conflicts) == 1


@pytest.mark.asyncio
async def test_world_master_monitor_pacing_stagnant_rounds():
    engine_cls = _build_world_master_class()
    engine = build_instance(engine_cls)

    rounds = [
        RoundStub(info_gain=0.05, conflict_escalation=0.1),
        RoundStub(info_gain=0.1, conflict_escalation=0.05),
        RoundStub(info_gain=0.0, conflict_escalation=0.02),
    ]

    pacing = await engine.monitor_pacing(rounds)

    assert hasattr(pacing, "type")
    assert pacing.type == "inject_incident"


@pytest.mark.asyncio
async def test_world_master_replan_route_recoverable_gap():
    engine_cls = _build_world_master_class()
    engine = build_instance(engine_cls)

    engine.analyze_gap = AsyncMock(return_value=SimpleNamespace(severity=0.5))
    engine.generate_bridge_chapters = AsyncMock(return_value=[{"title": "bridge"}])

    target_anchor = AttrDict(
        constraint_type="hard", required_conditions=["hero_has_sword"]
    )

    result = await engine.replan_route("scene-alpha", target_anchor, {"state": 1})

    assert result.success is True
    assert result.new_chapters == [{"title": "bridge"}]


@pytest.mark.asyncio
async def test_world_master_replan_route_soft_anchor():
    engine_cls = _build_world_master_class()
    engine = build_instance(engine_cls)

    engine.analyze_gap = AsyncMock(return_value=SimpleNamespace(severity=0.9))
    engine.soften_anchor = AsyncMock(return_value={"anchor_type": "midpoint"})

    target_anchor = AttrDict(
        constraint_type="soft", required_conditions=["hero_has_sword"]
    )

    result = await engine.replan_route("scene-alpha", target_anchor, {"state": 1})

    assert result.success is True
    assert result.modified_anchor == {"anchor_type": "midpoint"}


@pytest.mark.asyncio
async def test_world_master_replan_route_hard_anchor_unreachable():
    engine_cls = _build_world_master_class()
    engine = build_instance(engine_cls)

    engine.analyze_gap = AsyncMock(return_value=SimpleNamespace(severity=0.9))

    target_anchor = AttrDict(
        constraint_type="hard", required_conditions=["hero_has_sword"]
    )

    result = await engine.replan_route("scene-alpha", target_anchor, {"state": 1})

    assert result.success is False
    assert result.reason == "hard_anchor_unreachable"


@pytest.mark.asyncio
async def test_simulation_engine_run_round_returns_result():
    engine_cls = _build_simulation_engine_class()
    engine = build_instance(engine_cls)

    action = _build_agent_action()
    agent = Mock()
    agent.decide = AsyncMock(return_value=action)

    engine.character_engine = Mock()
    engine.character_engine.decide = AsyncMock(return_value=action)

    world_master = Mock()
    world_master.arbitrate = AsyncMock(return_value=_build_dm_arbitration())
    world_master.inject_sensory_seeds = AsyncMock(return_value=[{"type": "weather"}])
    engine.world_master = world_master

    engine.calculate_info_gain = AsyncMock(return_value=0.3)

    result = await engine.run_round(
        {"scene": "ctx"},
        [agent],
        AttrDict(round_id="r1"),
    )

    assert isinstance(result, SimulationRoundResult)
    assert result.info_gain == 0.3
    world_master.arbitrate.assert_awaited_once()
    world_master.inject_sensory_seeds.assert_awaited_once()


@pytest.mark.asyncio
async def test_simulation_engine_run_scene_triggers_inject_incident():
    engine_cls = _build_simulation_engine_class()
    engine = build_instance(engine_cls)

    engine.run_round = AsyncMock(return_value=_build_round(info_gain=0.05))

    world_master = Mock()
    world_master.monitor_pacing = AsyncMock(return_value=SimpleNamespace(type="inject_incident"))
    engine.world_master = world_master

    engine.inject_breaking_incident = AsyncMock()
    engine.smart_render = AsyncMock(return_value="rendered")
    engine.smart_renderer = Mock()
    engine.smart_renderer.render = AsyncMock(return_value="rendered")
    engine.should_end_scene = Mock(return_value=True)

    await engine.run_scene({"scene": "ctx"}, AttrDict(max_rounds=1))

    world_master.monitor_pacing.assert_awaited_once()
    engine.inject_breaking_incident.assert_awaited_once()


@pytest.mark.asyncio
async def test_smart_renderer_filters_low_info_gain_rounds():
    renderer_cls = _build_smart_renderer_class()
    renderer = build_instance(renderer_cls)

    rounds = [_build_round(info_gain=0.05), _build_round(info_gain=0.2)]

    beats = await renderer.extract_narrative_beats(rounds)

    assert isinstance(beats, list)
    assert len(beats) == 1
