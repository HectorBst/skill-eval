"""Read ``skill-eval.yaml`` settings and recorded per-case counts from YAML files.

Pydantic checks the structure (types, missing and unknown keys, so that a typo in a
gate name is reported instead of silently ignored); the domain then checks its own
rules. Every problem found is reported at once.
"""

from collections.abc import Callable, Hashable
from datetime import date
from pathlib import Path, PurePath
from typing import Annotated, Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    ValidationError,
)
from pydantic_core import ErrorDetails

from skill_eval.application.report import Environment, RunRecord
from skill_eval.domain.agreement import LabelledAnswer
from skill_eval.domain.config import (
    Agent,
    ConfigurationError,
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

DEFAULT_JUDGE_MINIMUM_AGREEMENT = 0.60

# Same rule as the Agent Skills specification for skill names.
SkillName = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", max_length=64)
]
Fingerprint = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{7,64}$")]
Version = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9A-Za-z][0-9A-Za-z.+-]*$")]


class InputError(ValueError):
    """Raised when an input file is unreadable or invalid; ``problems`` lists every issue."""

    def __init__(self, source: str, problems: list[str]) -> None:
        """Keep every problem and name the file they come from."""
        self.problems = tuple(problems)
        super().__init__(f"{source} is invalid:\n" + "\n".join(f"- {p}" for p in problems))


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- skill-eval.yaml -------------------------------------------------------------------


class _Execution(_Model):
    agent: Agent
    agent_version: StrictStr
    model: StrictStr
    judge_model: StrictStr | None = None
    effort: Effort
    installed_skills: StrictStr


class _Trials(_Model):
    invocation_per_case: StrictInt
    quality_per_case: StrictInt
    k_pass_at: StrictInt
    k_pass_hat: StrictInt


class _InvocationCases(_Model):
    positive: StrictStr
    negative: StrictStr


class _Invocation(_Model):
    max_turns: StrictInt
    cases: _InvocationCases


class _Quality(_Model):
    cases: StrictStr
    measure_lift: StrictBool
    judge_calibration: StrictStr | None = None
    judge_minimum_agreement: StrictFloat = DEFAULT_JUDGE_MINIMUM_AGREEMENT


class _Gates(_Model):
    invocation_recall: StrictFloat
    invocation_false_trigger_rate: StrictFloat
    invocation_pass_hat_k: StrictFloat
    quality_pass_at_1: StrictFloat
    quality_pass_hat_k: StrictFloat


class _ConfigFile(_Model):
    execution: _Execution
    trials: _Trials
    confidence_level: StrictFloat
    holdout_share: StrictFloat
    minimum_cases: StrictInt
    invocation: _Invocation
    quality: _Quality
    gates: _Gates


def load_config(path: Path) -> EvaluationConfig:
    """Read and check a ``skill-eval.yaml`` file.

    Raises:
        InputError: If the file is unreadable, malformed or breaks a rule.
    """
    return parse_config(_load_yaml(path), source=str(path))


def parse_config(data: object, *, source: str = "settings") -> EvaluationConfig:
    """Check already-loaded settings and build the domain configuration.

    Raises:
        InputError: If the structure is wrong or a domain rule is broken.
    """
    raw = _validate(_ConfigFile, data, source)
    problems = EvaluationConfig.shared_problems(
        confidence_level=raw.confidence_level,
        holdout_share=raw.holdout_share,
        minimum_cases=raw.minimum_cases,
    )
    execution = _collect(problems, lambda: _execution(raw.execution))
    trials = _collect(problems, lambda: Trials(**raw.trials.model_dump()))
    invocation = _collect(problems, lambda: _invocation(raw.invocation))
    quality = _collect(problems, lambda: _quality(raw.quality))
    gates = _collect(problems, lambda: Gates.from_values({GateName(k): v for k, v in raw.gates}))
    if (
        problems
        or execution is None
        or trials is None
        or invocation is None
        or quality is None
        or gates is None
    ):
        raise InputError(source, problems)
    return EvaluationConfig(
        execution=execution,
        trials=trials,
        confidence_level=raw.confidence_level,
        holdout_share=raw.holdout_share,
        minimum_cases=raw.minimum_cases,
        invocation=invocation,
        quality=quality,
        gates=gates,
    )


def _execution(raw: _Execution) -> Execution:
    return Execution(
        agent=raw.agent,
        agent_version=raw.agent_version,
        model=raw.model,
        judge_model=raw.judge_model,
        effort=raw.effort,
        installed_skills=PurePath(raw.installed_skills),
    )


