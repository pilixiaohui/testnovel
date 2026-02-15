from unittest.mock import AsyncMock, Mock

import pytest

from app.models import (
    ActionResult,
    AgentAction,
    ConvergenceCheck,
    DMArbitration,
    Intention,
    SnowflakeRoot,
    CharacterSheet,
)

from .llm_contract_helpers import (
    assert_messages_use_prompt,
    get_llm_engine_class,
    get_prompt_submodule,
    get_prompts_module,
    require_async_method,
    require_prompt,
)


def _build_root() -> SnowflakeRoot:
    return SnowflakeRoot(
        logline="Test story",
        three_disasters=["A", "B", "C"],
        ending="End",
        theme="Theme",
    )


def _build_characters() -> list[CharacterSheet]:
    return [
        CharacterSheet(
            name="Hero",
            ambition="Goal",
            conflict="Conflict",
            epiphany="Epiphany",
            voice_dna="Voice",
        )
    ]


def _build_acts() -> list[dict]:
    return [
        {"title": "Act 1", "purpose": "Setup", "tone": "tense"},
        {"title": "Act 2", "purpose": "Confront", "tone": "dark"},
        {"title": "Act 3", "purpose": "Resolve", "tone": "hopeful"},
    ]


def _build_chapters() -> list[dict]:
    return [
        {"title": "Chapter 1", "focus": "Intro", "pov_character_id": "c1"},
        {"title": "Chapter 2", "focus": "Conflict", "pov_character_id": "c1"},
        {"title": "Chapter 3", "focus": "Resolution", "pov_character_id": "c1"},
    ]


def _build_anchors() -> list[dict]:
    base_types = [
        "inciting_incident",
        "midpoint",
        "climax",
        "resolution",
    ]
    anchors: list[dict] = []
    for idx in range(10):
        anchor_type = base_types[idx] if idx < len(base_types) else f"anchor_{idx}"
        anchors.append(
            {
                "anchor_type": anchor_type,
                "description": f"desc-{idx}",
                "constraint_type": "hard",
                "required_conditions": ["cond"],
            }
        )
    return anchors


@pytest.mark.asyncio
async def test_generate_act_list_uses_step5a_prompt():
    llm_engine = get_llm_engine_class()
    require_async_method(llm_engine, "generate_act_list")

    engine = llm_engine(client=Mock())
    engine._call_model = AsyncMock(return_value=_build_acts())

    await engine.generate_act_list(_build_root(), _build_characters())

    prompt = require_prompt(get_prompts_module(), "SNOWFLAKE_STEP5A_SYSTEM_PROMPT")
    messages = engine._call_model.await_args.kwargs["messages"]
    assert_messages_use_prompt(messages, prompt)


@pytest.mark.asyncio
async def test_generate_chapter_list_uses_step5b_prompt():
    llm_engine = get_llm_engine_class()
    require_async_method(llm_engine, "generate_chapter_list")

    engine = llm_engine(client=Mock())
    engine._call_model = AsyncMock(return_value=_build_chapters())

    await engine.generate_chapter_list(_build_root(), _build_acts()[0], _build_characters())

    prompt = require_prompt(get_prompts_module(), "SNOWFLAKE_STEP5B_SYSTEM_PROMPT")
    messages = engine._call_model.await_args.kwargs["messages"]
    assert_messages_use_prompt(messages, prompt)


@pytest.mark.asyncio
async def test_generate_story_anchors_uses_anchor_prompt():
    llm_engine = get_llm_engine_class()
    require_async_method(llm_engine, "generate_story_anchors")

    engine = llm_engine(client=Mock())
    engine._call_model = AsyncMock(return_value=_build_anchors())

    await engine.generate_story_anchors(
        _build_root(), _build_characters(), _build_acts()
    )

    prompt = require_prompt(get_prompts_module(), "STORY_ANCHORS_SYSTEM_PROMPT")
    messages = engine._call_model.await_args.kwargs["messages"]
    assert_messages_use_prompt(messages, prompt)


@pytest.mark.asyncio
async def test_generate_agent_perception_uses_perceive_prompt():
    llm_engine = get_llm_engine_class()
    require_async_method(llm_engine, "generate_agent_perception")

    engine = llm_engine(client=Mock())
    engine._call_model = AsyncMock(return_value={"beliefs_patch": {"fact": "v"}})

    await engine.generate_agent_perception(
        {"name": "Hero", "voice_dna": "Voice"}, "scene"
    )

    prompt = require_prompt(get_prompt_submodule("character_agent"), "PERCEIVE_PROMPT")
    messages = engine._call_model.await_args.kwargs["messages"]
    assert_messages_use_prompt(messages, prompt)


