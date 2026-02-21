from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import SCENE_MAX_COUNT, SCENE_MIN_COUNT
from app.constants import DEFAULT_BRANCH_ID
from app.logic.snowflake_manager import SnowflakeManager
from app.main import app
from app.models import (
    ActionResult,
    AgentAction,
    CharacterSheet,
    CharacterValidationResult,
    Chapter,
    DMArbitration,
    SceneNode,
    SimulationRoundResult,
    SnowflakeRoot,
)
from tests.shared_stubs import GraphStorageStub

WUXIA_IDEA = "江湖少年沈孤舟追查师门灭门真相，并在十章内完成复仇与自我救赎。"
CHAPTER_COUNT = 10
RENDERED_CHAPTER_CONTENT = "侠" * 2000


class WuxiaStoryEngine:
    async def generate_logline_options(self, raw_idea: str) -> list[str]:
        return [f"{raw_idea}·方向{idx}" for idx in range(1, 11)]

    async def generate_root_structure(self, idea: str) -> SnowflakeRoot:
        return SnowflakeRoot(
            logline=idea,
            three_disasters=["师门覆灭", "同盟背叛", "身份反转"],
            ending="主角放下仇恨，护住江湖平衡",
            theme="侠义高于私仇",
        )

    async def generate_characters(self, _root: SnowflakeRoot) -> list[CharacterSheet]:
        return [
            CharacterSheet(
                name="沈孤舟",
                ambition="查明灭门真相",
                conflict="复仇执念与侠义底线冲突",
                epiphany="真正的侠是止戈而非滥杀",
                voice_dna="冷静克制",
            ),
            CharacterSheet(
                name="林秋水",
                ambition="守护百姓与同门",
                conflict="家国责任与个人情感拉扯",
                epiphany="直面真实才能并肩作战",
                voice_dna="温柔坚韧",
            ),
            CharacterSheet(
                name="阎无夜",
                ambition="重建魔教秩序",
                conflict="控制欲与旧日情义冲突",
                epiphany="强权无法换来认同",
                voice_dna="锋利凌厉",
            ),
        ]

    async def validate_characters(
        self,
        _root: SnowflakeRoot,
        _characters: list[CharacterSheet],
    ) -> CharacterValidationResult:
        return CharacterValidationResult(valid=True, issues=[])

    async def generate_scene_list(
        self,
        _root: SnowflakeRoot,
        _characters: list[CharacterSheet],
    ) -> list[SceneNode]:
        return [
            SceneNode(
                branch_id=DEFAULT_BRANCH_ID,
                title=f"第{idx + 1}场：江湖风云",
                sequence_index=idx,
                parent_act_id=None,
                pov_character_id=None,
                expected_outcome=f"主线推进至节点{idx + 1}",
                conflict_type="external",
                actual_outcome="未决",
                is_dirty=False,
            )
            for idx in range(SCENE_MIN_COUNT)
        ]

    async def generate_act_list(
        self,
        _root: SnowflakeRoot,
        _characters: list[CharacterSheet],
    ) -> list[dict[str, Any]]:
        return [
            {
                "title": "第一幕：血债初启",
                "purpose": "确立复仇动机与江湖格局",
                "tone": "压抑紧绷",
            },
            {
                "title": "第二幕：问剑终局",
                "purpose": "揭示真相并完成价值抉择",
                "tone": "悲壮克制",
            },
        ]

    async def generate_chapter_list(
        self,
        _root: SnowflakeRoot,
        act: dict[str, Any],
        _characters: list[CharacterSheet],
    ) -> list[dict[str, Any]]:
        start = 1 if int(act.get("sequence", 1)) == 1 else 6
        return [
            {
                "title": f"第{idx}章：刀光入梦",
                "focus": f"围绕关键冲突推进第{idx}章",
                "pov_character_id": None,
            }
            for idx in range(start, start + 5)
        ]

    async def generate_story_anchors(
        self,
        _root: SnowflakeRoot,
        _characters: list[CharacterSheet],
        _acts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "anchor_type": "inciting_incident" if idx == 0 else f"anchor_{idx + 1}",
                "description": f"第{idx + 1}个关键剧情锚点",
                "constraint_type": "hard" if idx % 2 == 0 else "soft",
                "required_conditions": [f"cond_{idx + 1}"],
            }
            for idx in range(CHAPTER_COUNT)
        ]


