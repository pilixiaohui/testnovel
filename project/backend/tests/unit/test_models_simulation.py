import pytest
from pydantic import ValidationError

from tests.unit import models_contract_helpers as helpers


def _agent_action():
    AgentAction = helpers.require_model("AgentAction")
    return AgentAction(
        agent_id="agent-1",
        internal_thought="think",
        action_type="attack",
        action_target="target",
        dialogue=None,
        action_description="desc",
    )


def _action_result():
    ActionResult = helpers.require_model("ActionResult")
    return ActionResult(
        action_id="action-1",
        agent_id="agent-1",
        success="success",
        reason="ok",
        actual_outcome="done",
    )


def _dm_arbitration():
    DMArbitration = helpers.require_model("DMArbitration")
    return DMArbitration(round_id="round-1", action_results=[_action_result()])


def test_simulation_round_result_accepts_nested_models():
    SimulationRoundResult = helpers.require_model("SimulationRoundResult")
    result = SimulationRoundResult(
        round_id="round-1",
        agent_actions=[_agent_action()],
        dm_arbitration=_dm_arbitration(),
        narrative_events=[],
        sensory_seeds=[],
        convergence_score=0.5,
        drama_score=0.6,
        info_gain=0.3,
        stagnation_count=0,
    )
    assert result.info_gain == 0.3


def test_replan_request_requires_failed_conditions():
    ReplanRequest = helpers.require_model("ReplanRequest")
    ReplanRequest(
        current_scene_id="scene-alpha",
        target_anchor_id="anchor-1",
        world_state_snapshot={"state": "ok"},
        failed_conditions=["cond"],
    )
    with pytest.raises(ValidationError):
        ReplanRequest(
            current_scene_id="scene-alpha",
            target_anchor_id="anchor-1",
            world_state_snapshot={"state": "ok"},
        )


def test_replan_result_requires_reason():
    ReplanResult = helpers.require_model("ReplanResult")
    ReplanResult(
        success=True,
        new_chapters=[],
        modified_anchor=None,
        reason="recoverable",
    )
    with pytest.raises(ValidationError):
        ReplanResult(
            success=False,
            new_chapters=[],
            modified_anchor=None,
        )
