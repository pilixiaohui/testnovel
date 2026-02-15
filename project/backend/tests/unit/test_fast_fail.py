import pytest
from pydantic import ValidationError

from app.main import SimulationRoundPayload, SimulationScenePayload
from app.services.simulation_engine import SimulationEngine
from app.services.smart_renderer import SmartRenderer


def _build_engine(*, smart_renderer=None) -> SimulationEngine:
    return SimulationEngine(
        character_engine=object(),
        world_master=object(),
        storage=object(),
        llm=object(),
        smart_renderer=smart_renderer,
    )


@pytest.mark.asyncio
async def test_smart_renderer_requires_llm():
    renderer = SmartRenderer()
    with pytest.raises(ValueError, match="llm is required for smart rendering"):
        await renderer.render([], {"id": "scene-alpha"})


@pytest.mark.asyncio
async def test_simulation_engine_requires_renderer():
    engine = _build_engine(smart_renderer=None)
    with pytest.raises(ValueError, match="smart_renderer is required"):
        await engine.smart_render([], {"scene": "ctx"})


@pytest.mark.asyncio
async def test_inject_breaking_incident_requires_events():
    engine = _build_engine(smart_renderer=object())
    with pytest.raises(ValueError, match="scene_context.events is required"):
        await engine.inject_breaking_incident({})
    with pytest.raises(ValueError, match="scene_context.events must be a list"):
        await engine.inject_breaking_incident({"events": "boom"})


@pytest.mark.asyncio
async def test_force_conflict_escalation_requires_fields():
    engine = _build_engine(smart_renderer=object())
    with pytest.raises(ValueError, match="scene_context.conflict_escalation is required"):
        await engine.force_conflict_escalation({})
    with pytest.raises(ValueError, match="scene_context.events is required"):
        await engine.force_conflict_escalation({"conflict_escalation": 0.2})
    with pytest.raises(ValueError, match="scene_context.events must be a list"):
        await engine.force_conflict_escalation(
            {"conflict_escalation": 0.2, "events": "bad"}
        )


def test_simulation_payload_requires_fields():
    with pytest.raises(ValidationError):
        SimulationScenePayload(max_rounds=1)
    with pytest.raises(ValidationError):
        SimulationRoundPayload(scene_context={}, agents=[])
    with pytest.raises(ValidationError):
        SimulationRoundPayload(scene_context={}, agents=[], round_id="")
