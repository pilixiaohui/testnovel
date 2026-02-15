import pytest

from app.constants import DEFAULT_BRANCH_ID
from app.services.llm_engine import LocalStoryEngine


@pytest.mark.asyncio
async def test_generate_logline_options_returns_ten_and_strips():
    engine = LocalStoryEngine()
    result = await engine.generate_logline_options(" idea ")
    assert len(result) == 10
    assert result[0].startswith("idea")


@pytest.mark.asyncio
async def test_generate_logline_options_rejects_blank():
    engine = LocalStoryEngine()
    with pytest.raises(ValueError):
        await engine.generate_logline_options("   ")


@pytest.mark.asyncio
async def test_generate_root_structure_requires_non_empty():
    engine = LocalStoryEngine()
    with pytest.raises(ValueError):
        await engine.generate_root_structure(" ")


@pytest.mark.asyncio
async def test_validate_characters_returns_valid():
    engine = LocalStoryEngine()
    root = await engine.generate_root_structure("Seed idea")
    characters = await engine.generate_characters(root)
    result = await engine.validate_characters(root, characters)
    assert result.valid is True
    assert result.issues == []


@pytest.mark.asyncio
async def test_generate_scene_list_assigns_pov_and_branch():
    engine = LocalStoryEngine()
    root = await engine.generate_root_structure("Seed idea")
    characters = await engine.generate_characters(root)
    scenes = await engine.generate_scene_list(root, characters)
    assert len(scenes) == 50
    assert all(scene.branch_id == DEFAULT_BRANCH_ID for scene in scenes)
    assert all(scene.pov_character_id is not None for scene in scenes)


@pytest.mark.asyncio
async def test_generate_scene_list_requires_characters():
    engine = LocalStoryEngine()
    root = await engine.generate_root_structure("Seed idea")
    with pytest.raises(ValueError):
        await engine.generate_scene_list(root, [])


@pytest.mark.asyncio
async def test_generate_act_list_returns_required_fields():
    engine = LocalStoryEngine()
    root = await engine.generate_root_structure("Seed idea")
    characters = await engine.generate_characters(root)
    acts = await engine.generate_act_list(root, characters)
    assert len(acts) == 3
    assert all(act.get("title") for act in acts)
    assert all(act.get("purpose") for act in acts)
    assert all(act.get("tone") for act in acts)


@pytest.mark.asyncio
async def test_generate_chapter_list_returns_three_chapters():
    engine = LocalStoryEngine()
    root = await engine.generate_root_structure("Seed idea")
    characters = await engine.generate_characters(root)
    chapters = await engine.generate_chapter_list(root, {"title": "Act 1"}, characters)
    assert len(chapters) == 3
    assert all(chapter.get("title") for chapter in chapters)
    assert all(chapter.get("focus") for chapter in chapters)
    assert all(chapter.get("pov_character_id") for chapter in chapters)


@pytest.mark.asyncio
async def test_generate_story_anchors_returns_valid_types():
    engine = LocalStoryEngine()
    root = await engine.generate_root_structure("Seed idea")
    characters = await engine.generate_characters(root)
    acts = await engine.generate_act_list(root, characters)
    anchors = await engine.generate_story_anchors(root, characters, acts)
    assert 10 <= len(anchors) <= 15
    valid_types = {"inciting_incident", "midpoint", "climax", "resolution"}
    valid_constraints = {"hard", "soft", "flexible"}
    for anchor in anchors:
        assert anchor.get("anchor_type") in valid_types
        assert anchor.get("constraint_type") in valid_constraints
        required = anchor.get("required_conditions")
        assert isinstance(required, list)

