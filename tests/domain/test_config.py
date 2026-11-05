from dataclasses import replace
from pathlib import PurePath

import pytest

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
from skill_eval.domain.verdicts import Bound

GATE_VALUES = {
    GateName.INVOCATION_RECALL: 0.85,
    GateName.INVOCATION_FALSE_TRIGGER_RATE: 0.10,
    GateName.INVOCATION_PASS_HAT_K: 0.50,
    GateName.QUALITY_PASS_AT_1: 0.75,
    GateName.QUALITY_PASS_HAT_K: 0.60,
}


def _execution(**changes: object) -> Execution:
    values: dict[str, object] = {
        "agent": Agent.CLAUDE_CODE,
        "agent_version": "2.1.309",
        "model": "claude-sonnet-5-5",
        "judge_model": "claude-haiku-5-5",
        "effort": Effort.MEDIUM,
        "installed_skills": PurePath("skills"),
    }
    values.update(changes)
    return Execution(**values)  # type: ignore[arg-type]


def _config(**changes: object) -> EvaluationConfig:
    values: dict[str, object] = {
        "execution": _execution(),
        "trials": _trials(10, 10, 3, 5),
        "confidence_level": 0.95,
        "holdout_share": 0.4,
        "minimum_cases": 15,
        "invocation": InvocationSettings(
            max_turns=3, positive_cases=PurePath("pos"), negative_cases=PurePath("neg")
        ),
        "quality": _quality(0.6),
        "gates": Gates.from_values(GATE_VALUES),
    }
    values.update(changes)
    return EvaluationConfig(**values)  # type: ignore[arg-type]


def _trials(invocation: int, quality: int, k_pass_at: int, k_pass_hat: int) -> Trials:
    return Trials(
        invocation_per_case=invocation,
        quality_per_case=quality,
        k_pass_at=k_pass_at,
        k_pass_hat=k_pass_hat,
    )


def _quality(agreement: float) -> QualitySettings:
    return QualitySettings(
        cases=PurePath("q"),
        measure_lift=True,
        judge_calibration=PurePath("q/judge"),
        judge_minimum_agreement=agreement,
    )


def _problems(error: pytest.ExceptionInfo[ConfigurationError]) -> tuple[str, ...]:
    return error.value.problems


class TestExecution:
    def test_accepts_an_exact_version(self) -> None:
        assert _execution().agent_version == "2.1.309"

    @pytest.mark.parametrize("version", ["latest", "stable", "auto", "2.1", "v2.1.309", ""])
    def test_rejects_moving_or_partial_versions(self, version: str) -> None:
        with pytest.raises(ConfigurationError, match="exact version"):
            _execution(agent_version=version)

    def test_reports_every_problem_at_once(self) -> None:
        with pytest.raises(ConfigurationError) as error:
            _execution(agent_version="latest", model="", judge_model="")
        assert len(_problems(error)) == 3
        assert "- execution.model must name the tested model." in str(error.value)

    def test_judge_model_is_optional(self) -> None:
        assert _execution(judge_model=None).judge_model is None


class TestTrials:
    def test_accepts_the_example(self) -> None:
        assert _trials(10, 10, 3, 5).warnings() == []

    def test_k_values_must_be_at_least_two(self) -> None:
        with pytest.raises(ConfigurationError) as error:
            _trials(10, 10, 1, 1)
        assert _problems(error) == (
            "trials.k_pass_at must be at least 2, got 1.",
            "trials.k_pass_hat must be at least 2, got 1.",
        )

    def test_each_per_case_value_must_reach_k_pass_hat(self) -> None:
        with pytest.raises(ConfigurationError) as error:
            _trials(4, 4, 3, 5)
        assert _problems(error) == (
            "trials.invocation_per_case (4) must be at least k_pass_hat (5).",
            "trials.quality_per_case (4) must be at least k_pass_hat (5).",
        )

    def test_quality_per_case_must_reach_k_pass_at(self) -> None:
        expected = r"quality_per_case \(5\) must be at least k_pass_at \(6\)"
        with pytest.raises(ConfigurationError, match=expected):
            _trials(10, 5, 6, 5)

    def test_warns_below_twice_k_pass_hat(self) -> None:
        assert _trials(10, 6, 3, 5).warnings() == [
            (
                "trials.quality_per_case (6) is below twice k_pass_hat (10): "
                "pass^k per case will be coarse."
            )
        ]


class TestSections:
    def test_invocation_needs_a_turn_and_distinct_folders(self) -> None:
        with pytest.raises(ConfigurationError) as error:
            InvocationSettings(
                max_turns=0, positive_cases=PurePath("cases"), negative_cases=PurePath("cases")
            )
        assert len(_problems(error)) == 2

    @pytest.mark.parametrize("agreement", [0.0, -0.2, 1.1])
    def test_judge_agreement_must_be_reachable(self, agreement: float) -> None:
        with pytest.raises(ConfigurationError, match="judge_minimum_agreement"):
            _quality(agreement)


class TestGates:
    def test_bounds_are_fixed_per_gate(self) -> None:
        gates = Gates.from_values(GATE_VALUES)
        assert gates[GateName.INVOCATION_RECALL].bound is Bound.MINIMUM
        assert gates[GateName.INVOCATION_FALSE_TRIGGER_RATE].bound is Bound.MAXIMUM
        assert list(gates.limits) == list(GateName)

    def test_reports_missing_and_out_of_range_gates(self) -> None:
        values = dict(GATE_VALUES)
        del values[GateName.QUALITY_PASS_HAT_K]
        values[GateName.INVOCATION_RECALL] = 85.0
        with pytest.raises(ConfigurationError) as error:
            Gates.from_values(values)
        assert _problems(error) == (
            "gates.quality_pass_hat_k is missing.",
            "gates.invocation_recall must lie between 0 and 1, got 85.0.",
        )


class TestEvaluationConfig:
    def test_accepts_the_example(self) -> None:
        config = _config()
        assert config.warnings() == []
        assert replace(config, minimum_cases=20).minimum_cases == 20

    def test_rejects_invalid_shared_settings(self) -> None:
        with pytest.raises(ConfigurationError) as error:
            _config(confidence_level=95, holdout_share=0.0, minimum_cases=1)
        assert len(_problems(error)) == 3

    def test_forwards_trial_warnings(self) -> None:
        assert len(_config(trials=_trials(5, 5, 3, 5)).warnings()) == 2
