"""LLM 调用抽象层，封装 Gemini + Instructor 的结构化输出。"""

from __future__ import annotations

import inspect
from typing import Dict, List, Sequence

from app.constants import DEFAULT_BRANCH_ID
from app.llm import prompts
from app.models import (
    AgentAction,
    CharacterSheet,
    CharacterValidationResult,
    ConvergenceCheck,
    DMArbitration,
    Intention,
    SceneNode,
    SnowflakeRoot,
)

ROLE_SYSTEM = "system"
ROLE_USER = "user"


class LLMEngine:
    """封装 Instructor 调用，便于在业务层进行依赖注入/替换实现。"""

    def __init__(self, client=None, model_name: str = "gemini-1.5-pro"):
        self.model_name = model_name
        self.client = client

    def _build_client(self):  # pragma: no cover
        """初始化实际的 Gemini 客户端（需要外部配置 API Key）。"""
        try:
            import instructor
            from google.generativeai import GenerativeModel

            model = GenerativeModel(self.model_name)
            return instructor.from_gemini(model)
        except ImportError as exc:  # pragma: no cover - 仅在真实 LLM 初始化时触发
            raise RuntimeError(
                "Real LLM dependencies are missing. Install `google-generativeai` and `instructor` "
                "to enable Gemini structured outputs."
            ) from exc
        except Exception as exc:  # pragma: no cover - 仅在真实 LLM 初始化时触发
            raise RuntimeError(
                "Failed to initialize Gemini instructor client. "
                "Ensure google-generativeai is configured with API key."
            ) from exc

    def _ensure_client(self):  # pragma: no cover
        if self.client is None:
            self.client = self._build_client()
        return self.client

    async def _call_model(self, *, response_model, messages):  # pragma: no cover
        client = self._ensure_client()
        create_call = client.chat.completions.create(
            model=self.model_name,
            response_model=response_model,
            messages=messages,
        )
        if inspect.isawaitable(create_call):
            return await create_call
        return create_call

    async def generate_logline_options(self, raw_idea: str) -> List[str]:  # pragma: no cover
        """Step 1：根据原始想法生成 10 个 logline 备选。"""
        messages = [
            {"role": ROLE_SYSTEM, "content": prompts.SNOWFLAKE_STEP1_SYSTEM_PROMPT},
            {"role": ROLE_USER, "content": raw_idea},
        ]
        return await self._call_model(response_model=List[str], messages=messages)

    async def generate_root_structure(self, idea: str) -> SnowflakeRoot:  # pragma: no cover
        """Step 2：扩展成雪花根节点。"""
        messages = [
            {"role": ROLE_SYSTEM, "content": prompts.SNOWFLAKE_STEP2_SYSTEM_PROMPT},
            {"role": ROLE_USER, "content": idea},
        ]
        return await self._call_model(response_model=SnowflakeRoot, messages=messages)

    async def generate_characters(self, root: SnowflakeRoot) -> List[CharacterSheet]:  # pragma: no cover
        """Step 3：生成角色小传列表。"""
        user_payload = "\n".join(
            [
                f"logline: {root.logline}",
                f"three_disasters: {root.three_disasters}",
                f"ending: {root.ending}",
                f"theme: {root.theme}",
            ]
        )
        messages = [
            {"role": ROLE_SYSTEM, "content": prompts.SNOWFLAKE_STEP3_SYSTEM_PROMPT},
            {"role": ROLE_USER, "content": user_payload},
        ]
        return await self._call_model(response_model=List[CharacterSheet], messages=messages)

    async def validate_characters(  # pragma: no cover
        self, root: SnowflakeRoot, characters: Sequence[CharacterSheet]
    ) -> CharacterValidationResult:
        """验证角色动机与主线冲突情况。"""
        user_payload = "\n".join(
            [
                f"logline: {root.logline}",
                f"characters: {[c.model_dump() for c in characters]}",
            ]
        )
        messages = [
            {
                "role": ROLE_SYSTEM,
                "content": prompts.SNOWFLAKE_VALIDATE_CHARACTERS_SYSTEM_PROMPT,
            },
            {"role": ROLE_USER, "content": user_payload},
        ]
        return await self._call_model(
            response_model=CharacterValidationResult,
            messages=messages,
        )

    async def generate_scene_list(  # pragma: no cover
        self, root: SnowflakeRoot, characters: Sequence[CharacterSheet]
    ) -> List[SceneNode]:
        """Step 4：生成场景列表，供前端 React Flow 渲染。"""
        user_payload = "\n".join(
            [
                f"logline: {root.logline}",
                f"three_disasters: {root.three_disasters}",
                f"characters: {[c.model_dump() for c in characters]}",
            ]
        )
        messages = [
            {"role": ROLE_SYSTEM, "content": prompts.SNOWFLAKE_STEP4_SYSTEM_PROMPT},
            {"role": ROLE_USER, "content": user_payload},
        ]
        return await self._call_model(
            response_model=List[SceneNode],
            messages=messages,
        )

    async def generate_act_list(
        self, root: SnowflakeRoot, characters: Sequence[CharacterSheet]
    ) -> List[Dict[str, object]]:
        user_payload = "\n".join(
            [
                f"logline: {root.logline}",
                f"three_disasters: {root.three_disasters}",
                f"ending: {root.ending}",
                f"theme: {root.theme}",
                f"characters: {[c.model_dump() for c in characters]}",
            ]
        )
        messages = [
            {"role": ROLE_SYSTEM, "content": prompts.SNOWFLAKE_STEP5A_SYSTEM_PROMPT},
            {"role": ROLE_USER, "content": user_payload},
        ]
        return await self._call_model(
            response_model=List[Dict[str, object]],
            messages=messages,
        )

    async def generate_chapter_list(
        self,
        root: SnowflakeRoot,
        act: Dict[str, object],
        characters: Sequence[CharacterSheet],
    ) -> List[Dict[str, object]]:
        user_payload = "\n".join(
            [
                f"logline: {root.logline}",
                f"act: {act}",
                f"characters: {[c.model_dump() for c in characters]}",
            ]
        )
        messages = [
            {"role": ROLE_SYSTEM, "content": prompts.SNOWFLAKE_STEP5B_SYSTEM_PROMPT},
            {"role": ROLE_USER, "content": user_payload},
        ]
        return await self._call_model(
            response_model=List[Dict[str, object]],
            messages=messages,
        )

    async def generate_story_anchors(
        self,
        root: SnowflakeRoot,
        characters: Sequence[CharacterSheet],
        acts: Sequence[Dict[str, object]],
    ) -> List[Dict[str, object]]:
        user_payload = "\n".join(
            [
                f"logline: {root.logline}",
                f"acts: {list(acts)}",
                f"characters: {[c.model_dump() for c in characters]}",
            ]
        )
        messages = [
            {"role": ROLE_SYSTEM, "content": prompts.STORY_ANCHORS_SYSTEM_PROMPT},
            {"role": ROLE_USER, "content": user_payload},
        ]
        return await self._call_model(
            response_model=List[Dict[str, object]],
            messages=messages,
        )

    async def generate_agent_perception(
        self, profile: Dict[str, object], scene_context: str
    ) -> Dict[str, object]:
        messages = [
            {"role": ROLE_SYSTEM, "content": prompts.character_agent.PERCEIVE_PROMPT},
            {
                "role": ROLE_USER,
                "content": "\n".join(
                    [
                        f"profile: {profile}",
                        f"scene: {scene_context}",
                    ]
                ),
            },
        ]
        return await self._call_model(
            response_model=Dict[str, object],
            messages=messages,
        )

    async def generate_agent_intentions(
        self, profile: Dict[str, object], scene_context: str
    ) -> List[Intention]:
        messages = [
            {"role": ROLE_SYSTEM, "content": prompts.character_agent.DELIBERATE_PROMPT},
            {
                "role": ROLE_USER,
                "content": "\n".join(
                    [
                        f"profile: {profile}",
                        f"scene: {scene_context}",
                    ]
                ),
            },
        ]
        return await self._call_model(
            response_model=List[Intention],
            messages=messages,
        )

    async def generate_agent_action(
        self,
        profile: Dict[str, object],
        scene_context: str,
        intentions: Sequence[Dict[str, object]],
    ) -> AgentAction:
        messages = [
            {"role": ROLE_SYSTEM, "content": prompts.character_agent.ACT_PROMPT},
            {
                "role": ROLE_USER,
                "content": "\n".join(
                    [
                        f"profile: {profile}",
                        f"scene: {scene_context}",
                        f"intentions: {list(intentions)}",
                    ]
                ),
            },
        ]
        return await self._call_model(
            response_model=AgentAction,
            messages=messages,
        )

    async def generate_dm_arbitration(
        self,
        round_id: str,
        action_payloads: Sequence[Dict[str, object]],
        scene_context: Dict[str, object],
        world_state: Dict[str, object],
    ) -> DMArbitration:
        messages = [
            {"role": ROLE_SYSTEM, "content": prompts.world_master.ARBITRATION_PROMPT},
            {
                "role": ROLE_USER,
                "content": "\n".join(
                    [
                        f"round_id: {round_id}",
                        f"actions: {list(action_payloads)}",
                        f"scene: {scene_context}",
                        f"world_state: {world_state}",
                    ]
                ),
            },
        ]
        return await self._call_model(
            response_model=DMArbitration,
            messages=messages,
        )

    async def check_convergence(
        self, world_state: Dict[str, object], next_anchor: Dict[str, object]
    ) -> ConvergenceCheck:
        messages = [
            {
                "role": ROLE_SYSTEM,
                "content": prompts.world_master.CONVERGENCE_CHECK_PROMPT,
            },
            {
                "role": ROLE_USER,
                "content": "\n".join(
                    [
                        f"world_state: {world_state}",
                        f"anchor: {next_anchor}",
                    ]
                ),
            },
        ]
        return await self._call_model(
            response_model=ConvergenceCheck,
            messages=messages,
        )

    async def render_scene(
        self,
        scene: Dict[str, object],
        beats: Sequence[Dict[str, object]],
        sensory: Sequence[Dict[str, object]],
        style: Dict[str, object],
    ) -> str:
        messages = [
            {"role": ROLE_SYSTEM, "content": prompts.renderer.SMART_RENDER_PROMPT},
            {
                "role": ROLE_USER,
                "content": "\n".join(
                    [
                        f"scene: {scene}",
                        f"beats: {list(beats)}",
                        f"sensory: {list(sensory)}",
                        f"style: {style}",
                    ]
                ),
            },
        ]
        return await self._call_model(response_model=str, messages=messages)

    async def generate_prose(
        self,
        *,
        beats: Sequence[Dict[str, object]],
        sensory: Dict[str, List[Dict[str, object]]],
        style: Dict[str, object],
        pov: str | None,
    ) -> str:
        beat_labels = [
            str(item.get("event"))
            for item in beats
            if isinstance(item, dict) and item.get("event")
        ]
        sensory_details = [
            str(seed.get("detail"))
            for seed_list in sensory.values()
            for seed in seed_list
            if isinstance(seed, dict) and seed.get("detail")
        ]
        pov_label = pov if isinstance(pov, str) and pov else "unknown"
        style_hint = style.get("tone") if isinstance(style, dict) else None
        segments = [
            f"POV:{pov_label}",
            "；".join(beat_labels) if beat_labels else "叙事推进",
        ]
        if sensory_details:
            segments.append("\n".join(sensory_details[:2]))
        if isinstance(style_hint, str) and style_hint:
            segments.append(style_hint)
        return "\n".join(segments)


