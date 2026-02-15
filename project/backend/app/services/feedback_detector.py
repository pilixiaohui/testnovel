"""Feedback detector for recursive feedback loops."""

from __future__ import annotations

from typing import Sequence

from app.models import FeedbackReport, SimulationRoundResult


class FeedbackDetector:
    """递归反馈检测与修正处理。"""

    async def detect_feedback(
        self, rounds: Sequence[SimulationRoundResult]
    ) -> FeedbackReport | None:
        latest = rounds[-1]
        if latest.stagnation_count >= 3:
            severity = min(1.0, 0.5 + 0.1 * latest.stagnation_count)
            return FeedbackReport(
                trigger="stagnation",
                feedback={
                    "info_gain": latest.info_gain,
                    "stagnation_count": latest.stagnation_count,
                },
                corrections=[{"action": "inject_incident"}],
                severity=severity,
            )
        if latest.stagnation_count > 0:
            return None
        if latest.convergence_score <= 0.2:
            severity = min(1.0, 0.7 + (0.2 - latest.convergence_score) * 1.5)
            return FeedbackReport(
                trigger="divergence",
                feedback={
                    "convergence_score": latest.convergence_score,
                    "drama_score": latest.drama_score,
                },
                corrections=[{"action": "recenter_objective"}],
                severity=severity,
            )
        if latest.info_gain <= 0.05 and latest.drama_score <= 0.2:
            severity = min(1.0, 0.4 + (0.05 - latest.info_gain) * 6)
            return FeedbackReport(
                trigger="repetition",
                feedback={
                    "info_gain": latest.info_gain,
                    "drama_score": latest.drama_score,
                },
                corrections=[{"action": "introduce_twist"}],
                severity=severity,
            )
        return None

    async def process_feedback(
        self,
        scene_context: dict[str, object],
        rounds: Sequence[SimulationRoundResult],
    ) -> tuple[FeedbackReport | None, dict[str, object]]:
        report = await self.detect_feedback(rounds)
        updated_context = dict(scene_context)
        if report is None:
            return None, updated_context
        events = list(updated_context["events"])
        for correction in report.corrections:
            action = correction.action
            events.append({"type": "feedback", "action": action})
        updated_context["events"] = events
        return report, updated_context
