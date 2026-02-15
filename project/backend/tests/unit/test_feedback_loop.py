import pytest

from app.models import ActionResult, AgentAction, DMArbitration, SimulationRoundResult
from app.services.feedback_detector import FeedbackDetector


def _build_action_result() -> ActionResult:
    return ActionResult(
        action_id="act-1",
        agent_id="agent-1",
        success="success",
        reason="ok",
        actual_outcome="clear",
    )


def _build_dm_arbitration() -> DMArbitration:
    return DMArbitration(round_id="round-1", action_results=[_build_action_result()])


def _build_agent_action() -> AgentAction:
    return AgentAction(
        agent_id="agent-1",
        internal_thought="wait",
        action_type="wait",
        action_target="",
        dialogue=None,
        action_description="pause",
    )


def _build_round(stagnation_count: int, info_gain: float = 0.05) -> SimulationRoundResult:
    return SimulationRoundResult(
        round_id="round-1",
        agent_actions=[_build_agent_action()],
        dm_arbitration=_build_dm_arbitration(),
        narrative_events=[{"event": "beat"}],
        sensory_seeds=[{"type": "weather", "detail": "rain"}],
        convergence_score=0.1,
        drama_score=0.2,
        info_gain=info_gain,
        stagnation_count=stagnation_count,
    )


@pytest.mark.asyncio
async def test_detect_feedback_returns_report_on_stagnation():
    detector = FeedbackDetector()

    report = await detector.detect_feedback([_build_round(stagnation_count=3)])

    assert report is not None
    assert report.trigger == "stagnation"
    assert report.feedback["stagnation_count"] == 3
    assert report.feedback["info_gain"] == 0.05
    assert report.corrections[0]["action"] == "inject_incident"
    assert report.severity == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_process_feedback_appends_event_when_triggered():
    detector = FeedbackDetector()
    scene_context = {"scene_id": "scene-alpha", "events": [{"type": "beat"}]}

    report, updated_context = await detector.process_feedback(
        scene_context, [_build_round(stagnation_count=4)]
    )

    assert report is not None
    assert updated_context["events"][-1]["type"] == "feedback"
    assert updated_context["events"][-1]["action"] == "inject_incident"
    assert len(scene_context["events"]) == 1


@pytest.mark.asyncio
async def test_process_feedback_returns_none_when_no_trigger():
    detector = FeedbackDetector()
    scene_context = {"scene_id": "scene-alpha", "events": [{"type": "beat"}]}

    report, updated_context = await detector.process_feedback(
        scene_context, [_build_round(stagnation_count=1)]
    )

    assert report is None
    assert updated_context["events"] == scene_context["events"]
