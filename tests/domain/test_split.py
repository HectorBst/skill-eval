import pytest
from hypothesis import given
from hypothesis import strategies as st

from skill_eval.domain.estimators import CaseCount
from skill_eval.domain.split import holdout_position, is_kept_aside, split_cases

printable = st.characters(categories=("L", "N", "P", "S"))
names = st.lists(st.text(printable, min_size=1, max_size=20), unique=True, max_size=60)


def _cases(case_names: list[str]) -> list[CaseCount]:
    return [CaseCount(name, 10, 5) for name in case_names]


def test_position_is_fixed_and_documented() -> None:
    # Frozen values: changing the hash would silently move cases between parts.
    assert holdout_position("pos-english-12") == pytest.approx(0.254727125, abs=1e-9)
    assert holdout_position("neg-email-08") == pytest.approx(0.784931885, abs=1e-9)
    assert is_kept_aside("pos-english-12", 0.4)
    assert not is_kept_aside("neg-email-08", 0.4)


def test_split_keeps_order_and_partitions() -> None:
    cases = _cases([f"case-{i:02d}" for i in range(50)])
    split = split_cases(cases, 0.4)
    assert len(split.kept_aside) + len(split.tuning) == 50
    assert {c.name for c in split.kept_aside}.isdisjoint({c.name for c in split.tuning})
    assert list(split.kept_aside) == [c for c in cases if c in split.kept_aside]


def test_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError, match="unique within a set: dup"):
        split_cases(_cases(["dup", "other", "dup"]), 0.4)


@pytest.mark.parametrize("share", [0.0, 1.0])
def test_rejects_degenerate_share(share: float) -> None:
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        split_cases(_cases(["a"]), share)


@given(names, names)
def test_adding_cases_never_moves_existing_ones(existing: list[str], added: list[str]) -> None:
    before = split_cases(_cases(existing), 0.4)
    after = split_cases(_cases(existing + [n for n in added if n not in existing]), 0.4)
    kept_before = {c.name for c in before.kept_aside}
    kept_after = {c.name for c in after.kept_aside}
    assert kept_before == kept_after & set(existing)


@given(st.text(min_size=1))
def test_position_is_in_unit_interval(name: str) -> None:
    assert 0.0 <= holdout_position(name) < 1.0


def test_composed_and_decomposed_spellings_share_a_position() -> None:
    composed, decomposed = "q-r\u00e9sum\u00e9", "q-re\u0301sume\u0301"
    assert composed != decomposed
    assert holdout_position(composed) == holdout_position(decomposed)
