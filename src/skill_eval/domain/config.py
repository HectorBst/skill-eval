"""Evaluation settings and the rules they must follow before anything runs.

The settings mirror ``skill-eval.yaml``. Each section checks its own rules and reports
every broken rule at once, so that a team fixing its file sees all problems in one go.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePath

from skill_eval.domain.verdicts import Bound, Limit

_EXACT_VERSION = re.compile(r"\d+\.\d+\.\d+")
_MIN_K = 2


class ConfigurationError(ValueError):
    """Raised when settings break one or more rules; ``problems`` lists them all."""

    def __init__(self, problems: list[str]) -> None:
        """Keep every problem and build a readable message from them."""
        self.problems = tuple(problems)
        super().__init__("Invalid settings:\n" + "\n".join(f"- {p}" for p in problems))


def _raise_if_any(problems: list[str]) -> None:
    if problems:
        raise ConfigurationError(problems)


class Agent(StrEnum):
    """Agents the runner can drive."""

    CLAUDE_CODE = "claude_code"
    CODEX_CLI = "codex_cli"
    GEMINI_CLI = "gemini_cli"


class Effort(StrEnum):
    """Reasoning effort of the tested model."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


@dataclass(frozen=True, slots=True, kw_only=True)
class Execution:
    """What runs the skill.

    Attributes:
        agent: Agent that runs the skill.
        agent_version: Exact agent version; triggering changes between versions.
        model: Model being tested.
        judge_model: Model that grades answers no rule can check, if any.
        effort: Reasoning effort of the tested model.
        installed_skills: Folder holding every skill installed in real use.
    """

    agent: Agent
    agent_version: str
    model: str
    judge_model: str | None
    effort: Effort
    installed_skills: PurePath

    def __post_init__(self) -> None:
        """Require an exact agent version and named models."""
        problems = []
        if not _EXACT_VERSION.fullmatch(self.agent_version):
            problems.append(
                f"execution.agent_version must be an exact version such as 2.1.309, "
                f"got {self.agent_version!r}: a moving version makes results incomparable."
            )
        if not self.model:
            problems.append("execution.model must name the tested model.")
        if self.judge_model == "":
            problems.append("execution.judge_model must name a model or be left out.")
        _raise_if_any(problems)


@dataclass(frozen=True, slots=True, kw_only=True)
class Trials:
    """How many times each case runs, and the k of pass@k and pass^k.

    Attributes:
        invocation_per_case: Trials per invocation case.
        quality_per_case: Trials per quality case.
        k_pass_at: Number of tries a user would accept (pass@k).
        k_pass_hat: Number of uses in a row the skill must hold over (pass^k).
    """

    invocation_per_case: int
    quality_per_case: int
    k_pass_at: int
    k_pass_hat: int

    def __post_init__(self) -> None:
        """Check the rules listed at the top of ``skill-eval.yaml``."""
        problems = []
        if self.k_pass_at < _MIN_K:
            problems.append(f"trials.k_pass_at must be at least {_MIN_K}, got {self.k_pass_at}.")
        if self.k_pass_hat < _MIN_K:
            problems.append(f"trials.k_pass_hat must be at least {_MIN_K}, got {self.k_pass_hat}.")
        for name, per_case in self._per_case():
            if per_case < self.k_pass_hat:
                problems.append(
                    f"trials.{name} ({per_case}) must be at least k_pass_hat ({self.k_pass_hat})."
                )
        if self.quality_per_case < self.k_pass_at:
            problems.append(
                f"trials.quality_per_case ({self.quality_per_case}) must be at least "
                f"k_pass_at ({self.k_pass_at})."
            )
        _raise_if_any(problems)

    def warnings(self) -> list[str]:
        """List settings that are valid but give poor estimates.

        With as many trials as ``k_pass_hat``, pass^k of a case can only be 0 or 1;
        at least twice as many trials give a graded estimate.
        """
        return [
            f"trials.{name} ({per_case}) is below twice k_pass_hat ({2 * self.k_pass_hat}): "
            "pass^k per case will be coarse."
            for name, per_case in self._per_case()
            if per_case < 2 * self.k_pass_hat
        ]

    def _per_case(self) -> Iterator[tuple[str, int]]:
        yield "invocation_per_case", self.invocation_per_case
        yield "quality_per_case", self.quality_per_case


@dataclass(frozen=True, slots=True, kw_only=True)
class InvocationSettings:
    """Settings of the invocation part.

    Attributes:
        max_turns: Conversation turns per trial.
        positive_cases: Folder of requests the skill must handle.
        negative_cases: Folder of close requests where the skill must not start.
    """

    max_turns: int
    positive_cases: PurePath
    negative_cases: PurePath

    def __post_init__(self) -> None:
        """Require at least one turn and two distinct case folders."""
        problems = []
        if self.max_turns < 1:
            problems.append(f"invocation.max_turns must be at least 1, got {self.max_turns}.")
        if self.positive_cases == self.negative_cases:
            problems.append("invocation positive and negative cases must be distinct folders.")
        _raise_if_any(problems)


