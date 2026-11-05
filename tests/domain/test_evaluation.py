from dataclasses import replace

import pytest

from skill_eval.domain.agreement import LabelledAnswer
from skill_eval.domain.comparison import Change
from skill_eval.domain.config import GateName
from skill_eval.domain.estimators import CaseCount
from skill_eval.domain.evaluation import (
    EvaluationError,
    Observations,
    PreviousRun,
    evaluate,
    summarize,
)
from skill_eval.domain.intervals import Estimate
from skill_eval.domain.results import Diagnostics, GateResult
from skill_eval.domain.split import Split
from skill_eval.domain.verdicts import Verdict
from tests.support import example


def _published(estimate: Estimate) -> tuple[float, float, float]:
    return (
        round(estimate.value, 3),
        round(estimate.interval.low, 2),
        round(estimate.interval.high, 2),
    )


def _cases(prefix: str, successes: list[int], runs: int = 10) -> tuple[CaseCount, ...]:
    return tuple(CaseCount(f"{prefix}-{i:02d}", runs, value) for i, value in enumerate(successes))


def _observations(
    positive: list[int], negative_started: list[int], quality: list[int]
) -> Observations:
    return Observations(
        positive=Split(_cases("pos", positive), ()),
        negative=Split(_cases("neg", [10 - started for started in negative_started]), ()),
        quality=Split(_cases("q", quality), ()),
    )


class TestExample:
    """The example result, figure by figure."""

    evaluation = evaluate(example.config(), example.observations(), example.previous_run())

    def test_summary(self) -> None:
        summary = self.evaluation.summary
        assert not summary.releasable
        assert summary.reason == "3 gates inconclusive"
        assert summary.next_step == (
            "Fix the cases listed under diagnostics, then add test cases kept aside and run again."
        )

    def test_invocation(self) -> None:
        invocation = self.evaluation.invocation
        assert (invocation.positive_cases, invocation.negative_cases) == (20, 20)
        assert (invocation.positive_runs, invocation.negative_runs) == (200, 200)
        assert (invocation.started_when_expected, invocation.missed) == (180, 20)
        assert invocation.started_by_mistake == 6
        assert _published(invocation.recall) == (0.900, 0.81, 0.99)
        assert _published(invocation.false_trigger_rate) == (0.030, 0.00, 0.06)
        assert invocation.precision is not None
        assert round(invocation.precision, 3) == 0.968
        assert _published(invocation.pass_hat_k) == (0.745, 0.56, 0.93)
        assert _published(invocation.pass_hat_k_negative) == (0.883, 0.75, 1.00)
        tuning = invocation.tuning
        assert (tuning.positive_cases, tuning.negative_cases) == (30, 30)
        assert tuning.recall is not None
        assert tuning.false_trigger_rate is not None
        assert (round(tuning.recall, 3), round(tuning.false_trigger_rate, 3)) == (0.947, 0.023)

    def test_quality(self) -> None:
        quality = self.evaluation.quality
        assert (quality.cases, quality.runs, quality.successful_runs) == (15, 150, 122)
        assert _published(quality.pass_at_1) == (0.813, 0.65, 0.98)
        assert _published(quality.pass_at_k) == (0.917, 0.77, 1.00)
        assert _published(quality.pass_hat_k) == (0.611, 0.36, 0.86)
        assert [round(v, 3) for v in quality.pass_hat_k_by_uses] == [
            0.813, 0.735, 0.681, 0.642, 0.611, 0.587, 0.567, 0.551, 0.540, 0.533,
        ]  # fmt: skip
        assert quality.without_skill is not None
        assert _published(quality.without_skill.pass_at_1) == (0.527, 0.40, 0.66)
        assert quality.without_skill.successful_runs == 79
        assert quality.lift is not None
        assert _published(quality.lift) == (0.287, 0.19, 0.38)
        assert quality.judge is not None
        assert quality.judge.kappa is not None
        assert (round(quality.judge.kappa, 2), quality.judge.labelled_answers) == (0.78, 24)
        assert quality.judge.trusted
        assert quality.tuning.cases == 23
        assert quality.tuning.pass_at_1 is not None
        assert round(quality.tuning.pass_at_1, 3) == 0.896

    def test_comparison(self) -> None:
        comparison = self.evaluation.comparison
        assert comparison is not None
        assert comparison.previous_version == "e81b4d0"
        assert _published(comparison.invocation_recall.difference) == (0.055, 0.01, 0.10)
        assert comparison.invocation_recall.change is Change.IMPROVED
        assert _published(comparison.quality_pass_at_1.difference) == (0.020, -0.02, 0.06)
        assert comparison.quality_pass_at_1.change is Change.NO_CLEAR_CHANGE

    def test_gates(self) -> None:
        verdicts = {gate.name: gate.verdict for gate in self.evaluation.gates}
        assert verdicts == {
            GateName.INVOCATION_RECALL: Verdict.INCONCLUSIVE,
            GateName.INVOCATION_FALSE_TRIGGER_RATE: Verdict.PASSED,
            GateName.INVOCATION_PASS_HAT_K: Verdict.PASSED,
            GateName.QUALITY_PASS_AT_1: Verdict.INCONCLUSIVE,
            GateName.QUALITY_PASS_HAT_K: Verdict.INCONCLUSIVE,
        }
        assert all(gate.reason is None for gate in self.evaluation.gates)

    def test_diagnostics(self) -> None:
        diagnostics = self.evaluation.diagnostics

        def shown(cases: tuple[CaseCount, ...]) -> dict[str, str]:
            return {case.name: f"{case.successes}/{case.runs}" for case in cases}

        assert shown(diagnostics.invocation_unstable) == {
            "pos-implicit-07": "5/10",
            "pos-english-12": "3/10",
        }
        assert shown(diagnostics.invocation_started_by_mistake) == {
            "neg-pdf-03": "2/10",
            "neg-email-08": "2/10",
            "neg-slack-15": "2/10",
        }
        assert shown(diagnostics.quality_never_succeeds) == {"q-incomplete-input-04": "0/10"}
        assert shown(diagnostics.quality_unstable) == {
            "q-long-doc-09": "5/10",
            "q-multi-source-11": "4/10",
        }

    def test_no_comparison_without_previous_run(self) -> None:
        assert evaluate(example.config(), example.observations()).comparison is None


