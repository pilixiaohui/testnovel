import pytest
from pydantic import ValidationError

from tests.unit import models_contract_helpers as helpers


def _action_result_kwargs(**overrides):
    data = {
        "action_id": "action-1",
        "agent_id": "agent-1",
        "success": "success",
        "reason": "ok",
        "actual_outcome": "done",
    }
    data.update(overrides)
    return data


def test_action_result_success_enum():
    ActionResult = helpers.require_model("ActionResult")
    ActionResult(**_action_result_kwargs())
    with pytest.raises(ValidationError):
        ActionResult(**_action_result_kwargs(success="unknown"))


def test_dmarbitration_defaults_empty_lists():
    ActionResult = helpers.require_model("ActionResult")
    DMArbitration = helpers.require_model("DMArbitration")

    result = ActionResult(**_action_result_kwargs())
    arbitration = DMArbitration(round_id="round-1", action_results=[result])
    assert arbitration.conflicts_resolved == []
    assert arbitration.environment_changes == []


def test_convergence_check_distance_bounds_and_default_action():
    ConvergenceCheck = helpers.require_model("ConvergenceCheck")

    model = ConvergenceCheck(
        next_anchor_id="anchor-1",
        distance=0.2,
        convergence_needed=True,
    )
    assert model.suggested_action is None

    with pytest.raises(ValidationError):
        ConvergenceCheck(
            next_anchor_id="anchor-1",
            distance=1.1,
            convergence_needed=True,
        )
    with pytest.raises(ValidationError):
        ConvergenceCheck(
            next_anchor_id="anchor-1",
            distance=-0.1,
            convergence_needed=False,
        )
