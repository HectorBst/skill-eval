from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from skill_eval.adapters.yaml_input import (
    InputError,
    load_config,
    load_record,
    parse_config,
    parse_record,
)
from tests.support import example
from tests.support.paths import CONFIG_EXAMPLE, RECORD_EXAMPLE


def _example_config_data() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(CONFIG_EXAMPLE.read_text(encoding="utf-8"))
    return data


def _example_record_data() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(RECORD_EXAMPLE.read_text(encoding="utf-8"))
    return data


class TestConfig:
    def test_reads_the_example(self) -> None:
        assert load_config(CONFIG_EXAMPLE) == example.config()

    def test_judge_settings_are_optional(self) -> None:
        data = _example_config_data()
        del data["execution"]["judge_model"]
        del data["quality"]["judge_calibration"]
        del data["quality"]["judge_minimum_agreement"]
        config = parse_config(data)
        assert config.execution.judge_model is None
        assert config.quality.judge_calibration is None
        assert config.quality.judge_minimum_agreement == 0.60

    def test_reports_unknown_keys_such_as_typos(self) -> None:
        data = _example_config_data()
        data["gates"]["invocation_recal"] = 0.9
        with pytest.raises(InputError) as error:
            parse_config(data, source="skill-eval.yaml")
        assert "gates.invocation_recal: Extra inputs are not permitted" in error.value.problems
        assert str(error.value).startswith("skill-eval.yaml is invalid:")

    def test_asks_to_quote_versions_read_as_numbers(self) -> None:
        data = _example_config_data()
        data["execution"]["agent_version"] = 2.1
        with pytest.raises(InputError) as error:
            parse_config(data)
        assert error.value.problems == (
            (
                "execution.agent_version: Input should be a valid string "
                "(quote the value to keep it as text)"
            ),
        )

    def test_reports_domain_rules_of_every_section_at_once(self) -> None:
        data = _example_config_data()
        data["execution"]["agent_version"] = "latest"
        data["trials"]["k_pass_hat"] = 20
        data["invocation"]["max_turns"] = 0
        data["quality"]["judge_minimum_agreement"] = 0
        data["gates"]["quality_pass_at_1"] = 75
        data["confidence_level"] = 95
        with pytest.raises(InputError) as error:
            parse_config(data)
        problems = error.value.problems
        assert problems[0].startswith("confidence_level must be strictly between 0 and 1")
        assert problems[1].startswith("execution.agent_version must be an exact version")
        # k_pass_hat 20 breaks both per-case rules
        assert "trials.invocation_per_case (10) must be at least k_pass_hat (20)." in problems
        assert "trials.quality_per_case (10) must be at least k_pass_hat (20)." in problems
        assert problems[-1] == "gates.quality_pass_at_1 must lie between 0 and 1, got 75.0."
        assert len(problems) == 7

    def test_reports_unknown_agent(self) -> None:
        data = _example_config_data()
        data["execution"]["agent"] = "copilot"
        with pytest.raises(InputError, match=r"execution\.agent: Input should be"):
            parse_config(data)

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "skill-eval.yaml"
        path.write_text("", encoding="utf-8")
        with pytest.raises(InputError, match=r"\(top level\): Input should be a valid dictionary"):
            load_config(path)

    def test_malformed_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "skill-eval.yaml"
        path.write_text("execution: [unclosed", encoding="utf-8")
        with pytest.raises(InputError, match="is not valid YAML"):
            load_config(path)

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(InputError, match="cannot be read: No such file or directory"):
            load_config(tmp_path / "missing.yaml")


class TestRecord:
    def test_reads_the_example(self) -> None:
        record = load_record(RECORD_EXAMPLE)
        assert record.skill == "mon-skill"
        assert record.skill_version == "3f2a9c1"
        assert record.date == date(2026, 11, 5)
        assert record.environment.installed_skills == 34
        assert len(record.positive_started) == 50
        assert len(record.negative_started) == 50
        assert len(record.quality_succeeded) == 38
        assert len(record.quality_without_skill) == 15
        assert len(record.judge_answers) == 24

    def test_without_skill_and_calibration_are_optional(self) -> None:
        data = _example_record_data()
        del data["quality"]["without_skill"]
        del data["judge_calibration"]
        record = parse_record(data)
        assert record.quality_without_skill == ()
        assert record.judge_answers == ()

    def test_reports_impossible_counts_with_their_case(self) -> None:
        data = _example_record_data()
        data["invocation"]["positive"]["pos-03"] = {"runs": 10, "started": 12}
        data["quality"]["with_skill"]["q-01"] = {"runs": 0, "succeeded": 0}
        with pytest.raises(InputError) as error:
            parse_record(data)
        assert error.value.problems == (
            "invocation.positive.pos-03: Case 'pos-03' has 12 successes for 10 runs.",
            "quality.with_skill.q-01: Case 'q-01' needs at least one run, got 0.",
        )

    def test_rejects_unquoted_numeric_hash(self) -> None:
        data = _example_record_data()
        data["skill_version"] = 1234567
        with pytest.raises(InputError, match="skill_version: Input should be a valid string"):
            parse_record(data)


class TestStrictness:
    def test_rejects_repeated_keys(self, tmp_path: Path) -> None:
        text = RECORD_EXAMPLE.read_text(encoding="utf-8")
        path = tmp_path / "record.yaml"
        path.write_text(
            text.replace(
                "    pos-05: {runs: 10, started: 10}\n", "    pos-05: {runs: 10, started: 10}\n" * 2
            ),
            encoding="utf-8",
        )
        with pytest.raises(InputError, match="key 'pos-05' appears twice"):
            load_record(path)

    def test_rejects_non_utf8_files(self, tmp_path: Path) -> None:
        path = tmp_path / "record.yaml"
        path.write_bytes("skill: café\n".encode("latin-1"))
        with pytest.raises(InputError, match="is not UTF-8 text"):
            load_record(path)

    @pytest.mark.parametrize("value", [True, "0.95"])
    def test_rejects_booleans_and_strings_for_numbers(self, value: object) -> None:
        data = _example_config_data()
        data["confidence_level"] = value
        with pytest.raises(InputError, match="confidence_level: Input should be a valid number"):
            parse_config(data)

    def test_accepts_integers_for_limits(self) -> None:
        data = _example_config_data()
        data["gates"]["invocation_recall"] = 1
        assert parse_config(data).gates.limits  # 1 is a valid limit

    @pytest.mark.parametrize(
        ("field", "value"),
        [("skill", "Mon Skill"), ("skill_version", "3f2a9c1\n"), ("skill_version", "xyz")],
    )
    def test_rejects_malformed_identifiers(self, field: str, value: str) -> None:
        data = _example_record_data()
        data[field] = value
        with pytest.raises(InputError, match=f"{field}: String should match pattern"):
            parse_record(data)
