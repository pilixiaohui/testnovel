
import pytest

from orchestrator.parsing import (
    ParsingRules,
    ReportRules,
    extract_report_blockers,
    extract_report_coverage_percent,
    extract_report_iteration,
    extract_report_verdict,
)


def test_extract_report_iteration_multiline() -> None:
    parsing_rules = ParsingRules(
        critical_fields={"iteration"},
        optional_fields={"verdict", "blockers"},
        use_defaults_on_failure=True,
    )
    report = "header line\niteration: 20\nnotes"
    assert extract_report_iteration(report_text=report, parsing_rules=parsing_rules) == 20


def test_extract_report_blockers_defaults_when_optional() -> None:
    parsing_rules = ParsingRules(
        critical_fields={"iteration"},
        optional_fields={"blockers"},
        use_defaults_on_failure=True,
    )
    report_rules = ReportRules(
        apply_to=set(),
        require_verdict=False,
        verdict_prefix="verdict:",
        verdict_allowed={"PASS"},
        blocker_prefix="blockers:",
        blocker_clear_value="none",
    )
    report = "iteration: 1\nverdict: PASS\n"
    assert (
        extract_report_blockers(
            report_text=report,
            report_rules=report_rules,
            parsing_rules=parsing_rules,
        )
        == []
    )


def test_extract_report_verdict_optional_invalid_returns_none() -> None:
    parsing_rules = ParsingRules(
        critical_fields={"iteration"},
        optional_fields={"verdict"},
        use_defaults_on_failure=True,
    )
    report_rules = ReportRules(
        apply_to=set(),
        require_verdict=True,
        verdict_prefix="verdict:",
        verdict_allowed={"PASS"},
        blocker_prefix="blockers:",
        blocker_clear_value="none",
    )
    report = "iteration: 1\nverdict: MAYBE\n"
    assert (
        extract_report_verdict(
            report_text=report,
            report_rules=report_rules,
            parsing_rules=parsing_rules,
        )
        is None
    )


def test_extract_report_verdict_required_missing_raises() -> None:
    parsing_rules = ParsingRules(
        critical_fields={"iteration"},
        optional_fields={"verdict"},
        use_defaults_on_failure=False,
    )
    report_rules = ReportRules(
        apply_to=set(),
        require_verdict=True,
        verdict_prefix="verdict:",
        verdict_allowed={"PASS"},
        blocker_prefix="blockers:",
        blocker_clear_value="none",
    )
    report = "iteration: 1\n"
    with pytest.raises(RuntimeError):
        extract_report_verdict(
            report_text=report,
            report_rules=report_rules,
            parsing_rules=parsing_rules,
        )


def test_extract_report_coverage_percent_multiline() -> None:
    report = "iteration: 1\ncoverage: 82.5%\n"
    assert extract_report_coverage_percent(report_text=report) == 82.5
