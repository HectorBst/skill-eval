"""Build the report of one run from its recorded per-case counts.

The trial runner (not written yet) will record per-case counts; this use case splits
them, evaluates them and returns everything the result file shows. It never touches
files: readers and writers are adapters.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum

from skill_eval.domain.agreement import LabelledAnswer
from skill_eval.domain.config import EvaluationConfig
from skill_eval.domain.estimators import CaseCount
from skill_eval.domain.evaluation import Observations, PreviousRun, evaluate
from skill_eval.domain.results import Evaluation
from skill_eval.domain.split import split_cases
from skill_eval.domain.verdicts import Verdict


@dataclass(frozen=True, slots=True, kw_only=True)
class Environment:
    """What a run depended on, recorded so that two results can be compared fairly.

    Attributes:
        installed_skills: Number of skills installed during the run.
        installed_skills_hash: Fingerprint of the installed skills.
        inspect_ai: Version of inspect-ai.
        inspect_swe: Version of inspect-swe.
    """

    installed_skills: int
    installed_skills_hash: str
    inspect_ai: str
    inspect_swe: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RunRecord:
    """Per-case counts of one run, with what identifies the run.

    Invocation counts are runs where the skill started, as observed; quality counts are
    runs where every check passed.

    Attributes:
        skill: Skill name.
        skill_version: Fingerprint of the evaluated skill.
        date: Day the trials ran.
        environment: What the run depended on.
        positive_started: Positive invocation cases.
        negative_started: Negative invocation cases.
        quality_succeeded: Quality cases run with the skill.
        quality_without_skill: Quality cases run without the skill, if measured.
        judge_answers: Answers graded by both the judge and a person.
    """

    skill: str
    skill_version: str
    date: date
    environment: Environment
    positive_started: tuple[CaseCount, ...]
    negative_started: tuple[CaseCount, ...]
    quality_succeeded: tuple[CaseCount, ...]
    quality_without_skill: tuple[CaseCount, ...] = ()
    judge_answers: tuple[LabelledAnswer, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Report:
    """Everything the result file shows.

    Attributes:
        config: Settings the run used.
        record: Counts and identification of the run.
        evaluation: Scores, verdicts and diagnostics.
        warnings: Settings or inputs that weaken the result without invalidating it.
    """

    config: EvaluationConfig
    record: RunRecord
    evaluation: Evaluation
    warnings: tuple[str, ...] = field(default=())


class Outcome(IntEnum):
    """Process exit code that follows the verdict, for CI jobs.

    ``INCONCLUSIVE`` has its own code so that a pipeline can let it pass with a warning
    (GitLab ``allow_failure: exit_codes``) while still blocking a failure.
    """

    RELEASABLE = 0
    FAILED = 1
    USAGE_ERROR = 2
    INCONCLUSIVE = 3
    INVALID_INPUT = 4
    INTERNAL_ERROR = 5


class ReportError(ValueError):
    """Raised when two records cannot be used together."""


def build_report(
    config: EvaluationConfig, record: RunRecord, previous: RunRecord | None = None
) -> Report:
    """Split the recorded cases, evaluate them, and compare with a previous version.

    Args:
        config: Settings of the run.
        record: Per-case counts of the run.
        previous: Per-case counts of the last run of a previous version of the skill.

    Raises:
        ReportError: If the previous record is about another skill.
        EvaluationError: If the counts cannot support an evaluation.
    """
    warnings = [*config.warnings(), *_run_count_warnings(config, record)]
    previous_run = None
    if previous is not None:
        warnings += _comparison_warnings(record, previous)
        previous_run = _previous_run(previous, config.holdout_share)
    observations = _observations(record, config.holdout_share)
    evaluation = evaluate(config, observations, previous_run)
    warnings += _lift_warnings(config, record, observations)
    return Report(config=config, record=record, evaluation=evaluation, warnings=tuple(warnings))


def outcome_of(report: Report) -> Outcome:
    """Map the verdicts of a report to the process exit code."""
    if report.evaluation.summary.releasable:
        return Outcome.RELEASABLE
    if any(gate.verdict is Verdict.FAILED for gate in report.evaluation.gates):
        return Outcome.FAILED
    return Outcome.INCONCLUSIVE


def _observations(record: RunRecord, share: float) -> Observations:
    return Observations(
        positive=split_cases(record.positive_started, share),
        negative=split_cases((case.inverted() for case in record.negative_started), share),
        quality=split_cases(record.quality_succeeded, share),
        quality_without_skill=record.quality_without_skill,
        judge_answers=record.judge_answers,
    )


def _previous_run(previous: RunRecord, share: float) -> PreviousRun:
    return PreviousRun(
        version=previous.skill_version,
        positive=split_cases(previous.positive_started, share).kept_aside,
        quality=split_cases(previous.quality_succeeded, share).kept_aside,
    )


_LISTED_AT_MOST = 5


def _names(cases: list[str]) -> str:
    shown = ", ".join(cases[:_LISTED_AT_MOST])
    return shown + (
        f" and {len(cases) - _LISTED_AT_MOST} more" if len(cases) > _LISTED_AT_MOST else ""
    )


def _run_count_warnings(config: EvaluationConfig, record: RunRecord) -> list[str]:
    expected = {
        "invocation_per_case": (
            config.trials.invocation_per_case,
            (*record.positive_started, *record.negative_started),
        ),
        "quality_per_case": (
            config.trials.quality_per_case,
            (*record.quality_succeeded, *record.quality_without_skill),
        ),
    }
    warnings = []
    for setting, (runs, cases) in expected.items():
        off = [f"{case.name} ({case.runs})" for case in cases if case.runs != runs]
        if off:
            warnings.append(
                f"{len(off)} cases did not run trials.{setting} ({runs}) times: {_names(off)}."
            )
    return warnings


def _lift_warnings(
    config: EvaluationConfig, record: RunRecord, observations: Observations
) -> list[str]:
    without = {case.name for case in record.quality_without_skill}
    if not config.quality.measure_lift:
        return ["quality.without_skill is ignored: measure_lift is not set."] if without else []
    if not without:
        return ["quality.measure_lift is set but the record holds no run without skill."]
    warnings = []
    kept_aside = [case.name for case in observations.quality.kept_aside]
    missing = [name for name in kept_aside if name not in without]
    if missing:
        warnings.append(
            f"quality.without_skill covers {len(kept_aside) - len(missing)} of "
            f"{len(kept_aside)} quality cases kept aside; the lift uses only those. "
            f"Missing: {_names(missing)}."
        )
    unknown = sorted(without - {case.name for case in record.quality_succeeded})
    if unknown:
        warnings.append(
            f"quality.without_skill lists cases never run with the skill: {_names(unknown)}."
        )
    return warnings


def _comparison_warnings(record: RunRecord, previous: RunRecord) -> list[str]:
    if previous.skill != record.skill:
        raise ReportError(
            f"The previous record is about skill {previous.skill!r}, not {record.skill!r}."
        )
    warnings = []
    if previous.skill_version == record.skill_version:
        warnings.append(f"The previous record has the same skill version {record.skill_version}.")
    if previous.environment != record.environment:
        warnings.append(
            "The previous record ran with other installed skills or Inspect versions: "
            "differences may come from the environment, not from the skill."
        )
    return warnings