class WuxiaRenderGateway:
    async def render_scene(self, _payload):
        return RENDERED_CHAPTER_CONTENT


class ShortRenderGateway:
    async def render_scene(self, _payload):
        return "侠" * 1700


class WuxiaCharacterAgentEngine:
    async def decide(self, agent_id: str, _scene_context: dict[str, Any]) -> AgentAction:
        return AgentAction(
            agent_id=agent_id,
            internal_thought="先探再攻",
            action_type="investigate",
            action_target="黑水帮据点",
            dialogue="今夜先摸清敌情。",
            action_description="潜入据点侦查线索",
        )


class WuxiaWorldMasterEngine:
    async def arbitrate(
        self,
        round_id: str,
        actions: list[dict[str, Any]],
        _world_state: dict[str, Any],
        _narrative_events: list[dict[str, Any]],
    ) -> DMArbitration:
        agent_id = "agent-1"
        if actions and isinstance(actions[0], dict):
            agent_id = str(actions[0].get("agent_id", "agent-1"))
        return DMArbitration(
            round_id=round_id,
            action_results=[
                ActionResult(
                    action_id="action-1",
                    agent_id=agent_id,
                    success="success",
                    reason="情报获取成功",
                    actual_outcome="获得敌方布防图",
                )
            ],
        )


class WuxiaSimulationEngine:
    class _CharacterEngine:
        async def decide(self, agent_id: str, _scene_context: dict[str, Any]) -> dict[str, Any]:
            return {
                "agent_id": agent_id,
                "internal_thought": "稳住局势",
                "action_type": "wait",
                "action_target": "",
                "dialogue": None,
                "action_description": "静观其变",
            }

    def __init__(self) -> None:
        self.character_engine = self._CharacterEngine()

    async def run_round(self, _scene_context, agents, config) -> SimulationRoundResult:
        agent_id = agents[0].agent_id if agents else "agent-1"
        return SimulationRoundResult(
            round_id=config.round_id,
            agent_actions=[
                AgentAction(
                    agent_id=agent_id,
                    internal_thought="借势破局",
                    action_type="negotiate",
                    action_target="中立门派",
                    dialogue="请借道相助。",
                    action_description="以利益换取支援",
                )
            ],
            dm_arbitration=DMArbitration(
                round_id=config.round_id,
                action_results=[
                    ActionResult(
                        action_id="round-action-1",
                        agent_id=agent_id,
                        success="success",
                        reason="盟约达成",
                        actual_outcome="获得临时援军",
                    )
                ],
            ),
            narrative_events=[{"event": "雨夜结盟"}],
            sensory_seeds=[{"type": "weather", "detail": "夜雨"}],
            convergence_score=0.72,
            drama_score=0.81,
            info_gain=0.65,
            stagnation_count=0,
        )

    async def run_scene(self, _scene_context, _config) -> str:
        return "江湖夜雨中，众人终在破庙结盟，剑指幕后真凶。"


