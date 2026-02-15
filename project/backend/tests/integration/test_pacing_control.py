from __future__ import annotations

import pytest

from app.models import ActionResult, AgentAction, DMArbitration, SimulationRoundResult
from app.services.simulation_engine import SimulationEngine
from app.services.world_master import WorldMasterEngine


class RoundStub:
    def __init__(self, info_gain: float, conflict_escalation: float) -> None:
        self.info_gain = info_gain
        self.conflict_escalation = conflict_escalation


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


def _build_round(
    *,
    info_gain: float = 0.3,
    convergence_score: float = 0.2,
    stagnation_count: int = 0,
) -> SimulationRoundResult:
    return SimulationRoundResult(
        round_id="round-1",
        agent_actions=[_build_agent_action()],
        dm_arbitration=_build_dm_arbitration(),
        narrative_events=[{"event": "beat"}],
        sensory_seeds=[{"type": "weather", "detail": "rain"}],
        convergence_score=convergence_score,
        drama_score=0.3,
        info_gain=info_gain,
        stagnation_count=stagnation_count,
    )


@pytest.mark.asyncio
async def test_monitor_pacing_inject_incident_when_avg_low():
    engine = WorldMasterEngine()

    rounds = [
        RoundStub(info_gain=0.05, conflict_escalation=0.1),
        RoundStub(info_gain=0.1, conflict_escalation=0.1),
        RoundStub(info_gain=0.0, conflict_escalation=0.1),
    ]

    pacing = await engine.monitor_pacing(rounds)

    assert pacing.type == "inject_incident"


@pytest.mark.asyncio
async def test_monitor_pacing_force_escalation_when_deescalating():
    engine = WorldMasterEngine()

    rounds = [
        RoundStub(info_gain=0.3, conflict_escalation=0.6),
        RoundStub(info_gain=0.3, conflict_escalation=0.4),
        RoundStub(info_gain=0.3, conflict_escalation=0.2),
    ]

    pacing = await engine.monitor_pacing(rounds)

    assert pacing.type == "force_escalation"


@pytest.mark.asyncio
async def test_calculate_info_gain_detects_new_facts():
    engine = SimulationEngine(
        character_engine=object(),
        world_master=object(),
        storage=object(),
        llm=object(),
    )

    prev_state = {
        "facts": ["hero_has_sword"],
        "relations": ["hero:ally:sidekick"],
        "secrets": [],
        "conflict_escalation": 0.1,
    }
    curr_state = {
        "facts": ["hero_has_sword", "villain_identity"],
        "relations": ["hero:ally:sidekick"],
        "secrets": ["villain_identity"],
        "conflict_escalation": 0.6,
    }

    gain = await engine.calculate_info_gain(prev_state, curr_state)

    assert 0.0 < gain <= 1.0

    no_change = {
        "facts": ["hero_has_sword"],
        "relations": ["hero:ally:sidekick"],
        "secrets": [],
        "conflict_escalation": 0.1,
    }
    gain = await engine.calculate_info_gain(prev_state, no_change)

    assert gain == 0.0


@pytest.mark.asyncio
async def test_inject_breaking_incident_appends_event():
    engine = SimulationEngine(
        character_engine=object(),
        world_master=object(),
        storage=object(),
        llm=object(),
    )

    scene_context = {"events": []}

    await engine.inject_breaking_incident(scene_context)

    assert scene_context["events"]
    assert scene_context["events"][-1]["type"] == "breaking_incident"


@pytest.mark.asyncio
async def test_force_conflict_escalation_increases_level():
    engine = SimulationEngine(
        character_engine=object(),
        world_master=object(),
        storage=object(),
        llm=object(),
    )

    scene_context = {"events": [], "conflict_escalation": 0.2}

    await engine.force_conflict_escalation(scene_context)

    assert scene_context["conflict_escalation"] > 0.2
    assert scene_context["events"][-1]["type"] == "force_escalation"


def test_should_end_scene_when_stagnant_or_converged():
    engine = SimulationEngine(
        character_engine=object(),
        world_master=object(),
        storage=object(),
        llm=object(),
    )

    converged = _build_round(convergence_score=0.95, stagnation_count=0)
    assert engine.should_end_scene(converged) is True

    stagnant = _build_round(convergence_score=0.2, stagnation_count=3)
    assert engine.should_end_scene(stagnant) is True

    ongoing = _build_round(convergence_score=0.2, stagnation_count=0)
    assert engine.should_end_scene(ongoing) is False
