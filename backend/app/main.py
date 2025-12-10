"""FastAPI 入口，暴露雪花流程接口。"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, List
from pathlib import Path

from fastapi import Depends, FastAPI, WebSocket
from pydantic import BaseModel, Field

from app.logic.snowflake_manager import SnowflakeManager
from app.models import CharacterSheet, SceneNode, SnowflakeRoot
from app.services.llm_engine import LLMEngine
from app.services.topone_client import ToponeClient
from app.storage.graph import GraphStorage

app = FastAPI(title="Snowflake Engine API", version="0.1.0")


class LoglinePayload(BaseModel):
    logline: str


class ScenePayload(BaseModel):
    root: SnowflakeRoot
    characters: List[CharacterSheet] = Field(default_factory=list)


class ToponeMessage(BaseModel):
    role: str
    text: str


class ToponeGeneratePayload(BaseModel):
    model: str | None = None
    system_instruction: str | None = None
    messages: List[ToponeMessage]
    generation_config: dict | None = None
    timeout: float | None = None


def get_llm_engine() -> LLMEngine:
    """默认依赖注入，可在测试中 override。"""
    return LLMEngine()


@lru_cache(maxsize=1)
def get_graph_storage() -> GraphStorage:
    """GraphStorage 单例，避免重复建立连接。"""
    db_path = os.getenv("KUZU_DB_PATH", Path("data") / "snowflake.db")
    return GraphStorage(db_path=db_path)


def get_snowflake_manager(
    engine: LLMEngine = Depends(get_llm_engine),
    storage: GraphStorage = Depends(get_graph_storage),
) -> SnowflakeManager:
    """默认使用严格场景数量校验，可在测试 override。"""
    return SnowflakeManager(engine=engine, storage=storage)


@lru_cache(maxsize=1)
def get_topone_client() -> ToponeClient:
    """TopOne Gemini 客户端单例，读取 .env 配置。"""
    return ToponeClient()


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


@app.post("/api/v1/llm/topone/generate")
async def generate_topone_content(
    payload: ToponeGeneratePayload,
    client: ToponeClient = Depends(get_topone_client),
) -> Any:
    """调用 TopOne Gemini 原生接口，支持模型切换。"""
    return await client.generate_content(
        messages=[msg.model_dump() for msg in payload.messages],
        system_instruction=payload.system_instruction,
        generation_config=payload.generation_config,
        model=payload.model,
        timeout=payload.timeout,
    )


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
