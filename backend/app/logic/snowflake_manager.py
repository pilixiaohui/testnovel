"""雪花流程编排，负责将 LLM 输出组织成业务步骤。"""

from __future__ import annotations

from typing import List, Sequence

from app.models import CharacterSheet, SnowflakeRoot
from app.services.llm_engine import LLMEngine


class SnowflakeManager:
    """雪花写作法的业务 orchestrator。"""

    def __init__(self, engine: LLMEngine):
        self.engine = engine

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

