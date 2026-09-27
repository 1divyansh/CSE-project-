"""
models.py - Core data models for SplitSquad.

Design rules:
  * Zero imports. Pure Python classes only.
  * Every money value is an int in paise (1 rupee = 100 paise).
    Floats are never stored, so there is no rounding drift.
  * Dates are plain strings in "DD-MM-YYYY" form (validated in validator.py).
"""


SPLIT_EQUAL = "equal"
SPLIT_EXACT = "exact"
SPLIT_PERCENTAGE = "percentage"
SPLIT_SHARES = "shares"
SPLIT_TYPES = (SPLIT_EQUAL, SPLIT_EXACT, SPLIT_PERCENTAGE, SPLIT_SHARES)


def format_paise(paise):
    """Render an integer paise amount as a rupee string, e.g. 125050 -> '1250.50'."""
    sign = "-" if paise < 0 else ""
    paise = abs(paise)
    rupees = paise // 100
    remainder = paise % 100
    if remainder < 10:
        return sign + str(rupees) + ".0" + str(remainder)
    return sign + str(rupees) + "." + str(remainder)


def _require_int(value, field):
    # bool is a subclass of int; reject it explicitly so True never becomes 1 paisa.
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(field + " must be an int (paise), got " + type(value).__name__)


class Member:
    """A person in a group. Names are the identity key within a group."""

    def __init__(self, name, member_id=None):
        if not isinstance(name, str) or name.strip() == "":
            raise ValueError("Member name must be a non-empty string")
        self.name = name.strip()
        self.member_id = member_id

    def key(self):
        """Case-insensitive identity used for uniqueness checks."""
        return self.name.lower()

    def __eq__(self, other):
        if not isinstance(other, Member):
            return NotImplemented
        return self.key() == other.key()

    def __hash__(self):
        return hash(self.key())

    def __repr__(self):
        return "Member(name=" + repr(self.name) + ", member_id=" + repr(self.member_id) + ")"


class Expense:
    """
    A single shared expense.

    amount   : total in paise (int).
    paid_by  : name of the member who paid.
    shares   : dict {member_name: paise_owed}. The values must sum to `amount`.
               Computing shares from the split type is the caller's job;
               validator.py provides the checks.
    split_values : the inputs the shares were computed from, kept so an edit
               can recompute them - {name: paise} for exact, {name: hundredths
               of a percent} for percentage, {name: share count} for shares,
               None for equal.
    """

    def __init__(self, expense_id, description, amount, paid_by, date,
                 split_type=SPLIT_EQUAL, shares=None, category="General",
                 split_values=None):
        _require_int(amount, "amount")
        if amount <= 0:
            raise ValueError("Expense amount must be positive")
        if split_type not in SPLIT_TYPES:
            raise ValueError("Unknown split type: " + repr(split_type))

        self.expense_id = expense_id
        self.description = description
        self.amount = amount
        self.paid_by = paid_by
        self.date = date
        self.split_type = split_type
        self.shares = {}
        if shares is not None:
            for name in shares:
                _require_int(shares[name], "share for " + repr(name))
                self.shares[name] = shares[name]
        self.category = category
        self.split_values = None
        if split_values is not None:
            self.split_values = {}
            for name in split_values:
                _require_int(split_values[name], "split value for " + repr(name))
                self.split_values[name] = split_values[name]

    def participants(self):
        return list(self.shares.keys())

    def __repr__(self):
        return ("Expense(id=" + repr(self.expense_id)
                + ", description=" + repr(self.description)
                + ", amount=" + format_paise(self.amount)
                + ", paid_by=" + repr(self.paid_by)
                + ", date=" + repr(self.date)
                + ", category=" + repr(self.category)
                + ", split_type=" + repr(self.split_type)
                + ", shares={" + ", ".join(
                    repr(n) + ": " + format_paise(p) for n, p in self.shares.items())
                + "})")


