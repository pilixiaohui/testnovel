"""雪花流程编排，负责将 LLM 输出组织成业务步骤。"""

from __future__ import annotations

from typing import List, Sequence

from app.models import CharacterSheet, SceneNode, SnowflakeRoot
from app.services.llm_engine import LLMEngine


class SnowflakeManager:
    """雪花写作法的业务 orchestrator。"""

    def __init__(
        self,
        engine: LLMEngine,
        min_scenes: int = 50,
        max_scenes: int = 100,
    ):
        self.engine = engine
        self.min_scenes = min_scenes
        self.max_scenes = max_scenes

    async def execute_step_1_logline(self, raw_idea: str) -> List[str]:
        options = await self.engine.generate_logline_options(raw_idea)
        if not options:
            raise ValueError("No logline options generated")
        return options

    async def execute_step_2_structure(self, selected_logline: str) -> SnowflakeRoot:
        return await self.engine.generate_root_structure(selected_logline)

    async def execute_step_3_characters(
        self, root: SnowflakeRoot
    ) -> List[CharacterSheet]:
        characters = await self.engine.generate_characters(root)

        validator = getattr(self.engine, "validate_characters", None)
        if callable(validator):
            validation = await validator(root, characters)
            if hasattr(validation, "valid") and not validation.valid:
                issues = getattr(validation, "issues", None) or []
                details = "; ".join(issues) if issues else "Character validation failed"
                raise ValueError(details)

        return characters

    async def execute_step_4_scenes(
        self, root: SnowflakeRoot, characters: Sequence[CharacterSheet]
    ) -> List[SceneNode]:
        scenes = await self.engine.generate_scene_list(root, characters)

        if not self.min_scenes <= len(scenes) <= self.max_scenes:
            raise ValueError(
                f"Scene count {len(scenes)} outside required range "
                f"{self.min_scenes}-{self.max_scenes}"
            )

        ids = [str(scene.id) for scene in scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("Scene IDs must be unique")

        for scene in scenes:
            if not scene.expected_outcome or not scene.expected_outcome.strip():
                raise ValueError("Scene expected_outcome is required")
            if not scene.conflict_type or not scene.conflict_type.strip():
                raise ValueError("Scene conflict_type is required")

        return scenes
