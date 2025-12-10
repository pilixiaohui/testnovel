"""LLM 调用抽象层，封装 Gemini + Instructor 的结构化输出。"""

from __future__ import annotations

import inspect
from typing import List, Sequence

import instructor
from google.generativeai import GenerativeModel

from app.models import CharacterSheet, CharacterValidationResult, SceneNode, SnowflakeRoot


class LLMEngine:
    """封装 Instructor 调用，便于在业务层 Mock。"""

    def __init__(self, client=None, model_name: str = "gemini-1.5-pro"):
        self.model_name = model_name
        self.client = client

    def _build_client(self):
        """初始化实际的 Gemini 客户端（需要外部配置 API Key）。"""
        model = GenerativeModel(self.model_name)
        try:
            return instructor.from_gemini(model)
        except Exception as exc:  # pragma: no cover - 仅在真实 LLM 初始化时触发
            raise RuntimeError(
                "Failed to initialize Gemini instructor client. "
                "Ensure google-generativeai is configured with API key."
            ) from exc

    def _ensure_client(self):
        if self.client is None:
            self.client = self._build_client()
        return self.client

    async def _call_model(self, *, response_model, messages):
        client = self._ensure_client()
        create_call = client.chat.completions.create(
            model=self.model_name,
            response_model=response_model,
            messages=messages,
        )
        if inspect.isawaitable(create_call):
            return await create_call
        return create_call

    async def generate_logline_options(self, raw_idea: str) -> List[str]:
        """Step 1：根据原始想法生成 10 个 logline 备选。"""
        messages = [
            {"role": "system", "content": "你是一名故事策划，输出 10 个一句话 logline。"},
            {"role": "user", "content": raw_idea},
        ]
        return await self._call_model(response_model=List[str], messages=messages)

    async def generate_root_structure(self, idea: str) -> SnowflakeRoot:
        """Step 2：扩展成雪花根节点。"""
        messages = [
            {"role": "system", "content": "你是资深小说架构师。使用雪花写作法扩展用户想法。"},
            {"role": "user", "content": idea},
        ]
        return await self._call_model(response_model=SnowflakeRoot, messages=messages)

    async def generate_characters(self, root: SnowflakeRoot) -> List[CharacterSheet]:
        """Step 3：生成角色小传列表。"""
        messages = [
            {"role": "system", "content": "基于雪花根节点生成主要角色小传列表。"},
            {
                "role": "user",
                "content": f"logline: {root.logline}\nthree_disasters: {root.three_disasters}\nending: {root.ending}\ntheme: {root.theme}",
            },
        ]
        return await self._call_model(response_model=List[CharacterSheet], messages=messages)

    async def validate_characters(
        self, root: SnowflakeRoot, characters: Sequence[CharacterSheet]
    ) -> CharacterValidationResult:
        """验证角色动机与主线冲突情况。"""
        messages = [
            {"role": "system", "content": "检查角色动机与剧情主线是否冲突，给出通过/问题列表。"},
            {
                "role": "user",
                "content": f"logline: {root.logline}\ncharacters: {[c.model_dump() for c in characters]}",
            },
        ]
        return await self._call_model(
            response_model=CharacterValidationResult,
            messages=messages,
        )

    async def generate_scene_list(
        self, root: SnowflakeRoot, characters: Sequence[CharacterSheet]
    ) -> List[SceneNode]:
        """Step 4：生成场景列表，供前端 React Flow 渲染。"""
        messages = [
            {
                "role": "system",
                "content": "生成 50-100 个场景节点，每个节点包含预期结果与冲突类型。",
            },
            {
                "role": "user",
                "content": (
                    f"logline: {root.logline}\n"
                    f"three_disasters: {root.three_disasters}\n"
                    f"characters: {[c.model_dump() for c in characters]}"
                ),
            },
        ]
        return await self._call_model(
            response_model=List[SceneNode],
            messages=messages,
        )
