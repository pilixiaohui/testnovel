"""Smart renderer for simulation rounds."""

from __future__ import annotations

from typing import Dict, List, Sequence

from app.models import SimulationRoundResult


class SmartRenderer:
    """智能渲染管线。"""

    def __init__(self, llm=None, retrieval_service=None):
        self.llm = llm
        self.retrieval_service = retrieval_service

    async def render(
        self, rounds: Sequence[SimulationRoundResult], scene: Dict[str, object]
    ) -> str:
        beats = await self.extract_narrative_beats(rounds)
        sensory_details = self._collect_sensory_seeds(rounds)

        if self.llm is None:
            scene_id = self._get_field(scene, "id", None) or self._get_field(
                scene, "scene_id", None
            )
            if scene_id is not None:
                raise ValueError("llm is required for smart rendering")
            return f"beats:{len(beats)}"

        scene_id = self._get_field(scene, "id", None)
        pov = self._get_field(scene, "pov_character_id", None)
        style_context = {}
        if self.retrieval_service is not None:
            style_context = await self.retrieval_service.get_style(
                scene_id=scene_id,
                includes=["previous_foreshadowing", "character_voice", "tone"],
            )

        content = await self.llm.generate_prose(
            beats=beats,
            sensory=sensory_details,
            style=style_context,
            pov=pov,
        )
        errors = await self.check_continuity_errors(content, scene)
        if errors:
            self._last_continuity_errors = errors
            content = await self.fix_continuity(content)
        return content

    async def extract_narrative_beats(
        self, rounds: Sequence[SimulationRoundResult]
    ) -> List[Dict[str, object]]:
        beats: list[dict[str, object]] = []
        for round_result in rounds:
            info_gain = self._get_field(round_result, "info_gain", 0.0) or 0.0
            if info_gain < 0.1:
                continue
            beats.extend(self._get_field(round_result, "narrative_events", []) or [])
        return beats

    async def check_continuity_errors(
        self, content: str, scene: Dict[str, object]
    ) -> list[dict[str, object]] | bool:
        rules = self._get_field(scene, "continuity_rules", None)
        if not rules:
            return False
        errors: list[dict[str, object]] = []
        character_locations = rules.get("character_locations", {})
        for character_id, expected in character_locations.items():
            actual = self._extract_location(content, character_id)
            if actual is None:
                continue
            if actual != expected:
                errors.append(
                    {
                        "type": "character_location",
                        "character_id": character_id,
                        "expected": expected,
                        "actual": actual,
                    }
                )
        return errors

    async def fix_continuity(self, content: str) -> str:
        for error in self._last_continuity_errors:
            if error["type"] != "character_location":
                raise ValueError(
                    f"Unsupported continuity error: {error['type']}"
                )
            character_id = error["character_id"]
            expected = error["expected"]
            actual = error["actual"]
            token = f"{character_id}@{actual}"
            replacement = f"{character_id}@{expected}"
            content = content.replace(token, replacement)
        return content

    def _collect_sensory_seeds(
        self, rounds: Sequence[SimulationRoundResult]
    ) -> Dict[str, List[Dict[str, object]]]:
        grouped: dict[str, list[dict[str, object]]] = {}
        for round_result in rounds:
            seeds = self._get_field(round_result, "sensory_seeds", []) or []
            for seed in seeds:
                seed_type = seed.get("type")
                if not seed_type:
                    continue
                grouped.setdefault(seed_type, []).append(seed)
        return grouped

    @staticmethod
    def _get_field(item: object, name: str, default: object) -> object:
        if isinstance(item, dict):
            return item.get(name, default)
        return getattr(item, name, default)

    @staticmethod
    def _extract_location(content: str, character_id: str) -> str | None:
        token = f"{character_id}@"
        if token not in content:
            return None
        tail = content.split(token, 1)[1]
        for sep in (" ", "\n", "\t", ",", ".", "!", "?", ";", ":"):
            if sep in tail:
                tail = tail.split(sep, 1)[0]
        return tail or None
