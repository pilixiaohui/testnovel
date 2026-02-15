"""Character agent engine (BDI decision flow)."""

from __future__ import annotations

import json
from typing import Dict, List, Sequence

from app.models import AgentAction, Intention

_TOP_DESIRE_LIMIT = 3


class CharacterAgentEngine:
    """BDI 角色代理引擎。"""

    def __init__(self, storage, llm):
        self.storage = storage
        self.llm = llm

    @staticmethod
    def _serialize_intentions(intentions: Sequence[object]) -> list[dict[str, object]]:
        serialized: list[dict[str, object]] = []
        for intent in intentions:
            if isinstance(intent, Intention):
                serialized.append(intent.model_dump())
            elif isinstance(intent, dict):
                serialized.append(intent)
            elif hasattr(intent, "model_dump"):
                serialized.append(intent.model_dump())
            else:
                raise ValueError("intention must be a dict or Intention")
        return serialized

    @staticmethod
    def _extract_beliefs_patch(payload: dict[str, object]) -> dict[str, object]:
        patch = payload.get("beliefs_patch")
        if patch is None:
            patch = payload.get("beliefs")
        if not isinstance(patch, dict):
            raise ValueError("beliefs_patch must be object")
        return patch

    @staticmethod
    def _load_desires(raw: object) -> list[dict[str, object]]:
        if raw is None:
            return []
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, list):
            raise ValueError("agent desires must be list")
        desires: list[dict[str, object]] = []
        for item in raw:
            if isinstance(item, dict):
                desires.append(item)
            elif hasattr(item, "model_dump"):
                desires.append(item.model_dump())
            else:
                raise ValueError("agent desires must be list of objects")
        return desires

    @staticmethod
    def _filter_active_desires(
        desires: list[dict[str, object]], last_updated_scene: int
    ) -> list[dict[str, object]]:
        active: list[dict[str, object]] = []
        for desire in desires:
            expires_at = desire.get("expires_at_scene")
            if expires_at is None or expires_at >= last_updated_scene:
                active.append(desire)
        return active

    async def perceive(self, agent_id: str, scene_context: Dict[str, object]) -> dict:
        payload = await self.llm.generate_agent_perception(
            {"agent_id": agent_id}, str(scene_context)
        )
        beliefs_patch = self._extract_beliefs_patch(payload)
        if hasattr(self.storage, "update_agent_beliefs"):
            return self.storage.update_agent_beliefs(
                agent_id=agent_id, beliefs_patch=beliefs_patch
            )
        return {"beliefs": beliefs_patch}

    async def deliberate(self, agent_id: str) -> List[Intention]:
        if not hasattr(self.storage, "get_agent_state"):
            return await self.llm.generate_agent_intentions(
                {"agent_id": agent_id}, f"agent_id: {agent_id}"
            )
        agent_state = self.storage.get_agent_state(agent_id)
        if agent_state is None:
            raise KeyError(f"agent state not found: {agent_id}")
        desires = self._load_desires(getattr(agent_state, "desires", None))
        last_updated = getattr(agent_state, "last_updated_scene", 0) or 0
        active = self._filter_active_desires(desires, last_updated)
        active.sort(key=lambda item: item.get("priority", 0), reverse=True)
        top_desires = active[:_TOP_DESIRE_LIMIT]
        profile = {"agent_id": agent_id, "desires": top_desires}
        return await self.llm.generate_agent_intentions(
            profile, f"agent_id: {agent_id}"
        )

    async def act(self, agent_id: str, scene_context: Dict[str, object]) -> AgentAction:
        if not isinstance(scene_context, dict):
            raise ValueError("scene_context must be dict")
        if "scene" not in scene_context:
            raise ValueError("scene_context requires scene")
        intentions = await self.deliberate(agent_id)
        if not intentions:
            return AgentAction(
                agent_id=agent_id,
                internal_thought="wait",
                action_type="wait",
                action_target="",
                dialogue=None,
                action_description="wait",
            )
        return await self.llm.generate_agent_action(
            {"agent_id": agent_id},
            str(scene_context),
            self._serialize_intentions(intentions),
        )

    async def decide(self, agent_id: str, scene_context: Dict[str, object]) -> AgentAction:
        await self.perceive(agent_id, scene_context)
        await self.deliberate(agent_id)
        return await self.act(agent_id, scene_context)
