"""Write the result of an evaluation as the commented YAML of the contract.

The layout and the comments follow ``docs/skill-eval-result.example.yaml``: people
without a statistics background read this file, so every score carries a plain
English comment. PyYAML cannot emit comments, hence a small line writer; the output is
checked by loading it back in the tests.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import yaml

from skill_eval.application.report import Report
from skill_eval.domain.config import EvaluationConfig, GateName
from skill_eval.domain.estimators import CaseCount
from skill_eval.domain.intervals import Estimate, Interval
from skill_eval.domain.results import (
    Diagnostics,
    GateResult,
    InvocationResult,
    QualityResult,
    ScoreChange,
    VersionComparison,
)
from skill_eval.domain.verdicts import Verdict

_NOTE_COLUMN = 33
_MAX_DIGITS = 6
_INDENT = "  "


class _Lines:
    """Accumulate YAML lines with indentation and aligned end-of-line comments."""

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._depth = 0

    def blank(self) -> None:
        self._lines.append("")

    def comment(self, *texts: str) -> None:
        # Text from inputs (versions, warnings) must not break out of the comment.
        flat = (" ".join(text.splitlines()) for text in texts)
        self._lines.extend(f"{_INDENT * self._depth}# {text}" for text in flat)

    def entry(self, key: str, value: str | None = None, note: str | None = None) -> None:
        line = f"{_INDENT * self._depth}{key}:" + (f" {value}" if value is not None else "")
        if note:
            line = f"{line.ljust(_NOTE_COLUMN - 1)} # {note}"
        self._lines.append(line)

    @contextmanager
    def block(self, key: str, note: str | None = None) -> Iterator[None]:
        self.entry(key, note=note)
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1

    def text(self) -> str:
        return "\n".join(self._lines) + "\n"


def write_result(report: Report, path: Path) -> None:
    """Write the result file of a report."""
    path.write_text(render_result(report), encoding="utf-8")


def render_result(report: Report) -> str:
    """Render the result file of a report as text."""
    lines = _Lines()
    lines.comment(
        "skill-eval-result.yaml",
        'Result of one evaluation run. Read "summary" first; details follow.',
    )
    lines.blank()
    _summary(lines, report)
    lines.blank()
    _run(lines, report)
    lines.blank()
    level = _percent(report.config.confidence_level)
    lines.comment(
        "Each score gives a value, then a range [low, high]: the true score lies in that range",
        f"{level} times out of 100. A wide range means too few test cases to be sure.",
        "All blocking scores below are computed on the cases kept aside.",
    )
    lines.blank()
    evaluation = report.evaluation
    _invocation(lines, evaluation.invocation, report.config)
    lines.blank()
    _quality(lines, evaluation.quality, report.config)
    if evaluation.comparison is not None:
        lines.blank()
        _comparison(lines, evaluation.comparison)
    lines.blank()
    _gates(lines, evaluation.gates)
    lines.blank()
    _diagnostics(lines, evaluation.diagnostics)
    return lines.text()


def _summary(lines: _Lines, report: Report) -> None:
    summary = report.evaluation.summary
    with lines.block("summary"):
        lines.entry("releasable", _bool(summary.releasable))
        lines.comment(_summary_note(report.evaluation.gates))
        lines.entry("reason", _text(summary.reason))
        lines.entry("next_step", _text(summary.next_step))
        for warning in report.warnings:
            lines.comment(f"Warning: {warning}")


def _summary_note(gates: tuple[GateResult, ...]) -> str:
    failed = sum(gate.verdict is Verdict.FAILED for gate in gates)
    inconclusive = sum(gate.verdict is Verdict.INCONCLUSIVE for gate in gates)
    if failed:
        return "At least one score is on the wrong side of its limit."
    if inconclusive:
        return (
            f"No score is on the wrong side of its limit, but {_number_word(inconclusive)} "
            f"range{'s are' if inconclusive > 1 else ' is'} too wide to conclude."
        )
    return "Every score is on the right side of its limit, range included."


def _run(lines: _Lines, report: Report) -> None:
    config, record = report.config, report.record
    execution, trials = config.execution, config.trials
    with lines.block("run"):
        lines.entry("skill", _text(record.skill))
        lines.entry(
            "skill_version",
            _quoted(record.skill_version),
            "Hash of SKILL.md: compare results only within one version",
        )
        lines.entry("date", record.date.isoformat())
        with lines.block("settings", "Copied from skill-eval.yaml"):
            lines.entry("agent", execution.agent.value)
            lines.entry("agent_version", _quoted(execution.agent_version))
            lines.entry("model", _text(execution.model))
            lines.entry("judge_model", _text(execution.judge_model))
            lines.entry("effort", execution.effort.value)
            lines.entry(
                "trials",
                _flow(
                    invocation_per_case=str(trials.invocation_per_case),
                    quality_per_case=str(trials.quality_per_case),
                    k_pass_at=str(trials.k_pass_at),
                    k_pass_hat=str(trials.k_pass_hat),
                ),
            )
            lines.entry("confidence_level", repr(config.confidence_level))
            lines.entry("holdout_share", repr(config.holdout_share))
            lines.entry("minimum_cases", str(config.minimum_cases))
        environment = record.environment
        with lines.block("environment", "Recorded so that two results can be compared fairly"):
            lines.entry("installed_skills", str(environment.installed_skills))
            lines.entry("installed_skills_hash", _quoted(environment.installed_skills_hash))
            lines.entry("inspect_ai", _quoted(environment.inspect_ai))
            lines.entry("inspect_swe", _quoted(environment.inspect_swe))
        with lines.block("runner", "Fixed by the runner, recorded for traceability"):
            lines.entry(
                "interval_method",
                "student_t_by_case",
                "Wilson interval when every case has the same value",
            )
            lines.entry("invocation_max_turns", str(config.invocation.max_turns))
            lines.entry("quality_run_success", "all_checks")
            lines.entry("split", "by_case_name")


def _invocation(lines: _Lines, result: InvocationResult, config: EvaluationConfig) -> None:
    k = config.trials.k_pass_hat
    with lines.block("invocation"):
        lines.entry(
            "cases_kept_aside",
            _flow(positive=str(result.positive_cases), negative=str(result.negative_cases)),
        )
        lines.entry(
            "runs", _flow(positive=str(result.positive_runs), negative=str(result.negative_runs))
        )
        with lines.block("counts"):
            lines.entry(
                "started_when_expected",
                str(result.started_when_expected),
                "Positive runs where the skill started",
            )
            lines.entry("missed", str(result.missed), "Positive runs where it did not start")
            lines.entry(
                "started_by_mistake",
                str(result.started_by_mistake),
                "Negative runs where it started anyway",
            )
        lines.blank()
        lines.comment("Starts when it should: share of positive runs where the skill started.")
        lines.entry(
            "recall", _estimate(result.recall, _limit_of(config, GateName.INVOCATION_RECALL))
        )
        lines.comment(
            "Starts by mistake on similar requests: share of negative runs where the skill started."
        )
        lines.entry(
            "false_trigger_rate",
            _estimate(
                result.false_trigger_rate,
                _limit_of(config, GateName.INVOCATION_FALSE_TRIGGER_RATE),
            ),
        )
        lines.comment(
            "Share of starts that were justified. Reported only: it depends on the share of",
            "positive cases in the test set, and real usage has fewer, so real precision is lower.",
        )
        lines.entry("precision", _optional_score(result.precision))
        lines.comment(
            f"Starts every time it should, {k} uses in a row "
            "(positive cases; the gate applies here)."
        )
        lines.entry(
            "pass_hat_k",
            _estimate(result.pass_hat_k, _limit_of(config, GateName.INVOCATION_PASS_HAT_K)),
        )
        lines.comment(
            f"Never starts by mistake, {k} uses in a row (negative cases). Reported only."
        )
        lines.entry("pass_hat_k_negative", _estimate(result.pass_hat_k_negative))
        lines.comment(
            "Cases used to improve the skill. Reported only: the skill was tuned on them."
        )
        tuning = result.tuning
        lines.entry(
            "tuning",
            _flow(
                cases=_flow(
                    positive=str(tuning.positive_cases), negative=str(tuning.negative_cases)
                ),
                recall=_optional_score(tuning.recall),
                false_trigger_rate=_optional_score(tuning.false_trigger_rate),
            ),
        )


def _quality(lines: _Lines, result: QualityResult, config: EvaluationConfig) -> None:
    trials = config.trials
    with lines.block("quality"):
        lines.entry("cases_kept_aside", str(result.cases))
        lines.entry("runs", str(result.runs))
        lines.entry("successful_runs", str(result.successful_runs), "Runs where every check passed")
        lines.blank()
        lines.comment("Does the job well on a single use: what to expect from one use.")
        lines.entry(
            "pass_at_1", _estimate(result.pass_at_1, _limit_of(config, GateName.QUALITY_PASS_AT_1))
        )
        lines.comment(
            f"Does the job well at least once in {trials.k_pass_at} tries. "
            "No limit: used for diagnosis."
        )
        lines.entry("pass_at_k", _estimate(result.pass_at_k))
        lines.comment(
            f"Does the job well every time, {trials.k_pass_hat} uses in a row: "
            "what a user relying on the skill gets."
        )
        lines.entry(
            "pass_hat_k",
            _estimate(result.pass_hat_k, _limit_of(config, GateName.QUALITY_PASS_HAT_K)),
        )
        lines.comment(*_curve_note(result, trials.k_pass_hat))
        lines.entry(
            "pass_hat_k_by_uses", "[" + ", ".join(map(_score, result.pass_hat_k_by_uses)) + "]"
        )
        _without_skill(lines, result)
        if result.judge is not None:
            lines.comment(
                f"Agreement between the judge and a person on {result.judge.labelled_answers} "
                "graded answers."
            )
            kappa = (
                "null"
                if result.judge.kappa is None
                else _against(result.judge.kappa, config.quality.judge_minimum_agreement, 2)
            )
            lines.entry(
                "judge_agreement",
                _flow(
                    kappa=kappa,
                    labelled_answers=str(result.judge.labelled_answers),
                    trusted=_bool(result.judge.trusted),
                ),
            )
        lines.entry(
            "tuning",
            _flow(
                cases=str(result.tuning.cases), pass_at_1=_optional_score(result.tuning.pass_at_1)
            ),
        )


def _curve_note(result: QualityResult, k: int) -> tuple[str, ...]:
    spread_evenly = result.pass_at_1.value**k
    observed = result.pass_hat_k.value
    if result.successful_runs in (0, result.runs):
        outcome = "No run failed" if result.successful_runs else "No run succeeded"
        return (
            (
                f"The same score for 1 to {len(result.pass_hat_k_by_uses)} uses in a row. "
                f"{outcome}: nothing to locate."
            ),
        )
    reading = (
        "failures are concentrated."
        if observed > spread_evenly
        else "failures are spread over many cases."
    )
    return (
        (
            f"The same score for 1 to {len(result.pass_hat_k_by_uses)} uses in a row. "
            "A slow decline means failures sit on a few cases,"
        ),
        (
            f"which can be fixed one by one. Here {_score(observed)} at {k} uses, against "
            f"{_score(spread_evenly)} if failures were spread"
        ),
        f"evenly over all cases: {reading}",
    )


def _without_skill(lines: _Lines, result: QualityResult) -> None:
    if result.without_skill is None or result.lift is None:
        return
    lines.comment("What the skill adds: the same cases run without the skill. Reported only.")
    without = result.without_skill
    lines.entry(
        "without_skill",
        _flow(
            pass_at_1=_score(without.pass_at_1.value),
            range=_range(without.pass_at_1.interval),
            successful_runs=str(without.successful_runs),
        ),
    )
    lines.entry(
        "lift",
        _flow(value=_signed(result.lift.value, 3), range=_range(result.lift.interval, signed=True)),
        "Case by case difference, with minus without",
    )


def _comparison(lines: _Lines, comparison: VersionComparison) -> None:
    with lines.block("compared_with_previous_version"):
        lines.comment(
            "Same cases kept aside, compared case by case with the last result of version "
            f"{comparison.previous_version}."
        )
        lines.entry("previous_version", _quoted(comparison.previous_version))
        lines.entry("invocation_recall", _change(comparison.invocation_recall))
        lines.entry("quality_pass_at_1", _change(comparison.quality_pass_at_1))


def _gates(lines: _Lines, gates: tuple[GateResult, ...]) -> None:
    width = max(len(gate.name) for gate in gates) + 1
    with lines.block("gates"):
        lines.comment(
            "passed: whole range on the right side of the limit",
            "failed: whole range on the wrong side of the limit",
            "inconclusive: range straddles the limit; add test cases and run again",
        )
        for gate in gates:
            fields = {
                gate.limit.bound.value: _limit(gate.limit.value),
                "value": _against(gate.estimate.value, gate.limit.value, 3),
                "range": _range(gate.estimate.interval, limit=gate.limit.value),
                "verdict": gate.verdict.value,
            }
            if gate.reason:
                fields["reason"] = _quoted(gate.reason)
            lines.entry(gate.name, " " * (width - len(gate.name) - 1) + _flow(**fields))


def _diagnostics(lines: _Lines, diagnostics: Diagnostics) -> None:
    categories = [
        (
            "invocation_unstable",
            diagnostics.invocation_unstable,
            "Starts only part of the time: the description misses these phrasings",
        ),
        (
            "invocation_started_by_mistake",
            diagnostics.invocation_started_by_mistake,
            "Starts when it should not: the description is too broad",
        ),
        (
            "quality_never_succeeds",
            diagnostics.quality_never_succeeds,
            "Fails every time: missing capability or unclear instructions",
        ),
        (
            "quality_unstable",
            diagnostics.quality_unstable,
            "Succeeds only part of the time: ambiguous steps, consider a script",
        ),
    ]
    listed = [(key, cases, note) for key, cases, note in categories if cases]
    if not listed:
        lines.entry("diagnostics", "{}", "No case kept aside needs attention")
        return
    with lines.block("diagnostics"):
        lines.comment("Cases kept aside to look at first, with successes out of runs.")
        for key, cases, note in listed:
            with lines.block(key, note):
                for case in cases:
                    lines.entry(_text(case.name), _quoted(_ratio(case)))


# --- Scalars ----------------------------------------------------------------------------


def _flow(**fields: str) -> str:
    return "{" + ", ".join(f"{key}: {value}" for key, value in fields.items()) + "}"


def _estimate(estimate: Estimate, limit: float | None = None) -> str:
    value = _score(estimate.value) if limit is None else _against(estimate.value, limit, 3)
    return _flow(value=value, range=_range(estimate.interval, limit=limit))


def _limit_of(config: EvaluationConfig, name: GateName) -> float:
    return config.gates[name].value


def _change(change: ScoreChange) -> str:
    difference = change.difference
    return _flow(
        change=_signed(difference.value, 3),
        range=_range(difference.interval, signed=True),
        verdict=change.change.value,
    )


def _score(value: float) -> str:
    return f"{value:.3f}"


def _optional_score(value: float | None) -> str:
    return "null" if value is None else _score(value)


def _limit(value: float) -> str:
    return f"{value:.2f}" if round(value, 2) == value else repr(value)


def _range(interval: Interval, *, signed: bool = False, limit: float | None = None) -> str:
    if limit is not None:
        return f"[{_against(interval.low, limit, 2)}, {_against(interval.high, limit, 2)}]"
    return f"[{_bound(interval.low, signed=signed)}, {_bound(interval.high, signed=signed)}]"


def _bound(value: float, *, signed: bool) -> str:
    return _signed(value, 2) if signed else f"{_unsigned_zero(value, 2):.2f}"


def _against(value: float, limit: float, digits: int) -> str:
    """Round ``value`` without changing which side of ``limit`` it reads on.

    A low bound of 0.8495 shown as 0.85 next to a 0.85 minimum would contradict an
    ``inconclusive`` verdict; decimals are added until the side is kept.
    """
    for shown_digits in range(digits, _MAX_DIGITS + 1):
        shown = _unsigned_zero(value, shown_digits)
        if _side(shown, limit) == _side(value, limit):
            return f"{shown:.{shown_digits}f}"
    return repr(value)


def _side(value: float, limit: float) -> int:
    return (value > limit) - (value < limit)


def _signed(value: float, digits: int) -> str:
    return f"{_unsigned_zero(value, digits):+.{digits}f}"


def _unsigned_zero(value: float, digits: int) -> float:
    rounded = round(value, digits)
    return 0.0 if rounded == 0 else rounded


def _ratio(case: CaseCount) -> str:
    return f"{case.successes}/{case.runs}"


def _percent(level: float) -> str:
    return f"{level * 100:g}"


def _bool(value: bool) -> str:  # noqa: FBT001 - formats a value, not a flag
    return "true" if value else "false"


def _text(value: str | None) -> str:
    """Render a string as a plain scalar when YAML reads it back unchanged, else quote it."""
    if value is None:
        return "null"
    dumped: str = yaml.safe_dump(value, allow_unicode=True, width=1_000_000).strip()
    return dumped.removesuffix("\n...").strip()


def _quoted(value: str) -> str:
    """Always quote: hashes and versions must not be read back as numbers or dates."""
    return json.dumps(value, ensure_ascii=False)


def _number_word(number: int) -> str:
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    return words.get(number, str(number))
