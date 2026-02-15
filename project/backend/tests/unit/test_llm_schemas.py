import pytest
from pydantic import ValidationError

from app.llm import schemas


def test_logic_check_payload_requires_non_empty_outline():
    with pytest.raises(ValidationError):
        schemas.LogicCheckPayload(
            outline_requirement="",
            world_state={},
            user_intent="intent",
            mode="standard",
        )


def test_state_extract_payload_requires_entity_ids():
    with pytest.raises(ValidationError):
        schemas.StateExtractPayload(content="text", entity_ids=[])


def test_scene_render_payload_defaults_world_state():
    payload = schemas.SceneRenderPayload(
        voice_dna="voice",
        conflict_type="internal",
        outline_requirement="outline",
        user_intent="intent",
        expected_outcome="outcome",
    )
    assert payload.world_state == {}



def test_topone_generate_payload_rejects_empty_message_fields():
    with pytest.raises(ValidationError):
        schemas.ToponeGeneratePayload(messages=[{"role": "", "text": "hi"}])

    with pytest.raises(ValidationError):
        schemas.ToponeGeneratePayload(messages=[{"role": "user", "text": ""}])


def test_topone_generate_payload_rejects_timeout_less_than_600_seconds():
    with pytest.raises(ValidationError):
        schemas.ToponeGeneratePayload(
            messages=[{"role": "user", "text": "hi"}],
            timeout=599.9,
        )


def test_topone_generate_payload_allows_optional_fields():
    payload = schemas.ToponeGeneratePayload(messages=[{"role": "user", "text": "hi"}])
    assert payload.model is None
    assert payload.system_instruction is None
    assert payload.generation_config is None
    assert payload.timeout is None


def test_topone_generate_payload_accepts_timeout_equal_to_600_seconds():
    payload = schemas.ToponeGeneratePayload(
        messages=[{"role": "user", "text": "hi"}],
        timeout=600,
    )
    assert payload.timeout == 600
