"""Paths of the contract files shipped in docs/."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_EXAMPLE = ROOT / "docs" / "skill-eval.example.yaml"
RESULT_EXAMPLE = ROOT / "docs" / "skill-eval-result.example.yaml"
RECORD_EXAMPLE = ROOT / "docs" / "skill-eval-record.example.yaml"
RECORD_PREVIOUS = ROOT / "tests" / "fixtures" / "record-previous-version.yaml"

# Example case names that the split by name puts among tuning cases, replaced in the
# example record by close names that it keeps aside.
RENAMED_IN_RECORD = {
    "neg-email-08": "neg-email-04",
    "q-long-doc-09": "q-long-doc-04",
    "q-incomplete-input-04": "q-incomplete-input-01",
}
