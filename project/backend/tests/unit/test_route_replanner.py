from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.world_master import WorldMasterEngine


def _get_anchor_value(anchor, name: str):
    if isinstance(anchor, dict):
        return anchor.get(name)
    return getattr(anchor, name)


def _assert_anchor_shape(anchor):
    assert anchor is not None
    anchor_type = _get_anchor_value(anchor, "anchor_type")
    description = _get_anchor_value(anchor, "description")
    constraint_type = _get_anchor_value(anchor, "constraint_type")
    required_conditions = _get_anchor_value(anchor, "required_conditions")

    assert isinstance(anchor_type, str) and anchor_type
    assert isinstance(description, str) and description
    assert isinstance(constraint_type, str) and constraint_type
    assert isinstance(required_conditions, list)
    assert all(isinstance(item, str) for item in required_conditions)


@pytest.mark.asyncio
async def test_replan_route_recoverable_gap_generates_bridge_chapters():
    engine = WorldMasterEngine()
    engine.analyze_gap = AsyncMock(return_value=SimpleNamespace(severity=0.5))
    engine.generate_bridge_chapters = AsyncMock(return_value=[{"title": "bridge"}])

    target_anchor = {
        "constraint_type": "hard",
        "required_conditions": ["cond"],
    }

    result = await engine.replan_route("scene-alpha", target_anchor, {"state": 1})

    assert result.success is True
    assert result.new_chapters == [{"title": "bridge"}]
    assert result.reason == "recoverable"
    engine.generate_bridge_chapters.assert_awaited_once_with(
        from_state={"state": 1},
        to_conditions=["cond"],
        max_chapters=3,
    )


@pytest.mark.asyncio
async def test_replan_route_hard_anchor_unreachable_when_gap_high():
    engine = WorldMasterEngine()
    engine.analyze_gap = AsyncMock(return_value=SimpleNamespace(severity=0.9))

    target_anchor = {
        "constraint_type": "hard",
        "required_conditions": ["cond"],
    }

    result = await engine.replan_route("scene-alpha", target_anchor, {"state": 1})

    assert result.success is False
    assert result.reason == "hard_anchor_unreachable"


@pytest.mark.asyncio
async def test_replan_route_flexible_anchor_returns_modified_anchor():
    engine = WorldMasterEngine()
    engine.analyze_gap = AsyncMock(return_value=SimpleNamespace(severity=0.9))
    engine.generate_equivalent_anchor = AsyncMock(
        return_value={
            "anchor_type": "alt",
            "description": "alt path",
            "constraint_type": "flexible",
            "required_conditions": ["cond"],
        }
    )

    target_anchor = {
        "anchor_type": "midpoint",
        "description": "hero gains ally",
        "constraint_type": "flexible",
        "required_conditions": ["cond"],
    }

    result = await engine.replan_route("scene-alpha", target_anchor, {"state": 1})

    assert result.success is True
    assert result.modified_anchor == {
        "anchor_type": "alt",
        "description": "alt path",
        "constraint_type": "flexible",
        "required_conditions": ["cond"],
    }
    assert result.reason == "flexible_anchor"
    engine.generate_equivalent_anchor.assert_awaited_once_with(
        target_anchor, {"state": 1}
    )


@pytest.mark.asyncio
async def test_replan_route_missing_required_conditions_raises_key_error():
    engine = WorldMasterEngine()

    with pytest.raises(KeyError):
        await engine.replan_route("scene-alpha", {"constraint_type": "hard"}, {"state": 1})


@pytest.mark.asyncio
async def test_analyze_gap_reports_missing_conditions_and_severity_range():
    engine = WorldMasterEngine()

    world_state = {
        "hero_has_sword": True,
        "ally_trusts_hero": False,
    }
    required_conditions = ["hero_has_sword", "ally_trusts_hero", "has_map"]

    gap = await engine.analyze_gap(world_state, required_conditions)

    assert 0 <= gap.severity <= 1
    assert isinstance(gap.recoverable, bool)
    assert gap.missing_conditions == ["ally_trusts_hero", "has_map"]


