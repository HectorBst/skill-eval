"""Turn per-case counts into scores, verdicts, diagnostics and a summary.

Inputs are counts already split between tuning and kept aside (see ``split``). Every
blocking score uses the cases kept aside only; scores on tuning cases are reported for
information. Successes always count the desired outcome: for positive invocation
cases, runs where the skill started; for negative ones, runs where it did not start;
for quality cases, runs where every check passed.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from skill_eval.domain.agreement import LabelledAnswer, cohen_kappa
from skill_eval.domain.comparison import Change, paired_difference, read_change
from skill_eval.domain.config import EvaluationConfig, GateName, QualitySettings
from skill_eval.domain.estimators import CaseCount, mean_over_cases, pass_at_k, pass_hat_k
from skill_eval.domain.intervals import Estimate, estimate_share
from skill_eval.domain.results import (
    Diagnostics,
    Evaluation,
    GateResult,
    InvocationResult,
    InvocationTuning,
    JudgeAgreement,
    QualityResult,
    QualityTuning,
    ScoreChange,
    Summary,
    VersionComparison,
    WithoutSkill,
)
from skill_eval.domain.split import Split
from skill_eval.domain.verdicts import Verdict

UNSTABLE_AT_MOST = 0.5
"""A case kept aside that succeeds at most this share of the time is listed for diagnosis."""


class EvaluationError(ValueError):
    """Raised when counts cannot support an evaluation."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Observations:
    """Per-case counts of one run.

    Attributes:
        positive: Positive invocation cases; success means the skill started.
        negative: Negative invocation cases; success means the skill did not start.
        quality: Quality cases with the skill; success means every check passed.
        quality_without_skill: Same quality cases run without the skill, if measured.
        judge_answers: Answers graded by both the judge and a person.
    """

    positive: Split[CaseCount]
    negative: Split[CaseCount]
    quality: Split[CaseCount]
    quality_without_skill: tuple[CaseCount, ...] = ()
    judge_answers: tuple[LabelledAnswer, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class PreviousRun:
    """Counts of the last evaluation of a previous version, on cases kept aside."""

    version: str
    positive: tuple[CaseCount, ...]
    quality: tuple[CaseCount, ...]


def evaluate(
    config: EvaluationConfig, observations: Observations, previous: PreviousRun | None = None
) -> Evaluation:
    """Compute every score, verdict and diagnostic of one evaluation.

    Args:
        config: Evaluation settings.
        observations: Per-case counts, split between tuning and kept aside.
        previous: Counts of a previous version, to compare case by case.

    Returns:
        The full evaluation.

    Raises:
        EvaluationError: If a set has no case kept aside, a case has fewer runs than a k
            value needs, or the previous version shares no case with this one.
    """
    _check_counts(config, observations)
    invocation = _invocation(config, observations)
    quality = _quality(config, observations)
    gates = _gates(config, invocation, quality)
    diagnostics = diagnose(observations)
    return Evaluation(
        summary=summarize(gates, diagnostics),
        invocation=invocation,
        quality=quality,
        comparison=_compare(config, observations, previous) if previous else None,
        gates=gates,
        diagnostics=diagnostics,
    )


def diagnose(observations: Observations) -> Diagnostics:
    """List the cases kept aside that explain low scores, in their input order."""
    quality = observations.quality.kept_aside
    return Diagnostics(
        invocation_unstable=tuple(
            case
            for case in observations.positive.kept_aside
            if case.success_rate <= UNSTABLE_AT_MOST
        ),
        invocation_started_by_mistake=tuple(
            case.inverted() for case in observations.negative.kept_aside if case.failures
        ),
        quality_never_succeeds=tuple(case for case in quality if case.successes == 0),
        quality_unstable=tuple(
            case for case in quality if case.successes and case.success_rate <= UNSTABLE_AT_MOST
        ),
    )


def summarize(gates: Sequence[GateResult], diagnostics: Diagnostics) -> Summary:
    """Say whether the skill can be shared, why, and what to do next."""
    failed = sum(gate.verdict is Verdict.FAILED for gate in gates)
    inconclusive = sum(gate.verdict is Verdict.INCONCLUSIVE for gate in gates)
    if not failed and not inconclusive:
        return Summary(
            releasable=True,
            reason="all gates passed",
            next_step="Share the skill, and keep this result to compare the next version.",
        )
    parts = [_count(failed, "failed"), _count(inconclusive, "inconclusive")]
    return Summary(
        releasable=False,
        reason=", ".join(part for part in parts if part),
        next_step=_next_step(failed=failed, has_diagnostics=_has_any(diagnostics)),
    )


def _check_counts(config: EvaluationConfig, observations: Observations) -> None:
    sets = {
        "positive invocation": observations.positive,
        "negative invocation": observations.negative,
        "quality": observations.quality,
    }
    for label, split in sets.items():
        if not split.kept_aside:
            total = len(split.tuning)
            raise EvaluationError(
                f"No {label} case is kept aside (0 of {total}): add cases and run again."
            )
    needed = {
        "invocation": config.trials.k_pass_hat,
        "quality": max(config.trials.k_pass_hat, config.trials.k_pass_at),
    }
    cases = [
        *(("invocation", case) for case in observations.positive.kept_aside),
        *(("invocation", case) for case in observations.negative.kept_aside),
        *(("quality", case) for case in observations.quality.kept_aside),
    ]
    short = [f"{case.name} ({case.runs})" for part, case in cases if case.runs < needed[part]]
    if short:
        raise EvaluationError(f"Cases with fewer runs than k needs: {', '.join(short)}.")


def _invocation(config: EvaluationConfig, observations: Observations) -> InvocationResult:
    level, k = config.confidence_level, config.trials.k_pass_hat
    positive, negative = observations.positive.kept_aside, observations.negative.kept_aside
    started = sum(case.successes for case in positive)
    mistaken = sum(case.failures for case in negative)
    return InvocationResult(
        positive_cases=len(positive),
        negative_cases=len(negative),
        positive_runs=sum(case.runs for case in positive),
        negative_runs=sum(case.runs for case in negative),
        started_when_expected=started,
        missed=sum(case.failures for case in positive),
        started_by_mistake=mistaken,
        recall=estimate_share([case.success_rate for case in positive], level),
        false_trigger_rate=estimate_share([1.0 - case.success_rate for case in negative], level),
        precision=started / (started + mistaken) if started + mistaken else None,
        pass_hat_k=estimate_share([pass_hat_k(case, k) for case in positive], level),
        pass_hat_k_negative=estimate_share([pass_hat_k(case, k) for case in negative], level),
        tuning=InvocationTuning(
            positive_cases=len(observations.positive.tuning),
            negative_cases=len(observations.negative.tuning),
            recall=_mean_or_none(case.success_rate for case in observations.positive.tuning),
            false_trigger_rate=_mean_or_none(
                1.0 - case.success_rate for case in observations.negative.tuning
            ),
        ),
    )


def _quality(config: EvaluationConfig, observations: Observations) -> QualityResult:
    level, trials = config.confidence_level, config.trials
    cases = observations.quality.kept_aside
    shortest = min(case.runs for case in cases)
    without = (
        _without_skill(cases, observations.quality_without_skill, level)
        if config.quality.measure_lift
        else None
    )
    return QualityResult(
        cases=len(cases),
        runs=sum(case.runs for case in cases),
        successful_runs=sum(case.successes for case in cases),
        pass_at_1=estimate_share([case.success_rate for case in cases], level),
        pass_at_k=estimate_share([pass_at_k(case, trials.k_pass_at) for case in cases], level),
        pass_hat_k=estimate_share([pass_hat_k(case, trials.k_pass_hat) for case in cases], level),
        pass_hat_k_by_uses=tuple(
            mean_over_cases(pass_hat_k(case, k) for case in cases) for k in range(1, shortest + 1)
        ),
        without_skill=without[0] if without else None,
        lift=without[1] if without else None,
        judge=_judge(config.quality, observations.judge_answers),
        tuning=QualityTuning(
            cases=len(observations.quality.tuning),
            pass_at_1=_mean_or_none(case.success_rate for case in observations.quality.tuning),
        ),
    )


def _without_skill(
    cases: Sequence[CaseCount], without: Sequence[CaseCount], level: float
) -> tuple[WithoutSkill, Estimate] | None:
    by_name = {case.name: case for case in without}
    shared = [case for case in cases if case.name in by_name]
    if not shared:
        return None
    baseline = [by_name[case.name] for case in shared]
    lift = paired_difference(
        {case.name: case.success_rate for case in shared},
        {case.name: case.success_rate for case in baseline},
        level,
    )
    summary = WithoutSkill(
        pass_at_1=estimate_share([case.success_rate for case in baseline], level),
        successful_runs=sum(case.successes for case in baseline),
    )
    return summary, lift


def _judge(settings: QualitySettings, answers: Sequence[LabelledAnswer]) -> JudgeAgreement | None:
    if settings.judge_calibration is None:
        return None
    kappa = cohen_kappa(answers) if answers else None
    trusted = kappa is not None and kappa >= settings.judge_minimum_agreement
    return JudgeAgreement(kappa=kappa, labelled_answers=len(answers), trusted=trusted)


def _gates(
    config: EvaluationConfig, invocation: InvocationResult, quality: QualityResult
) -> tuple[GateResult, ...]:
    scores = {
        GateName.INVOCATION_RECALL: invocation.recall,
        GateName.INVOCATION_FALSE_TRIGGER_RATE: invocation.false_trigger_rate,
        GateName.INVOCATION_PASS_HAT_K: invocation.pass_hat_k,
        GateName.QUALITY_PASS_AT_1: quality.pass_at_1,
        GateName.QUALITY_PASS_HAT_K: quality.pass_hat_k,
    }
    results = []
    for name, estimate in scores.items():
        limit = config.gates[name]
        reason = _forced_inconclusive(name, estimate, config, quality.judge)
        verdict = Verdict.INCONCLUSIVE if reason else limit.judge(estimate.interval)
        results.append(
            GateResult(name=name, limit=limit, estimate=estimate, verdict=verdict, reason=reason)
        )
    return tuple(results)


def _forced_inconclusive(
    name: GateName, estimate: Estimate, config: EvaluationConfig, judge: JudgeAgreement | None
) -> str | None:
    if estimate.cases < config.minimum_cases:
        return f"only {estimate.cases} cases kept aside, {config.minimum_cases} needed"
    if name.startswith("quality") and judge is not None and not judge.trusted:
        return _untrusted_judge_reason(judge, config.quality.judge_minimum_agreement)
    return None


def _untrusted_judge_reason(judge: JudgeAgreement, minimum: float) -> str:
    if not judge.labelled_answers:
        return "no answer graded by a person to calibrate the judge"
    if judge.kappa is None:
        return "graded answers all carry one grade: the judge's agreement cannot be measured"
    return f"the judge agrees too little with people (kappa {judge.kappa:.3f} < {minimum})"


def _compare(
    config: EvaluationConfig, observations: Observations, previous: PreviousRun
) -> VersionComparison:
    def change(current: Iterable[CaseCount], before: Iterable[CaseCount]) -> ScoreChange:
        try:
            difference = paired_difference(
                {case.name: case.success_rate for case in current},
                {case.name: case.success_rate for case in before},
                config.confidence_level,
            )
        except ValueError as error:
            raise EvaluationError(f"Cannot compare with {previous.version}: {error}") from error
        if difference.cases < config.minimum_cases:
            return ScoreChange(difference=difference, change=Change.NO_CLEAR_CHANGE)
        return ScoreChange(
            difference=difference, change=read_change(difference, higher_is_better=True)
        )

    return VersionComparison(
        previous_version=previous.version,
        invocation_recall=change(observations.positive.kept_aside, previous.positive),
        quality_pass_at_1=change(observations.quality.kept_aside, previous.quality),
    )


def _mean_or_none(values: Iterable[float]) -> float | None:
    collected = list(values)
    return mean_over_cases(collected) if collected else None


def _has_any(diagnostics: Diagnostics) -> bool:
    return any(
        (
            diagnostics.invocation_unstable,
            diagnostics.invocation_started_by_mistake,
            diagnostics.quality_never_succeeds,
            diagnostics.quality_unstable,
        )
    )


def _count(number: int, verdict: str) -> str:
    if not number:
        return ""
    return f"{number} gate{'s' if number > 1 else ''} {verdict}"


def _next_step(*, failed: int, has_diagnostics: bool) -> str:
    if failed:
        return "Improve the skill on the cases used for tuning, then run again."
    if has_diagnostics:
        return (
            "Fix the cases listed under diagnostics, then add test cases kept aside and run again."
        )
    return "Add test cases kept aside and run again."