@dataclass(frozen=True, slots=True, kw_only=True)
class QualitySettings:
    """Settings of the quality part.

    Attributes:
        cases: Folder of quality cases.
        measure_lift: Also run each case without the skill, for information.
        judge_calibration: Folder of answers graded by a person, if a check uses the judge.
        judge_minimum_agreement: Cohen's kappa below which judge-based results are unreliable.
    """

    cases: PurePath
    measure_lift: bool
    judge_calibration: PurePath | None
    judge_minimum_agreement: float

    def __post_init__(self) -> None:
        """Require a kappa threshold that some agreement can meet."""
        if not 0.0 < self.judge_minimum_agreement <= 1.0:
            problem = (
                "quality.judge_minimum_agreement must be above 0 and at most 1, "
                f"got {self.judge_minimum_agreement}."
            )
            raise ConfigurationError([problem])


class GateName(StrEnum):
    """The five gates, in the order the result lists them."""

    INVOCATION_RECALL = "invocation_recall"
    INVOCATION_FALSE_TRIGGER_RATE = "invocation_false_trigger_rate"
    INVOCATION_PASS_HAT_K = "invocation_pass_hat_k"  # noqa: S105 - "pass" as in pass^k
    QUALITY_PASS_AT_1 = "quality_pass_at_1"  # noqa: S105
    QUALITY_PASS_HAT_K = "quality_pass_hat_k"  # noqa: S105


_BOUNDS: dict[GateName, Bound] = {
    GateName.INVOCATION_RECALL: Bound.MINIMUM,
    GateName.INVOCATION_FALSE_TRIGGER_RATE: Bound.MAXIMUM,
    GateName.INVOCATION_PASS_HAT_K: Bound.MINIMUM,
    GateName.QUALITY_PASS_AT_1: Bound.MINIMUM,
    GateName.QUALITY_PASS_HAT_K: Bound.MINIMUM,
}


@dataclass(frozen=True, slots=True, kw_only=True)
class Gates:
    """Limits every score must meet for the skill to be shared."""

    limits: dict[GateName, Limit]

    @classmethod
    def from_values(cls, values: dict[GateName, float]) -> "Gates":
        """Build the gates from their limit values; the bound of each gate is fixed.

        Raises:
            ConfigurationError: If a gate is missing or a limit is outside ``[0, 1]``.
        """
        problems = [f"gates.{name} is missing." for name in GateName if name not in values]
        problems += [
            f"gates.{name} must lie between 0 and 1, got {value}."
            for name, value in values.items()
            if not 0.0 <= value <= 1.0
        ]
        _raise_if_any(problems)
        return cls(limits={name: Limit(_BOUNDS[name], values[name]) for name in GateName})

    def __getitem__(self, name: GateName) -> Limit:
        """Return the limit of one gate."""
        return self.limits[name]


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluationConfig:
    """Everything ``skill-eval.yaml`` sets for one evaluation.

    Attributes:
        execution: What runs the skill.
        trials: Trials per case and the k values.
        confidence_level: Confidence level of every range.
        holdout_share: Share of cases kept aside to decide.
        minimum_cases: Below this many cases kept aside, a gate is inconclusive.
        invocation: Invocation settings.
        quality: Quality settings.
        gates: Limits to meet.
    """

    execution: Execution
    trials: Trials
    confidence_level: float
    holdout_share: float
    minimum_cases: int
    invocation: InvocationSettings
    quality: QualitySettings
    gates: Gates

    def __post_init__(self) -> None:
        """Check the settings shared by both parts."""
        _raise_if_any(
            self.shared_problems(
                confidence_level=self.confidence_level,
                holdout_share=self.holdout_share,
                minimum_cases=self.minimum_cases,
            )
        )

    @staticmethod
    def shared_problems(
        *, confidence_level: float, holdout_share: float, minimum_cases: int
    ) -> list[str]:
        """List the broken rules among the settings shared by both parts.

        Exposed so that a reader can report these problems together with those of the
        sections, before the whole configuration can be built.
        """
        problems = []
        if not 0.0 < confidence_level < 1.0:
            problems.append(
                f"confidence_level must be strictly between 0 and 1, got {confidence_level}."
            )
        if not 0.0 < holdout_share < 1.0:
            problems.append(f"holdout_share must be strictly between 0 and 1, got {holdout_share}.")
        if minimum_cases < _MIN_K:
            problems.append(
                f"minimum_cases must be at least {_MIN_K} for a range to exist, "
                f"got {minimum_cases}."
            )
        return problems

    def warnings(self) -> list[str]:
        """List settings that are valid but weaken the evaluation."""
        return self.trials.warnings()