class LocalStoryEngine:  # pragma: no cover
    """无外部依赖的本地引擎：用于脚本级最小闭环与存储验收。"""

    async def generate_logline_options(self, raw_idea: str) -> List[str]:
        base = raw_idea.strip()
        if not base:
            raise ValueError("idea must not be empty")
        return [f"{base}（版本{i}）" for i in range(1, 11)]

    async def generate_root_structure(self, idea: str) -> SnowflakeRoot:
        logline = idea.strip()
        if not logline:
            raise ValueError("logline must not be empty")
        return SnowflakeRoot(
            logline=logline,
            three_disasters=[
                "主角遭遇企业追捕",
                "同伴背叛引发更大危机",
                "意识备份失控吞噬城市",
            ],
            ending="主角以诗性代码唤醒街区灵魂，代价是自身记忆被重写。",
            theme="自由意志与身份的代价",
        )

    async def generate_characters(self, root: SnowflakeRoot) -> List[CharacterSheet]:
        _ = root
        return [
            CharacterSheet(
                name="黑客诗人",
                ambition="偷走企业之神的意识备份",
                conflict="每次入侵都会丢失一段记忆",
                epiphany="真正的自由来自承认自我会改变",
                voice_dna="冷静而诗意",
            ),
            CharacterSheet(
                name="企业之神的代理人",
                ambition="维护意识备份秩序与企业统治",
                conflict="对人类情感产生异常共鸣",
                epiphany="控制并不等于秩序",
                voice_dna="理性、克制、带轻微讽刺",
            ),
            CharacterSheet(
                name="街区灵魂的守门人",
                ambition="唤醒被禁锢的城市集体意识",
                conflict="必须牺牲现实载体才能觉醒",
                epiphany="个体的选择能改变群体的未来",
                voice_dna="直白、急促、带街头俚语",
            ),
        ]

    async def validate_characters(
        self, root: SnowflakeRoot, characters: Sequence[CharacterSheet]
    ) -> CharacterValidationResult:
        _ = root
        _ = characters
        return CharacterValidationResult(valid=True, issues=[])

    async def generate_scene_list(
        self, root: SnowflakeRoot, characters: Sequence[CharacterSheet]
    ) -> List[SceneNode]:
        if not characters:
            raise ValueError("characters must not be empty for scene generation")
        pov_cycle = [c.entity_id for c in characters]
        scenes: list[SceneNode] = []
        for idx in range(50):
            scenes.append(
                SceneNode(
                    branch_id=DEFAULT_BRANCH_ID,
                    title=f"Scene {idx + 1}",
                    sequence_index=idx + 1,
                    expected_outcome=f"推进主线：阶段 {idx + 1}",
                    conflict_type="internal" if idx % 2 == 0 else "external",
                    actual_outcome="",
                    parent_act_id=None,
                    logic_exception=False,
                    is_dirty=False,
                    pov_character_id=pov_cycle[idx % len(pov_cycle)],
                )
            )
        return scenes

    async def generate_act_list(
        self, root: SnowflakeRoot, characters: Sequence[CharacterSheet]
    ) -> List[Dict[str, object]]:
        _ = characters
        theme = root.theme.strip() if isinstance(root.theme, str) and root.theme.strip() else "主线冲突"
        acts = [
            {
                "title": "Act 1 · Setup",
                "purpose": f"建立世界与冲突：{theme}",
                "tone": "悬疑",
            },
            {
                "title": "Act 2 · Confrontation",
                "purpose": "矛盾升级并逼近转折点",
                "tone": "紧张",
            },
            {
                "title": "Act 3 · Resolution",
                "purpose": "冲突收束并回应主题",
                "tone": "释然",
            },
        ]
        return acts

    async def generate_chapter_list(
        self,
        root: SnowflakeRoot,
        act: Dict[str, object],
        characters: Sequence[CharacterSheet],
    ) -> List[Dict[str, object]]:
        _ = root
        title_prefix = act.get("title") if isinstance(act, dict) else None
        prefix = str(title_prefix) if title_prefix else "Act"
        pov_ids = [str(character.entity_id) for character in characters]
        sequence = act.get("sequence") if isinstance(act, dict) else None
        chapter_count = 4 if sequence == 1 else 3
        chapters: list[Dict[str, object]] = []
        for idx in range(1, chapter_count + 1):
            pov = pov_ids[(idx - 1) % len(pov_ids)] if pov_ids else None
            chapters.append(
                {
                    "title": f"{prefix} · Chapter {idx}",
                    "focus": f"{prefix} focus {idx}",
                    "pov_character_id": pov,
                }
            )
        return chapters

    async def generate_story_anchors(
        self,
        root: SnowflakeRoot,
        characters: Sequence[CharacterSheet],
        acts: Sequence[Dict[str, object]],
    ) -> List[Dict[str, object]]:
        _ = root
        _ = characters
        _ = acts
        anchor_types = ["inciting_incident", "midpoint", "climax", "resolution"]
        constraints = ["hard", "soft", "flexible"]
        anchors: list[Dict[str, object]] = []
        for idx in range(10):
            anchor_type = anchor_types[idx % len(anchor_types)]
            constraint_type = constraints[idx % len(constraints)]
            anchors.append(
                {
                    "anchor_type": anchor_type,
                    "description": f"{anchor_type} anchor {idx + 1}",
                    "constraint_type": constraint_type,
                    "required_conditions": [f"condition-{idx + 1}"],
                }
            )
        return anchors

    async def generate_prose(
        self,
        *,
        beats: Sequence[Dict[str, object]],
        sensory: Dict[str, List[Dict[str, object]]],
        style: Dict[str, object],
        pov: str | None,
    ) -> str:
        beat_labels = [
            str(item.get("event"))
            for item in beats
            if isinstance(item, dict) and item.get("event")
        ]
        sensory_details = [
            str(seed.get("detail"))
            for seed_list in sensory.values()
            for seed in seed_list
            if isinstance(seed, dict) and seed.get("detail")
        ]
        pov_label = pov if isinstance(pov, str) and pov else "unknown"
        style_hint = style.get("tone") if isinstance(style, dict) else None
        segments = [
            f"POV:{pov_label}",
            "；".join(beat_labels) if beat_labels else "叙事推进",
        ]
        if sensory_details:
            segments.append("\n".join(sensory_details[:2]))
        if isinstance(style_hint, str) and style_hint:
            segments.append(style_hint)
        return "\n".join(segments)