class WuxiaGraphStorageStub(GraphStorageStub):
    def __init__(self) -> None:
        super().__init__()
        self.root_counter = 0
        self.root_ids: set[str] = set()
        self.entities_by_root: dict[str, list[dict[str, Any]]] = {}
        self.acts: dict[str, dict[str, Any]] = {}
        self.acts_by_root: dict[str, list[str]] = {}
        self.chapters: dict[str, Chapter] = {}
        self.chapters_by_act: dict[str, list[str]] = {}
        self.anchors: dict[str, dict[str, Any]] = {}
        self.anchors_by_root_branch: dict[tuple[str, str], list[str]] = {}
        self.subplots: dict[str, Any] = {}
        self.subplots_by_root_branch: dict[tuple[str, str], list[str]] = {}
        self.agents: dict[str, dict[str, Any]] = {}

    def save_snowflake(self, root, characters, scenes) -> str:
        _ = (root, scenes)
        self.root_counter += 1
        root_id = f"root-{self.root_counter}"
        self.root_ids.add(root_id)
        self.entities_by_root[root_id] = [
            {
                "entity_id": str(character.entity_id),
                "name": character.name,
                "entity_type": "character",
                "tags": ["character"],
                "arc_status": "active",
                "semantic_states": {},
            }
            for character in characters
        ]
        return root_id

    def list_entities(self, *, root_id: str, branch_id: str) -> list[dict[str, Any]]:
        _ = branch_id
        if root_id not in self.root_ids:
            raise KeyError(f"root not found: {root_id}")
        return list(self.entities_by_root.get(root_id, []))

    def create_act(self, *, root_id: str, seq: int, title: str, purpose: str, tone: str):
        if root_id not in self.root_ids:
            raise KeyError(f"root not found: {root_id}")
        act_id = f"{root_id}:act:{seq}"
        act = {
            "id": act_id,
            "root_id": root_id,
            "sequence": seq,
            "title": title,
            "purpose": purpose,
            "tone": tone,
        }
        self.acts[act_id] = act
        self.acts_by_root.setdefault(root_id, []).append(act_id)
        return dict(act)

    def list_acts(self, *, root_id: str):
        act_ids = self.acts_by_root.get(root_id, [])
        acts = [self.acts[act_id] for act_id in act_ids]
        return sorted(acts, key=lambda item: int(item["sequence"]))

    def create_chapter(self, *, act_id: str, seq: int, title: str, focus: str, pov_character_id=None):
        chapter_id = f"{act_id}:chapter:{seq}"
        chapter = Chapter(
            id=chapter_id,
            act_id=act_id,
            sequence=seq,
            title=title,
            focus=focus,
            pov_character_id=pov_character_id,
        )
        self.chapters[chapter_id] = chapter
        self.chapters_by_act.setdefault(act_id, []).append(chapter_id)
        return self._chapter_to_dict(chapter)

    def get_chapter(self, chapter_id: str) -> Chapter | None:
        return self.chapters.get(chapter_id)

    def update_chapter(self, chapter: Chapter) -> Chapter:
        self.chapters[chapter.id] = chapter
        return chapter

    def list_chapters(self, *, act_id: str) -> list[dict[str, Any]]:
        chapter_ids = self.chapters_by_act.get(act_id, [])
        return [self._chapter_to_dict(self.chapters[chapter_id]) for chapter_id in chapter_ids]

    def create_anchor(
        self,
        *,
        root_id: str,
        branch_id: str,
        seq: int,
        type: str,
        desc: str,
        constraint: str,
        conditions: str,
    ) -> dict[str, Any]:
        anchor_id = f"{root_id}:anchor:{seq}"
        anchor = {
            "id": anchor_id,
            "root_id": root_id,
            "branch_id": branch_id,
            "sequence": seq,
            "anchor_type": type,
            "description": desc,
            "constraint_type": constraint,
            "required_conditions": conditions,
            "deadline_scene": None,
            "achieved": False,
        }
        self.anchors[anchor_id] = anchor
        self.anchors_by_root_branch.setdefault((root_id, branch_id), []).append(anchor_id)
        return dict(anchor)

    def list_anchors(self, *, root_id: str, branch_id: str) -> list[dict[str, Any]]:
        anchor_ids = self.anchors_by_root_branch.get((root_id, branch_id), [])
        anchors = [self.anchors[anchor_id] for anchor_id in anchor_ids]
        return sorted(anchors, key=lambda item: int(item["sequence"]))

    def create_subplot(self, subplot):
        self.subplots[subplot.id] = subplot
        self.subplots_by_root_branch.setdefault((subplot.root_id, subplot.branch_id), []).append(
            subplot.id
        )
        return subplot

    def list_subplots(self, *, root_id: str, branch_id: str) -> list[dict[str, Any]]:
        subplot_ids = self.subplots_by_root_branch.get((root_id, branch_id), [])
        return [
            {
                "id": self.subplots[subplot_id].id,
                "root_id": self.subplots[subplot_id].root_id,
                "branch_id": self.subplots[subplot_id].branch_id,
                "title": self.subplots[subplot_id].title,
                "subplot_type": self.subplots[subplot_id].subplot_type,
                "protagonist_id": self.subplots[subplot_id].protagonist_id,
                "central_conflict": self.subplots[subplot_id].central_conflict,
                "status": self.subplots[subplot_id].status,
            }
            for subplot_id in subplot_ids
        ]

    def init_character_agent(self, *, char_id: str, branch_id: str, initial_desires: list[dict[str, Any]]) -> dict[str, Any]:
        agent_id = f"agent:{char_id}:{branch_id}"
        if agent_id not in self.agents:
            self.agents[agent_id] = {
                "id": agent_id,
                "character_id": char_id,
                "branch_id": branch_id,
                "beliefs": {},
                "desires": list(initial_desires),
                "intentions": [],
                "memory": [],
                "private_knowledge": {},
                "last_updated_scene": 0,
                "version": 1,
            }
        return dict(self.agents[agent_id])

    @staticmethod
    def _chapter_to_dict(chapter: Chapter) -> dict[str, Any]:
        review_status = chapter.review_status.value if hasattr(chapter.review_status, "value") else chapter.review_status
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


