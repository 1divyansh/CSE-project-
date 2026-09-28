# ledger.py
# Adds and deletes expenses in the group's list, and works out everyone's
# balance. Nothing is saved to a file - it is all in group["expenses"].
#
# Balance meaning:
#   positive -> this person should get money back
#   negative -> this person owes money
#
# Money only moves between members, so all the balances together must
# always add up to exactly 0. We check this every time.

from models import create_expense, find_member
from split_calculator import calculate_split


def get_member_name(group, name):
    # Returns the saved spelling of the name, or raises an error
    saved_name = find_member(group, name)
    if saved_name is None:
        raise ValueError(name + " is not a member of " + group["name"])
    return saved_name


def calculate_balances(group):
    balances = {}

    # Everyone starts at 0
    for member in group["members"]:
        balances[member] = 0

    for expense in group["expenses"]:
        # The payer gets back the whole amount...
        payer = expense["payer"]
        balances[payer] = balances[payer] + expense["amount"]

        # ...and every participant owes their share
        for person in expense["shares"]:
            balances[person] = balances[person] - expense["shares"][person]

    # Zero-sum check: all balances together must be exactly 0
    total = 0
    for member in balances:
        total = total + balances[member]
    if total != 0:
        raise ValueError("Ledger error: balances add up to " + str(total)
                         + " paise instead of 0")

    return balances


def add_expense(group, description, amount, payer, participants, split_type, values):
    description = description.strip()
    if description == "":
        raise ValueError("Description cannot be empty")

    # Use the saved spelling of every name ("rahul" -> "Rahul")
    payer = get_member_name(group, payer)

    people = []
    for person in participants:
        people.append(get_member_name(group, person))

    fixed_values = None
    if values is not None:
        fixed_values = {}
        for person in values:
            fixed_values[get_member_name(group, person)] = values[person]

    shares = calculate_split(split_type, amount, people, fixed_values)
    expense = create_expense(description, amount, payer, shares, split_type)

    group["expenses"].append(expense)

    # If the balances do not add up to 0 any more, undo the change
    try:
        calculate_balances(group)
    except ValueError:
        group["expenses"].pop()
        raise

    return expense


def delete_expense(group, position):
    # position starts at 0, like a normal list index
    if position < 0 or position >= len(group["expenses"]):
        raise ValueError("There is no expense number " + str(position + 1))

    removed = group["expenses"].pop(position)

    # If the balances do not add up to 0 any more, put it back
    try:
        calculate_balances(group)
    except ValueError:
        group["expenses"].insert(position, removed)
        raise

    return removed
