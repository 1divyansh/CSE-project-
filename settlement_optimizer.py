"""
settlement_optimizer.py - Turn net balances into a short list of payments.

Greedy algorithm:
  1. Pick the member with the largest positive balance (biggest creditor)
     and the member with the most negative balance (biggest debtor).
  2. The debtor pays the creditor min(credit, debt) - enough to bring at
     least one of them to exactly zero.
  3. Adjust both temporary balances and repeat until everyone is at zero.

Every round zeroes at least one person, so n members need at most n - 1
payments. (Finding the absolute minimum number of payments is NP-hard; this
greedy plan is the standard practical choice and is usually optimal for
small groups.) Everything is integer paise, so no rounding is involved.

No imports beyond the project's own modules: the "largest" searches are
plain linear scans rather than heapq.
"""

from models import Settlement
from validator import ValidationError, validate_date
from ledger import check_invariant


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _largest_creditor(balances):
    """Name with the largest positive balance, or None. Ties keep member order."""
    best = None
    for name in balances:
        value = balances[name]
        if value > 0 and (best is None or value > balances[best]):
            best = name
    return best


def _largest_debtor(balances):
    """Name with the most negative balance, or None. Ties keep member order."""
    best = None
    for name in balances:
        value = balances[name]
        if value < 0 and (best is None or value < balances[best]):
            best = name
    return best


def simplify_debts(balances):
    """
    balances: {name: paise}, positive = is owed, negative = owes; must sum to 0.

    Returns a list of unsaved Settlement objects (payer = debtor,
    payee = creditor, date None). The input dict is not modified.

        simplify_debts({"Asha": -3000, "Ravi": 5000, "Meera": -2000})
            -> [Settlement(Asha -> Ravi, 30.00), Settlement(Meera -> Ravi, 20.00)]
    """
    remaining = {}
    total = 0
    for name in balances:
        value = balances[name]
        if not _is_int(value):
            raise ValidationError("Balance for " + repr(name) + " must be integer paise")
        remaining[name] = value
        total += value
    if total != 0:
        raise ValidationError("Balances must sum to zero before settling, got "
                              + str(total) + " paise")

    plan = []
    while True:
        creditor = _largest_creditor(remaining)
        debtor = _largest_debtor(remaining)
        # Balances sum to zero, so creditors run out exactly when debtors do.
        if creditor is None or debtor is None:
            break
        amount = min(remaining[creditor], -remaining[debtor])
        plan.append(Settlement(debtor, creditor, amount, None))
        remaining[creditor] -= amount
        remaining[debtor] += amount

    for name in remaining:
        if remaining[name] != 0:
            raise AssertionError("Settlement plan left " + repr(name) + " at "
                                 + str(remaining[name]) + " paise")
    return plan


def plan_settlements(group):
    """Suggested payments that would settle every debt in the group (not saved)."""
    return simplify_debts(check_invariant(group))


def apply_settlements(group, settlements, date):
    """
    Record payments on the group, stamped with `date` (DD-MM-YYYY).

    All-or-nothing: if any payment is rejected or the ledger invariant fails,
    group.settlements is restored and the error re-raised.
    Returns the recorded Settlement objects (with ids assigned).
    """
    date = validate_date(date)
    snapshot = list(group.settlements)
    recorded = []
    try:
        for planned in settlements:
            settlement = Settlement(planned.payer, planned.payee, planned.amount, date)
            recorded.append(group.add_settlement(settlement))
        check_invariant(group)
    except Exception:
        group.settlements[:] = snapshot
        raise
    return recorded


def settle_up(group, date):
    """
    Plan and record every payment needed to bring all balances to zero.
    Returns the recorded settlements (empty if everyone is already square).
    """
    plan = plan_settlements(group)
    snapshot = list(group.settlements)
    recorded = apply_settlements(group, plan, date)

    balances = check_invariant(group)
    for name in balances:
        if balances[name] != 0:
            group.settlements[:] = snapshot
            raise AssertionError("After settling up, " + repr(name) + " still has "
                                 + str(balances[name]) + " paise")
    return recorded
