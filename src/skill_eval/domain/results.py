"""What one evaluation produces, before any formatting.

The structure follows ``docs/skill-eval-result.example.yaml``; adapters only format it.
"""

from dataclasses import dataclass

from skill_eval.domain.comparison import Change
from skill_eval.domain.config import GateName
from skill_eval.domain.estimators import CaseCount
from skill_eval.domain.intervals import Estimate
from skill_eval.domain.verdicts import Limit, Verdict


@dataclass(frozen=True, slots=True, kw_only=True)
class InvocationTuning:
    """Point scores on the cases used for tuning, reported for information only."""

    positive_cases: int
    negative_cases: int
    recall: float | None
    false_trigger_rate: float | None


@dataclass(frozen=True, slots=True, kw_only=True)
class InvocationResult:
    """Invocation scores, computed on the cases kept aside.

    Attributes:
        positive_cases: Positive cases kept aside.
        negative_cases: Negative cases kept aside.
        positive_runs: Trials on positive cases kept aside.
        negative_runs: Trials on negative cases kept aside.
        started_when_expected: Positive trials where the skill started.
        missed: Positive trials where it did not start.
        started_by_mistake: Negative trials where it started anyway.
        recall: Share of positive trials where the skill started, case by case.
        false_trigger_rate: Share of negative trials where it started, case by case.
        precision: Share of starts that were justified, or None without any start.
        pass_hat_k: Starts every time it should, k uses in a row (positive cases).
        pass_hat_k_negative: Never starts by mistake, k uses in a row (negative cases).
        tuning: Point scores on the cases used for tuning.
    """

    positive_cases: int
    negative_cases: int
    positive_runs: int
    negative_runs: int
    started_when_expected: int
    missed: int
    started_by_mistake: int
    recall: Estimate
    false_trigger_rate: Estimate
    precision: float | None
    pass_hat_k: Estimate
    pass_hat_k_negative: Estimate
    tuning: InvocationTuning


@dataclass(frozen=True, slots=True, kw_only=True)
class WithoutSkill:
    """Quality of the same cases run without the skill installed."""

    pass_at_1: Estimate
    successful_runs: int


@dataclass(frozen=True, slots=True, kw_only=True)
class JudgeAgreement:
    """Agreement between judge and person on graded answers.

    Attributes:
        kappa: Cohen's kappa, or None when it cannot be measured.
        labelled_answers: Number of answers graded by both.
        trusted: Whether results relying on the judge can decide a gate.
    """

    kappa: float | None
    labelled_answers: int
    trusted: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class QualityTuning:
    """Point score on the cases used for tuning, reported for information only."""

    cases: int
    pass_at_1: float | None


@dataclass(frozen=True, slots=True, kw_only=True)
class QualityResult:
    """Quality scores, computed on the cases kept aside.

    Attributes:
        cases: Quality cases kept aside.
        runs: Trials on those cases.
        successful_runs: Trials where every check passed.
        pass_at_1: Does the job well on a single use.
        pass_at_k: Does the job well at least once in k tries; diagnosis only.
        pass_hat_k: Does the job well k uses in a row.
        pass_hat_k_by_uses: pass^k for k from 1 to the smallest number of runs of a case.
        without_skill: Same cases without the skill, when measured.
        lift: Case-by-case pass@1 difference, with minus without the skill.
        judge: Judge calibration, when a check relies on the judge.
        tuning: Point score on the cases used for tuning.
    """

    cases: int
    runs: int
    successful_runs: int
    pass_at_1: Estimate
    pass_at_k: Estimate
    pass_hat_k: Estimate
    pass_hat_k_by_uses: tuple[float, ...]
    without_skill: WithoutSkill | None
    lift: Estimate | None
    judge: JudgeAgreement | None
    tuning: QualityTuning


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreChange:
    """Case-by-case change of one score against the previous version."""

    difference: Estimate
    change: Change


@dataclass(frozen=True, slots=True, kw_only=True)
class VersionComparison:
    """Comparison with the last result of a previous version, on shared cases."""

    previous_version: str
    invocation_recall: ScoreChange
    quality_pass_at_1: ScoreChange


@dataclass(frozen=True, slots=True, kw_only=True)
class GateResult:
    """Verdict of one gate.

    Attributes:
        name: Gate name.
        limit: Limit the score must meet.
        estimate: Score and range the verdict is read on.
        verdict: Verdict of the gate.
        reason: Why the verdict was forced to inconclusive, if it was.
    """

    name: GateName
    limit: Limit
    estimate: Estimate
    verdict: Verdict
    reason: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Diagnostics:
    """Cases kept aside to look at first, each with its raw count.

    Invocation counts are runs where the skill started; quality counts are runs
    where every check passed.
    """

    invocation_unstable: tuple[CaseCount, ...]
    invocation_started_by_mistake: tuple[CaseCount, ...]
    quality_never_succeeds: tuple[CaseCount, ...]
    quality_unstable: tuple[CaseCount, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Summary:
    """What to read first: can the skill be shared, why, and what to do next."""

    releasable: bool
    reason: str
    next_step: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Evaluation:
    """Full outcome of one evaluation."""

    summary: Summary
    invocation: InvocationResult
    quality: QualityResult
    comparison: VersionComparison | None
    gates: tuple[GateResult, ...]
    diagnostics: Diagnostics