@pytest.mark.asyncio
async def test_generate_agent_intentions_uses_deliberate_prompt():
    llm_engine = get_llm_engine_class()
    require_async_method(llm_engine, "generate_agent_intentions")

    engine = llm_engine(client=Mock())
    intentions = [
        Intention(
            id="i1",
            desire_id="d1",
            action_type="investigate",
            target="target",
            expected_outcome="outcome",
            risk_assessment=0.2,
        )
    ]
    engine._call_model = AsyncMock(return_value=intentions)

    await engine.generate_agent_intentions(
        {"name": "Hero", "voice_dna": "Voice"}, "scene"
    )

    prompt = require_prompt(
        get_prompt_submodule("character_agent"), "DELIBERATE_PROMPT"
    )
    messages = engine._call_model.await_args.kwargs["messages"]
    assert_messages_use_prompt(messages, prompt)


@pytest.mark.asyncio
async def test_generate_agent_action_uses_act_prompt():
    llm_engine = get_llm_engine_class()
    require_async_method(llm_engine, "generate_agent_action")

    engine = llm_engine(client=Mock())
    action = AgentAction(
        agent_id="a1",
        internal_thought="think",
        action_type="wait",
        action_target="",
        dialogue=None,
        action_description="desc",
    )
    engine._call_model = AsyncMock(return_value=action)

    await engine.generate_agent_action(
        {"name": "Hero", "voice_dna": "Voice"},
        "scene",
        [{"intent": "wait"}],
    )

    prompt = require_prompt(get_prompt_submodule("character_agent"), "ACT_PROMPT")
    messages = engine._call_model.await_args.kwargs["messages"]
    assert_messages_use_prompt(messages, prompt)


@pytest.mark.asyncio
async def test_generate_dm_arbitration_uses_arbitration_prompt():
    llm_engine = get_llm_engine_class()
    require_async_method(llm_engine, "generate_dm_arbitration")

    engine = llm_engine(client=Mock())
    arbitration = DMArbitration(
        round_id="r1",
        action_results=[
            ActionResult(
                action_id="a1",
                agent_id="agent",
                success="success",
                reason="ok",
                actual_outcome="outcome",
            )
        ],
    )
    engine._call_model = AsyncMock(return_value=arbitration)

    await engine.generate_dm_arbitration("r1", [{"id": "a1"}], {}, {})

    prompt = require_prompt(get_prompt_submodule("world_master"), "ARBITRATION_PROMPT")
    messages = engine._call_model.await_args.kwargs["messages"]
    assert_messages_use_prompt(messages, prompt)


@pytest.mark.asyncio
async def test_check_convergence_uses_convergence_prompt():
    llm_engine = get_llm_engine_class()
    require_async_method(llm_engine, "check_convergence")

    engine = llm_engine(client=Mock())
    convergence = ConvergenceCheck(
        next_anchor_id="anchor-1",
        distance=0.3,
        convergence_needed=False,
        suggested_action=None,
    )
    engine._call_model = AsyncMock(return_value=convergence)

    await engine.check_convergence({"state": 1}, {"anchor": "a"})

    prompt = require_prompt(
        get_prompt_submodule("world_master"), "CONVERGENCE_CHECK_PROMPT"
    )
    messages = engine._call_model.await_args.kwargs["messages"]
    assert_messages_use_prompt(messages, prompt)


@pytest.mark.asyncio
async def test_render_scene_uses_smart_render_prompt():
    llm_engine = get_llm_engine_class()
    require_async_method(llm_engine, "render_scene")

    engine = llm_engine(client=Mock())
    engine._call_model = AsyncMock(return_value="content")

    await engine.render_scene(
        {"title": "Scene", "pov": "Hero", "tone": "tense"},
        [{"beat": "b1"}],
        [{"detail": "rain"}],
        {"foreshadowing": "x", "voice_dna": "y"},
    )

    prompt = require_prompt(get_prompt_submodule("renderer"), "SMART_RENDER_PROMPT")
    messages = engine._call_model.await_args.kwargs["messages"]
    assert_messages_use_prompt(messages, prompt)