class Settlement:
    """A payment from one member to another that reduces a debt."""

    def __init__(self, payer, payee, amount, date, settlement_id=None):
        _require_int(amount, "amount")
        if amount <= 0:
            raise ValueError("Settlement amount must be positive")
        if payer.lower() == payee.lower():
            raise ValueError("Payer and payee must be different members")

        self.settlement_id = settlement_id
        self.payer = payer
        self.payee = payee
        self.amount = amount
        self.date = date

    def __repr__(self):
        return ("Settlement(id=" + repr(self.settlement_id)
                + ", payer=" + repr(self.payer)
                + ", payee=" + repr(self.payee)
                + ", amount=" + format_paise(self.amount)
                + ", date=" + repr(self.date) + ")")


class Group:
    """A named set of members with their expenses and settlements."""

    def __init__(self, name, members=None):
        if not isinstance(name, str) or name.strip() == "":
            raise ValueError("Group name must be a non-empty string")
        self.name = name.strip()
        self.members = []
        self.expenses = []
        self.settlements = []
        # Ids are never reused, even after a delete, so the audit log stays unambiguous.
        self.next_expense_id = 1
        self.next_settlement_id = 1
        if members is not None:
            for member in members:
                self.add_member(member)

    # ---- members -------------------------------------------------------

    def get_member(self, name):
        """Return the Member matching `name` (case-insensitive), or None."""
        target = name.strip().lower()
        for member in self.members:
            if member.key() == target:
                return member
        return None

    def has_member(self, name):
        return self.get_member(name) is not None

    def add_member(self, member):
        """Add a Member (or a plain name). Rejects duplicate names."""
        if isinstance(member, str):
            member = Member(member)
        if self.has_member(member.name):
            raise ValueError("Member " + repr(member.name) + " already exists in group")
        if member.member_id is None:
            member.member_id = 1
            for existing in self.members:
                if existing.member_id >= member.member_id:
                    member.member_id = existing.member_id + 1
        self.members.append(member)
        return member

    def member_names(self):
        return [m.name for m in self.members]

    # ---- expenses & settlements ---------------------------------------

    def get_expense(self, expense_id):
        for expense in self.expenses:
            if expense.expense_id == expense_id:
                return expense
        return None

    def check_expense(self, expense):
        """Raise ValueError unless the expense references real members and balances."""
        if not self.has_member(expense.paid_by):
            raise ValueError("Payer " + repr(expense.paid_by) + " is not in the group")
        total = 0
        for name in expense.shares:
            if not self.has_member(name):
                raise ValueError("Participant " + repr(name) + " is not in the group")
            total += expense.shares[name]
        if total != expense.amount:
            raise ValueError("Shares total " + format_paise(total)
                             + " does not match expense " + format_paise(expense.amount))

    def add_expense(self, expense):
        """Attach an Expense after checking it references real members and balances."""
        self.check_expense(expense)
        if expense.expense_id is None:
            expense.expense_id = self.next_expense_id
        elif self.get_expense(expense.expense_id) is not None:
            raise ValueError("Expense id " + str(expense.expense_id) + " is already used")
        if expense.expense_id >= self.next_expense_id:
            self.next_expense_id = expense.expense_id + 1
        self.expenses.append(expense)
        return expense

    def add_settlement(self, settlement):
        for name in (settlement.payer, settlement.payee):
            if not self.has_member(name):
                raise ValueError(repr(name) + " is not in the group")
        if settlement.settlement_id is None:
            settlement.settlement_id = self.next_settlement_id
        if settlement.settlement_id >= self.next_settlement_id:
            self.next_settlement_id = settlement.settlement_id + 1
        self.settlements.append(settlement)
        return settlement

    def total_spent(self):
        total = 0
        for expense in self.expenses:
            total += expense.amount
        return total

    def __repr__(self):
        return ("Group(name=" + repr(self.name)
                + ", members=" + repr(self.member_names())
                + ", expenses=" + str(len(self.expenses))
                + ", settlements=" + str(len(self.settlements))
                + ", total_spent=" + format_paise(self.total_spent()) + ")")
