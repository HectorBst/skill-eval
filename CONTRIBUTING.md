# Contributing

## Workflow

1. Open or pick an issue; one pull request solves one issue.
2. Branch from `main` with a typed prefix: `feat/`, `fix/`, `docs/`, `chore/`, `ci/`,
   `refactor/`, `test/`.
3. Keep the history linear: rebase on `main`, never merge `main` into your branch.
4. Title the pull request as a [Conventional Commit](https://www.conventionalcommits.org/)
   (`feat(domain): add pass^k estimator`): with a squash merge, the title becomes the
   commit on `main`.
5. Merge by **squash** (default) or **rebase** when every commit is meaningful on its own.
   Merge commits are disabled.

Stacked pull requests are fine: target the branch below, and GitHub retargets the
next one to `main` when the lower one is merged and its branch deleted.

## Local checks

```bash
uv run pre-commit install --install-hooks   # once
uv run pre-commit run --all-files           # what CI runs, minus the test matrix
uv run pytest                               # tests and the 85 % coverage gate
uv run diff-cover coverage.xml --compare-branch=origin/main --fail-under=75
```

The gitleaks hook builds gitleaks with Go; pre-commit downloads a Go toolchain when none
is installed. Update hook versions with `uv run pre-commit autoupdate`.

## Code rules

- Code, comments, docstrings, logs and exception messages in English.
- Domain code (`src/skill_eval/domain`) imports nothing from `application`, `adapters`
  or any I/O library; it is tested without agents, network or files.
- Every public function and class has a docstring; comments only explain an intent or
  a constraint the code cannot show.
- Inject a dependency only when a test or a second implementation needs it.
- Each statistic in the domain is tested against figures that can be recomputed by
  hand, starting with those of `docs/skill-eval-result.example.yaml`.
