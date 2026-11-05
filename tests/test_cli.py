import runpy
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from skill_eval.cli import main
from tests.support.paths import (
    CONFIG_EXAMPLE,
    RECORD_EXAMPLE,
    RECORD_PREVIOUS,
    RENAMED_IN_RECORD,
    RESULT_EXAMPLE,
)


def _expected_result() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(RESULT_EXAMPLE.read_text(encoding="utf-8"))
    for category in data["diagnostics"].values():
        for old, new in RENAMED_IN_RECORD.items():
            if old in category:
                category[new] = category.pop(old)
    return data


def _report_args(output: Path | None = None) -> list[str]:
    args = ["report", "--config", str(CONFIG_EXAMPLE), "--record", str(RECORD_EXAMPLE)]
    args += ["--previous", str(RECORD_PREVIOUS)]
    return [*args, "--output", str(output)] if output else args


def test_report_reproduces_the_example_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "skill-eval-result.yaml"
    assert main(_report_args(output)) == 3
    assert yaml.safe_load(output.read_text(encoding="utf-8")) == _expected_result()
    assert capsys.readouterr().err == ("mon-skill 3f2a9c1: not releasable (3 gates inconclusive)\n")


def test_report_writes_to_stdout_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(_report_args()) == 3
    assert yaml.safe_load(capsys.readouterr().out) == _expected_result()


def test_check_config(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check-config", str(CONFIG_EXAMPLE)]) == 0
    assert capsys.readouterr().out == f"{CONFIG_EXAMPLE}: valid\n"


def test_check_config_prints_warnings(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = CONFIG_EXAMPLE.read_text(encoding="utf-8")
    path = tmp_path / "skill-eval.yaml"
    path.write_text(text.replace("quality_per_case: 10", "quality_per_case: 6"), encoding="utf-8")
    assert main(["check-config", str(path)]) == 0
    assert "warning: trials.quality_per_case (6) is below twice" in capsys.readouterr().err


def test_invalid_input_exits_with_4(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "skill-eval.yaml"
    path.write_text("confidence_level: 2\n", encoding="utf-8")
    assert main(["check-config", str(path)]) == 4
    assert capsys.readouterr().err.startswith(f"error: {path} is invalid:")


def test_usage_error_exits_with_2() -> None:
    with pytest.raises(SystemExit) as error:
        main(["report"])
    assert error.value.code == 2


def test_module_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["skill-eval", "check-config", str(CONFIG_EXAMPLE)])
    with pytest.raises(SystemExit) as error:
        runpy.run_module("skill_eval", run_name="__main__")
    assert error.value.code == 0


def test_report_prints_warnings(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    record = yaml.safe_load(RECORD_EXAMPLE.read_text(encoding="utf-8"))
    del record["quality"]["without_skill"]
    path = tmp_path / "record.yaml"
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    args = ["report", "--config", str(CONFIG_EXAMPLE), "--record", str(path)]
    assert main([*args, "--output", str(tmp_path / "result.yaml")]) == 3
    assert "warning: quality.measure_lift is set" in capsys.readouterr().err


def test_unwritable_output_exits_with_4(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(_report_args(tmp_path / "missing" / "result.yaml")) == 4
    assert "cannot be written: No such file or directory" in capsys.readouterr().err


def test_crash_exits_with_5_not_with_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def crash(*_args: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("skill_eval.cli.build_report", crash)
    assert main(_report_args()) == 5
    assert "RuntimeError: boom" in capsys.readouterr().err
