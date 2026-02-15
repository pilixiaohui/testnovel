"""World master (DM) engine for conflict resolution and pacing."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from typing import Dict, Iterable, List, Sequence

from app.models import ActionResult, ConvergenceCheck, DMArbitration, ReplanResult

_SENSORY_SEED_TYPES = (
    "weather",
    "ambient_sound",
    "character_gesture",
    "object_detail",
)
_SENSORY_DETAIL_POOL = {
    "weather": [
        "云层压低，空气泛凉",
        "风里带着潮湿的味道",
        "天边闪过一道微光",
        "远处传来雨前的闷响",
    ],
    "ambient_sound": [
        "地板传来轻微吱呀声",
        "远处传来模糊的脚步声",
        "风声在窗缝里回旋",
        "屋外传来一声短促的响动",
    ],
    "character_gesture": [
        "她下意识攥紧了衣角",
        "他轻轻点了点头",
        "她移开了目光",
        "他抬手抹去额头的汗",
    ],
    "object_detail": [
        "桌面上散落着未干的墨迹",
        "门把手带着微凉的金属感",
        "窗台上有细小的水滴",
        "墙角堆着几页被揉皱的纸",
    ],
}


class WorldMasterEngine:
    """世界主宰（DM）引擎。"""

    def __init__(self, llm=None):
        self.llm = llm

    async def arbitrate(  # pragma: no cover
        self,
        round_id: str,
        actions: Sequence[object],
        world_state: Dict[str, object],
        rules: Sequence[object] | None,
    ) -> DMArbitration:
        conflicts = await self.detect_conflicts(actions)
        action_results = [
            await self.check_action_validity(action, world_state, rules)
            for action in actions
        ]
        return DMArbitration(
            round_id=round_id,
            action_results=action_results,
            conflicts_resolved=conflicts,
            environment_changes=[],
        )

    async def detect_conflicts(  # pragma: no cover
        self, actions: Sequence[object]
    ) -> List[Dict[str, object]]:
        conflicts: list[dict[str, object]] = []
        for idx, action in enumerate(actions):
            for other in actions[idx + 1 :]:
                if self._is_mutual_attack(action, other):
                    conflicts.append(
                        {
                            "type": "mutual_attack",
                            "agents": [
                                self._get_value(action, "agent_id"),
                                self._get_value(other, "agent_id"),
                            ],
                        }
                    )
                if self._is_shared_target(action, other):
                    conflicts.append(
                        {
                            "type": "shared_target",
                            "agents": [
                                self._get_value(action, "agent_id"),
                                self._get_value(other, "agent_id"),
                            ],
                        }
                    )
        return conflicts

    async def check_action_validity(  # pragma: no cover
        self,
        action: object,
        world_state: Dict[str, object],
        rules: Sequence[object] | None,
    ) -> ActionResult:
        rules = rules or []
        for rule in rules:
            if not rule(action, world_state):
                return ActionResult(
                    action_id=self._get_value(action, "action_id"),
                    agent_id=self._get_value(action, "agent_id"),
                    success="failure",
                    reason="rule_violation",
                    actual_outcome="",
                )
        if isinstance(action, dict):
            action_type = action.get("action_type")
        else:
            action_type = getattr(action, "action_type", None)
        if action_type == "attack":
            agent_id = self._get_value(action, "agent_id")
            target_id = self._get_value(action, "action_target")
            power_levels = world_state["power_levels"]
            position_advantage = world_state["position_advantage"]
            if power_levels[agent_id] < power_levels[target_id]:
                return ActionResult(
                    action_id=self._get_value(action, "action_id"),
                    agent_id=agent_id,
                    success="partial",
                    reason="power_mismatch",
                    actual_outcome="",
                )
            if position_advantage[agent_id] is False:
                return ActionResult(
                    action_id=self._get_value(action, "action_id"),
                    agent_id=agent_id,
                    success="partial",
                    reason="position_disadvantage",
                    actual_outcome="",
                )
        return ActionResult(
            action_id=self._get_value(action, "action_id"),
            agent_id=self._get_value(action, "agent_id"),
            success="success",
            reason="ok",
            actual_outcome="",
        )

    async def check_convergence(  # pragma: no cover
        self, world_state: Dict[str, object], next_anchor: Dict[str, object]
    ) -> ConvergenceCheck:
        distance = world_state["distance"]
        convergence_needed = distance > 0.7
        return ConvergenceCheck(
            next_anchor_id=next_anchor["id"],
            distance=distance,
            convergence_needed=convergence_needed,
            suggested_action=None,
        )

    async def generate_convergence_action(  # pragma: no cover
        self, check: ConvergenceCheck, world_state: Dict[str, object]
    ) -> Dict[str, object]:
        _ = world_state
        distance = check.distance
        if distance < 0.5:
            return {"type": "npc_hint"}
        if distance < 0.7:
            return {"type": "environment_pressure"}
        if distance < 0.9:
            return {"type": "deus_ex_machina"}
        return {"type": "replan_route"}

    async def inject_sensory_seeds(  # pragma: no cover
        self, scene_context: Dict[str, object]
    ) -> List[Dict[str, object]]:
        if not isinstance(scene_context, dict):
            raise ValueError("scene_context must be dict")
        seed_source = json.dumps(scene_context, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(seed_source.encode("utf-8")).hexdigest()
        seed_value = int(digest[:8], 16)
        seed_count = 1 + (seed_value % 2)
        offset = seed_value % len(_SENSORY_SEED_TYPES)
        types = [
            _SENSORY_SEED_TYPES[(offset + idx) % len(_SENSORY_SEED_TYPES)]
            for idx in range(seed_count)
        ]

        mood = scene_context.get("mood")
        weather = scene_context.get("weather")
        char_id = scene_context.get("char_id") or scene_context.get("character_id")
        seeds: list[dict[str, object]] = []
        for idx, seed_type in enumerate(types):
            detail_pool = _SENSORY_DETAIL_POOL[seed_type]
            detail_index = int(digest[8 + idx * 2 : 10 + idx * 2], 16) % len(
                detail_pool
            )
            detail = detail_pool[detail_index]
            if seed_type == "weather" and isinstance(weather, str) and weather:
                detail = f"{weather}的气息渗进空气"
            elif seed_type == "ambient_sound" and isinstance(mood, str) and mood:
                detail = f"{detail}，气氛显得{mood}"
            seed: dict[str, object] = {"type": seed_type, "detail": detail}
            if seed_type == "character_gesture" and isinstance(char_id, str) and char_id:
                seed["char_id"] = char_id
            seeds.append(seed)
        return seeds

    async def monitor_pacing(  # pragma: no cover
        self, rounds: Sequence[object]
    ) -> SimpleNamespace:
        recent = list(rounds)[-3:]
        avg_info_gain = sum(r.info_gain for r in recent) / len(recent)
        if avg_info_gain < 0.2:
            return SimpleNamespace(type="inject_incident", reason="stagnation")
        if self._is_deescalating(recent):
            return SimpleNamespace(type="force_escalation", reason="deescalation")
        return SimpleNamespace(type="continue")

    async def replan_route(  # pragma: no cover
        self,
        current_scene: str,
        target_anchor: object,
        world_state: Dict[str, object],
    ) -> ReplanResult:
        required_conditions = self._get_value(target_anchor, "required_conditions")
        constraint_type = self._get_value(target_anchor, "constraint_type")
        gap_analysis = await self.analyze_gap(world_state, required_conditions)
        if gap_analysis.severity < 0.7:
            new_chapters = await self.generate_bridge_chapters(
                from_state=world_state,
                to_conditions=required_conditions,
                max_chapters=3,
            )
            return ReplanResult(
                success=True,
                new_chapters=new_chapters,
                modified_anchor=None,
                reason="recoverable",
            )
        if constraint_type == "soft":
            modified = await self.soften_anchor(target_anchor, world_state)
            return ReplanResult(
                success=True,
                new_chapters=[],
                modified_anchor=modified,
                reason="soft_anchor",
            )
        if constraint_type == "flexible":
            replacement = await self.generate_equivalent_anchor(target_anchor, world_state)
            return ReplanResult(
                success=True,
                new_chapters=[],
                modified_anchor=replacement,
                reason="flexible_anchor",
            )
        return ReplanResult(
            success=False,
            new_chapters=[],
            modified_anchor=None,
            reason="hard_anchor_unreachable",
        )

    async def analyze_gap(  # pragma: no cover
        self, world_state: Dict[str, object], conditions: Sequence[str]
    ):
        missing_conditions = [
            condition
            for condition in conditions
            if not world_state.get(condition)
        ]
        total_conditions = len(conditions) or 1
        severity = len(missing_conditions) / total_conditions
        recoverable = severity < 0.7
        return SimpleNamespace(
            severity=severity,
            recoverable=recoverable,
            missing_conditions=missing_conditions,
        )

    async def generate_bridge_chapters(  # pragma: no cover
        self,
        *,
        from_state: Dict[str, object],
        to_conditions: Sequence[str],
        max_chapters: int,
    ) -> List[Dict[str, object]]:
        _ = from_state
        conditions = list(to_conditions)
        desired_count = len(conditions) or 1
        chapter_count = min(max_chapters, desired_count)
        return [
            {
                "title": f"bridge_{index + 1}",
                "goal": conditions[index] if index < len(conditions) else "progress",
            }
            for index in range(chapter_count)
        ]

    async def soften_anchor(  # pragma: no cover
        self, target_anchor: object, world_state: Dict[str, object]
    ):
        _ = world_state
        return {
            "anchor_type": self._get_value(target_anchor, "anchor_type"),
            "description": self._get_value(target_anchor, "description"),
            "constraint_type": "soft",
            "required_conditions": list(
                self._get_value(target_anchor, "required_conditions")
            ),
        }

    async def generate_equivalent_anchor(  # pragma: no cover
        self, target_anchor: object, world_state: Dict[str, object]
    ):
        _ = world_state
        anchor_type = self._get_value(target_anchor, "anchor_type")
        description = self._get_value(target_anchor, "description")
        required_conditions = list(self._get_value(target_anchor, "required_conditions"))
        return {
            "anchor_type": anchor_type,
            "description": f"equivalent: {description}",
            "constraint_type": "flexible",
            "required_conditions": required_conditions,
        }

    def _get_value(self, action: object, name: str):  # pragma: no cover
        if isinstance(action, dict):
            return action[name]
        return getattr(action, name)

    def _is_mutual_attack(  # pragma: no cover
        self, action: object, other: object
    ) -> bool:
        return (
            self._get_value(action, "action_type") == "attack"
            and self._get_value(other, "action_type") == "attack"
            and self._get_value(action, "action_target")
            == self._get_value(other, "agent_id")
            and self._get_value(other, "action_target")
            == self._get_value(action, "agent_id")
        )

    def _is_shared_target(  # pragma: no cover
        self, action: object, other: object
    ) -> bool:
        return (
            self._get_value(action, "action_type")
            == self._get_value(other, "action_type")
            and self._get_value(action, "action_target")
            == self._get_value(other, "action_target")
        )

    def _is_deescalating(self, rounds: Sequence[object]) -> bool:  # pragma: no cover
        if len(rounds) < 3:
            return False
        values = [r.conflict_escalation for r in rounds[-3:]]
        return values[0] > values[1] > values[2]
