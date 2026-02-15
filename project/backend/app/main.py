"""FastAPI 入口，暴露雪花流程接口。"""

from __future__ import annotations

import json
import logging
import os
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4
from types import SimpleNamespace
from functools import lru_cache
from typing import Any, List, Mapping

import httpx
from fastapi import BackgroundTasks, Body, Depends, FastAPI, HTTPException, Query, Path, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from app.llm.topone_gateway import ToponeGateway
from app.llm import prompts as snowflake_prompts
from app.config import (
    SCENE_MAX_COUNT,
    SCENE_MIN_COUNT,
    TOPONE_DEFAULT_MODEL,
    TOPONE_TIMEOUT_SECONDS,
    require_memgraph_host,
    require_memgraph_port,
)
from app.logic.snowflake_manager import SnowflakeManager
from app.models import (
    AnchorCheckPayload,
    AnchorCreatePayload,
    AnchorGeneratePayload,
    AnchorUpdatePayload,
    AppSettingsView,
    AgentDecidePayload,
    AgentDesiresPayload,
    AgentInitPayload,
    BranchPayload,
    BranchView,
    CharacterSheet,
    ChapterReviewPayload,
    CharacterView,
    Commit,
    CommitResult,
    CommitScenePayload,
    ConvergenceCheck,
    CreateEntityPayload,
    Entity,
    Root,
    SceneOrigin,
    SceneVersion,
    Act,
    Chapter,
    StoryAnchor,
    UpdateEntityPayload,
    CreateSceneOriginPayload,
    CreateSceneOriginResult,
    DeleteSceneOriginPayload,
    Desire,
    DMArbitratePayload,
    DMConvergePayload,
    DMIntervenePayload,
    DMReplanPayload,
    EntityRelationView,
    EntityView,
    FeedbackLoopPayload,
    ForkFromCommitPayload,
    ForkFromScenePayload,
    GcPayload,
    GcResult,
    IdeaPayload,
    ImpactLevel,
    LoglinePayload,
    LogicCheckPayload,
    LogicCheckResult,
    RenderScenePayload,
    ReviewStatus,
    ResetBranchPayload,
    RootGraphView,
    RootListItem,
    RootListView,
    ProjectCreatePayload,
    SceneCompletePayload,
    SceneCompletionOrchestratePayload,
    SceneCompletionResult,
    SceneContextView,
    SceneNode,
    ScenePayload,
    SceneReorderPayload,
    SceneReorderResult,
    SceneRenderPayload,
    SceneRenderResult,
    SceneView,
    SimulationRoundPayload,
    SimulationRoundResult,
    SimulationScenePayload,
    SnowflakeRoot,
    SnowflakePromptSet,
    StateExtractPayload,
    StateProposal,
    Step4Result,
    Step5aPayload,
    Step5bPayload,
    SaveSnowflakeStepPayload,
    StructureTreeActView,
    StructureTreeView,
    SubplotCreatePayload,
    ToponeGeneratePayload,
    UpsertRelationPayload,
)
from app.services.character_agent import CharacterAgentEngine
from app.services.llm_engine import LLMEngine, LocalStoryEngine
from app.services.simulation_engine import SimulationEngine
from app.services.feedback_detector import FeedbackDetector
from app.services.smart_renderer import SmartRenderer
from app.services.subplot_manager import SubplotManager
from app.services.topone_client import ToponeClient
from app.services.world_master import WorldMasterEngine
from app.constants import DEFAULT_BRANCH_ID
from app.storage.ports import GraphStoragePort
from app.storage.schema import SimulationLog, Subplot

app = FastAPI(title="Snowflake Engine API", version="0.1.0")

logger = logging.getLogger(__name__)


# Global exception mapping to avoid leaking 500 for validation/infrastructure issues.

def _normalize_unhandled_exception(exc: Exception) -> tuple[int, str]:
    if isinstance(
        exc,
        (ValueError, TypeError, KeyError, ValidationError, json.JSONDecodeError),
    ):
        detail = str(exc) or "invalid request payload"
        return 422, detail
    detail = str(exc) or exc.__class__.__name__
    return 503, f"service unavailable: {detail}"


@app.exception_handler(Exception)
async def _unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    status_code, detail = _normalize_unhandled_exception(exc)
    logger.exception("Unhandled exception")
    return JSONResponse(status_code=status_code, content={"detail": detail})

_ALLOWED_SNOWFLAKE_ENGINES = {"local", "llm", "gemini"}

_SNOWFLAKE_PROMPT_STORE: dict[tuple[str, str], SnowflakePromptSet] = {}


def _default_app_settings() -> AppSettingsView:
    return AppSettingsView(
        llm_config={
            "model": TOPONE_DEFAULT_MODEL,
            "temperature": 0.7,
            "max_tokens": 1024,
            "timeout": int(TOPONE_TIMEOUT_SECONDS),
            "system_instruction": "",
        },
        system_config={
            "auto_save": True,
            "ui_density": "comfortable",
        },
    )


_APP_SETTINGS = _default_app_settings()


def _default_snowflake_prompt_set() -> SnowflakePromptSet:
    return SnowflakePromptSet(
        step1=snowflake_prompts.SNOWFLAKE_STEP1_SYSTEM_PROMPT,
        step2=snowflake_prompts.SNOWFLAKE_STEP2_SYSTEM_PROMPT,
        step3=snowflake_prompts.SNOWFLAKE_STEP3_SYSTEM_PROMPT,
        step4=snowflake_prompts.SNOWFLAKE_STEP4_SYSTEM_PROMPT,
        step5=(
            f"{snowflake_prompts.SNOWFLAKE_STEP5A_SYSTEM_PROMPT}\n"
            f"{snowflake_prompts.SNOWFLAKE_STEP5B_SYSTEM_PROMPT}"
        ),
        step6=snowflake_prompts.STORY_ANCHORS_SYSTEM_PROMPT,
    )


def _get_snowflake_prompt_set(root_id: str, branch_id: str) -> SnowflakePromptSet:
    cached = _SNOWFLAKE_PROMPT_STORE.get((root_id, branch_id))
    if cached is None:
        return _default_snowflake_prompt_set()
    return cached.model_copy(deep=True)


def _require_snowflake_engine_mode() -> str:  # pragma: no cover
    raw = os.getenv("SNOWFLAKE_ENGINE")
    if raw is None:
        raise RuntimeError(
            "SNOWFLAKE_ENGINE 未配置：必须显式设置为 local/llm/gemini（例如：SNOWFLAKE_ENGINE=local）。"
        )
    mode = raw.strip().lower()
    if mode not in _ALLOWED_SNOWFLAKE_ENGINES:
        raise RuntimeError(f"SNOWFLAKE_ENGINE={raw!r} 非法：必须为 local/llm/gemini。")
    return mode



def _count_rendered_chars(content: str) -> int:
    return sum(
        1
        for ch in content
        if not ch.isspace() and not unicodedata.category(ch).startswith("P")
    )


def _raise_upstream_http_error(exc: httpx.HTTPError) -> None:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        status_code = exc.response.status_code
        raise HTTPException(
            status_code=status_code,
            detail=f"upstream llm request failed with status {status_code}",
        ) from exc
    if isinstance(exc, httpx.TimeoutException):
        raise HTTPException(status_code=504, detail="upstream llm request timed out") from exc
    raise HTTPException(status_code=503, detail="upstream llm service unavailable") from exc


@app.on_event("startup")
async def _validate_snowflake_engine_config() -> None:  # pragma: no cover
    try:
        _require_snowflake_engine_mode()
    except RuntimeError as exc:
        logger.error("snowflake engine config invalid: %s", exc)



def get_llm_engine() -> LLMEngine | LocalStoryEngine | ToponeGateway:  # pragma: no cover
    """默认依赖注入，可在测试中 override。"""
    try:
        engine_mode = _require_snowflake_engine_mode()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if engine_mode == "local":
        return LocalStoryEngine()
    if engine_mode == "llm":
        return LLMEngine()
    if engine_mode == "gemini":
        return get_topone_gateway()
    raise RuntimeError("unreachable")


@lru_cache(maxsize=1)
def get_graph_storage() -> GraphStoragePort:  # pragma: no cover
    """Graph storage 单例，避免重复建立连接。"""
    try:
        host = require_memgraph_host()
        port = require_memgraph_port()
        from app.storage.memgraph_storage import MemgraphStorage

        return MemgraphStorage(host=host, port=port)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"memgraph unavailable: {exc}") from exc



