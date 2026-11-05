from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from skill_eval.adapters.yaml_result import render_result, write_result
from skill_eval.application.report import Environment, Report, RunRecord
from skill_eval.domain.evaluation import evaluate
from skill_eval.domain.results import Diagnostics
from skill_eval.domain.verdicts import Verdict
from tests.support import example
from tests.support.paths import RESULT_EXAMPLE

RECORD = RunRecord(
    skill="mon-skill",
    skill_version="3f2a9c1",
    date=date(2026, 11, 5),
    environment=Environment(
        installed_skills=34,
        installed_skills_hash="9c04e2b",
        inspect_ai="0.3.287",
        inspect_swe="0.2.67",
    ),
    positive_started=(),
    negative_started=(),
    quality_succeeded=(),
)


def _example_report() -> Report:
    evaluation = evaluate(example.config(), example.observations(), example.previous_run())
    return Report(config=example.config(), record=RECORD, evaluation=evaluation)


def _load(text: str) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(text)
    return data


def test_reproduces_the_example_result_file() -> None:
    expected = _load(RESULT_EXAMPLE.read_text(encoding="utf-8"))
    assert _load(render_result(_example_report())) == expected


def test_keeps_the_explanations_for_readers() -> None:
    text = render_result(_example_report())
    assert text.startswith("# skill-eval-result.yaml\n")
    assert "  # No score is on the wrong side of its limit, but three ranges are too wide" in text
    assert "# 95 times out of 100. A wide range means too few test cases to be sure." in text
    assert '  skill_version: "3f2a9c1"' in text
    assert "  invocation_recall:             {minimum: 0.85, value: 0.900" in text
    assert "Here 0.611 at 5 uses, against 0.356 if failures were spread" in text
    assert "evenly over all cases: failures are concentrated." in text


def test_quotes_hashes_so_they_stay_text() -> None:
    report = replace(_example_report(), record=replace(RECORD, skill_version="0012345"))
    assert _load(render_result(report))["run"]["skill_version"] == "0012345"


def test_optional_parts_and_warnings() -> None:
    report = _example_report()
    quality = replace(report.evaluation.quality, without_skill=None, lift=None, judge=None)
    invocation = replace(report.evaluation.invocation, precision=None)
    empty = Diagnostics(
        invocation_unstable=(),
        invocation_started_by_mistake=(),
        quality_never_succeeds=(),
        quality_unstable=(),
    )
    gates = (replace(report.evaluation.gates[0], reason="only 5 cases kept aside, 15 needed"),)
    evaluation = replace(
        report.evaluation,
        quality=quality,
        invocation=invocation,
        comparison=None,
        diagnostics=empty,
        gates=gates + report.evaluation.gates[1:],
    )
    text = render_result(replace(report, evaluation=evaluation, warnings=("check this",)))
    data = _load(text)
    assert "without_skill" not in data["quality"]
    assert "judge_agreement" not in data["quality"]
    assert "compared_with_previous_version" not in data
    assert data["invocation"]["precision"] is None
    assert data["diagnostics"] == {}
    assert data["gates"]["invocation_recall"]["reason"] == "only 5 cases kept aside, 15 needed"
    assert "  # Warning: check this" in text


def test_summary_notes_follow_the_verdicts() -> None:
    report = _example_report()
    failed = replace(report.evaluation.gates[0], verdict=Verdict.FAILED)
    passed = tuple(replace(g, verdict=Verdict.PASSED) for g in report.evaluation.gates)
    single = (report.evaluation.gates[0], *passed[1:])
    texts = [
        render_result(replace(report, evaluation=replace(report.evaluation, gates=gates)))
        for gates in ((failed, *passed[1:]), passed, single)
    ]
    assert "At least one score is on the wrong side of its limit." in texts[0]
    assert "Every score is on the right side of its limit, range included." in texts[1]
    assert "but one range is too wide to conclude." in texts[2]


def test_write_result(tmp_path: Path) -> None:
    path = tmp_path / "result.yaml"
    write_result(_example_report(), path)
    assert path.read_text(encoding="utf-8") == render_result(_example_report())


def test_missing_judge_model_is_null() -> None:
    report = _example_report()
    config = replace(report.config, execution=replace(report.config.execution, judge_model=None))
    data = _load(render_result(replace(report, config=config)))
    assert data["run"]["settings"]["judge_model"] is None


def test_curve_note_when_failures_are_spread() -> None:
    report = _example_report()
    quality = replace(
        report.evaluation.quality,
        pass_hat_k=replace(report.evaluation.quality.pass_hat_k, value=0.30),
    )
    report = replace(report, evaluation=replace(report.evaluation, quality=quality))
    assert "evenly over all cases: failures are spread over many cases." in render_result(report)


class TestDisplayedSide:
    """Rounding never moves a figure to the other side of its limit."""

    def _gate_line(self, report: Report) -> dict[str, Any]:
        gates: dict[str, Any] = _load(render_result(report))["gates"]
        return gates

    def test_low_bound_just_below_a_minimum_keeps_a_third_decimal(self) -> None:
        report = _example_report()
        gate = report.evaluation.gates[0]
        estimate = replace(gate.estimate, interval=replace(gate.estimate.interval, low=0.8495))
        gates = (replace(gate, estimate=estimate), *report.evaluation.gates[1:])
        shown = self._gate_line(replace(report, evaluation=replace(report.evaluation, gates=gates)))
        # 0.8495 rounds to 0.85 at two and three decimals: four are needed.
        assert shown["invocation_recall"]["range"] == [0.8495, 0.99]
        assert shown["invocation_recall"]["verdict"] == "inconclusive"

    def test_falls_back_to_full_precision(self) -> None:
        report = _example_report()
        gate = report.evaluation.gates[0]
        estimate = replace(
            gate.estimate, interval=replace(gate.estimate.interval, low=0.8499999999)
        )
        gates = (replace(gate, estimate=estimate), *report.evaluation.gates[1:])
        shown = self._gate_line(replace(report, evaluation=replace(report.evaluation, gates=gates)))
        assert shown["invocation_recall"]["range"][0] == 0.8499999999

    def test_kappa_just_below_the_minimum(self) -> None:
        report = _example_report()
        assert report.evaluation.quality.judge is not None
        judge = replace(report.evaluation.quality.judge, kappa=0.5996, trusted=False)
        quality = replace(report.evaluation.quality, judge=judge)
        data = _load(
            render_result(replace(report, evaluation=replace(report.evaluation, quality=quality)))
        )
        assert data["quality"]["judge_agreement"]["kappa"] == 0.5996  # not 0.60


def test_comments_stay_on_one_line() -> None:
    text = render_result(replace(_example_report(), warnings=("first line\nsecond line",)))
    assert "  # Warning: first line second line\n" in text
    _load(text)


def test_curve_note_without_any_failure_or_success() -> None:
    report = _example_report()
    for successes, outcome in ((150, "No run failed"), (0, "No run succeeded")):
        quality = replace(report.evaluation.quality, successful_runs=successes)
        text = render_result(
            replace(report, evaluation=replace(report.evaluation, quality=quality))
        )
        assert f"uses in a row. {outcome}: nothing to locate." in text