@pytest.fixture()
def api(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ENGINE", "local")
    storage = WuxiaGraphStorageStub()
    story_engine = WuxiaStoryEngine()
    manager = SnowflakeManager(
        engine=story_engine,
        storage=storage,
        min_scenes=SCENE_MIN_COUNT,
        max_scenes=SCENE_MAX_COUNT,
    )

    app.dependency_overrides = {}
    app.dependency_overrides[main.get_graph_storage] = lambda: storage
    app.dependency_overrides[main.get_llm_engine] = lambda: story_engine
    app.dependency_overrides[main.get_snowflake_manager] = lambda: manager
    app.dependency_overrides[main.get_topone_gateway] = lambda: WuxiaRenderGateway()
    app.dependency_overrides[main.get_character_agent_engine] = lambda: WuxiaCharacterAgentEngine()
    app.dependency_overrides[main.get_world_master_engine] = lambda: WuxiaWorldMasterEngine()
    app.dependency_overrides[main.get_simulation_engine] = lambda: WuxiaSimulationEngine()

    with TestClient(app) as test_client:
        yield test_client, storage, story_engine

    app.dependency_overrides = {}


def _run_snowflake_steps(client: TestClient) -> dict[str, Any]:
    step1_response = client.post("/api/v1/snowflake/step1", json={"idea": WUXIA_IDEA})
    assert step1_response.status_code == 200
    loglines = step1_response.json()
    assert len(loglines) == 10

    step2_response = client.post("/api/v1/snowflake/step2", json={"logline": loglines[0]})
    assert step2_response.status_code == 200
    root = step2_response.json()

    step3_response = client.post("/api/v1/snowflake/step3", json=root)
    assert step3_response.status_code == 200
    characters = step3_response.json()

    step4_response = client.post("/api/v1/snowflake/step4", json={"root": root, "characters": characters})
    assert step4_response.status_code == 200
    step4_result = step4_response.json()
    assert step4_result["branch_id"] == DEFAULT_BRANCH_ID
    assert len(step4_result["scenes"]) == SCENE_MIN_COUNT

    step5_payload = {"root_id": step4_result["root_id"], "root": root, "characters": characters}
    step5a_response = client.post("/api/v1/snowflake/step5a", json=step5_payload)
    assert step5a_response.status_code == 200
    acts = step5a_response.json()
    assert len(acts) == 2

    step5b_response = client.post("/api/v1/snowflake/step5b", json=step5_payload)
    assert step5b_response.status_code == 200
    chapters = step5b_response.json()
    assert len(chapters) == CHAPTER_COUNT

    return {
        "loglines": loglines,
        "root": root,
        "characters": characters,
        "root_id": step4_result["root_id"],
        "branch_id": step4_result["branch_id"],
        "chapters": chapters,
        "step5_payload": step5_payload,
    }


def test_wuxia_ten_chapter_e2e_flow(api):
    client, storage, _story_engine = api
    flow = _run_snowflake_steps(client)

    repeat_step1_before = len(storage.root_ids)
    repeat_step1_response = client.post("/api/v1/snowflake/step1", json={"idea": WUXIA_IDEA})
    assert repeat_step1_response.status_code == 200
    assert repeat_step1_response.json() == flow["loglines"]
    assert len(storage.root_ids) == repeat_step1_before

    entities_response = client.get(
        f"/api/v1/roots/{flow['root_id']}/entities",
        params={"branch_id": flow["branch_id"]},
    )
    assert entities_response.status_code == 200
    entities = entities_response.json()
    protagonist_id = entities[0]["entity_id"]

    anchors_response = client.post(
        f"/api/v1/roots/{flow['root_id']}/anchors",
        json={"branch_id": flow["branch_id"], "root": flow["root"], "characters": flow["characters"]},
    )
    assert anchors_response.status_code == 200
    assert len(anchors_response.json()) == CHAPTER_COUNT

    subplot_response = client.post(
        f"/api/v1/roots/{flow['root_id']}/subplots",
        json={
            "branch_id": flow["branch_id"],
            "title": "暗线：魔教旧怨",
            "subplot_type": "revenge",
            "protagonist_id": protagonist_id,
            "central_conflict": "主角必须在复仇和守护百姓之间做选择",
        },
    )
    assert subplot_response.status_code == 200
    assert subplot_response.json()["status"] == "dormant"

    acts_response = client.get(f"/api/v1/roots/{flow['root_id']}/acts")
    assert acts_response.status_code == 200
    chapters_from_world: list[dict[str, Any]] = []
    for act in acts_response.json():
        chapters_response = client.get(f"/api/v1/acts/{act['id']}/chapters")
        assert chapters_response.status_code == 200
        chapters_from_world.extend(chapters_response.json())
    assert len(chapters_from_world) == CHAPTER_COUNT

    for chapter in chapters_from_world:
        render_response = client.post(f"/api/v1/chapters/{chapter['id']}/render", json={})
        assert render_response.status_code == 200
        assert 1800 <= len(render_response.json()["rendered_content"]) <= 2200
        review_response = client.post(
            f"/api/v1/chapters/{chapter['id']}/review",
            json={"status": "approved"},
        )
        assert review_response.status_code == 200

    idempotent_review = client.post(
        f"/api/v1/chapters/{chapters_from_world[0]['id']}/review",
        json={"status": "approved"},
    )
    assert idempotent_review.status_code == 200

    agent_init_payload = {
        "branch_id": flow["branch_id"],
        "initial_desires": [{"goal": "为师门雪耻", "priority": "high"}],
    }
    init_response = client.post(f"/api/v1/entities/{protagonist_id}/agent/init", json=agent_init_payload)
    assert init_response.status_code == 200
    init_again_response = client.post(f"/api/v1/entities/{protagonist_id}/agent/init", json=agent_init_payload)
    assert init_again_response.status_code == 200
    assert len(storage.agents) == 1

    decide_response = client.post(
        f"/api/v1/entities/{protagonist_id}/agent/decide",
        json={"scene_context": {"scene_id": "scene-1", "world_state": {"enemy": "魔教"}}},
    )
    assert decide_response.status_code == 200
    action = decide_response.json()

    arbitrate_response = client.post(
        "/api/v1/dm/arbitrate",
        json={"round_id": "round-1", "actions": [action], "world_state": {"enemy": "魔教"}},
    )
    assert arbitrate_response.status_code == 200

    round_response = client.post(
        "/api/v1/simulation/round",
        json={
            "scene_context": {"scene_id": "scene-1"},
            "agents": [{"agent_id": protagonist_id}],
            "round_id": "round-1",
        },
    )
    assert round_response.status_code == 200

    scene_response = client.post(
        "/api/v1/simulation/scene",
        json={"scene_context": {"scene_id": "scene-1", "world_state": {"enemy": "魔教"}}, "max_rounds": 2},
    )
    assert scene_response.status_code == 200
    assert "江湖" in scene_response.json()["content"]


def test_wuxia_major_endpoint_error_paths(api):
    client, _storage, story_engine = api
    flow = _run_snowflake_steps(client)

    assert client.post("/api/v1/snowflake/step1", json={}).status_code == 422
    assert client.post("/api/v1/snowflake/step2", json={}).status_code == 422
    assert client.post(
        "/api/v1/snowflake/step3",
        json={
            "logline": "无效根",
            "three_disasters": ["只给两个", "会触发422"],
            "ending": "结局",
            "theme": "主题",
        },
    ).status_code == 422
    assert client.post("/api/v1/snowflake/step4", json={"root": flow["root"]}).status_code == 422

    original_generate_act_list = story_engine.generate_act_list

    async def invalid_generate_act_list(
        _root: SnowflakeRoot,
        _characters: list[CharacterSheet],
    ) -> list[dict[str, Any]]:
        return [{"title": "缺字段的幕"}]

    story_engine.generate_act_list = invalid_generate_act_list
    assert client.post("/api/v1/snowflake/step5a", json=flow["step5_payload"]).status_code == 400
    story_engine.generate_act_list = original_generate_act_list

    original_generate_chapter_list = story_engine.generate_chapter_list

    async def invalid_generate_chapter_list(
        _root: SnowflakeRoot,
        _act: dict[str, Any],
        _characters: list[CharacterSheet],
    ) -> list[dict[str, Any]]:
        return [{"title": f"短章{idx}", "focus": "不足", "pov_character_id": None} for idx in range(4)]

    story_engine.generate_chapter_list = invalid_generate_chapter_list
    assert client.post("/api/v1/snowflake/step5b", json=flow["step5_payload"]).status_code == 422
    story_engine.generate_chapter_list = original_generate_chapter_list

    original_generate_story_anchors = story_engine.generate_story_anchors

    async def invalid_generate_story_anchors(
        _root: SnowflakeRoot,
        _characters: list[CharacterSheet],
        _acts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "anchor_type": f"anchor_{idx + 1}",
                "description": f"过少锚点{idx + 1}",
                "constraint_type": "hard",
                "required_conditions": [f"cond_{idx + 1}"],
            }
            for idx in range(9)
        ]

    story_engine.generate_story_anchors = invalid_generate_story_anchors
    assert client.post(
        f"/api/v1/roots/{flow['root_id']}/anchors",
        json={"branch_id": flow["branch_id"], "root": flow["root"], "characters": flow["characters"]},
    ).status_code == 400
    story_engine.generate_story_anchors = original_generate_story_anchors

    assert client.post(
        f"/api/v1/roots/{flow['root_id']}/subplots",
        json={
            "branch_id": flow["branch_id"],
            "subplot_type": "revenge",
            "protagonist_id": flow["characters"][0]["entity_id"],
            "central_conflict": "缺失标题会报错",
        },
    ).status_code == 422

    app.dependency_overrides[main.get_topone_gateway] = lambda: ShortRenderGateway()
    assert client.post(f"/api/v1/chapters/{flow['chapters'][0]['id']}/render", json={}).status_code == 400
    app.dependency_overrides[main.get_topone_gateway] = lambda: WuxiaRenderGateway()

    assert client.post(
        f"/api/v1/chapters/{flow['chapters'][0]['id']}/review",
        json={"status": "unknown"},
    ).status_code == 400
    assert client.post(
        f"/api/v1/entities/{flow['characters'][0]['entity_id']}/agent/init",
        json={"initial_desires": []},
    ).status_code == 422
    assert client.post(
        f"/api/v1/entities/{flow['characters'][0]['entity_id']}/agent/decide",
        json={},
    ).status_code == 422
    assert client.post(
        "/api/v1/dm/arbitrate",
        json={"round_id": "", "actions": [], "world_state": {}},
    ).status_code == 422
    assert client.post(
        "/api/v1/simulation/round",
        json={
            "scene_context": {"scene_id": "scene-error"},
            "agents": [{"name": "缺少agent_id"}],
            "round_id": "round-error",
        },
    ).status_code == 422
    assert client.post(
        "/api/v1/simulation/scene",
        json={"scene_context": {"scene_id": "scene-error"}, "max_rounds": 0},
    ).status_code == 422
