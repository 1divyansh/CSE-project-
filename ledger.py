"""
ledger.py - In-memory ledger for a SplitSquad group.

No standard-library imports and no file handling: expenses live only in
group.expenses (a plain Python list) for as long as the program runs.

Balance sign convention (integer paise):
    positive -> the group owes this member money
    negative -> this member owes the group money

Money only moves between members, so the balances must always add up to
exactly 0. calculate_balances() checks this every time it runs.
"""

from models import Expense, SPLIT_EQUAL
from validator import ValidationError
from split_calculator import calculate_split


class InMemoryLedger:
    """Adds, removes and balances the expenses of one Group."""

    def __init__(self, group):
        self.group = group

    # ---- helpers -------------------------------------------------------

    def _member_name(self, name):
        """Return the member's stored spelling ('asha' -> 'Asha') or raise."""
        member = self.group.find_member(name)
        if member is None:
            raise ValidationError(name + " is not a member of " + self.group.name)
        return member.name

    # ---- expenses ------------------------------------------------------

    def add_expense(self, description, amount, paid_by, members=None,
                    split_type=SPLIT_EQUAL, values=None):
        """
        Create an expense, append it to group.expenses and return it.

        amount     : total in paise (from validator.parse_amount)
        paid_by    : name of the member who paid
        members    : names sharing the cost; None means everyone in the group
        split_type : "equal", "exact", "percentage" or "shares"
        values     : {name: value} for non-equal splits - paise for exact,
                     hundredths of a percent for percentage, share counts for shares
        """
        description = " ".join(description.split())
        if description == "":
            raise ValidationError("Description cannot be empty")
        paid_by = self._member_name(paid_by)

        if members is None:
            members = self.group.member_names()
        names = []
        for name in members:
            names.append(self._member_name(name))

        # Re-key values with the stored spellings so they match `names`.
        clean_values = None
        if values is not None:
            clean_values = {}
            for name in values:
                clean_values[self._member_name(name)] = values[name]

        shares = calculate_split(split_type, amount, names, clean_values)
        expense = Expense(description, amount, paid_by, shares, split_type)

        self.group.expenses.append(expense)
        try:
            self.calculate_balances()
        except AssertionError:
            self.group.expenses.remove(expense)   # undo, then report the problem
            raise
        return expense

    def delete_expense(self, index):
        """
        Remove the expense at position `index` (0-based) in group.expenses
        and return it.
        """
        expenses = self.group.expenses
        if index < 0 or index >= len(expenses):
            raise ValidationError("There is no expense number " + str(index + 1))
        expense = expenses.pop(index)
        try:
            self.calculate_balances()
        except AssertionError:
            expenses.insert(index, expense)       # put it back exactly where it was
            raise
        return expense

    def list_expenses(self):
        return self.group.expenses

    # ---- balances ------------------------------------------------------

    def calculate_balances(self):
        """
        Work out every member's net balance from scratch:
            the payer gets +amount, each person in the split gets -their share.
        Returns {member_name: paise}.
        """
        balances = {}
        for member in self.group.members:
            balances[member.name] = 0

        for expense in self.group.expenses:
            balances[self._member_name(expense.paid_by)] += expense.amount
            for name in expense.shares:
                balances[self._member_name(name)] -= expense.shares[name]

        # Manual invariant check. Written as an explicit raise instead of an
        # `assert` statement because `python -O` silently removes asserts.
        total = 0
        for name in balances:
            total += balances[name]
        if total != 0:
            raise AssertionError("Balances add up to " + str(total)
                                 + " paise instead of 0 - the ledger is inconsistent")
        return balances
