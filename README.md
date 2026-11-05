# skill-eval

Checks an agent skill (a `SKILL.md` folder) before it is shared. Two questions are
measured separately:

- **invocation**: does the skill start when it should, and only then?
- **quality**: once started, does it do the job well?

Each test case runs several times in fresh conversations. Scores are given as ranges
computed case by case, and each gate returns one of three verdicts: `passed`, `failed`
or `inconclusive`. Only cases kept aside (never used to tune the skill) decide.
Execution is meant to run on [Inspect](https://inspect.aisi.org.uk/) and
[Inspect SWE](https://meridianlabs-ai.github.io/inspect_swe/).

**Status**: pre-alpha. The method is fixed (see `docs/reprise/`), the scoping note is
under review (`docs/cadrage.md`), no trial runner exists yet.

## Contract

| File | Role |
|---|---|
| [`docs/skill-eval.example.yaml`](docs/skill-eval.example.yaml) | Input: what to run and the gates to meet |
| [`docs/skill-eval-result.example.yaml`](docs/skill-eval-result.example.yaml) | Output: scores, ranges, verdicts, diagnostics |

## Layout

Hexagonal: the evaluation method lives in a pure domain that is tested without any
agent, network or file.

```
src/skill_eval/
  domain/        pure method: estimators, intervals, verdicts, configuration rules
  application/   use cases and the ports they need
  adapters/      YAML files, Inspect (later), CI reports (later)
  cli.py         command-line entry point
```

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pre-commit install --install-hooks
uv run pytest
```

Quality gates, enforced by pre-commit and CI:

| Check | Tool | Limit |
|---|---|---|
| Lint and format | ruff | no finding |
| Types | mypy `--strict` | no error |
| Cognitive complexity | complexipy | 15 per function |
| Coverage, whole code base | pytest-cov | 85 % lines and branches |
| Coverage, lines changed by a pull request | diff-cover | 75 % |
| Secrets | gitleaks | no finding, whole history |
| Known vulnerabilities | pip-audit | none in locked dependencies |

Pull requests are merged by squash or rebase only, never by merge commit. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).
