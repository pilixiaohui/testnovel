"""FastAPI 入口，暴露雪花流程接口。"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from app.models import SnowflakeRoot
from app.services.llm_engine import LLMEngine

app = FastAPI(title="Snowflake Engine API", version="0.1.0")


class LoglinePayload(BaseModel):
    logline: str


def get_llm_engine() -> LLMEngine:
    """默认依赖注入，可在测试中 override。"""
    return LLMEngine()


@app.post("/api/v1/snowflake/step2", response_model=SnowflakeRoot)
async def generate_structure_endpoint(
    payload: LoglinePayload, engine: LLMEngine = Depends(get_llm_engine)
) -> SnowflakeRoot:
    return await engine.generate_root_structure(payload.logline)

