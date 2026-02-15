import pytest
from pydantic import ValidationError

from tests.unit import models_contract_helpers as helpers


def _desire_kwargs(**overrides):
    data = {
        "id": "desire-1",
        "type": "short_term",
        "description": "desc",
        "priority": 5,
        "satisfaction_condition": "condition",
        "created_at_scene": 1,
    }
    data.update(overrides)
    return data


def _intention_kwargs(**overrides):
    data = {
        "id": "intention-1",
        "desire_id": "desire-1",
        "action_type": "attack",
        "target": "target",
        "expected_outcome": "outcome",
        "risk_assessment": 0.5,
    }
    data.update(overrides)
    return data


def test_desire_priority_bounds():
    Desire = helpers.require_model("Desire")
    Desire(**_desire_kwargs())
    with pytest.raises(ValidationError):
        Desire(**_desire_kwargs(priority=11))
    with pytest.raises(ValidationError):
        Desire(**_desire_kwargs(priority=0))


def test_desire_type_enum_and_default_expires():
    Desire = helpers.require_model("Desire")
    model = Desire(**_desire_kwargs())
    assert model.expires_at_scene is None
    with pytest.raises(ValidationError):
        Desire(**_desire_kwargs(type="invalid"))


def test_intention_action_type_enum_and_risk_bounds():
    Intention = helpers.require_model("Intention")
    Intention(**_intention_kwargs())
    with pytest.raises(ValidationError):
        Intention(**_intention_kwargs(action_type="sing"))
    with pytest.raises(ValidationError):
        Intention(**_intention_kwargs(risk_assessment=1.5))
    with pytest.raises(ValidationError):
        Intention(**_intention_kwargs(risk_assessment=-0.1))


def test_agent_action_dialogue_optional():
    AgentAction = helpers.require_model("AgentAction")
    action = AgentAction(
        agent_id="agent-1",
        internal_thought="think",
        action_type="attack",
        action_target="target",
        dialogue=None,
        action_description="desc",
    )
    assert action.dialogue is None
