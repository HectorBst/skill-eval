"""Split of test cases between cases used for tuning and cases kept aside.

Each case is assigned from its name alone, so adding, removing or reordering other
cases never moves it: a case used to tune the skill can never become a case that
judges it. The price is that the number of cases kept aside varies around
``holdout_share`` times the number of cases instead of matching it exactly.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol
from unicodedata import normalize

_POSITION_BYTES = 8
_POSITION_RANGE = 1 << (8 * _POSITION_BYTES)


class Named(Protocol):
    """Anything identified by a case name."""

    @property
    def name(self) -> str:
        """Case name, unique within its set."""
        ...


@dataclass(frozen=True, slots=True)
class Split[T: Named]:
    """Cases of one set, divided between tuning and decision.

    Attributes:
        kept_aside: Cases that decide the verdict; never used to improve the skill.
        tuning: Cases the skill may be improved on.
    """

    kept_aside: tuple[T, ...]
    tuning: tuple[T, ...]


def holdout_position(name: str) -> float:
    """Map a case name to a fixed position in ``[0, 1)``, uniform over names.

    The name is normalized to Unicode NFC first: macOS stores file names decomposed
    (NFD), and two spellings of one accented name must not land on different sides.
    """
    digest = sha256(normalize("NFC", name).encode("utf-8")).digest()[:_POSITION_BYTES]
    return int.from_bytes(digest, "big") / _POSITION_RANGE


def is_kept_aside(name: str, share: float) -> bool:
    """Tell whether a case is kept aside for a given holdout share."""
    return holdout_position(name) < share


def split_cases[T: Named](cases: Iterable[T], share: float) -> Split[T]:
    """Divide the cases of one set, keeping their order within each part.

    Args:
        cases: Cases of one set (positive, negative or quality), with unique names.
        share: Holdout share, strictly between 0 and 1.

    Raises:
        ValueError: If the share is invalid or two cases share a name.
    """
    if not 0.0 < share < 1.0:
        raise ValueError(f"Holdout share must be strictly between 0 and 1, got {share}.")
    collected = list(cases)
    duplicates = sorted(name for name, n in Counter(c.name for c in collected).items() if n > 1)
    if duplicates:
        raise ValueError(f"Case names must be unique within a set: {', '.join(duplicates)}.")
    kept_aside = tuple(case for case in collected if is_kept_aside(case.name, share))
    tuning = tuple(case for case in collected if not is_kept_aside(case.name, share))
    return Split(kept_aside, tuning)
