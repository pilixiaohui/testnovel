"""FastAPI 入口，暴露雪花流程接口。"""

from __future__ import annotations

from typing import List

from fastapi import Depends, FastAPI, WebSocket
from pydantic import BaseModel, Field

from app.logic.snowflake_manager import SnowflakeManager
from app.models import CharacterSheet, SceneNode, SnowflakeRoot
from app.services.llm_engine import LLMEngine

app = FastAPI(title="Snowflake Engine API", version="0.1.0")


class LoglinePayload(BaseModel):
    logline: str


class ScenePayload(BaseModel):
    root: SnowflakeRoot
    characters: List[CharacterSheet] = Field(default_factory=list)


def get_llm_engine() -> LLMEngine:
    """默认依赖注入，可在测试中 override。"""
    return LLMEngine()


def get_snowflake_manager(engine: LLMEngine = Depends(get_llm_engine)) -> SnowflakeManager:
    """默认使用严格场景数量校验，可在测试 override。"""
    return SnowflakeManager(engine=engine)


@app.post("/api/v1/snowflake/step2", response_model=SnowflakeRoot)
async def generate_structure_endpoint(
    payload: LoglinePayload, engine: LLMEngine = Depends(get_llm_engine)
) -> SnowflakeRoot:
    return await engine.generate_root_structure(payload.logline)


@app.post("/api/v1/snowflake/step4", response_model=List[SceneNode])
async def generate_scene_endpoint(
    payload: ScenePayload, manager: SnowflakeManager = Depends(get_snowflake_manager)
) -> List[SceneNode]:
    return await manager.execute_step_4_scenes(payload.root, payload.characters)


@app.websocket("/ws/negotiation")
async def negotiation_socket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_json()
            # 简单回传确认，后续可扩展为协商协议
            await websocket.send_json({"ack": message})
    except Exception:
        await websocket.close()