@pytest.mark.asyncio
async def test_analyze_gap_calculates_severity_and_recoverable_threshold():
    engine = WorldMasterEngine()

    world_state = {"cond_a": True}
    required_conditions = ["cond_a", "cond_b", "cond_c", "cond_d"]

    gap = await engine.analyze_gap(world_state, required_conditions)

    assert gap.severity == 0.75
    assert gap.recoverable is False
    assert gap.missing_conditions == ["cond_b", "cond_c", "cond_d"]


@pytest.mark.asyncio
async def test_generate_bridge_chapters_returns_between_one_and_three():
    engine = WorldMasterEngine()

    chapters = await engine.generate_bridge_chapters(
        from_state={"scene": "intro"},
        to_conditions=["hero_has_sword", "has_map"],
        max_chapters=3,
    )

    assert isinstance(chapters, list)
    assert 1 <= len(chapters) <= 3
    assert all(isinstance(item, dict) for item in chapters)


@pytest.mark.asyncio
async def test_generate_bridge_chapters_maps_goals_and_limits_count():
    engine = WorldMasterEngine()

    chapters = await engine.generate_bridge_chapters(
        from_state={"scene": "intro"},
        to_conditions=["cond_a", "cond_b", "cond_c", "cond_d"],
        max_chapters=2,
    )

    assert [item["goal"] for item in chapters] == ["cond_a", "cond_b"]
    assert len(chapters) == 2


@pytest.mark.asyncio
async def test_generate_bridge_chapters_uses_progress_when_no_conditions():
    engine = WorldMasterEngine()

    chapters = await engine.generate_bridge_chapters(
        from_state={"scene": "intro"},
        to_conditions=[],
        max_chapters=3,
    )

    assert chapters == [{"title": "bridge_1", "goal": "progress"}]


@pytest.mark.asyncio
async def test_soften_anchor_returns_story_anchor_shape():
    engine = WorldMasterEngine()
    target_anchor = {
        "anchor_type": "midpoint",
        "description": "hero gains ally",
        "constraint_type": "hard",
        "required_conditions": ["ally_trusts_hero"],
    }

    modified = await engine.soften_anchor(
        target_anchor, {"ally_trusts_hero": False}
    )

    _assert_anchor_shape(modified)


@pytest.mark.asyncio
async def test_soften_anchor_sets_soft_constraint_and_copies_conditions():
    engine = WorldMasterEngine()
    conditions = ["ally_trusts_hero"]
    target_anchor = {
        "anchor_type": "midpoint",
        "description": "hero gains ally",
        "constraint_type": "hard",
        "required_conditions": conditions,
    }

    modified = await engine.soften_anchor(target_anchor, {"ally_trusts_hero": False})

    assert modified["constraint_type"] == "soft"
    assert modified["required_conditions"] == conditions
    assert modified["required_conditions"] is not conditions


@pytest.mark.asyncio
async def test_generate_equivalent_anchor_returns_story_anchor_shape():
    engine = WorldMasterEngine()
    target_anchor = {
        "anchor_type": "midpoint",
        "description": "hero gains ally",
        "constraint_type": "flexible",
        "required_conditions": ["ally_trusts_hero"],
    }

    modified = await engine.generate_equivalent_anchor(
        target_anchor, {"ally_trusts_hero": False}
    )

    _assert_anchor_shape(modified)


@pytest.mark.asyncio
async def test_generate_equivalent_anchor_prefixes_description_and_sets_flexible():
    engine = WorldMasterEngine()
    target_anchor = {
        "anchor_type": "midpoint",
        "description": "hero gains ally",
        "constraint_type": "hard",
        "required_conditions": ["ally_trusts_hero"],
    }

    modified = await engine.generate_equivalent_anchor(
        target_anchor, {"ally_trusts_hero": False}
    )

    assert modified["constraint_type"] == "flexible"
    assert modified["description"] == "equivalent: hero gains ally"


