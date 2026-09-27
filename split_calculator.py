"""
split_calculator.py - Turn an expense total into per-member amounts owed.

Rules:
  * No standard-library imports (no math). Only //, %, *, + and friends.
  * All money is integer paise. Every function returns a dict
    {participant: paise_owed} whose values add up to EXACTLY the total -
    no paisa is ever created or lost.

Rounding strategy (the "largest remainder" method):
  1. Give everyone the floor of their fair share using //.
  2. The paise left over (found with %) are handed out one at a time.
     For an equal split everyone has the same fractional claim, so the
     leftovers simply go to the first few members in list order:
         10000 among 3  ->  3334, 3333, 3333
     For weighted splits (percentage / shares) the leftovers go first to
     whoever was rounded down the most, with list order breaking ties.
"""

from models import SPLIT_EQUAL, SPLIT_EXACT, SPLIT_PERCENTAGE, SPLIT_SHARES
from validator import (ValidationError, FULL_PERCENT, format_hundredths,
                       validate_exact_split)


# ----------------------------------------------------------------------
# Input checks shared by every split type
# ----------------------------------------------------------------------

def _is_int(value):
    # bool is a subclass of int; True must never count as 1 paisa or 1 share.
    return isinstance(value, int) and not isinstance(value, bool)


def _check_total(total_paise):
    if not _is_int(total_paise):
        raise ValidationError("Total must be an integer number of paise")
    if total_paise <= 0:
        raise ValidationError("Total must be greater than zero")


def _check_participants(participants):
    if len(participants) == 0:
        raise ValidationError("Split must include at least one person")
    seen = {}
    for person in participants:
        if person in seen:
            raise ValidationError(repr(person) + " appears more than once in the split")
        seen[person] = True


def _values_for(participants, values, label):
    """
    Line up per-person values with `participants`.

    `values` may be a dict {participant: value} or a list/tuple in the same
    order as `participants`. Returns a list aligned with `participants`.
    """
    if isinstance(values, dict):
        aligned = []
        for person in participants:
            if person not in values:
                raise ValidationError("Missing " + label + " for " + repr(person))
            aligned.append(values[person])
        for person in values:
            if person not in participants:
                raise ValidationError(repr(person) + " has a " + label
                                      + " but is not in the split")
        return aligned

    if len(values) != len(participants):
        raise ValidationError("Expected " + str(len(participants)) + " " + label
                              + " values, got " + str(len(values)))
    return list(values)


def _allocate(total_paise, participants, weights):
    """
    Split `total_paise` in proportion to integer `weights` (largest remainder).

    For person i:  exact share = total * w_i / W
        floor part = (total * w_i) // W
        leftover   = (total * w_i) %  W   <- how much was rounded away
    The paise still unassigned after flooring go one each to the people with
    the biggest leftover. sorted() is stable, so equal leftovers keep list order.
    """
    weight_sum = 0
    for w in weights:
        weight_sum += w

    result = {}
    assigned = 0
    leftovers = []
    for index in range(len(participants)):
        scaled = total_paise * weights[index]
        floor_part = scaled // weight_sum
        result[participants[index]] = floor_part
        assigned += floor_part
        leftovers.append((scaled % weight_sum, index))

    remaining = total_paise - assigned   # always < number of participants
    ranked = sorted(leftovers, key=lambda item: -item[0])
    for position in range(remaining):
        person = participants[ranked[position][1]]
        result[person] += 1
    return result


# ----------------------------------------------------------------------
# The four split types
# ----------------------------------------------------------------------

def split_equal(total_paise, participants):
    """
    Divide the total evenly. The first (total % n) people pay one extra paisa.

        split_equal(10000, ["A", "B", "C"]) -> {"A": 3334, "B": 3333, "C": 3333}
    """
    _check_total(total_paise)
    _check_participants(participants)

    count = len(participants)
    base = total_paise // count
    extra = total_paise % count

    result = {}
    for index in range(count):
        result[participants[index]] = base + (1 if index < extra else 0)
    return result


def split_exact(total_paise, participants, amounts):
    """
    Each person owes a stated amount in paise; the amounts must sum to the total.

        split_exact(10000, ["A", "B"], {"A": 7000, "B": 3000}) -> {"A": 7000, "B": 3000}
    """
    _check_total(total_paise)
    _check_participants(participants)
    aligned = _values_for(participants, amounts, "amount")

    result = {}
    for index in range(len(participants)):
        result[participants[index]] = aligned[index]
    validate_exact_split(total_paise, result)
    return result


def split_percentage(total_paise, participants, percentages):
    """
    Split by percentage. Percentages are integers in hundredths of a percent
    (as produced by validator.parse_percentage): 50% -> 5000, 33.33% -> 3333.
    They must add up to 10000 (i.e. 100%).

        split_percentage(10000, ["A", "B", "C"], [3333, 3333, 3334])
            -> {"A": 3333, "B": 3333, "C": 3334}
    """
    _check_total(total_paise)
    _check_participants(participants)
    aligned = _values_for(participants, percentages, "percentage")

    running = 0
    for index in range(len(aligned)):
        value = aligned[index]
        if not _is_int(value):
            raise ValidationError("Percentage for " + repr(participants[index])
                                  + " must be an integer in hundredths (e.g. 50% -> 5000)")
        if value < 0:
            raise ValidationError("Percentage for " + repr(participants[index])
                                  + " cannot be negative")
        running += value
    if running != FULL_PERCENT:
        raise ValidationError("Percentages must add up to 100, but they add up to "
                              + format_hundredths(running))

    return _allocate(total_paise, participants, aligned)


def split_shares(total_paise, participants, shares):
    """
    Split by whole-number shares (e.g. a couple counts as 2, a single as 1).
    A share of 0 means the person is listed but owes nothing.

        split_shares(10000, ["A", "B", "C"], [2, 1, 1])
            -> {"A": 5000, "B": 2500, "C": 2500}
    """
    _check_total(total_paise)
    _check_participants(participants)
    aligned = _values_for(participants, shares, "share")

    total_shares = 0
    for index in range(len(aligned)):
        value = aligned[index]
        if not _is_int(value):
            raise ValidationError("Shares for " + repr(participants[index])
                                  + " must be a whole number")
        if value < 0:
            raise ValidationError("Shares for " + repr(participants[index])
                                  + " cannot be negative")
        total_shares += value
    if total_shares == 0:
        raise ValidationError("At least one person must have a share greater than zero")

    return _allocate(total_paise, participants, aligned)


# ----------------------------------------------------------------------
# Single entry point for the UI layer
# ----------------------------------------------------------------------

def calculate_split(split_type, total_paise, participants, values=None):
    """
    Dispatch to the right calculator by split type name.
    `values` is ignored for equal splits and required for the others.
    """
    if split_type == SPLIT_EQUAL:
        return split_equal(total_paise, participants)
    if values is None:
        raise ValidationError("A " + repr(split_type) + " split needs per-person values")
    if split_type == SPLIT_EXACT:
        return split_exact(total_paise, participants, values)
    if split_type == SPLIT_PERCENTAGE:
        return split_percentage(total_paise, participants, values)
    if split_type == SPLIT_SHARES:
        return split_shares(total_paise, participants, values)
    raise ValidationError("Unknown split type: " + repr(split_type))