def get_snowflake_manager(  # pragma: no cover
    engine: LLMEngine | LocalStoryEngine | ToponeGateway = Depends(get_llm_engine),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> SnowflakeManager:
    """默认使用严格场景数量校验，可在测试 override。"""
    return SnowflakeManager(
        engine=engine,
        storage=storage,
        min_scenes=SCENE_MIN_COUNT,
        max_scenes=SCENE_MAX_COUNT,
    )


@lru_cache(maxsize=1)
def get_topone_client() -> ToponeClient:  # pragma: no cover
    """TopOne Gemini 客户端单例，读取 .env 配置。"""
    return ToponeClient()


@lru_cache(maxsize=1)
def get_topone_gateway() -> ToponeGateway:  # pragma: no cover
    """TopOne 统一网关单例：结构化输出校验入口。"""
    return ToponeGateway(get_topone_client())


def get_character_agent_engine(
    storage: GraphStoragePort = Depends(get_graph_storage),
    llm: LLMEngine | LocalStoryEngine | ToponeGateway = Depends(get_llm_engine),
) -> CharacterAgentEngine:  # pragma: no cover
    return CharacterAgentEngine(storage=storage, llm=llm)


def get_world_master_engine(
    llm: LLMEngine | LocalStoryEngine | ToponeGateway = Depends(get_llm_engine),
) -> WorldMasterEngine:  # pragma: no cover
    return WorldMasterEngine(llm=llm)


def get_smart_renderer(
    llm: LLMEngine | LocalStoryEngine | ToponeGateway = Depends(get_llm_engine),
) -> SmartRenderer:  # pragma: no cover
    return SmartRenderer(llm=llm)


def get_subplot_manager(
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> SubplotManager:  # pragma: no cover
    return SubplotManager(storage)


def get_simulation_engine(
    character_engine: CharacterAgentEngine = Depends(get_character_agent_engine),
    world_master: WorldMasterEngine = Depends(get_world_master_engine),
    storage: GraphStoragePort = Depends(get_graph_storage),
    llm: LLMEngine | LocalStoryEngine | ToponeGateway = Depends(get_llm_engine),
    smart_renderer: SmartRenderer = Depends(get_smart_renderer),
) -> SimulationEngine:  # pragma: no cover
    return SimulationEngine(
        character_engine=character_engine,
        world_master=world_master,
        storage=storage,
        llm=llm,
        smart_renderer=smart_renderer,
    )


def get_feedback_detector() -> FeedbackDetector:  # pragma: no cover
    return FeedbackDetector()


@app.post("/api/v1/snowflake/step2", response_model=SnowflakeRoot)
async def generate_structure_endpoint(  # pragma: no cover
    payload: LoglinePayload,
    engine: LLMEngine | LocalStoryEngine | ToponeGateway = Depends(get_llm_engine),
) -> SnowflakeRoot:
    try:
        return await engine.generate_root_structure(payload.logline)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        _raise_upstream_http_error(exc)


@app.post("/api/v1/snowflake/step1", response_model=List[str])
async def generate_loglines_endpoint(  # pragma: no cover
    payload: IdeaPayload, manager: SnowflakeManager = Depends(get_snowflake_manager)
) -> List[str]:
    try:
        return await manager.execute_step_1_logline(payload.idea)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        _raise_upstream_http_error(exc)


@app.post("/api/v1/snowflake/step3", response_model=List[CharacterSheet])
async def generate_characters_endpoint(  # pragma: no cover
    root: SnowflakeRoot, manager: SnowflakeManager = Depends(get_snowflake_manager)
) -> List[CharacterSheet]:
    try:
        return await manager.execute_step_3_characters(root)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        _raise_upstream_http_error(exc)


@app.post("/api/v1/snowflake/step4", response_model=Step4Result)
async def generate_scene_endpoint(  # pragma: no cover
    payload: ScenePayload, manager: SnowflakeManager = Depends(get_snowflake_manager)
) -> Step4Result:
    try:
        scenes = await manager.execute_step_4_scenes(payload.root, payload.characters)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        _raise_upstream_http_error(exc)
    if not manager.last_persisted_root_id:
        raise HTTPException(status_code=500, detail="step4 did not persist root_id")
    return Step4Result(
        root_id=manager.last_persisted_root_id,
        branch_id=DEFAULT_BRANCH_ID,
        scenes=scenes,
    )


@app.post("/api/v1/roots/{root_id}/snowflake/steps")
async def save_snowflake_step_endpoint(  # pragma: no cover
    root_id: str = Path(..., min_length=1),
    payload: SaveSnowflakeStepPayload = Body(...),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, bool]:
    def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ValueError(f"{label} is required")
        return value

    def require_list(value: Any, label: str) -> List[Any]:
        if not isinstance(value, list):
            raise ValueError(f"{label} list is required")
        return value

    def require_str(value: Any, label: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{label} is required")
        return value

    def require_nonempty_str(value: Any, label: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{label} is required")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError(f"{label} is required")
        return trimmed

    def require_storage_method(name: str) -> Any:
        method = getattr(storage, name, None)
        if method is None:
            raise HTTPException(status_code=500, detail=f"storage missing {name}")
        return method

    try:
        storage.get_root_snapshot(root_id=root_id, branch_id=DEFAULT_BRANCH_ID)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"storage unavailable: {exc}") from exc

    try:
        data = require_mapping(payload.data, "step data")
        if payload.step == "step1":
            loglines = require_list(data.get("logline"), "logline")
            normalized = [
                line.strip() for line in loglines if isinstance(line, str) and line.strip()
            ]
            if not normalized:
                raise ValueError("logline is required")
            snapshot = storage.get_root_snapshot(
                root_id=root_id, branch_id=DEFAULT_BRANCH_ID
            )
            update_root = require_storage_method("update_root")
            theme = snapshot.get("theme") if isinstance(snapshot.get("theme"), str) else ""
            ending = (
                snapshot.get("ending") if isinstance(snapshot.get("ending"), str) else ""
            )
            update_root(
                Root(
                    id=root_id,
                    logline=normalized[0],
                    theme=theme,
                    ending=ending,
                )
            )
            return {"ok": True}

        if payload.step == "step2":
            root_payload = require_mapping(data.get("root"), "root")
            logline = require_nonempty_str(root_payload.get("logline"), "root.logline")
            theme = require_str(root_payload.get("theme"), "root.theme")
            ending = require_str(root_payload.get("ending"), "root.ending")
            update_root = require_storage_method("update_root")
            update_root(
                Root(
                    id=root_id,
                    logline=logline,
                    theme=theme,
                    ending=ending,
                )
            )
            return {"ok": True}

        if payload.step == "step3":
            characters = require_list(data.get("characters"), "characters")
            existing_entities = storage.list_entities(
                root_id=root_id, branch_id=DEFAULT_BRANCH_ID
            )
            existing_by_id = {
                entity.get("entity_id"): entity
                for entity in existing_entities
                if entity.get("entity_id")
            }
            update_entity = require_storage_method("update_entity")
            for item in characters:
                record = require_mapping(item, "character")
                entity_id = record.get("id") or record.get("entity_id")
                if not isinstance(entity_id, str) or not entity_id.strip():
                    raise ValueError("character id is required")
                name = require_nonempty_str(record.get("name"), "character.name")
                ambition = require_nonempty_str(
                    record.get("ambition"), "character.ambition"
                )
                conflict = require_nonempty_str(
                    record.get("conflict"), "character.conflict"
                )
                epiphany = require_nonempty_str(
                    record.get("epiphany"), "character.epiphany"
                )
                voice_dna = require_nonempty_str(
                    record.get("voice_dna"), "character.voice_dna"
                )
                semantic_states = {
                    "ambition": ambition,
                    "conflict": conflict,
                    "epiphany": epiphany,
                    "voice_dna": voice_dna,
                }
                existing = existing_by_id.get(entity_id)
                if existing is None:
                    storage.create_entity(
                        root_id=root_id,
                        branch_id=DEFAULT_BRANCH_ID,
                        name=name,
                        entity_type="Character",
                        tags=[],
                        arc_status="active",
                        semantic_states=semantic_states,
                    )
                    continue
                entity = Entity(
                    id=entity_id,
                    root_id=root_id,
                    branch_id=DEFAULT_BRANCH_ID,
                    entity_type=existing.get("entity_type") or "Character",
                    name=name,
                    tags=existing.get("tags") or [],
                    semantic_states=semantic_states,
                    arc_status=existing.get("arc_status") or "active",
                    has_agent=bool(existing.get("has_agent", False)),
                    agent_state_id=existing.get("agent_state_id"),
                )
                update_entity(entity)
            return {"ok": True}

        if payload.step == "step4":
            scenes = require_list(data.get("scenes"), "scenes")
            update_scene_origin = require_storage_method("update_scene_origin")
            update_scene_version = require_storage_method("update_scene_version")
            latest_version_fn = getattr(storage, "_get_latest_scene_version", None)
            if latest_version_fn is None:
                raise HTTPException(
                    status_code=500, detail="storage missing latest scene version lookup"
                )
            for item in scenes:
                record = require_mapping(item, "scene")
                scene_id = require_nonempty_str(record.get("id"), "scene.id")
                title = require_nonempty_str(record.get("title"), "scene.title")
                sequence_index = record.get("sequence_index")
                if not isinstance(sequence_index, int):
                    raise ValueError("scene.sequence_index is required")
                expected_outcome = require_nonempty_str(
                    record.get("expected_outcome"), "scene.expected_outcome"
                )
                conflict_type = require_nonempty_str(
                    record.get("conflict_type"), "scene.conflict_type"
                )
                actual_outcome = record.get("actual_outcome")
                if actual_outcome is None:
                    actual_outcome = ""
                actual_outcome = require_str(actual_outcome, "scene.actual_outcome")
                pov_character_id = require_nonempty_str(
                    record.get("pov_character_id"), "scene.pov_character_id"
                )
                origin = storage.get_scene_origin(scene_id)
                if origin is None:
                    raise KeyError(f"scene origin not found: {scene_id}")
                updated_origin = SceneOrigin(
                    id=origin.id,
                    root_id=origin.root_id,
                    title=title,
                    initial_commit_id=origin.initial_commit_id,
                    sequence_index=sequence_index,
                    parent_act_id=record.get("parent_act_id") or origin.parent_act_id,
                    chapter_id=origin.chapter_id,
                    is_skeleton=origin.is_skeleton,
                )
                update_scene_origin(updated_origin)
                latest_version = latest_version_fn(scene_id)
                if latest_version is None:
                    raise KeyError(f"scene version not found: {scene_id}")
                updated_version = SceneVersion(
                    id=latest_version.id,
                    scene_origin_id=latest_version.scene_origin_id,
                    commit_id=latest_version.commit_id,
                    pov_character_id=pov_character_id,
                    status=latest_version.status,
                    expected_outcome=expected_outcome,
                    conflict_type=conflict_type,
                    actual_outcome=actual_outcome,
                    summary=latest_version.summary,
                    rendered_content=latest_version.rendered_content,
                    logic_exception=latest_version.logic_exception,
                    logic_exception_reason=latest_version.logic_exception_reason,
                    dirty=latest_version.dirty,
                    simulation_log_id=latest_version.simulation_log_id,
                    is_simulated=latest_version.is_simulated,
                )
                update_scene_version(updated_version)
            return {"ok": True}

        if payload.step == "step5":
            acts = require_list(data.get("acts"), "acts")
            chapters = require_list(data.get("chapters"), "chapters")
            update_act = require_storage_method("update_act")
            update_chapter = require_storage_method("update_chapter")
            for item in acts:
                record = require_mapping(item, "act")
                act_id = require_nonempty_str(record.get("id"), "act.id")
                sequence = record.get("sequence")
                if not isinstance(sequence, int):
                    raise ValueError("act.sequence is required")
                title = require_nonempty_str(record.get("title"), "act.title")
                purpose = require_nonempty_str(record.get("purpose"), "act.purpose")
                tone = require_nonempty_str(record.get("tone"), "act.tone")
                existing_act = storage.get_act(act_id)
                if existing_act is None:
                    raise KeyError(f"act not found: {act_id}")
                update_act(
                    Act(
                        id=act_id,
                        root_id=existing_act.root_id,
                        sequence=sequence,
                        title=title,
                        purpose=purpose,
                        tone=tone,
                    )
                )
            for item in chapters:
                record = require_mapping(item, "chapter")
                chapter_id = require_nonempty_str(record.get("id"), "chapter.id")
                sequence = record.get("sequence")
                if not isinstance(sequence, int):
                    raise ValueError("chapter.sequence is required")
                title = require_nonempty_str(record.get("title"), "chapter.title")
                focus = require_nonempty_str(record.get("focus"), "chapter.focus")
                pov_character_id = record.get("pov_character_id")
                if pov_character_id is not None and not isinstance(pov_character_id, str):
                    raise ValueError("chapter.pov_character_id is required")
                existing_chapter = storage.get_chapter(chapter_id)
                if existing_chapter is None:
                    raise KeyError(f"chapter not found: {chapter_id}")
                update_chapter(
                    Chapter(
                        id=chapter_id,
                        act_id=existing_chapter.act_id,
                        sequence=sequence,
                        title=title,
                        focus=focus,
                        pov_character_id=pov_character_id,
                        rendered_content=existing_chapter.rendered_content,
                        review_status=existing_chapter.review_status,
                    )
                )
            return {"ok": True}

        if payload.step == "step6":
            anchors = require_list(data.get("anchors"), "anchors")
            update_anchor = require_storage_method("update_anchor")
            for item in anchors:
                record = require_mapping(item, "anchor")
                anchor_id = require_nonempty_str(record.get("id"), "anchor.id")
                existing_anchor = storage.get_anchor(anchor_id)
                if existing_anchor is None:
                    raise KeyError(f"anchor not found: {anchor_id}")
                description = require_nonempty_str(
                    record.get("description"), "anchor.description"
                )
                constraint_type = require_nonempty_str(
                    record.get("constraint_type"), "anchor.constraint_type"
                )
                anchor_type = record.get("anchor_type") or existing_anchor.anchor_type
                if not isinstance(anchor_type, str) or not anchor_type.strip():
                    raise ValueError("anchor.anchor_type is required")
                required_conditions = record.get("required_conditions")
                if isinstance(required_conditions, list):
                    required_conditions_payload = json.dumps(required_conditions)
                elif isinstance(required_conditions, str):
                    required_conditions_payload = required_conditions
                else:
                    raise ValueError("anchor.required_conditions is required")
                achieved = record.get("achieved")
                if achieved is None:
                    achieved_value = bool(existing_anchor.achieved)
                elif isinstance(achieved, bool):
                    achieved_value = achieved
                else:
                    raise ValueError("anchor.achieved is required")
                update_anchor(
                    StoryAnchor(
                        id=existing_anchor.id,
                        root_id=existing_anchor.root_id,
                        branch_id=existing_anchor.branch_id,
                        sequence=existing_anchor.sequence,
                        anchor_type=anchor_type,
                        description=description,
                        constraint_type=constraint_type,
                        required_conditions=required_conditions_payload,
                        deadline_scene=existing_anchor.deadline_scene,
                        achieved=achieved_value,
                    )
                )
            return {"ok": True}

        raise ValueError("unsupported snowflake step")
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"storage unavailable: {exc}") from exc


@app.get("/api/v1/roots/{root_id}/snowflake/prompts", response_model=SnowflakePromptSet)
async def get_snowflake_prompts_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> SnowflakePromptSet:
    try:
        storage.get_root_snapshot(root_id=root_id, branch_id=branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _get_snowflake_prompt_set(root_id, branch_id)


@app.put("/api/v1/roots/{root_id}/snowflake/prompts", response_model=SnowflakePromptSet)
async def save_snowflake_prompts_endpoint(  # pragma: no cover
    root_id: str,
    payload: SnowflakePromptSet,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> SnowflakePromptSet:
    try:
        storage.get_root_snapshot(root_id=root_id, branch_id=branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _SNOWFLAKE_PROMPT_STORE[(root_id, branch_id)] = payload.model_copy(deep=True)
    return payload


@app.post("/api/v1/roots/{root_id}/snowflake/prompts/reset", response_model=SnowflakePromptSet)
async def reset_snowflake_prompts_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> SnowflakePromptSet:
    try:
        storage.get_root_snapshot(root_id=root_id, branch_id=branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _SNOWFLAKE_PROMPT_STORE.pop((root_id, branch_id), None)
    return _default_snowflake_prompt_set()


@app.get("/api/v1/settings/llm", response_model=AppSettingsView)
async def get_llm_settings_endpoint() -> AppSettingsView:
    return _APP_SETTINGS.model_copy(deep=True)


@app.put("/api/v1/settings/llm", response_model=AppSettingsView)
async def save_llm_settings_endpoint(payload: AppSettingsView) -> AppSettingsView:
    global _APP_SETTINGS
    _APP_SETTINGS = payload.model_copy(deep=True)
    return _APP_SETTINGS.model_copy(deep=True)


@app.post("/api/v1/snowflake/step5a")
async def generate_act_list_endpoint(  # pragma: no cover
    payload: Step5aPayload,
    engine: LLMEngine | LocalStoryEngine | ToponeGateway = Depends(get_llm_engine),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> List[dict[str, Any]]:
    try:
        acts = await engine.generate_act_list(payload.root, payload.characters)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        _raise_upstream_http_error(exc)
    if not acts:
        raise HTTPException(status_code=400, detail="step5a returned empty acts")
    created: list[dict[str, Any]] = []
    for idx, act in enumerate(acts, start=1):
        if not isinstance(act, Mapping):
            raise HTTPException(status_code=422, detail="step5a act item must be object")
        title = act.get("title")
        purpose = act.get("purpose")
        tone = act.get("tone")
        if not title or not purpose or not tone:
            raise HTTPException(status_code=400, detail="act fields are required")
        try:
            created.append(
                storage.create_act(
                    root_id=payload.root_id,
                    seq=idx,
                    title=title,
                    purpose=purpose,
                    tone=tone,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return created


@app.post("/api/v1/snowflake/step5b")
async def generate_chapter_list_endpoint(  # pragma: no cover
    payload: Step5bPayload,
    engine: LLMEngine | LocalStoryEngine | ToponeGateway = Depends(get_llm_engine),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> List[dict[str, Any]]:
    try:
        acts = storage.list_acts(root_id=payload.root_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not acts:
        raise HTTPException(status_code=404, detail="acts not found")
    chapters: list[dict[str, Any]] = []
    planned: list[tuple[str, list[dict[str, Any]]]] = []
    total_count = 0
    for act in acts:
        if not isinstance(act, Mapping):
            raise HTTPException(status_code=422, detail="step5b act item must be object")
        act_id = act.get("id")
        if not act_id:
            raise HTTPException(status_code=422, detail="act id is required")
        try:
            generated = await engine.generate_chapter_list(payload.root, act, payload.characters)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            _raise_upstream_http_error(exc)
        if not generated:
            raise HTTPException(status_code=422, detail="step5b returned empty chapters")
        total_count += len(generated)
        planned.append((act_id, generated))
    if total_count != 10:
        raise HTTPException(status_code=422, detail="chapter count must be 10")
    for act_id, generated in planned:
        for idx, chapter in enumerate(generated, start=1):
            if not isinstance(chapter, Mapping):
                raise HTTPException(status_code=422, detail="step5b chapter item must be object")
            title = chapter.get("title")
            focus = chapter.get("focus")
            pov_character_id = chapter.get("pov_character_id")
            if not title or not focus:
                raise HTTPException(status_code=422, detail="chapter fields are required")
            try:
                chapters.append(
                    storage.create_chapter(
                        act_id=act_id,
                        seq=idx,
                        title=title,
                        focus=focus,
                        pov_character_id=pov_character_id,
                    )
                )
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
    return chapters


@app.post("/api/v1/roots/{root_id}/anchors")
async def create_anchor_endpoint(  # pragma: no cover
    root_id: str,
    payload: AnchorGeneratePayload,
    engine: LLMEngine | LocalStoryEngine | ToponeGateway = Depends(get_llm_engine),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> List[dict[str, Any]]:
    try:
        acts = storage.list_acts(root_id=root_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not acts:
        raise HTTPException(status_code=400, detail="acts are required for anchors")
    anchors = await engine.generate_story_anchors(payload.root, payload.characters, acts)
    if not (10 <= len(anchors) <= 15):
        raise HTTPException(status_code=400, detail="invalid anchors count")
    created: list[dict[str, Any]] = []
    for idx, anchor in enumerate(anchors, start=1):
        anchor_type = anchor.get("anchor_type")
        description = anchor.get("description")
        constraint_type = anchor.get("constraint_type")
        required_conditions = anchor.get("required_conditions")
        if not anchor_type or not description or not constraint_type or required_conditions is None:
            raise HTTPException(status_code=400, detail="anchor fields are required")
        created.append(
            storage.create_anchor(
                root_id=root_id,
                branch_id=payload.branch_id,
                seq=idx,
                type=anchor_type,
                desc=description,
                constraint=constraint_type,
                conditions=json.dumps(required_conditions),
            )
        )
    return created


@app.get("/api/v1/roots/{root_id}/anchors")
async def list_anchors_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> List[dict[str, Any]]:
    try:
        return storage.list_anchors(root_id=root_id, branch_id=branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/roots/{root_id}/subplots")
async def list_subplots_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> List[dict[str, Any]]:
    try:
        return storage.list_subplots(root_id=root_id, branch_id=branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/roots/{root_id}/subplots")
async def create_subplot_endpoint(  # pragma: no cover
    root_id: str,
    payload: SubplotCreatePayload,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, Any]:
    subplot = Subplot(
        id=f"{root_id}:subplot:{uuid4()}",
        root_id=root_id,
        branch_id=payload.branch_id,
        title=payload.title,
        subplot_type=payload.subplot_type,
        protagonist_id=payload.protagonist_id,
        central_conflict=payload.central_conflict,
        status="dormant",
    )
    try:
        created = storage.create_subplot(subplot)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": created.id,
        "root_id": created.root_id,
        "branch_id": created.branch_id,
        "title": created.title,
        "subplot_type": created.subplot_type,
        "protagonist_id": created.protagonist_id,
        "central_conflict": created.central_conflict,
        "status": created.status,
    }


@app.post("/api/v1/subplots/{subplot_id}/activate")
async def activate_subplot_endpoint(  # pragma: no cover
    subplot_id: str,
    storage: GraphStoragePort = Depends(get_graph_storage),
    manager: SubplotManager = Depends(get_subplot_manager),
) -> dict[str, Any]:
    subplot = storage.get_subplot(subplot_id)
    if subplot is None:
        raise HTTPException(status_code=404, detail="subplot not found")
    try:
        updated = manager.activate_subplot(subplot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": updated.id,
        "root_id": updated.root_id,
        "branch_id": updated.branch_id,
        "title": updated.title,
        "subplot_type": updated.subplot_type,
        "protagonist_id": updated.protagonist_id,
        "central_conflict": updated.central_conflict,
        "status": updated.status,
    }


@app.post("/api/v1/subplots/{subplot_id}/resolve")
async def resolve_subplot_endpoint(  # pragma: no cover
    subplot_id: str,
    storage: GraphStoragePort = Depends(get_graph_storage),
    manager: SubplotManager = Depends(get_subplot_manager),
) -> dict[str, Any]:
    subplot = storage.get_subplot(subplot_id)
    if subplot is None:
        raise HTTPException(status_code=404, detail="subplot not found")
    try:
        updated = manager.resolve_subplot(subplot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": updated.id,
        "root_id": updated.root_id,
        "branch_id": updated.branch_id,
        "title": updated.title,
        "subplot_type": updated.subplot_type,
        "protagonist_id": updated.protagonist_id,
        "central_conflict": updated.central_conflict,
        "status": updated.status,
    }


@app.put("/api/v1/anchors/{id}")
async def update_anchor_endpoint(  # pragma: no cover
    id: str,
    payload: AnchorUpdatePayload,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, Any]:
    anchor = storage.get_anchor(id)
    if anchor is None:
        raise HTTPException(status_code=404, detail="anchor not found")
    if payload.description is not None:
        anchor.description = payload.description
    if payload.constraint_type is not None:
        anchor.constraint_type = payload.constraint_type
    if payload.required_conditions is not None:
        anchor.required_conditions = json.dumps(payload.required_conditions)
    if payload.achieved is not None:
        anchor.achieved = payload.achieved
    updated = storage.update_anchor(anchor)
    return {
        "id": updated.id,
        "root_id": updated.root_id,
        "branch_id": updated.branch_id,
        "sequence": updated.sequence,
        "anchor_type": updated.anchor_type,
        "description": updated.description,
        "constraint_type": updated.constraint_type,
        "required_conditions": updated.required_conditions,
        "deadline_scene": updated.deadline_scene,
        "achieved": updated.achieved,
    }


@app.post("/api/v1/anchors/{id}/check")
async def check_anchor_endpoint(  # pragma: no cover
    id: str,
    payload: AnchorCheckPayload,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, Any]:
    if not payload.world_state and payload.scene_version_id:
        try:
            marked = storage.mark_anchor_achieved(
                anchor_id=id, scene_version_id=payload.scene_version_id
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "id": marked.get("id", id),
            "reachable": True,
            "missing_conditions": [],
            "achieved": marked.get("achieved", True),
        }
    anchor = storage.get_anchor(id)
    if anchor is None:
        raise HTTPException(status_code=404, detail="anchor not found")
    required_conditions = anchor.required_conditions
    if isinstance(required_conditions, str):
        required_conditions = json.loads(required_conditions)
    if not isinstance(required_conditions, list):
        raise ValueError("anchor required_conditions must be list")
    missing = [
        condition
        for condition in required_conditions
        if not payload.world_state.get(condition)
    ]
    reachable = len(missing) == 0
    achieved = anchor.achieved
    if reachable and payload.scene_version_id:
        try:
            marked = storage.mark_anchor_achieved(
                anchor_id=id, scene_version_id=payload.scene_version_id
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        achieved = marked.get("achieved", True)
    return {
        "id": anchor.id,
        "reachable": reachable,
        "missing_conditions": missing,
        "achieved": achieved,
    }


@app.get("/api/v1/roots/{root_id}/acts")
async def list_acts_endpoint(  # pragma: no cover
    root_id: str,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> List[dict[str, Any]]:
    try:
        return storage.list_acts(root_id=root_id)
    except KeyError as exc:
        logger.warning("acts root not found: %s", root_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/acts/{act_id}/chapters")
async def list_chapters_endpoint(  # pragma: no cover
    act_id: str,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> List[dict[str, Any]]:
    return storage.list_chapters(act_id=act_id)


@app.post("/api/v1/chapters/{chapter_id}/render")
async def render_chapter_endpoint(  # pragma: no cover
    chapter_id: str,
    gateway: ToponeGateway = Depends(get_topone_gateway),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, str]:
    chapter = storage.get_chapter(chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    outline_requirement = (
        f"章节标题: {chapter.title}\n"
        f"章节焦点: {chapter.focus}\n"
        "请写约2000字的章节正文，建议 1500-2600 字（不含标点空白），尽量接近 2000 字。"
    )
    payload = SceneRenderPayload(
        voice_dna="neutral",
        conflict_type="internal",
        outline_requirement=outline_requirement,
        user_intent="render chapter",
        expected_outcome=chapter.focus,
        world_state={},
    )
    try:
        content = await gateway.render_scene(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    suggested_min = 1500
    suggested_max = 2600
    content_length = _count_rendered_chars(content)
    if content_length < suggested_min or content_length > suggested_max:
        logger.warning(
            "rendered_content length out of range: %s, expected %s-%s",
            content_length,
            suggested_min,
            suggested_max,
        )
    chapter.rendered_content = content
    try:
        storage.update_chapter(chapter)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"rendered_content": content}


@app.post("/api/v1/chapters/{chapter_id}/review")
async def review_chapter_endpoint(  # pragma: no cover
    chapter_id: str,
    payload: ChapterReviewPayload,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, str]:
    chapter = storage.get_chapter(chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    status = payload.status
    if status not in {ReviewStatus.approved.value, ReviewStatus.rejected.value}:
        raise HTTPException(status_code=400, detail="invalid status")
    chapter.review_status = ReviewStatus(status)
    try:
        storage.update_chapter(chapter)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": chapter_id, "review_status": status}


@app.get("/api/v1/chapters/{chapter_id}")
async def get_chapter_endpoint(  # pragma: no cover
    chapter_id: str,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, Any]:
    chapter = storage.get_chapter(chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    review_status = chapter.review_status
    if hasattr(review_status, "value"):
        review_status = review_status.value
    return {
        "id": chapter.id,
        "act_id": chapter.act_id,
        "sequence": chapter.sequence,
        "title": chapter.title,
        "focus": chapter.focus,
        "pov_character_id": chapter.pov_character_id,
        "rendered_content": chapter.rendered_content,
        "review_status": review_status,
    }


@app.post("/api/v1/entities/{id}/agent/init")
async def init_agent_endpoint(  # pragma: no cover
    id: str,
    payload: AgentInitPayload,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, Any]:
    try:
        return storage.init_character_agent(
            char_id=id,
            branch_id=payload.branch_id,
            initial_desires=payload.initial_desires,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/entities/{id}/agent/state")
async def get_agent_state_endpoint(  # pragma: no cover
    id: str,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, Any]:
    agent_id = f"agent:{id}:{branch_id}"
    agent = storage.get_agent_state(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return {
        "id": agent.id,
        "character_id": agent.character_id,
        "branch_id": agent.branch_id,
        "beliefs": agent.beliefs,
        "desires": agent.desires,
        "intentions": agent.intentions,
        "memory": agent.memory,
        "private_knowledge": agent.private_knowledge,
        "last_updated_scene": agent.last_updated_scene,
        "version": agent.version,
    }


@app.put("/api/v1/entities/{id}/agent/desires")
async def update_agent_desires_endpoint(  # pragma: no cover
    id: str,
    payload: AgentDesiresPayload,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, Any]:
    agent_id = f"agent:{id}:{branch_id}"
    desires = [desire.model_dump() for desire in payload.desires]
    try:
        return storage.update_agent_desires(agent_id=agent_id, desires=desires)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/entities/{id}/agent/decide")
async def agent_decide_endpoint(  # pragma: no cover
    id: str,
    payload: AgentDecidePayload,
    engine: CharacterAgentEngine = Depends(get_character_agent_engine),
) -> dict[str, Any]:
    action = await engine.decide(id, payload.scene_context)
    return action.model_dump()


@app.post("/api/v1/dm/arbitrate")
async def dm_arbitrate_endpoint(  # pragma: no cover
    payload: DMArbitratePayload,
    engine: WorldMasterEngine = Depends(get_world_master_engine),
) -> dict[str, Any]:
    arbitration = await engine.arbitrate(
        payload.round_id,
        payload.actions,
        payload.world_state,
        [],
    )
    return arbitration.model_dump()


@app.post("/api/v1/dm/converge")
async def dm_converge_endpoint(  # pragma: no cover
    payload: DMConvergePayload,
    engine: WorldMasterEngine = Depends(get_world_master_engine),
) -> dict[str, Any]:
    check = await engine.check_convergence(payload.world_state, payload.next_anchor)
    return check.model_dump()


@app.post("/api/v1/dm/intervene")
async def dm_intervene_endpoint(  # pragma: no cover
    payload: DMIntervenePayload,
    engine: WorldMasterEngine = Depends(get_world_master_engine),
) -> dict[str, Any]:
    check = ConvergenceCheck(**payload.check)
    return await engine.generate_convergence_action(check, payload.world_state)


@app.post("/api/v1/dm/replan")
async def dm_replan_endpoint(  # pragma: no cover
    payload: DMReplanPayload,
    engine: WorldMasterEngine = Depends(get_world_master_engine),
) -> dict[str, Any]:
    result = await engine.replan_route(
        payload.current_scene,
        payload.target_anchor,
        payload.world_state,
    )
    if result.reason == "hard_anchor_unreachable":
        raise HTTPException(status_code=422, detail=result.reason)
    return result.model_dump()


@app.get("/api/v1/simulation/agents")
async def simulation_agents_endpoint(  # pragma: no cover
    root_id: str = Query(..., min_length=1),
    branch_id: str = Query(..., min_length=1),
) -> dict[str, Any]:
    _ = (root_id, branch_id)
    return {"agents": [], "convergence": None}


@app.post("/api/v1/simulation/round")
async def simulation_round_endpoint(  # pragma: no cover
    payload: SimulationRoundPayload,
    engine: SimulationEngine = Depends(get_simulation_engine),
) -> dict[str, Any]:
    config = SimpleNamespace(round_id=payload.round_id)

    class AgentProxy:
        def __init__(self, agent_id: str, character_engine: CharacterAgentEngine) -> None:
            self.agent_id = agent_id
            self._engine = character_engine

        async def decide(self, agent_id: str, scene_context: dict[str, Any]):
            return await self._engine.decide(agent_id, scene_context)

    agents: list[object] = []
    if payload.agents:
        character_engine = getattr(engine, "character_engine", None)
        if character_engine is None:
            raise HTTPException(status_code=500, detail="character_engine is required")
        for agent in payload.agents:
            if not isinstance(agent, Mapping):
                raise HTTPException(status_code=422, detail="agent payload must be object")
            agent_id = agent.get("agent_id") or agent.get("id")
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise HTTPException(status_code=422, detail="agent_id is required")
            agents.append(AgentProxy(agent_id.strip(), character_engine))
    try:
        result = await engine.run_round(payload.scene_context, agents, config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        _raise_upstream_http_error(exc)
    return result.model_dump()


@app.post("/api/v1/simulation/scene")
async def simulation_scene_endpoint(  # pragma: no cover
    payload: SimulationScenePayload,
    engine: SimulationEngine = Depends(get_simulation_engine),
) -> dict[str, Any]:
    round_id_base = payload.scene_context.get("scene_id") or payload.scene_context.get("id")
    config = SimpleNamespace(max_rounds=payload.max_rounds, round_id=round_id_base)
    try:
        content = await engine.run_scene(payload.scene_context, config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TypeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        _raise_upstream_http_error(exc)
    return {"content": content}


@app.post("/api/v1/feedback/loop")
@app.post("/api/v1/simulation/feedback")
async def feedback_loop_endpoint(  # pragma: no cover
    payload: FeedbackLoopPayload,
    detector: FeedbackDetector = Depends(get_feedback_detector),
) -> dict[str, Any]:
    report, updated_context = await detector.process_feedback(
        payload.scene_context, payload.rounds
    )
    return {
        "report": report.model_dump() if report is not None else None,
        "scene_context": updated_context,
    }



def _normalize_simulation_log(log: SimulationLog) -> dict[str, Any]:
    payload = log.model_dump()
    agent_actions = json.loads(payload["agent_actions"])
    dm_arbitration = json.loads(payload["dm_arbitration"])
    if "round_id" not in dm_arbitration:
        dm_arbitration = dict(dm_arbitration)
        dm_arbitration["round_id"] = f"round-{payload['round_number']}"
    if "action_results" not in dm_arbitration:
        dm_arbitration = dict(dm_arbitration)
        dm_arbitration["action_results"] = []
    narrative_events = json.loads(payload["narrative_events"])
    sensory_seeds = json.loads(payload["sensory_seeds"])
    round_result = SimulationRoundResult(
        round_id=dm_arbitration["round_id"],
        agent_actions=agent_actions,
        dm_arbitration=dm_arbitration,
        narrative_events=narrative_events,
        sensory_seeds=sensory_seeds,
        convergence_score=payload["convergence_score"],
        drama_score=payload["drama_score"],
        info_gain=payload["info_gain"],
        stagnation_count=payload["stagnation_count"],
    )
    payload.update(round_result.model_dump())
    return payload


@app.get("/api/v1/simulation/logs/{scene_id}")
async def simulation_log_endpoint(  # pragma: no cover
    scene_id: str,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> list[dict[str, Any]]:
    logs = storage.list_simulation_logs(scene_id)
    if not logs:
        raise HTTPException(status_code=404, detail="simulation log not found")
    return [_normalize_simulation_log(log) for log in logs]


@app.post("/api/v1/render/scene")
async def render_scene_m4_endpoint(  # pragma: no cover
    payload: RenderScenePayload,
    renderer: SmartRenderer = Depends(get_smart_renderer),
) -> dict[str, Any]:
    content = await renderer.render(payload.rounds, payload.scene)
    return {"content": content}


@app.post("/api/v1/roots/{root_id}/branches", response_model=BranchView)
async def create_branch_endpoint(  # pragma: no cover
    root_id: str,
    payload: BranchPayload,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> BranchView:
    try:
        storage.create_branch(root_id=root_id, branch_id=payload.branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        status_code = 409 if "already exists" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return BranchView(root_id=root_id, branch_id=payload.branch_id)


@app.get("/api/v1/roots/{root_id}/branches", response_model=List[str])
async def list_branches_endpoint(  # pragma: no cover
    root_id: str, storage: GraphStoragePort = Depends(get_graph_storage)
) -> List[str]:
    try:
        return storage.list_branches(root_id=root_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/roots/{root_id}/branches/{branch_id}/switch", response_model=BranchView)
async def switch_branch_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Path(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> BranchView:
    try:
        storage.require_branch(root_id=root_id, branch_id=branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BranchView(root_id=root_id, branch_id=branch_id)


@app.post(
    "/api/v1/roots/{root_id}/branches/{branch_id}/merge",
    response_model=BranchView,
)
async def merge_branch_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Path(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> BranchView:
    try:
        storage.merge_branch(root_id=root_id, branch_id=branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BranchView(root_id=root_id, branch_id=branch_id)


@app.post(
    "/api/v1/roots/{root_id}/branches/{branch_id}/revert",
    response_model=BranchView,
)
async def revert_branch_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Path(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> BranchView:
    try:
        storage.revert_branch(root_id=root_id, branch_id=branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BranchView(root_id=root_id, branch_id=branch_id)


@app.post(
    "/api/v1/roots/{root_id}/branches/fork_from_commit",
    response_model=BranchView,
)
async def fork_from_commit_endpoint(  # pragma: no cover
    root_id: str,
    payload: ForkFromCommitPayload,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> BranchView:
    try:
        storage.fork_from_commit(
            root_id=root_id,
            source_commit_id=payload.source_commit_id,
            new_branch_id=payload.new_branch_id,
            parent_branch_id=payload.parent_branch_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        status_code = 409 if "already exists" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return BranchView(root_id=root_id, branch_id=payload.new_branch_id)


@app.post(
    "/api/v1/roots/{root_id}/branches/fork_from_scene",
    response_model=BranchView,
)
async def fork_from_scene_endpoint(  # pragma: no cover
    root_id: str,
    payload: ForkFromScenePayload,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> BranchView:
    try:
        storage.fork_from_scene(
            root_id=root_id,
            source_branch_id=payload.source_branch_id,
            scene_origin_id=payload.scene_origin_id,
            new_branch_id=payload.new_branch_id,
            commit_id=payload.commit_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        status_code = 409 if "already exists" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return BranchView(root_id=root_id, branch_id=payload.new_branch_id)


@app.post(
    "/api/v1/roots/{root_id}/branches/{branch_id}/reset",
    response_model=BranchView,
)
async def reset_branch_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Path(..., min_length=1),
    payload: ResetBranchPayload = Body(...),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> BranchView:
    try:
        storage.reset_branch_head(
            root_id=root_id, branch_id=branch_id, commit_id=payload.commit_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BranchView(root_id=root_id, branch_id=branch_id)


@app.get(
    "/api/v1/roots/{root_id}/branches/{branch_id}/history",
    response_model=List[Commit],
)
async def branch_history_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Path(..., min_length=1),
    limit: int = Query(50, ge=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> List[Commit]:
    try:
        return storage.get_branch_history(
            root_id=root_id, branch_id=branch_id, limit=limit
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/api/v1/roots/{root_id}/branches/{branch_id}/commit",
    response_model=CommitResult,
)
async def commit_scene_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Path(..., min_length=1),
    payload: CommitScenePayload = Body(...),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> CommitResult:
    try:
        return storage.commit_scene(
            root_id=root_id,
            branch_id=branch_id,
            scene_origin_id=payload.scene_origin_id,
            content=payload.content,
            message=payload.message,
            expected_head_version=payload.expected_head_version,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/api/v1/roots/{root_id}/scene_origins",
    response_model=CreateSceneOriginResult,
)
async def create_scene_origin_endpoint(  # pragma: no cover
    root_id: str,
    payload: CreateSceneOriginPayload,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> CreateSceneOriginResult:
    try:
        return storage.create_scene_origin(
            root_id=root_id,
            branch_id=branch_id,
            title=payload.title,
            parent_act_id=payload.parent_act_id,
            content=payload.content,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/commits/gc", response_model=GcResult)
async def gc_commits_endpoint(  # pragma: no cover
    payload: GcPayload,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> GcResult:
    try:
        return storage.gc_orphan_commits(retention_days=payload.retention_days)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/roots", response_model=RootListItem)
async def create_root_endpoint(
    payload: ProjectCreatePayload,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> RootListItem:
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        root_payload = SnowflakeRoot(
            logline=payload.name,
            three_disasters=["", "", ""],
            ending="",
            theme="",
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        root_id = storage.save_snowflake(
            root_payload,
            [],
            [],
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"storage unavailable: {exc}") from exc
    return RootListItem(
        root_id=root_id,
        name=payload.name,
        created_at=timestamp,
        updated_at=timestamp,
    )


@app.delete("/api/v1/roots/{root_id}")
async def delete_root_endpoint(
    root_id: str,
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, bool]:
    try:
        storage.delete_root(root_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True}


@app.get("/api/v1/roots", response_model=RootListView)
async def list_roots_endpoint(
    limit: int = Query(20, ge=1),
    offset: int = Query(0, ge=0),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> RootListView:
    try:
        roots = storage.list_roots(limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"storage unavailable: {exc}") from exc
    return RootListView(roots=roots)


@app.get("/api/v1/roots/{root_id}", response_model=RootGraphView)
async def get_root_graph_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> RootGraphView:
    try:
        snapshot = storage.get_root_snapshot(root_id=root_id, branch_id=branch_id)
    except KeyError as exc:
        logger.warning("root snapshot not found: %s", root_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return snapshot


@app.post("/api/v1/roots/{root_id}/entities", response_model=EntityView)
async def create_root_entity_endpoint(  # pragma: no cover
    root_id: str,
    payload: CreateEntityPayload,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> EntityView:
    try:
        entity_id = storage.create_entity(
            root_id=root_id,
            branch_id=branch_id,
            name=payload.name,
            entity_type=payload.entity_type,
            tags=payload.tags,
            arc_status=payload.arc_status,
            semantic_states=payload.semantic_states,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EntityView(
        entity_id=entity_id,
        name=payload.name,
        entity_type=payload.entity_type,
        tags=payload.tags,
        arc_status=payload.arc_status,
        semantic_states=payload.semantic_states,
    )


@app.get("/api/v1/roots/{root_id}/entities", response_model=List[EntityView])
async def list_root_entities_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> List[EntityView]:
    try:
        return storage.list_entities(root_id=root_id, branch_id=branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/v1/roots/{root_id}/entities/{entity_id}", response_model=EntityView)
async def update_root_entity_endpoint(  # pragma: no cover
    root_id: str,
    entity_id: str,
    payload: UpdateEntityPayload,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> EntityView:
    entity = Entity(
        id=entity_id,
        root_id=root_id,
        branch_id=branch_id,
        entity_type=payload.entity_type,
        name=payload.name,
        tags=payload.tags,
        semantic_states=payload.semantic_states,
        arc_status=payload.arc_status,
    )
    try:
        updated = storage.update_entity(entity)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EntityView(
        entity_id=updated.id,
        name=updated.name,
        entity_type=updated.entity_type,
        tags=list(updated.tags or []),
        arc_status=updated.arc_status,
        semantic_states=updated.semantic_states,
    )


@app.delete("/api/v1/roots/{root_id}/entities/{entity_id}")
async def delete_root_entity_endpoint(  # pragma: no cover
    root_id: str,
    entity_id: str,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, str]:
    try:
        storage.delete_entity(entity_id=entity_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"entity_id": entity_id}



@app.post("/api/v1/roots/{root_id}/relations", response_model=EntityRelationView)
async def upsert_relation_endpoint(  # pragma: no cover
    root_id: str,
    payload: UpsertRelationPayload,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> EntityRelationView:
    try:
        storage.upsert_entity_relation(
            root_id=root_id,
            branch_id=branch_id,
            from_entity_id=payload.from_entity_id,
            to_entity_id=payload.to_entity_id,
            relation_type=payload.relation_type,
            tension=payload.tension,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EntityRelationView(
        from_entity_id=payload.from_entity_id,
        to_entity_id=payload.to_entity_id,
        relation_type=payload.relation_type,
        tension=payload.tension,
    )


@app.get("/api/v1/scenes/{scene_id}/context", response_model=SceneContextView)
async def get_scene_context_endpoint(  # pragma: no cover
    scene_id: str,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> SceneContextView:
    try:
        return storage.get_scene_context(scene_id=scene_id, branch_id=branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/scenes/{scene_id}/diff")
async def diff_scene_versions_endpoint(  # pragma: no cover
    scene_id: str,
    from_commit_id: str = Query(..., min_length=1),
    to_commit_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, dict[str, Any]]:
    try:
        return storage.diff_scene_versions(
            scene_origin_id=scene_id,
            from_commit_id=from_commit_id,
            to_commit_id=to_commit_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/api/v1/roots/{root_id}/scenes/{scene_id}/delete",
    response_model=CommitResult,
)
async def delete_scene_origin_endpoint(  # pragma: no cover
    root_id: str,
    scene_id: str,
    payload: DeleteSceneOriginPayload,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> CommitResult:
    try:
        return storage.delete_scene_origin(
            root_id=root_id,
            branch_id=branch_id,
            scene_origin_id=scene_id,
            message=payload.message,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/scenes/{scene_id}/render", response_model=SceneRenderResult)
async def render_scene_endpoint(  # pragma: no cover
    scene_id: str,
    payload: SceneRenderPayload,
    branch_id: str = Query(..., min_length=1),
    gateway: ToponeGateway = Depends(get_topone_gateway),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> SceneRenderResult:
    if _require_snowflake_engine_mode() != "gemini":
        raise HTTPException(
            status_code=400,
            detail="scene render 仅支持 gemini 模式，请设置 SNOWFLAKE_ENGINE=gemini。",
        )

    content = await gateway.render_scene(payload)
    try:
        storage.save_scene_render(
            scene_id=scene_id,
            branch_id=branch_id,
            content=content,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SceneRenderResult(
        ok=True,
        scene_id=scene_id,
        branch_id=branch_id,
        content=content,
    )


@app.post("/api/v1/scenes/{scene_id}/complete")
async def complete_scene_endpoint(  # pragma: no cover
    scene_id: str,
    payload: SceneCompletePayload,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, Any]:
    try:
        storage.complete_scene(
            scene_id=scene_id,
            branch_id=branch_id,
            actual_outcome=payload.actual_outcome,
            summary=payload.summary,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "scene_id": scene_id,
        "branch_id": branch_id,
        "status": "committed",
        "actual_outcome": payload.actual_outcome,
        "summary": payload.summary,
    }


@app.post(
    "/api/v1/scenes/{scene_id}/complete/orchestrated",
    response_model=SceneCompletionResult,
    response_model_exclude_none=True,
)
async def complete_scene_orchestrated_endpoint(  # pragma: no cover
    scene_id: str,
    payload: SceneCompletionOrchestratePayload,
    background_tasks: BackgroundTasks,
    gateway: ToponeGateway = Depends(get_topone_gateway),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> SceneCompletionResult:
    if _require_snowflake_engine_mode() != "gemini":
        raise HTTPException(
            status_code=400,
            detail="场景完成编排仅支持 gemini 模式，请设置 SNOWFLAKE_ENGINE=gemini。",
        )

    mode = payload.mode.strip().lower()
    if mode not in {"force_execute", "standard"}:
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {payload.mode!r}")

    is_logic_exception = False
    if mode == "force_execute":
        reason = payload.force_reason or payload.user_intent
        try:
            storage.mark_scene_logic_exception(
                root_id=payload.root_id,
                branch_id=payload.branch_id,
                scene_id=scene_id,
                reason=reason,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        is_logic_exception = False
    if mode != "force_execute":
        try:
            is_logic_exception = storage.is_scene_logic_exception(
                root_id=payload.root_id,
                branch_id=payload.branch_id,
                scene_id=scene_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    logic_payload = LogicCheckPayload(
        outline_requirement=payload.outline_requirement,
        world_state=payload.world_state,
        user_intent=payload.user_intent,
        mode=mode,
        root_id=payload.root_id,
        branch_id=payload.branch_id,
        scene_id=scene_id,
        force_reason=payload.force_reason,
    )
    logic_result = await gateway.logic_check(logic_payload)
    if mode != "force_execute" and not logic_result.ok and not is_logic_exception:
        raise HTTPException(
            status_code=400, detail=f"logic_check rejected: decision={logic_result.decision}"
        )
    if mode != "force_execute" and not is_logic_exception:
        background_tasks.add_task(
            _apply_impact_level,
            storage=storage,
            root_id=payload.root_id,
            branch_id=payload.branch_id,
            scene_id=scene_id,
            impact_level=logic_result.impact_level,
        )

    extract_payload = StateExtractPayload(
        content=payload.content,
        entity_ids=payload.entity_ids,
        root_id=payload.root_id,
        branch_id=payload.branch_id,
    )
    proposals = await gateway.state_extract(extract_payload)
    if not proposals:
        raise HTTPException(status_code=400, detail="state_extract returned empty proposals.")
    try:
        proposals = _enrich_state_proposals(
            storage=storage,
            root_id=payload.root_id,
            branch_id=payload.branch_id,
            proposals=proposals,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        updated_entities: list[dict[str, Any]] = []
        if payload.confirmed_proposals:
            extracted_entity_ids = {proposal.entity_id for proposal in proposals}
            for confirmed in payload.confirmed_proposals:
                if confirmed.entity_id not in extracted_entity_ids:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "confirmed_proposals entity_id not found in extracted proposals: "
                            f"{confirmed.entity_id}"
                        ),
                    )
            updated_entities = _apply_state_proposals(
                storage=storage,
                root_id=payload.root_id,
                branch_id=payload.branch_id,
                proposals=payload.confirmed_proposals,
            )
        storage.complete_scene(
            scene_id=scene_id,
            branch_id=payload.branch_id,
            actual_outcome=payload.actual_outcome,
            summary=payload.summary,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SceneCompletionResult(
        ok=True,
        scene_id=scene_id,
        root_id=payload.root_id,
        branch_id=payload.branch_id,
        status="committed",
        actual_outcome=payload.actual_outcome,
        summary=payload.summary,
        logic_check=logic_result,
        extracted_proposals=proposals,
        confirmed_count=len(payload.confirmed_proposals),
        applied=len(updated_entities),
        updated_entities=updated_entities,
    )


@app.post("/api/v1/scenes/{scene_id}/dirty")
async def mark_scene_dirty_endpoint(  # pragma: no cover
    scene_id: str,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, Any]:
    try:
        storage.mark_scene_dirty(scene_id=scene_id, branch_id=branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "scene_id": scene_id, "branch_id": branch_id}


@app.get("/api/v1/roots/{root_id}/dirty_scenes", response_model=List[str])
async def list_dirty_scenes_endpoint(  # pragma: no cover
    root_id: str,
    branch_id: str = Query(..., min_length=1),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> List[str]:
    return storage.list_dirty_scenes(root_id=root_id, branch_id=branch_id)


@app.post("/api/v1/llm/topone/generate")
async def generate_topone_content(  # pragma: no cover
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


@app.post("/api/v1/logic/check", response_model=LogicCheckResult)
async def logic_check_endpoint(  # pragma: no cover
    payload: LogicCheckPayload,
    gateway: ToponeGateway = Depends(get_topone_gateway),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> LogicCheckResult:
    mode = payload.mode.strip().lower()
    if mode not in {"force_execute", "standard"}:
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {payload.mode!r}")

    has_locator = any(
        value is not None for value in (payload.root_id, payload.branch_id, payload.scene_id)
    )
    if has_locator and not all(
        value is not None for value in (payload.root_id, payload.branch_id, payload.scene_id)
    ):
        raise HTTPException(
            status_code=400,
            detail="root_id/branch_id/scene_id must be all provided or all omitted.",
        )

    if _require_snowflake_engine_mode() != "gemini":
        raise HTTPException(
            status_code=400,
            detail="logic_check 仅支持 gemini 模式，请设置 SNOWFLAKE_ENGINE=gemini。",
        )

    world_state = payload.world_state
    if payload.root_id is not None:
        try:
            world_state = storage.build_logic_check_world_state(
                root_id=payload.root_id,
                branch_id=payload.branch_id,
                scene_id=payload.scene_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if mode == "force_execute" and payload.root_id is not None:
        reason = payload.force_reason or payload.user_intent
        try:
            storage.mark_scene_logic_exception(
                root_id=payload.root_id,
                branch_id=payload.branch_id,
                scene_id=payload.scene_id,
                reason=reason,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    normalized_payload = payload.model_copy(update={"mode": mode, "world_state": world_state})
    logic_result = await gateway.logic_check(normalized_payload)
    if payload.root_id is None or not logic_result.ok or mode == "force_execute":
        return logic_result
    try:
        if storage.is_scene_logic_exception(
            root_id=payload.root_id,
            branch_id=payload.branch_id,
            scene_id=payload.scene_id,
        ):
            return logic_result
        _apply_impact_level(
            storage=storage,
            root_id=payload.root_id,
            branch_id=payload.branch_id,
            scene_id=payload.scene_id,
            impact_level=logic_result.impact_level,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return logic_result


@app.post(
    "/api/v1/state/extract",
    response_model=List[StateProposal],
    response_model_exclude_none=True,
)
async def state_extract_endpoint(  # pragma: no cover
    payload: StateExtractPayload,
    gateway: ToponeGateway = Depends(get_topone_gateway),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> List[StateProposal]:
    has_root = any(value is not None for value in (payload.root_id, payload.branch_id))
    if has_root and not all(value is not None for value in (payload.root_id, payload.branch_id)):
        raise HTTPException(
            status_code=400, detail="root_id/branch_id must be all provided or all omitted."
        )

    try:
        engine_mode = _require_snowflake_engine_mode()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if engine_mode == "gemini":
        proposals = await gateway.state_extract(payload)
    else:
        proposals = _local_state_extract(payload)

    if payload.root_id is None:
        return proposals

    try:
        return _enrich_state_proposals(
            storage=storage,
            root_id=payload.root_id,
            branch_id=payload.branch_id,
            proposals=proposals,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _local_state_extract(payload: StateExtractPayload) -> List[StateProposal]:  # pragma: no cover
    proposals: list[StateProposal] = []
    for entity_id in payload.entity_ids:
        proposals.append(
            StateProposal(entity_id=entity_id, confidence=0.1, semantic_states_patch={})
        )
    return proposals


def _enrich_state_proposals(  # pragma: no cover
    *,
    storage: GraphStoragePort,
    root_id: str,
    branch_id: str,
    proposals: List[StateProposal],
) -> List[StateProposal]:
    storage.require_root(root_id=root_id, branch_id=branch_id)
    enriched: list[StateProposal] = []
    for proposal in proposals:
        before = storage.get_entity_semantic_states(
            root_id=root_id,
            branch_id=branch_id,
            entity_id=proposal.entity_id,
        )
        after = before.copy()
        after.update(proposal.semantic_states_patch)
        enriched.append(
            proposal.model_copy(
                update={
                    "semantic_states_before": before,
                    "semantic_states_after": after,
                }
            )
        )
    return enriched


def _apply_state_proposals(  # pragma: no cover
    *,
    storage: GraphStoragePort,
    root_id: str,
    branch_id: str,
    proposals: List[StateProposal],
) -> list[dict[str, Any]]:
    if not proposals:
        raise ValueError("proposals must not be empty.")
    storage.require_root(root_id=root_id, branch_id=branch_id)
    updated_entities: list[dict[str, Any]] = []
    for proposal in proposals:
        updated = storage.apply_semantic_states_patch(
            root_id=root_id,
            branch_id=branch_id,
            entity_id=proposal.entity_id,
            patch=proposal.semantic_states_patch,
        )
        updated_entities.append({"entity_id": proposal.entity_id, "semantic_states": updated})
    return updated_entities


def _apply_impact_level(  # pragma: no cover
    *,
    storage: GraphStoragePort,
    root_id: str,
    branch_id: str,
    scene_id: str,
    impact_level: ImpactLevel,
) -> list[str]:
    if impact_level == ImpactLevel.NEGLIGIBLE:
        return []
    if impact_level == ImpactLevel.LOCAL:
        return storage.apply_local_scene_fix(
            root_id=root_id,
            branch_id=branch_id,
            scene_id=scene_id,
            limit=3,
        )
    if impact_level == ImpactLevel.CASCADING:
        return storage.mark_future_scenes_dirty(
            root_id=root_id,
            branch_id=branch_id,
            scene_id=scene_id,
        )
    raise ValueError(f"ImpactLevel {impact_level.value!r} is not supported in Phase1")


@app.post("/api/v1/state/commit")
async def state_commit_endpoint(  # pragma: no cover
    *,
    root_id: str = Query(..., min_length=1),
    branch_id: str = Query(..., min_length=1),
    proposals: List[StateProposal] = Body(...),
    storage: GraphStoragePort = Depends(get_graph_storage),
) -> dict[str, Any]:
    try:
        updated_entities = _apply_state_proposals(
            storage=storage,
            root_id=root_id,
            branch_id=branch_id,
            proposals=proposals,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "root_id": root_id,
        "branch_id": branch_id,
        "applied": len(updated_entities),
        "updated_entities": updated_entities,
    }
