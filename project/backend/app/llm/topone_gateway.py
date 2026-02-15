"""TopOne 统一网关：LLM 输出 -> JSON -> Pydantic 校验（快速失败）。"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Mapping, Sequence, TypeVar

from pydantic import TypeAdapter, ValidationError

from app.llm import prompts
from app.llm.schemas import (
    LogicCheckPayload,
    LogicCheckResult,
    SceneRenderPayload,
    StateExtractPayload,
    StateProposal,
)
from app.models import CharacterSheet, CharacterValidationResult, SceneNode, SnowflakeRoot
from app.services.topone_client import ToponeClient

T = TypeVar("T")


class LLMRole(str, Enum):
    ARCHITECT = "architect"
    REASONING = "reasoning"
    CREATIVE = "creative"
    FLASH = "flash"


def _model_for_role(client: ToponeClient, role: LLMRole) -> str:
    if role == LLMRole.FLASH:
        return client.secondary_model
    return client.default_model


def _extract_text(payload: Mapping[str, Any]) -> str:
    candidates = payload["candidates"]
    first = candidates[0]
    parts = first["content"]["parts"]
    return "".join(part["text"] for part in parts)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) < 3:
        return stripped
    if not lines[-1].strip().startswith("```"):
        return stripped
    return "\n".join(lines[1:-1]).strip()


def _parse_json_payload(text: str) -> Any:
    candidate = _strip_code_fence(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON model output: {exc.msg}") from exc


async def _generate_structured_output(
    *,
    client: ToponeClient,
    role: LLMRole,
    system_prompt: str,
    user_text: str,
    output_type: Any,
    generation_config: Mapping[str, Any] | None = None,
) -> T:
    response = await client.generate_content(
        messages=[{"role": "user", "text": user_text}],
        system_instruction=system_prompt,
        generation_config=generation_config,
        model=_model_for_role(client, role),
    )
    text = _extract_text(response).strip()
    parsed = _parse_json_payload(text)
    try:
        return TypeAdapter(output_type).validate_python(parsed)
    except ValidationError as exc:
        raise ValueError(f"invalid structured output schema: {exc}") from exc


class ToponeGateway:
    """对业务层暴露的 TopOne 单一入口。"""

    def __init__(self, client: ToponeClient) -> None:
        self._client = client

    async def generate_logline_options(self, raw_idea: str) -> list[str]:
        return await _generate_structured_output(
            client=self._client,
            role=LLMRole.CREATIVE,
            system_prompt=prompts.SNOWFLAKE_STEP1_SYSTEM_PROMPT,
            user_text=raw_idea,
            output_type=list[str],
        )

    async def generate_root_structure(self, idea: str) -> SnowflakeRoot:
        return await _generate_structured_output(
            client=self._client,
            role=LLMRole.ARCHITECT,
            system_prompt=prompts.SNOWFLAKE_STEP2_SYSTEM_PROMPT,
            user_text=idea,
            output_type=SnowflakeRoot,
        )

    async def generate_characters(self, root: SnowflakeRoot) -> list[CharacterSheet]:
        user_text = (
            f'logline: {root.logline}\nthree_disasters: {root.three_disasters}\n'
            f"ending: {root.ending}\ntheme: {root.theme}"
        )
        return await _generate_structured_output(
            client=self._client,
            role=LLMRole.CREATIVE,
            system_prompt=prompts.SNOWFLAKE_STEP3_SYSTEM_PROMPT,
            user_text=user_text,
            output_type=list[CharacterSheet],
        )

    async def validate_characters(
        self, root: SnowflakeRoot, characters: Sequence[CharacterSheet]
    ) -> CharacterValidationResult:
        user_text = f"logline: {root.logline}\ncharacters: {[c.model_dump() for c in characters]}"
        return await _generate_structured_output(
            client=self._client,
            role=LLMRole.REASONING,
            system_prompt=prompts.SNOWFLAKE_VALIDATE_CHARACTERS_SYSTEM_PROMPT,
            user_text=user_text,
            output_type=CharacterValidationResult,
        )

    async def generate_scene_list(
        self, root: SnowflakeRoot, characters: Sequence[CharacterSheet]
    ) -> list[SceneNode]:
        user_text = (
            f"logline: {root.logline}\nthree_disasters: {root.three_disasters}\n"
            f"characters: {[c.model_dump() for c in characters]}"
        )
        return await _generate_structured_output(
            client=self._client,
            role=LLMRole.CREATIVE,
            system_prompt=prompts.SNOWFLAKE_STEP4_SYSTEM_PROMPT,
            user_text=user_text,
            output_type=list[SceneNode],
        )

    async def generate_act_list(
        self, root: SnowflakeRoot, characters: Sequence[CharacterSheet]
    ) -> list[dict[str, object]]:
        user_text = (
            f"logline: {root.logline}\n"
            f"three_disasters: {root.three_disasters}\n"
            f"ending: {root.ending}\n"
            f"theme: {root.theme}\n"
            f"characters: {[c.model_dump() for c in characters]}"
        )
        return await _generate_structured_output(
            client=self._client,
            role=LLMRole.ARCHITECT,
            system_prompt=prompts.SNOWFLAKE_STEP5A_SYSTEM_PROMPT,
            user_text=user_text,
            output_type=list[dict[str, object]],
        )

    async def generate_chapter_list(
        self,
        root: SnowflakeRoot,
        act: Mapping[str, Any],
        characters: Sequence[CharacterSheet],
    ) -> list[dict[str, object]]:
        prompt_constraint = act.get("prompt_constraint")
        system_prompt = prompts.SNOWFLAKE_STEP5B_SYSTEM_PROMPT
        if prompt_constraint:
            system_prompt = (
                f"{system_prompt}\n必须严格遵守 prompt_constraint: {prompt_constraint}"
            )
        user_text = (
            f"logline: {root.logline}\n"
            f"act: {act}\n"
            f"characters: {[c.model_dump() for c in characters]}"
        )
        return await _generate_structured_output(
            client=self._client,
            role=LLMRole.ARCHITECT,
            system_prompt=system_prompt,
            user_text=user_text,
            output_type=list[dict[str, object]],
        )

    async def generate_story_anchors(
        self,
        root: SnowflakeRoot,
        characters: Sequence[CharacterSheet],
        acts: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, object]]:
        user_text = (
            f"logline: {root.logline}\n"
            f"acts: {list(acts)}\n"
            f"characters: {[c.model_dump() for c in characters]}"
        )
        return await _generate_structured_output(
            client=self._client,
            role=LLMRole.ARCHITECT,
            system_prompt=prompts.STORY_ANCHORS_SYSTEM_PROMPT,
            user_text=user_text,
            output_type=list[dict[str, object]],
        )

    async def logic_check(self, payload: LogicCheckPayload) -> LogicCheckResult:
        user_text = json.dumps(payload.model_dump(exclude_none=True), ensure_ascii=False)
        return await _generate_structured_output(
            client=self._client,
            role=LLMRole.REASONING,
            system_prompt=prompts.LOGIC_CHECK_SYSTEM_PROMPT,
            user_text=user_text,
            output_type=LogicCheckResult,
        )

    async def state_extract(self, payload: StateExtractPayload) -> list[StateProposal]:
        user_text = json.dumps(payload.model_dump(exclude_none=True), ensure_ascii=False)
        return await _generate_structured_output(
            client=self._client,
            role=LLMRole.FLASH,
            system_prompt=prompts.STATE_EXTRACT_SYSTEM_PROMPT,
            user_text=user_text,
            output_type=list[StateProposal],
        )

    async def generate_structured(
        self, payload: Mapping[str, Any]
    ) -> dict[str, str]:
        user_text = json.dumps(payload, ensure_ascii=False)
        return await _generate_structured_output(
            client=self._client,
            role=LLMRole.FLASH,
            system_prompt=prompts.ENTITY_RESOLUTION_SYSTEM_PROMPT,
            user_text=user_text,
            output_type=dict[str, str],
        )

    async def render_scene(self, payload: SceneRenderPayload) -> str:
        user_text = json.dumps(payload.model_dump(exclude_none=True), ensure_ascii=False)
        system_prompt = prompts.RENDER_SCENE_SYSTEM_PROMPT
        if payload.logic_exception or payload.force_reason:
            system_prompt = f"{system_prompt}\n戏剧性优先。"
        response = await self._client.generate_content(
            messages=[{"role": "user", "text": user_text}],
            system_instruction=system_prompt,
            model=_model_for_role(self._client, LLMRole.CREATIVE),
        )
        return _extract_text(response).strip()

    async def generate_prose(
        self,
        *,
        beats: Sequence[Mapping[str, Any]],
        sensory: Mapping[str, Sequence[Mapping[str, Any]]],
        style: Mapping[str, Any],
        pov: str | None,
    ) -> str:
        beat_labels = [
            str(item.get("event"))
            for item in beats
            if isinstance(item, Mapping) and item.get("event")
        ]
        sensory_details = [
            str(seed.get("detail"))
            for seed_list in sensory.values()
            for seed in seed_list
            if isinstance(seed, Mapping) and seed.get("detail")
        ]
        style_hint = style.get("tone") if isinstance(style, Mapping) else None
        pov_label = pov if isinstance(pov, str) and pov else "unknown"
        segments = [
            f"POV:{pov_label}",
            "；".join(beat_labels) if beat_labels else "叙事推进",
        ]
        if sensory_details:
            segments.append(" ".join(sensory_details[:2]))
        if isinstance(style_hint, str) and style_hint:
            segments.append(style_hint)
        return " ".join(segments)
