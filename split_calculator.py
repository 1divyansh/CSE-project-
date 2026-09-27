"""
split_calculator.py - Work out how much each member owes for an expense.

No imports beyond our own modules: only //, %, * and + are used.
Money is integer paise, and every function returns a dict
{member_name: paise_owed} whose values add up to EXACTLY the total.

Rounding rule (no paisa is ever dropped):
  1. Everyone gets the rounded-down amount, found with //.
  2. The paise left over, found with %, are handed out one at a time
     to the first few members in the list.

      split_equal(10000, ["Asha", "Ravi", "Meera"])
      10000 // 3 = 3333 each,  10000 % 3 = 1 paisa left over
      -> {"Asha": 3334, "Ravi": 3333, "Meera": 3333}
"""

from models import SPLIT_EQUAL, SPLIT_EXACT, SPLIT_PERCENTAGE, SPLIT_SHARES
from validator import ValidationError, validate_exact_split, validate_percentages


# ----------------------------------------------------------------------
# Checks shared by every split
# ----------------------------------------------------------------------

def _check_inputs(total, members):
    if total <= 0:
        raise ValidationError("Total must be greater than zero")
    if len(members) == 0:
        raise ValidationError("The split needs at least one person")
    seen = []
    for name in members:
        if name in seen:
            raise ValidationError(name + " is listed twice in the split")
        seen.append(name)


def _check_values_match(members, values, label):
    """Every member needs exactly one value, and no one else may have one."""
    for name in members:
        if name not in values:
            raise ValidationError("Missing " + label + " for " + name)
    for name in values:
        if name not in members:
            raise ValidationError(name + " has a " + label + " but is not in the split")


def _split_by_weights(total, members, weights):
    """
    Split `total` in proportion to whole-number `weights` {name: weight}.

    Each person first gets (total * weight) // sum_of_weights. Rounding down
    leaves a few paise unassigned, and those go one each to the first
    members in the list who were actually rounded down, i.e. whose
    (total * weight) % sum_of_weights is not 0. Anyone whose share came out
    exact (including a weight of 0) never receives a stray paisa, and there
    are always enough rounded-down members to absorb the leftover.
    """
    weight_sum = 0
    for name in members:
        weight_sum += weights[name]

    result = {}
    rounded_down = []
    assigned = 0
    for name in members:
        result[name] = (total * weights[name]) // weight_sum
        assigned += result[name]
        if (total * weights[name]) % weight_sum != 0:
            rounded_down.append(name)

    leftover = total - assigned
    for position in range(leftover):
        result[rounded_down[position]] += 1
    return result


# ----------------------------------------------------------------------
# The four split types
# ----------------------------------------------------------------------

def split_equal(total, members):
    """
    Everyone pays the same; the first (total % n) people pay 1 paisa more.
        split_equal(10000, ["Asha", "Ravi", "Meera"])
            -> {"Asha": 3334, "Ravi": 3333, "Meera": 3333}
    """
    _check_inputs(total, members)
    count = len(members)
    base = total // count
    extra = total % count

    result = {}
    position = 0
    for name in members:
        if position < extra:
            result[name] = base + 1
        else:
            result[name] = base
        position += 1
    return result


def split_exact(total, members, amounts):
    """
    Each person owes a stated amount in paise; they must add up to the total.
        split_exact(10000, ["Asha", "Ravi"], {"Asha": 7000, "Ravi": 3000})
            -> {"Asha": 7000, "Ravi": 3000}
    """
    _check_inputs(total, members)
    _check_values_match(members, amounts, "amount")
    validate_exact_split(total, amounts)

    result = {}
    for name in members:
        result[name] = amounts[name]
    return result


def split_percentage(total, members, percentages):
    """
    percentages: {name: hundredths of a percent}, as returned by
    validator.parse_percentage ("50" -> 5000, "33.33" -> 3333).
    They must add up to 10000 (100%).
        split_percentage(10000, ["Asha", "Ravi"], {"Asha": 7000, "Ravi": 3000})
            -> {"Asha": 7000, "Ravi": 3000}
    """
    _check_inputs(total, members)
    _check_values_match(members, percentages, "percentage")
    for name in members:
        if percentages[name] < 0:
            raise ValidationError(name + "'s percentage cannot be negative")
    validate_percentages(percentages)
    return _split_by_weights(total, members, percentages)


def split_shares(total, members, shares):
    """
    shares: {name: whole number of shares}, e.g. 2 for a couple, 1 for a single.
    A share of 0 means the person owes nothing.
        split_shares(10000, ["Asha", "Ravi", "Meera"], {"Asha": 2, "Ravi": 1, "Meera": 1})
            -> {"Asha": 5000, "Ravi": 2500, "Meera": 2500}
    """
    _check_inputs(total, members)
    _check_values_match(members, shares, "share count")
    share_total = 0
    for name in members:
        if shares[name] < 0:
            raise ValidationError(name + "'s shares cannot be negative")
        share_total += shares[name]
    if share_total == 0:
        raise ValidationError("At least one person must have more than 0 shares")
    return _split_by_weights(total, members, shares)


def calculate_split(split_type, total, members, values=None):
    """
    Run the right split by name. `values` is the per-person dict needed by
    exact, percentage and shares splits; it is ignored for equal splits.
    """
    if split_type == SPLIT_EQUAL:
        return split_equal(total, members)
    if values is None:
        raise ValidationError("A " + split_type + " split needs a value for each person")
    if split_type == SPLIT_EXACT:
        return split_exact(total, members, values)
    if split_type == SPLIT_PERCENTAGE:
        return split_percentage(total, members, values)
    if split_type == SPLIT_SHARES:
        return split_shares(total, members, values)
    raise ValidationError("Unknown split type: " + str(split_type))
