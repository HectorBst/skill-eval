from dataclasses import replace

import pytest

from skill_eval.adapters.yaml_input import load_config, load_record
from skill_eval.application.report import (
    Outcome,
    ReportError,
    build_report,
    outcome_of,
)
from skill_eval.domain.verdicts import Verdict
from tests.support.paths import CONFIG_EXAMPLE, RECORD_EXAMPLE, RECORD_PREVIOUS

CONFIG = load_config(CONFIG_EXAMPLE)
RECORD = load_record(RECORD_EXAMPLE)
PREVIOUS = load_record(RECORD_PREVIOUS)


def test_splits_by_name_and_evaluates() -> None:
    report = build_report(CONFIG, RECORD, PREVIOUS)
    invocation, quality = report.evaluation.invocation, report.evaluation.quality
    assert (invocation.positive_cases, invocation.negative_cases, quality.cases) == (20, 20, 15)
    assert (invocation.tuning.positive_cases, quality.tuning.cases) == (30, 23)
    assert report.evaluation.comparison is not None
    assert report.warnings == ()
    assert outcome_of(report) is Outcome.INCONCLUSIVE


def test_rejects_a_previous_record_of_another_skill() -> None:
    with pytest.raises(ReportError, match="about skill 'other', not 'mon-skill'"):
        build_report(CONFIG, RECORD, replace(PREVIOUS, skill="other"))


def test_warns_about_unfair_comparisons() -> None:
    previous = replace(
        PREVIOUS,
        skill_version=RECORD.skill_version,
        environment=replace(PREVIOUS.environment, installed_skills=12),
    )
    warnings = build_report(CONFIG, RECORD, previous).warnings
    assert warnings[0] == "The previous record has the same skill version 3f2a9c1."
    assert warnings[1].startswith("The previous record ran with other installed skills")


def test_warns_when_lift_is_asked_but_not_recorded() -> None:
    report = build_report(CONFIG, replace(RECORD, quality_without_skill=()))
    assert report.warnings == (
        "quality.measure_lift is set but the record holds no run without skill.",
    )


def test_outcome_follows_the_verdicts() -> None:
    report = build_report(CONFIG, RECORD)
    gates = report.evaluation.gates
    failed = replace(report.evaluation, gates=(replace(gates[0], verdict=Verdict.FAILED),))
    passed = replace(
        report.evaluation,
        summary=replace(report.evaluation.summary, releasable=True),
    )
    assert outcome_of(replace(report, evaluation=failed)) is Outcome.FAILED
    assert outcome_of(replace(report, evaluation=passed)) is Outcome.RELEASABLE


def test_warns_when_runs_differ_from_the_settings() -> None:
    short = tuple(
        replace(case, runs=6, successes=min(case.successes, 6))
        for case in RECORD.quality_succeeded[:7]
    )
    record = replace(RECORD, quality_succeeded=short + RECORD.quality_succeeded[7:])
    warnings = build_report(CONFIG, record).warnings
    assert warnings[0].startswith("7 cases did not run trials.quality_per_case (10) times: ")
    assert warnings[0].endswith(" and 2 more.")


def test_warns_about_partial_or_unknown_runs_without_skill() -> None:
    without = (
        *RECORD.quality_without_skill[1:],
        replace(RECORD.quality_without_skill[0], name="q-ghost"),
    )
    warnings = build_report(CONFIG, replace(RECORD, quality_without_skill=without)).warnings
    assert warnings[0].startswith("quality.without_skill covers 14 of 15 quality cases kept aside")
    assert warnings[1] == "quality.without_skill lists cases never run with the skill: q-ghost."


def test_ignores_runs_without_skill_when_lift_is_not_asked() -> None:
    config = replace(CONFIG, quality=replace(CONFIG.quality, measure_lift=False))
    report = build_report(config, RECORD)
    assert report.evaluation.quality.lift is None
    assert report.warnings == ("quality.without_skill is ignored: measure_lift is not set.",)