class TestGuards:
    def test_too_few_cases_kept_aside_forces_inconclusive(self) -> None:
        observations = _observations([10] * 5, [0] * 20, [10] * 20)
        recall = evaluate(example.config(), observations).gates[0]
        assert recall.verdict is Verdict.INCONCLUSIVE
        assert recall.reason == "only 5 cases kept aside, 15 needed"

    def test_untrusted_judge_forces_quality_gates_inconclusive(self) -> None:
        disagreeing = (LabelledAnswer(judge_passed=True, person_passed=False),) * 3 + (
            LabelledAnswer(judge_passed=False, person_passed=True),
        ) * 3
        observations = replace(
            _observations([10] * 20, [0] * 20, [10] * 20), judge_answers=disagreeing
        )
        evaluation = evaluate(example.config(), observations)
        quality_gates = [gate for gate in evaluation.gates if gate.name.startswith("quality")]
        assert {gate.verdict for gate in quality_gates} == {Verdict.INCONCLUSIVE}
        assert quality_gates[0].reason == (
            "the judge agrees too little with people (kappa -1.000 < 0.6)"
        )
        assert evaluation.quality.judge is not None
        assert not evaluation.quality.judge.trusted

    def test_missing_calibration_answers_mean_untrusted_judge(self) -> None:
        evaluation = evaluate(example.config(), _observations([10] * 20, [0] * 20, [10] * 20))
        assert evaluation.quality.judge is not None
        assert evaluation.quality.judge.kappa is None
        assert not evaluation.quality.judge.trusted
        assert evaluation.gates[3].reason == "no answer graded by a person to calibrate the judge"

    def test_single_grade_calibration_cannot_measure_agreement(self) -> None:
        answers = (LabelledAnswer(judge_passed=True, person_passed=True),) * 24
        observations = replace(_observations([10] * 20, [0] * 20, [10] * 20), judge_answers=answers)
        reason = evaluate(example.config(), observations).gates[4].reason
        assert reason == (
            "graded answers all carry one grade: the judge's agreement cannot be measured"
        )

    def test_judge_ignored_when_no_check_relies_on_it(self) -> None:
        config = example.config()
        config = replace(config, quality=replace(config.quality, judge_calibration=None))
        evaluation = evaluate(config, _observations([10] * 20, [0] * 20, [10] * 20))
        assert evaluation.quality.judge is None

    def test_no_case_kept_aside_is_an_error(self) -> None:
        observations = replace(
            _observations([10] * 20, [0] * 20, [10] * 20),
            negative=Split((), _cases("neg", [10] * 3)),
        )
        with pytest.raises(
            EvaluationError, match=r"No negative invocation case is kept aside \(0 of 3\)"
        ):
            evaluate(example.config(), observations)

    def test_cases_with_too_few_runs_are_an_error(self) -> None:
        observations = _observations([4] * 20, [0] * 20, [10] * 20)
        short = replace(observations, positive=Split(_cases("pos", [4] * 20, runs=4), ()))
        with pytest.raises(EvaluationError, match=r"fewer runs than k needs: pos-00 \(4\)"):
            evaluate(example.config(), short)

    def test_previous_run_without_shared_cases_is_an_error(self) -> None:
        previous = PreviousRun(version="old", positive=_cases("other", [10]), quality=())
        with pytest.raises(EvaluationError, match=r"Cannot compare with old: .*share no case"):
            evaluate(example.config(), example.observations(), previous)


