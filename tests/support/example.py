"""Per-case counts behind ``docs/skill-eval-result.example.yaml``.

The example result gives totals, scores and ranges but not the per-case counts. The
counts below were reconstructed so that every figure of the example is reproduced:
pass^10 = 0.533 = 8/15 fixes eight quality cases at 10/10, pass^9 then fixes one at
9/10, and the 122 successes leave three cases at 8/10 next to the three listed in the
diagnostics. Without-skill and previous-version counts were found by search; they are
one solution among several and only need to reproduce the published figures.

Invocation counts are given as the number of runs where the skill started.
"""

from skill_eval.domain.agreement import LabelledAnswer
from skill_eval.domain.estimators import CaseCount

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
