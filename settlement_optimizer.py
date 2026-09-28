# settlement_optimizer.py
# Turns everyone's balance into a short list of "X pays Y" payments.
#
# Greedy idea:
#   1. Find the person who should get the most money back.
#   2. Find the person who owes the most money.
#   3. The one who owes pays the other one as much as possible
#      (the smaller of the two amounts), so at least one of them is done.
#   4. Repeat until everyone is at 0.
# Each round finishes at least one person, so n people need at most
# n - 1 payments.

from models import create_settlement


def find_biggest_creditor(balances):
    # The person with the biggest positive balance, or None if nobody
    best_person = None
    for person in balances:
        if balances[person] > 0:
            if best_person is None or balances[person] > balances[best_person]:
                best_person = person
    return best_person


def find_biggest_debtor(balances):
    # The person with the most negative balance, or None if nobody
    best_person = None
    for person in balances:
        if balances[person] < 0:
            if best_person is None or balances[person] < balances[best_person]:
                best_person = person
    return best_person


def simplify_debts(balances):
    # Work on a copy so the original balances are not changed
    remaining = {}
    total = 0
    for person in balances:
        remaining[person] = balances[person]
        total = total + balances[person]

    if total != 0:
        raise ValueError("Balances must add up to 0 before settling")

    payments = []
    while True:
        creditor = find_biggest_creditor(remaining)
        debtor = find_biggest_debtor(remaining)

        # Balances add up to 0, so if one side is empty the other is too
        if creditor is None or debtor is None:
            break

        amount_owed_to_creditor = remaining[creditor]
        amount_debtor_owes = -remaining[debtor]

        if amount_owed_to_creditor < amount_debtor_owes:
            amount = amount_owed_to_creditor
        else:
            amount = amount_debtor_owes

        payments.append(create_settlement(debtor, creditor, amount))
        remaining[creditor] = remaining[creditor] - amount
        remaining[debtor] = remaining[debtor] + amount

    # Double check that everybody really ended at 0
    for person in remaining:
        if remaining[person] != 0:
            raise ValueError(person + " still has " + str(remaining[person])
                             + " paise after settling")

    return payments
