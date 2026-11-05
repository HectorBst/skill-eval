"""Agreement between the judge model and a person on the same graded answers."""

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class LabelledAnswer:
    """One answer graded by both the judge and a person.

    Attributes:
        judge_passed: Grade given by the judge model.
        person_passed: Grade given by the person, taken as the reference.
    """

    judge_passed: bool
    person_passed: bool


def cohen_kappa(answers: Sequence[LabelledAnswer]) -> float | None:
    """Compute Cohen's kappa, the agreement beyond chance between judge and person.

    Raw agreement overstates real agreement when one grade dominates; kappa removes the
    agreement expected by chance from the grade frequencies of each rater.

    Args:
        answers: Answers graded by both raters.

    Returns:
        Kappa between -1 and 1, or None when chance agreement is total (both raters
        always give the same single grade), in which case agreement cannot be measured.

    Raises:
        ValueError: If no answer is given.
    """
    if not answers:
        raise ValueError("Cohen's kappa needs at least one labelled answer.")
    total = len(answers)
    observed = Fraction(sum(a.judge_passed == a.person_passed for a in answers), total)
    judge_pass = Fraction(sum(a.judge_passed for a in answers), total)
    person_pass = Fraction(sum(a.person_passed for a in answers), total)
    expected = judge_pass * person_pass + (1 - judge_pass) * (1 - person_pass)
    if expected == 1:
        return None
    return float((observed - expected) / (1 - expected))