@pytest.mark.asyncio
async def test_replan_route_soft_anchor_returns_modified_anchor():
    engine = WorldMasterEngine()
    engine.analyze_gap = AsyncMock(return_value=SimpleNamespace(severity=0.9))
    engine.soften_anchor = AsyncMock(
        return_value={
            "anchor_type": "midpoint",
            "description": "softened",
            "constraint_type": "soft",
            "required_conditions": ["cond"],
        }
    )

    target_anchor = {
        "anchor_type": "midpoint",
        "description": "hero gains ally",
        "constraint_type": "soft",
        "required_conditions": ["cond"],
    }

    result = await engine.replan_route("scene-alpha", target_anchor, {"state": 1})

    assert result.success is True
    assert result.modified_anchor == {
        "anchor_type": "midpoint",
        "description": "softened",
        "constraint_type": "soft",
        "required_conditions": ["cond"],
    }
    assert result.reason == "soft_anchor"
    engine.soften_anchor.assert_awaited_once_with(target_anchor, {"state": 1})


@pytest.mark.asyncio
async def test_detect_conflicts_reports_mutual_attack():
    engine = WorldMasterEngine()
    actions = [
        SimpleNamespace(agent_id="a1", action_type="attack", action_target="a2"),
        SimpleNamespace(agent_id="a2", action_type="attack", action_target="a1"),
    ]

    conflicts = await engine.detect_conflicts(actions)

    assert len(conflicts) == 1
    assert conflicts[0]["type"] == "mutual_attack"
    assert conflicts[0]["agents"] == ["a1", "a2"]


@pytest.mark.asyncio
async def test_detect_conflicts_reports_shared_target():
    engine = WorldMasterEngine()
    actions = [
        SimpleNamespace(agent_id="a1", action_type="investigate", action_target="ruins"),
        SimpleNamespace(agent_id="a2", action_type="investigate", action_target="ruins"),
    ]

    conflicts = await engine.detect_conflicts(actions)

    assert len(conflicts) == 1
    assert conflicts[0]["type"] == "shared_target"
    assert conflicts[0]["agents"] == ["a1", "a2"]


@pytest.mark.asyncio
async def test_monitor_pacing_returns_inject_incident_on_low_info_gain():
    engine = WorldMasterEngine()
    rounds = [
        SimpleNamespace(info_gain=0.1, conflict_escalation=0.1),
        SimpleNamespace(info_gain=0.1, conflict_escalation=0.1),
        SimpleNamespace(info_gain=0.1, conflict_escalation=0.1),
    ]

    pacing = await engine.monitor_pacing(rounds)

    assert pacing.type == "inject_incident"
    assert pacing.reason == "stagnation"


@pytest.mark.asyncio
async def test_monitor_pacing_returns_force_escalation_on_deescalation():
    engine = WorldMasterEngine()
    rounds = [
        SimpleNamespace(info_gain=0.3, conflict_escalation=0.6),
        SimpleNamespace(info_gain=0.3, conflict_escalation=0.4),
        SimpleNamespace(info_gain=0.3, conflict_escalation=0.2),
    ]

    pacing = await engine.monitor_pacing(rounds)

    assert pacing.type == "force_escalation"
    assert pacing.reason == "deescalation"


@pytest.mark.asyncio
async def test_monitor_pacing_returns_continue_when_stable():
    engine = WorldMasterEngine()
    rounds = [
        SimpleNamespace(info_gain=0.3, conflict_escalation=0.2),
        SimpleNamespace(info_gain=0.3, conflict_escalation=0.2),
        SimpleNamespace(info_gain=0.3, conflict_escalation=0.2),
    ]

    pacing = await engine.monitor_pacing(rounds)

    assert pacing.type == "continue"


def test_is_deescalating_returns_false_when_short_history():
    engine = WorldMasterEngine()
    rounds = [
        SimpleNamespace(conflict_escalation=0.3),
        SimpleNamespace(conflict_escalation=0.2),
    ]

    assert engine._is_deescalating(rounds) is False
