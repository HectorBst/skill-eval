import importlib
from importlib.metadata import PackageNotFoundError

import pytest

import skill_eval


def test_version_is_exposed() -> None:
    assert skill_eval.__version__ == "0.1.0"


def test_version_falls_back_when_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_name: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr("importlib.metadata.version", missing)
    try:
        assert importlib.reload(skill_eval).__version__ == "0.0.0+unknown"
    finally:
        monkeypatch.undo()
        importlib.reload(skill_eval)
