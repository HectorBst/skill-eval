"""Per-case counts behind ``docs/skill-eval-result.example.yaml``.

The example result gives totals, scores and ranges but not the per-case counts. The
counts below were reconstructed so that every figure of the example is reproduced:
pass^10 = 0.533 = 8/15 fixes eight quality cases at 10/10, pass^9 then fixes one at
9/10, and the 122 successes leave three cases at 8/10 next to the three listed in the
diagnostics. Without-skill and previous-version counts were found by search; they are
one solution among several and only need to reproduce the published figures.

Invocation counts are given as the number of runs where the skill started.
"""

from pathlib import PurePath

from skill_eval.domain.agreement import LabelledAnswer
from skill_eval.domain.config import (
    Agent,
    Effort,
    EvaluationConfig,
    Execution,
    GateName,
    Gates,
    InvocationSettings,
    QualitySettings,
    Trials,
)
from skill_eval.domain.estimators import CaseCount
from skill_eval.domain.evaluation import Observations, PreviousRun
from skill_eval.domain.split import Split

RUNS = 10


def _started(name: str, started: int) -> CaseCount:
    return CaseCount(name, RUNS, started)


def _not_started(name: str, started: int) -> CaseCount:
    """Negative case: success means the skill did not start."""
    return CaseCount(name, RUNS, RUNS - started)


def _numbered(prefix: str, values: list[int], first: int = 1) -> list[tuple[str, int]]:
    return [(f"{prefix}-{index:02d}", value) for index, value in enumerate(values, first)]


# --- Invocation, cases kept aside ------------------------------------------------

# 14 cases at 10/10, 4 at 8/10, then the two listed under invocation_unstable.
POSITIVE_STARTED: list[tuple[str, int]] = [
    *_numbered("pos-holdout", [10] * 14 + [8] * 4),
    ("pos-implicit-07", 5),
    ("pos-english-12", 3),
]
POSITIVE_HOLDOUT = [_started(name, value) for name, value in POSITIVE_STARTED]

# Previous version, same cases (recall 0.845, so +0.055 for the current version).
POSITIVE_PREVIOUS_STARTED: dict[str, int] = dict(
    zip(
        [name for name, _ in POSITIVE_STARTED],
        [10] * 8 + [9] * 4 + [8] * 2 + [10, 8, 7, 5] + [5, 2],
        strict=True,
    )
)

# 17 cases never started, then the three listed under invocation_started_by_mistake.
NEGATIVE_STARTED: list[tuple[str, int]] = [
    *_numbered("neg-holdout", [0] * 17),
    ("neg-pdf-03", 2),
    ("neg-email-08", 2),
    ("neg-slack-15", 2),
]
NEGATIVE_HOLDOUT = [_not_started(name, value) for name, value in NEGATIVE_STARTED]

# --- Invocation, cases used for tuning --------------------------------------------

POSITIVE_TUNING = [
    _started(name, value) for name, value in _numbered("pos-tuning", [10] * 24 + [9] * 4 + [4] * 2)
]
NEGATIVE_TUNING = [
    _not_started(name, value)
    for name, value in _numbered("neg-tuning", [0] * 25 + [1] * 3 + [2] * 2)
]

# --- Quality, cases kept aside ----------------------------------------------------

QUALITY_SUCCEEDED: list[tuple[str, int]] = [
    *_numbered("q-holdout", [10] * 8 + [9] + [8] * 3),
    ("q-long-doc-09", 5),
    ("q-multi-source-11", 4),
    ("q-incomplete-input-04", 0),
]
QUALITY_HOLDOUT = [CaseCount(name, RUNS, value) for name, value in QUALITY_SUCCEEDED]

QUALITY_WITHOUT_SKILL: dict[str, int] = dict(
    zip(
        [name for name, _ in QUALITY_SUCCEEDED],
        [9, 8, 8, 6, 6, 5, 5, 4, 6, 7, 5, 4, 4, 2, 0],
        strict=True,
    )
)

QUALITY_PREVIOUS: dict[str, int] = dict(
    zip(
        [name for name, _ in QUALITY_SUCCEEDED],
        [10] * 6 + [9, 9, 8, 8, 7, 7, 6, 4, 1],
        strict=True,
    )
)

QUALITY_TUNING = [
    CaseCount(name, RUNS, value) for name, value in _numbered("q-tuning", [10] * 17 + [6] * 6)
]

# --- Judge calibration: 17 agreed passes, 5 agreed failures, 2 disagreements ---------

JUDGE_ANSWERS = (
    [LabelledAnswer(judge_passed=True, person_passed=True)] * 17
    + [LabelledAnswer(judge_passed=False, person_passed=False)] * 5
    + [LabelledAnswer(judge_passed=True, person_passed=False)]
    + [LabelledAnswer(judge_passed=False, person_passed=True)]
)


# --- Whole example, as domain inputs -------------------------------------------------


def config() -> EvaluationConfig:
    """Settings of docs/skill-eval.example.yaml."""
    return EvaluationConfig(
        execution=Execution(
            agent=Agent.CLAUDE_CODE,
            agent_version="2.1.309",
            model="claude-sonnet-5-5",
            judge_model="claude-haiku-5-5",
            effort=Effort.MEDIUM,
            installed_skills=PurePath("skills"),
        ),
        trials=Trials(invocation_per_case=10, quality_per_case=10, k_pass_at=3, k_pass_hat=5),
        confidence_level=0.95,
        holdout_share=0.4,
        minimum_cases=15,
        invocation=InvocationSettings(
            max_turns=3,
            positive_cases=PurePath("evals/invocation/positive"),
            negative_cases=PurePath("evals/invocation/negative"),
        ),
        quality=QualitySettings(
            cases=PurePath("evals/quality"),
            measure_lift=True,
            judge_calibration=PurePath("evals/quality/judge-calibration"),
            judge_minimum_agreement=0.60,
        ),
        gates=Gates.from_values(
            {
                GateName.INVOCATION_RECALL: 0.85,
                GateName.INVOCATION_FALSE_TRIGGER_RATE: 0.10,
                GateName.INVOCATION_PASS_HAT_K: 0.50,
                GateName.QUALITY_PASS_AT_1: 0.75,
                GateName.QUALITY_PASS_HAT_K: 0.60,
            }
        ),
    )


def observations() -> Observations:
    """Counts of the example, split as the example result reports them."""
    return Observations(
        positive=Split(tuple(POSITIVE_HOLDOUT), tuple(POSITIVE_TUNING)),
        negative=Split(tuple(NEGATIVE_HOLDOUT), tuple(NEGATIVE_TUNING)),
        quality=Split(tuple(QUALITY_HOLDOUT), tuple(QUALITY_TUNING)),
        quality_without_skill=tuple(
            CaseCount(name, RUNS, value) for name, value in QUALITY_WITHOUT_SKILL.items()
        ),
        judge_answers=tuple(JUDGE_ANSWERS),
    )


def previous_run() -> PreviousRun:
    """Counts of version e81b4d0 on the same cases kept aside."""
    return PreviousRun(
        version="e81b4d0",
        positive=tuple(_started(name, value) for name, value in POSITIVE_PREVIOUS_STARTED.items()),
        quality=tuple(CaseCount(name, RUNS, value) for name, value in QUALITY_PREVIOUS.items()),
    )
