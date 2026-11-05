"""Command-line entry point.

``skill-eval check-config`` validates a ``skill-eval.yaml`` file before anything runs.
``skill-eval report`` turns recorded per-case counts into the result file, and exits
with a code that follows the verdict (see ``Outcome``), so that a CI job can block on it.
"""

import argparse
import sys
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path

from skill_eval import __version__
from skill_eval.adapters.yaml_input import InputError, load_config, load_record
from skill_eval.adapters.yaml_result import render_result
from skill_eval.application.report import Outcome, ReportError, build_report, outcome_of
from skill_eval.domain.evaluation import EvaluationError

Handler = Callable[[argparse.Namespace], Outcome]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return the process exit code."""
    args = _parser().parse_args(argv)
    handler: Handler = args.handler
    try:
        return int(handler(args))
    except (InputError, EvaluationError, ReportError) as error:
        _error(f"error: {error}")
        return int(Outcome.INVALID_INPUT)
    except Exception:  # noqa: BLE001 - a crash must not exit with 1, which means "a gate failed"
        _error(traceback.format_exc().rstrip())
        return int(Outcome.INTERNAL_ERROR)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill-eval",
        description="Check an agent skill before sharing it.",
        epilog=(
            "Exit codes: 0 releasable, 1 a gate failed, 2 usage error, "
            "3 inconclusive, 4 invalid input, 5 internal error."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(required=True, metavar="command")

    check = commands.add_parser("check-config", help="validate a skill-eval.yaml file")
    check.add_argument("config", type=Path, help="path to skill-eval.yaml")
    check.set_defaults(handler=_check_config)

    report = commands.add_parser("report", help="write the result of recorded trials")
    report.add_argument("--config", type=Path, required=True, help="path to skill-eval.yaml")
    report.add_argument("--record", type=Path, required=True, help="per-case counts of the run")
    report.add_argument(
        "--previous", type=Path, help="per-case counts of the last run of a previous version"
    )
    report.add_argument("--output", type=Path, help="result file to write (default: stdout)")
    report.set_defaults(handler=_report)
    return parser


def _check_config(args: argparse.Namespace) -> Outcome:
    config = load_config(args.config)
    for warning in config.warnings():
        _error(f"warning: {warning}")
    sys.stdout.write(f"{args.config}: valid\n")
    return Outcome.RELEASABLE


def _report(args: argparse.Namespace) -> Outcome:
    config = load_config(args.config)
    record = load_record(args.record)
    previous = load_record(args.previous) if args.previous else None
    report = build_report(config, record, previous)
    text = render_result(report)
    if args.output:
        try:
            args.output.write_text(text, encoding="utf-8")
        except OSError as error:
            raise InputError(str(args.output), [f"cannot be written: {error.strerror}"]) from error
    else:
        sys.stdout.write(text)
    for warning in report.warnings:
        _error(f"warning: {warning}")
    summary = report.evaluation.summary
    verdict = "releasable" if summary.releasable else "not releasable"
    _error(f"{record.skill} {record.skill_version}: {verdict} ({summary.reason})")
    return outcome_of(report)


def _error(message: str) -> None:
    sys.stderr.write(message + "\n")
