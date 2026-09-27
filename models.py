"""
models.py - Data classes for SplitSquad (in-memory only).

No imports. Everything lives in ordinary Python lists and dicts for the
current session; nothing is saved when the program exits.

Money is always stored as an int in paise (1 rupee = 100 paise), so there
are no floating-point rounding errors.
"""


SPLIT_EQUAL = "equal"
SPLIT_EXACT = "exact"
SPLIT_PERCENTAGE = "percentage"
SPLIT_TYPES = (SPLIT_EQUAL, SPLIT_EXACT, SPLIT_PERCENTAGE)


def format_paise(paise):
    """Turn integer paise into a rupee string: 125050 -> '1250.50', -5 -> '-0.05'."""
    sign = ""
    if paise < 0:
        sign = "-"
        paise = -paise
    rupees = paise // 100
    cents = paise % 100
    if cents < 10:
        return sign + str(rupees) + ".0" + str(cents)
    return sign + str(rupees) + "." + str(cents)


class Member:
    """A person in the group. Names are unique within a group (ignoring case)."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "Member(name=" + repr(self.name) + ")"


class Expense:
    """
    One shared cost.

    amount     : total in paise
    paid_by    : name of the member who paid
    shares     : dict {member_name: paise they owe}; values add up to amount
    split_type : "equal", "exact" or "percentage"
    """

    def __init__(self, description, amount, paid_by, shares, split_type=SPLIT_EQUAL):
        self.description = description
        self.amount = amount
        self.paid_by = paid_by
        self.shares = shares
        self.split_type = split_type

    def __repr__(self):
        share_text = []
        for name in self.shares:
            share_text.append(name + ": " + format_paise(self.shares[name]))
        return ("Expense(description=" + repr(self.description)
                + ", amount=" + format_paise(self.amount)
                + ", paid_by=" + repr(self.paid_by)
                + ", split_type=" + repr(self.split_type)
                + ", shares={" + ", ".join(share_text) + "})")


class Settlement:
    """A payment of `amount` paise from `payer` to `payee` that clears a debt."""

    def __init__(self, payer, payee, amount):
        self.payer = payer
        self.payee = payee
        self.amount = amount

    def __repr__(self):
        return ("Settlement(" + self.payer + " pays " + self.payee
                + " " + format_paise(self.amount) + ")")


class Group:
    """A group of members and their expenses for the current session."""

    def __init__(self, name):
        self.name = name
        self.members = []    # list of Member
        self.expenses = []   # list of Expense

    def find_member(self, name):
        """Return the Member with this name (case-insensitive), or None."""
        wanted = name.strip().lower()
        for member in self.members:
            if member.name.lower() == wanted:
                return member
        return None

    def member_names(self):
        names = []
        for member in self.members:
            names.append(member.name)
        return names

    def add_member(self, name):
        member = Member(name)
        self.members.append(member)
        return member

    def add_expense(self, expense):
        self.expenses.append(expense)
        return expense

    def total_spent(self):
        total = 0
        for expense in self.expenses:
            total += expense.amount
        return total

    def __repr__(self):
        return ("Group(name=" + repr(self.name)
                + ", members=" + repr(self.member_names())
                + ", expenses=" + str(len(self.expenses))
                + ", total=" + format_paise(self.total_spent()) + ")")