class TestComparisonAndLift:
    def test_too_few_shared_cases_give_no_clear_change(self) -> None:
        previous = PreviousRun(
            version="old",
            positive=_cases("pos", [9, 9]),
            quality=_cases("q", [9, 9]),
        )
        comparison = evaluate(
            example.config(), _observations([10] * 20, [0] * 20, [10] * 20), previous
        ).comparison
        assert comparison is not None
        assert comparison.invocation_recall.difference.cases == 2
        assert comparison.invocation_recall.change is Change.NO_CLEAR_CHANGE

    def test_lift_only_when_asked(self) -> None:
        config = example.config()
        config = replace(config, quality=replace(config.quality, measure_lift=False))
        quality = evaluate(config, example.observations()).quality
        assert quality.without_skill is None
        assert quality.lift is None


class TestOutcomes:
    def test_perfect_skill_with_many_cases_is_releasable(self) -> None:
        answers = (LabelledAnswer(judge_passed=True, person_passed=True),) * 10 + (
            LabelledAnswer(judge_passed=False, person_passed=False),
        ) * 10
        observations = replace(_observations([10] * 40, [0] * 40, [10] * 40), judge_answers=answers)
        evaluation = evaluate(example.config(), observations)
        assert evaluation.summary.releasable
        assert evaluation.summary.reason == "all gates passed"
        assert evaluation.invocation.precision == 1.0
        assert evaluation.quality.without_skill is None
        assert evaluation.quality.lift is None
        assert evaluation.invocation.tuning.recall is None

    def test_failing_skill(self) -> None:
        config = example.config()
        config = replace(config, quality=replace(config.quality, judge_calibration=None))
        evaluation = evaluate(config, _observations([2] * 20, [9] * 20, [1] * 20))
        assert evaluation.summary.reason == "5 gates failed"
        assert evaluation.summary.next_step.startswith("Improve the skill on the cases used")

    def test_no_start_at_all_has_no_precision(self) -> None:
        evaluation = evaluate(example.config(), _observations([0] * 20, [0] * 20, [10] * 20))
        assert evaluation.invocation.precision is None


def test_summary_without_diagnostics_asks_for_more_cases() -> None:
    gate = TestExample.evaluation.gates[0]
    empty = Diagnostics(
        invocation_unstable=(),
        invocation_started_by_mistake=(),
        quality_never_succeeds=(),
        quality_unstable=(),
    )
    gates: list[GateResult] = [gate, replace(gate, verdict=Verdict.FAILED)]
    summary = summarize(gates, empty)
    assert summary.reason == "1 gate failed, 1 gate inconclusive"
    assert summarize([gate], empty).next_step == "Add test cases kept aside and run again."
