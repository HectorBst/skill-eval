"""Hexagonal boundaries, checked on the import statements of each layer."""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "skill_eval"

# What each layer may not import, directly or through a submodule.
FORBIDDEN = {
    "domain": ("skill_eval.application", "skill_eval.adapters", "skill_eval.cli", "yaml",
               "pydantic", "inspect_ai", "inspect_swe", "pathlib.Path"),
    "application": ("skill_eval.adapters", "skill_eval.cli", "yaml", "pydantic"),
    "adapters": ("skill_eval.cli",),
}  # fmt: skip


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def _modules(layer: str) -> list[Path]:
    return sorted((PACKAGE / layer).rglob("*.py"))


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_respects_its_boundaries(layer: str) -> None:
    violations = [
        f"{path.relative_to(PACKAGE)} imports {name}"
        for path in _modules(layer)
        for name in sorted(_imports(path))
        if any(name == banned or name.startswith(f"{banned}.") for banned in FORBIDDEN[layer])
    ]
    assert violations == []


def test_every_layer_has_modules() -> None:
    assert all(_modules(layer) for layer in FORBIDDEN)