def _invocation(raw: _Invocation) -> InvocationSettings:
    return InvocationSettings(
        max_turns=raw.max_turns,
        positive_cases=PurePath(raw.cases.positive),
        negative_cases=PurePath(raw.cases.negative),
    )


def _quality(raw: _Quality) -> QualitySettings:
    return QualitySettings(
        cases=PurePath(raw.cases),
        measure_lift=raw.measure_lift,
        judge_calibration=PurePath(raw.judge_calibration) if raw.judge_calibration else None,
        judge_minimum_agreement=raw.judge_minimum_agreement,
    )


def _collect[T](problems: list[str], build: Callable[[], T]) -> T | None:
    try:
        return build()
    except ConfigurationError as error:
        problems.extend(error.problems)
        return None


# --- Recorded counts --------------------------------------------------------------------


class _Started(_Model):
    runs: StrictInt
    started: StrictInt


class _Succeeded(_Model):
    runs: StrictInt
    succeeded: StrictInt


class _Environment(_Model):
    installed_skills: StrictInt
    installed_skills_hash: Fingerprint
    inspect_ai: Version
    inspect_swe: Version


class _RecordedInvocation(_Model):
    positive: dict[StrictStr, _Started]
    negative: dict[StrictStr, _Started]


class _RecordedQuality(_Model):
    with_skill: dict[StrictStr, _Succeeded]
    without_skill: dict[StrictStr, _Succeeded] = {}


class _Answer(_Model):
    judge_passed: StrictBool
    person_passed: StrictBool


class _RecordFile(_Model):
    skill: SkillName
    skill_version: Fingerprint
    date: date
    environment: _Environment
    invocation: _RecordedInvocation
    quality: _RecordedQuality
    judge_calibration: list[_Answer] = []


def load_record(path: Path) -> RunRecord:
    """Read recorded per-case counts.

    Raises:
        InputError: If the file is unreadable, malformed or holds impossible counts.
    """
    return parse_record(_load_yaml(path), source=str(path))


def parse_record(data: object, *, source: str = "record") -> RunRecord:
    """Check already-loaded counts and build the run record.

    Raises:
        InputError: If the structure is wrong or a count is impossible.
    """
    raw = _validate(_RecordFile, data, source)
    problems: list[str] = []
    record = RunRecord(
        skill=raw.skill,
        skill_version=raw.skill_version,
        date=raw.date,
        environment=Environment(**raw.environment.model_dump()),
        positive_started=_counts(problems, "invocation.positive", raw.invocation.positive),
        negative_started=_counts(problems, "invocation.negative", raw.invocation.negative),
        quality_succeeded=_counts(problems, "quality.with_skill", raw.quality.with_skill),
        quality_without_skill=_counts(problems, "quality.without_skill", raw.quality.without_skill),
        judge_answers=tuple(
            LabelledAnswer(judge_passed=a.judge_passed, person_passed=a.person_passed)
            for a in raw.judge_calibration
        ),
    )
    if problems:
        raise InputError(source, problems)
    return record


def _counts(
    problems: list[str], section: str, cases: dict[str, _Started] | dict[str, _Succeeded]
) -> tuple[CaseCount, ...]:
    built = []
    for name, case in cases.items():
        successes = case.started if isinstance(case, _Started) else case.succeeded
        try:
            built.append(CaseCount(name, case.runs, successes))
        except ValueError as error:
            problems.append(f"{section}.{name}: {error}")
    return tuple(built)


# --- Shared -----------------------------------------------------------------------------


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe loader that rejects a key repeated in one mapping.

    PyYAML keeps the last value of a repeated key, so a case listed twice would
    silently replace the first one.
    """

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:  # noqa: FBT001, FBT002 - PyYAML's signature
        seen: set[object] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if isinstance(key, Hashable) and key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"key {key!r} appears twice", key_node.start_mark
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _load_yaml(path: Path) -> object:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise InputError(str(path), [f"cannot be read: {error.strerror}"]) from error
    except UnicodeDecodeError as error:
        raise InputError(str(path), [f"is not UTF-8 text: {error.reason}"]) from error
    try:
        return yaml.load(text, Loader=_UniqueKeyLoader)  # noqa: S506 - subclass of SafeLoader
    except yaml.YAMLError as error:
        raise InputError(str(path), [f"is not valid YAML: {error}"]) from error


def _validate[M: _Model](model: type[M], data: object, source: str) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise InputError(source, [_describe(issue) for issue in error.errors()]) from error


def _describe(issue: ErrorDetails) -> str:
    location = ".".join(str(part) for part in issue["loc"]) or "(top level)"
    hint = " (quote the value to keep it as text)" if issue["type"] == "string_type" else ""
    return f"{location}: {issue['msg']}{hint}"
