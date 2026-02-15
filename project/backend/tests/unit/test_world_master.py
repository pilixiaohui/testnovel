from types import SimpleNamespace

import pytest

from app.models import ConvergenceCheck
from app.services.world_master import WorldMasterEngine


@pytest.mark.asyncio
async def test_generate_convergence_action_thresholds():
    engine = WorldMasterEngine()

    cases = [
        (0.4, "npc_hint"),
        (0.6, "environment_pressure"),
        (0.8, "deus_ex_machina"),
        (0.95, "replan_route"),
    ]

    for distance, expected in cases:
        check = ConvergenceCheck(
            next_anchor_id="anchor-1",
            distance=distance,
            convergence_needed=True,
        )
        result = await engine.generate_convergence_action(check, {"state": 1})
        assert result["type"] == expected


@pytest.mark.asyncio
async def test_inject_sensory_seeds_returns_valid_shape_and_count():
    engine = WorldMasterEngine()

    seeds = await engine.inject_sensory_seeds({"scene_id": "scene-alpha", "mood": "tense"})

    assert isinstance(seeds, list)
    assert 1 <= len(seeds) <= 2
    allowed_types = {"weather", "ambient_sound", "character_gesture", "object_detail"}
    for seed in seeds:
        assert isinstance(seed, dict)
        assert seed["type"] in allowed_types
        assert isinstance(seed["detail"], str) and seed["detail"]
        if "char_id" in seed:
            assert isinstance(seed["char_id"], str) and seed["char_id"]


@pytest.mark.asyncio
async def test_inject_sensory_seeds_changes_with_scene_context():
    engine = WorldMasterEngine()

    seeds_a = await engine.inject_sensory_seeds(
        {"scene_id": "scene-alpha", "mood": "tense", "weather": "storm"}
    )
    seeds_b = await engine.inject_sensory_seeds(
        {"scene_id": "scene-2", "mood": "calm", "weather": "sunny"}
    )

    assert seeds_a != seeds_b


@pytest.mark.asyncio
async def test_check_action_validity_returns_partial_on_power_mismatch():
    engine = WorldMasterEngine()
    action = SimpleNamespace(
        action_id="action-1",
        agent_id="agent-1",
        action_type="attack",
        action_target="target-1",
    )
    world_state = {
        "power_levels": {"agent-1": 3, "target-1": 8},
        "position_advantage": {"agent-1": True},
    }

    result = await engine.check_action_validity(action, world_state, rules=[])

    assert result.success == "partial"


@pytest.mark.asyncio
async def test_check_action_validity_returns_partial_on_position_disadvantage():
    engine = WorldMasterEngine()
    action = SimpleNamespace(
        action_id="action-2",
        agent_id="agent-1",
        action_type="attack",
        action_target="target-1",
    )
    world_state = {
        "power_levels": {"agent-1": 9, "target-1": 3},
        "position_advantage": {"agent-1": False},
    }

    result = await engine.check_action_validity(action, world_state, rules=[])

    assert result.success == "partial"


@pytest.mark.asyncio
async def test_check_action_validity_returns_success_on_advantage():
    engine = WorldMasterEngine()
    action = SimpleNamespace(
        action_id="action-3",
        agent_id="agent-1",
        action_type="attack",
        action_target="target-1",
    )
    world_state = {
        "power_levels": {"agent-1": 9, "target-1": 3},
        "position_advantage": {"agent-1": True},
    }

    result = await engine.check_action_validity(action, world_state, rules=[])

    assert result.success == "success"
