"""Simulation engine for running narrative rounds and scenes."""

from __future__ import annotations

import json

from types import SimpleNamespace
from typing import Dict, List, Sequence

from app.models import AgentAction, DMArbitration, SimulationRoundResult
from app.storage.schema import SimulationLog


class SimulationEngine:
    """推演引擎。"""

    def __init__(self, character_engine, world_master, storage, llm, smart_renderer=None):
        self.character_engine = character_engine
        self.world_master = world_master
        self.storage = storage
        self.llm = llm
        self.smart_renderer = smart_renderer

    async def run_round(
        self, scene_context: Dict[str, object], agents: Sequence[object], config
    ) -> SimulationRoundResult:
        agent_actions: list[AgentAction] = []
        for agent in agents:
            action = await agent.decide(agent.agent_id, scene_context)
            agent_actions.append(action)

        action_payloads = [
            {
                "action_id": f"{config.round_id}-{idx}",
                "agent_id": action.agent_id,
                "action_type": action.action_type,
                "action_target": action.action_target,
            }
            for idx, action in enumerate(agent_actions)
        ]

        dm_arbitration: DMArbitration = await self.world_master.arbitrate(
            config.round_id,
            action_payloads,
            scene_context,
            {},
        )
        sensory_seeds = await self.world_master.inject_sensory_seeds(scene_context)
        info_gain = await self.calculate_info_gain(scene_context, dm_arbitration)

        return SimulationRoundResult(
            round_id=config.round_id,
            agent_actions=agent_actions,
            dm_arbitration=dm_arbitration,
            narrative_events=[{"event": "round"}],
            sensory_seeds=sensory_seeds,
            convergence_score=0.0,
            drama_score=0.0,
            info_gain=info_gain,
            stagnation_count=0,
        )

    async def run_scene(self, scene_skeleton: Dict[str, object], config) -> str:
        rounds: list[SimulationRoundResult] = []
        agents = (
            config["agents"]
            if isinstance(config, dict) and "agents" in config
            else []
        )
        max_rounds = config["max_rounds"] if isinstance(config, dict) else config.max_rounds
        round_id_base = (
            config.get("round_id")
            if isinstance(config, dict)
            else getattr(config, "round_id", None)
        )
        if not round_id_base:
            round_id_base = (
                scene_skeleton.get("scene_id")
                or scene_skeleton.get("id")
                or "round"
            )
        scene_id = scene_skeleton.get("scene_id")
        scene_version_id = scene_skeleton.get("scene_version_id")
        stagnation_count = 0

        def normalize_anchor(anchor: Dict[str, object]) -> Dict[str, object]:
            required_conditions = anchor["required_conditions"]
            if isinstance(required_conditions, str):
                required_conditions = json.loads(required_conditions)
            if not isinstance(required_conditions, list):
                raise ValueError("anchor required_conditions must be list")
            normalized = dict(anchor)
            normalized["required_conditions"] = required_conditions
            return normalized

        world_state = scene_skeleton.get("world_state")
        if world_state is None and (
            scene_skeleton.get("root_id")
            or scene_skeleton.get("branch_id")
            or scene_skeleton.get("next_anchor")
        ):
            raise ValueError("world_state is required for convergence flow")

        next_anchor = None
        if world_state is not None:
            next_anchor = scene_skeleton.get("next_anchor")
            if next_anchor:
                next_anchor = normalize_anchor(next_anchor)
            else:
                root_id = scene_skeleton.get("root_id")
                branch_id = scene_skeleton.get("branch_id")
                if not root_id or not branch_id:
                    raise ValueError("root_id and branch_id are required for anchor lookup")
                next_anchor = normalize_anchor(
                    self.storage.get_next_unachieved_anchor(
                        root_id=root_id, branch_id=branch_id
                    )
                )
            scene_skeleton["next_anchor"] = next_anchor

        for idx in range(max_rounds):
            round_number = idx + 1
            round_config = SimpleNamespace(round_id=f"{round_id_base}-{round_number}")
            result = await self.run_round(scene_skeleton, agents, round_config)
            if result.info_gain < 0.1:
                stagnation_count += 1
            else:
                stagnation_count = 0
            result.stagnation_count = stagnation_count
            rounds.append(result)

            pacing = await self.world_master.monitor_pacing(rounds)
            if pacing.type == "inject_incident":
                await self.inject_breaking_incident(scene_skeleton)
            elif pacing.type == "force_escalation":
                await self.force_conflict_escalation(scene_skeleton)

            if world_state is not None and next_anchor is not None:
                check = await self.world_master.check_convergence(world_state, next_anchor)
                result.convergence_score = max(0.0, 1.0 - check.distance)
                action = await self.world_master.generate_convergence_action(
                    check, world_state
                )
                if check.distance > 0.9 or action.get("type") == "replan_route":
                    if not scene_id:
                        raise ValueError("scene_id is required for replan_route")
                    replan_result = await self.world_master.replan_route(
                        scene_id,
                        next_anchor,
                        world_state,
                    )
                    if not replan_result.success:
                        raise ValueError(replan_result.reason)
                    result.narrative_events.append(
                        {"event": "replan_route", "reason": replan_result.reason}
                    )
                    if replan_result.modified_anchor:
                        next_anchor = normalize_anchor(replan_result.modified_anchor)
                        scene_skeleton["next_anchor"] = next_anchor
                else:
                    result.narrative_events.append(
                        {"event": "convergence_action", "action": action}
                    )

                required_conditions = next_anchor["required_conditions"]
                missing_conditions = [
                    condition
                    for condition in required_conditions
                    if not world_state.get(condition)
                ]
                if not missing_conditions:
                    if not scene_version_id:
                        raise ValueError(
                            "scene_version_id is required to mark anchor achieved"
                        )
                    marked = self.storage.mark_anchor_achieved(
                        anchor_id=next_anchor["id"],
                        scene_version_id=scene_version_id,
                    )
                    result.narrative_events.append(
                        {"event": "anchor_achieved", "anchor_id": marked["id"]}
                    )
                    root_id = marked.get("root_id") or scene_skeleton.get("root_id")
                    branch_id = marked.get("branch_id") or scene_skeleton.get("branch_id")
                    if not root_id or not branch_id:
                        raise ValueError(
                            "root_id and branch_id are required for next anchor"
                        )
                    next_anchor = normalize_anchor(
                        self.storage.get_next_unachieved_anchor(
                            root_id=root_id, branch_id=branch_id
                        )
                    )
                    scene_skeleton["next_anchor"] = next_anchor

            if scene_id and scene_version_id:
                log = SimulationLog(
                    id=f"sim:{scene_id}:round:{round_number}",
                    scene_version_id=scene_version_id,
                    round_number=round_number,
                    agent_actions=json.dumps(
                        [action.model_dump() for action in result.agent_actions]
                    ),
                    dm_arbitration=json.dumps(result.dm_arbitration.model_dump()),
                    narrative_events=json.dumps(result.narrative_events),
                    sensory_seeds=json.dumps(result.sensory_seeds),
                    convergence_score=result.convergence_score,
                    drama_score=result.drama_score,
                    info_gain=result.info_gain,
                    stagnation_count=result.stagnation_count,
                )
                self.storage.create_simulation_log(log)

            if self.should_end_scene(result):
                break

        return await self.smart_render(rounds, scene_skeleton)

    async def calculate_info_gain(
        self, prev_state: Dict[str, object], curr_state: object
    ) -> float:
        def _get_value(state: object, key: str, default: object) -> object:
            if isinstance(state, dict):
                return state.get(key, default)
            return getattr(state, key, default)

        def _as_list(value: object) -> list:
            if value is None:
                return []
            if isinstance(value, list):
                return value
            if isinstance(value, (set, tuple)):
                return list(value)
            return [value]

        prev_facts = set(_as_list(_get_value(prev_state, "facts", [])))
        curr_facts = set(_as_list(_get_value(curr_state, "facts", [])))
        prev_relations = set(_as_list(_get_value(prev_state, "relations", [])))
        curr_relations = set(_as_list(_get_value(curr_state, "relations", [])))
        prev_secrets = set(_as_list(_get_value(prev_state, "secrets", [])))
        curr_secrets = set(_as_list(_get_value(curr_state, "secrets", [])))

        new_info = len(curr_facts - prev_facts)
        new_info += len(curr_relations - prev_relations)
        new_info += len(curr_secrets - prev_secrets)

        prev_conflict = float(_get_value(prev_state, "conflict_escalation", 0.0) or 0.0)
        curr_conflict = float(_get_value(curr_state, "conflict_escalation", 0.0) or 0.0)
        conflict_delta = max(0.0, curr_conflict - prev_conflict)

        if new_info == 0 and conflict_delta <= 0.0:
            return 0.0

        total_info = max(len(curr_facts) + len(curr_relations) + len(curr_secrets), 1)
        info_ratio = new_info / total_info
        score = info_ratio + min(conflict_delta, 1.0)
        return min(score, 1.0)

    async def inject_breaking_incident(
        self, scene_context: Dict[str, object]
    ) -> None:
        events = scene_context.get("events")
        if events is None:
            raise ValueError("scene_context.events is required")
        if not isinstance(events, list):
            raise ValueError("scene_context.events must be a list")
        events.append(
            {
                "type": "breaking_incident",
                "detail": "breaking incident to shake stagnation",
            }
        )

    async def force_conflict_escalation(
        self, scene_context: Dict[str, object]
    ) -> None:
        if "conflict_escalation" not in scene_context:
            raise ValueError("scene_context.conflict_escalation is required")
        current_level = float(scene_context["conflict_escalation"])
        new_level = min(current_level + 0.2, 1.0)
        scene_context["conflict_escalation"] = new_level
        events = scene_context.get("events")
        if events is None:
            raise ValueError("scene_context.events is required")
        if not isinstance(events, list):
            raise ValueError("scene_context.events must be a list")
        events.append(
            {
                "type": "force_escalation",
                "level": new_level,
            }
        )

    def should_end_scene(self, round_result: SimulationRoundResult) -> bool:
        if round_result.convergence_score >= 0.9:
            return True
        if round_result.stagnation_count >= 3:
            return True
        return False

    async def smart_render(  # pragma: no cover
        self, rounds: Sequence[SimulationRoundResult], scene: Dict[str, object]
    ) -> str:
        if self.smart_renderer is None:
            raise ValueError("smart_renderer is required")
        return await self.smart_renderer.render(rounds, scene)
