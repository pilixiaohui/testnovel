import json

import pytest

from app.llm.schemas import LogicCheckPayload, StateExtractPayload
from app.llm.topone_gateway import ToponeGateway


class QueueClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []
        self.default_model = "default-model"
        self.secondary_model = "secondary-model"

    async def generate_content(
        self,
        *,
        messages,
        system_instruction=None,
        generation_config=None,
        model=None,
    ):
        self.calls.append(
            {
                "messages": messages,
                "system_instruction": system_instruction,
                "generation_config": generation_config,
                "model": model,
            }
        )
        text = self._responses.pop(0)
        return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


@pytest.mark.asyncio
async def test_gateway_structured_outputs_cover_roles():
    responses = [
        json.dumps(["a", "b"]),
        json.dumps(
            {
                "logline": "L",
                "three_disasters": ["A", "B", "C"],
                "ending": "E",
                "theme": "T",
            }
        ),
        json.dumps(
            [
                {
                    "name": "Hero",
                    "ambition": "A",
                    "conflict": "C",
                    "epiphany": "E",
                    "voice_dna": "V",
                }
            ]
        ),
        json.dumps({"valid": True, "issues": []}),
        json.dumps(
            [
                {
                    "branch_id": "main",
                    "title": "Scene 1",
                    "sequence_index": 0,
                    "expected_outcome": "O",
                    "conflict_type": "internal",
                    "actual_outcome": "",
                    "parent_act_id": None,
                    "logic_exception": False,
                    "is_dirty": False,
                }
            ]
        ),
        json.dumps(
            {
                "ok": True,
                "mode": "standard",
                "decision": "execute",
                "impact_level": "local",
                "warnings": [],
            }
        ),
        json.dumps(
            [
                {
                    "entity_id": "entity-1",
                    "confidence": 0.9,
                    "semantic_states_patch": {"hp": "100"},
                }
            ]
        ),
    ]
    client = QueueClient(responses)
    gateway = ToponeGateway(client)

    loglines = await gateway.generate_logline_options("idea")
    assert loglines == ["a", "b"]

    root = await gateway.generate_root_structure("idea")
    assert root.logline == "L"

    characters = await gateway.generate_characters(root)
    assert characters[0].name == "Hero"

    validation = await gateway.validate_characters(root, characters)
    assert validation.valid is True

    scenes = await gateway.generate_scene_list(root, characters)
    assert scenes[0].branch_id == "main"

    payload = LogicCheckPayload(
        outline_requirement="outline",
        world_state={},
        user_intent="intent",
        mode="standard",
    )
    result = await gateway.logic_check(payload)
    assert result.decision == "execute"

    state_payload = StateExtractPayload(content="text", entity_ids=["entity-1"])
    proposals = await gateway.state_extract(state_payload)
    assert proposals[0].entity_id == "entity-1"

    assert client.calls[0]["model"] == client.default_model
    assert client.calls[-1]["model"] == client.secondary_model

@pytest.mark.asyncio
async def test_gateway_structured_entity_resolution_uses_flash_model():
    responses = [json.dumps({"他": "e1"})]
    client = QueueClient(responses)
    gateway = ToponeGateway(client)

    payload = {
        "text": "他走进房间。",
        "known_entities": [
            {"id": "e1", "name": "John", "entity_type": "Character"}
        ],
    }

    result = await gateway.generate_structured(payload)

    assert result == {"他": "e1"}
    assert client.calls[-1]["model"] == client.secondary_model
    user_text = client.calls[-1]["messages"][0]["text"]
    assert json.loads(user_text) == payload


@pytest.mark.asyncio
async def test_gateway_accepts_json_fenced_output():
    responses = [
        """```json
{\"logline\":\"L\",\"three_disasters\":[\"A\",\"B\",\"C\"],\"ending\":\"E\",\"theme\":\"T\"}
```"""
    ]
    client = QueueClient(responses)
    gateway = ToponeGateway(client)

    root = await gateway.generate_root_structure("idea")

    assert root.logline == "L"
    assert root.three_disasters == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_gateway_invalid_json_raises_value_error():
    responses = ["not-a-json-payload"]
    client = QueueClient(responses)
    gateway = ToponeGateway(client)

    with pytest.raises(ValueError, match="invalid JSON"):
        await gateway.generate_root_structure("idea")