"""
settlement_optimizer.py - Turn net balances into a short list of payments.

Greedy algorithm:
  1. Find the member with the largest positive balance (biggest creditor)
     and the member with the most negative balance (biggest debtor).
  2. The debtor pays the creditor min(credit, debt), which brings at least
     one of them to exactly 0.
  3. Update both temporary balances and repeat until everyone is at 0.

Every round clears at least one person, so n members need at most n - 1
payments. No imports beyond our own modules; the "largest" searches are
simple loops. All amounts are integer paise, so nothing is rounded.
"""

from models import Settlement
from validator import ValidationError


def _largest_creditor(balances):
    """Name with the largest positive balance, or None. Ties go to whoever comes first."""
    best = None
    for name in balances:
        if balances[name] > 0 and (best is None or balances[name] > balances[best]):
            best = name
    return best


def _largest_debtor(balances):
    """Name with the most negative balance, or None. Ties go to whoever comes first."""
    best = None
    for name in balances:
        if balances[name] < 0 and (best is None or balances[name] < balances[best]):
            best = name
    return best


def simplify_debts(balances):
    """
    balances: {name: paise} from InMemoryLedger.calculate_balances()
              (positive = is owed money, negative = owes money).

    Returns a list of Settlement objects: payer = debtor, payee = creditor.
    The balances dict passed in is not changed.

        simplify_debts({"Asha": -3000, "Ravi": 5000, "Meera": -2000})
            -> [Settlement(Asha pays Ravi 30.00), Settlement(Meera pays Ravi 20.00)]
    """
    remaining = {}
    total = 0
    for name in balances:
        remaining[name] = balances[name]
        total += balances[name]
    if total != 0:
        raise ValidationError("Balances must add up to 0 before settling (they add up to "
                              + str(total) + " paise)")

    plan = []
    while True:
        creditor = _largest_creditor(remaining)
        debtor = _largest_debtor(remaining)
        if creditor is None or debtor is None:
            break          # sum is 0, so no creditors left means no debtors left too
        amount = min(remaining[creditor], -remaining[debtor])
        plan.append(Settlement(debtor, creditor, amount))
        remaining[creditor] -= amount
        remaining[debtor] += amount

    # Manual check that the plan really clears everyone.
    for name in remaining:
        if remaining[name] != 0:
            raise AssertionError(name + " still has " + str(remaining[name])
                                 + " paise after settling")
    return plan


def plan_settlements(ledger):
    """Convenience: settlement plan for an InMemoryLedger's current balances."""
    return simplify_debts(ledger.calculate_balances())
