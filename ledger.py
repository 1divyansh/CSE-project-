"""
ledger.py - Expense CRUD and balance computation for a Group.

All operations work on the group's plain Python lists (group.expenses,
group.settlements). After every create/update/delete the ledger re-derives
every member's balance and checks the financial invariant:

    sum of all member balances == 0

Money only moves between members, so any non-zero total means a bug. If the
check fails, the change is rolled back before the error propagates.

Balance sign convention (paise):
    positive -> the group owes this member money
    negative -> this member owes the group money

Each CRUD function takes an optional `audit` object (storage_manager.AuditLog
or anything with the same record() method). The ledger stays usable in
memory, with no file I/O, when it is omitted.
"""

from models import Expense, SPLIT_EQUAL, SPLIT_TYPES, format_paise
from validator import ValidationError, validate_date, validate_text, date_sort_key
from split_calculator import calculate_split
from storage_manager import AUDIT_ADD, AUDIT_EDIT, AUDIT_DELETE


DEFAULT_CATEGORY = "General"
DESCRIPTION_MAX_LENGTH = 80
CATEGORY_MAX_LENGTH = 30

# Marks "argument not supplied" in update_expense, so None stays a real value.
_KEEP = object()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _member_name(group, name):
    """Map any spelling ('asha', ' Asha ') to the member's stored name."""
    member = group.get_member(name) if isinstance(name, str) else None
    if member is None:
        raise ValidationError(repr(name) + " is not a member of " + repr(group.name))
    return member.name


def _member_values(group, participants, values):
    """
    Canonicalise the keys of a per-person values dict, or turn a list aligned
    with `participants` into such a dict. None stays None.
    """
    if values is None:
        return None
    if isinstance(values, dict):
        result = {}
        for name in values:
            key = _member_name(group, name)
            if key in result:
                raise ValidationError(repr(key) + " is given two split values")
            result[key] = values[name]
        return result
    if len(values) != len(participants):
        raise ValidationError("Expected " + str(len(participants))
                              + " split values, got " + str(len(values)))
    result = {}
    for index in range(len(participants)):
        result[participants[index]] = values[index]
    return result


def _build_expense(group, expense_id, description, amount, paid_by, date,
                   participants, split_type, values, category):
    """Validate every input and return a new, not-yet-attached Expense."""
    if split_type not in SPLIT_TYPES:
        raise ValidationError("Unknown split type: " + repr(split_type))
    description = validate_text(description, "Description", DESCRIPTION_MAX_LENGTH)
    category = validate_text(category, "Category", CATEGORY_MAX_LENGTH)
    date = validate_date(date)
    paid_by = _member_name(group, paid_by)

    names = []
    for name in participants:
        names.append(_member_name(group, name))
    split_values = None if split_type == SPLIT_EQUAL else _member_values(group, names, values)

    shares = calculate_split(split_type, amount, names, split_values)
    expense = Expense(expense_id, description, amount, paid_by, date,
                      split_type, shares, category, split_values)
    group.check_expense(expense)
    return expense


def _index_of(group, expense_id):
    for index in range(len(group.expenses)):
        if group.expenses[index].expense_id == expense_id:
            return index
    raise ValidationError("No expense with id " + repr(expense_id)
                          + " in " + repr(group.name))


def _commit(group, snapshot):
    """Check the invariant; on any failure restore the expense list and re-raise."""
    try:
        check_invariant(group)
    except Exception:
        group.expenses[:] = snapshot
        raise


def _shares_text(shares):
    parts = []
    for name in shares:
        parts.append(name + " " + format_paise(shares[name]))
    return ", ".join(parts)


def describe_expense(expense):
    """One-line human summary, used for audit entries and listings."""
    return (expense.description + " [" + expense.category + "] "
            + format_paise(expense.amount) + " paid by " + expense.paid_by
            + " on " + expense.date + "; " + expense.split_type + " split: "
            + _shares_text(expense.shares))


def _describe_changes(old, new):
    changes = []
    if old.description != new.description:
        changes.append("description " + repr(old.description) + " -> " + repr(new.description))
    if old.amount != new.amount:
        changes.append("amount " + format_paise(old.amount) + " -> " + format_paise(new.amount))
    if old.paid_by != new.paid_by:
        changes.append("paid_by " + old.paid_by + " -> " + new.paid_by)
    if old.date != new.date:
        changes.append("date " + old.date + " -> " + new.date)
    if old.category != new.category:
        changes.append("category " + old.category + " -> " + new.category)
    if old.split_type != new.split_type:
        changes.append("split " + old.split_type + " -> " + new.split_type)
    elif old.split_values != new.split_values:
        changes.append("split values " + repr(old.split_values) + " -> " + repr(new.split_values))
    if old.shares != new.shares:
        changes.append("shares {" + _shares_text(old.shares) + "} -> {"
                       + _shares_text(new.shares) + "}")
    return changes


# ----------------------------------------------------------------------
# Balances and the invariant
# ----------------------------------------------------------------------

def compute_balances(group):
    """
    Net balance per member, in paise, derived from scratch every time.

      expense    : payer +amount, each participant -their share
      settlement : payer +amount (paid off debt), payee -amount (was repaid)
    """
    balances = {}
    for member in group.members:
        balances[member.name] = 0

    for expense in group.expenses:
        balances[_member_name(group, expense.paid_by)] += expense.amount
        for name in expense.shares:
            balances[_member_name(group, name)] -= expense.shares[name]

    for settlement in group.settlements:
        balances[_member_name(group, settlement.payer)] += settlement.amount
        balances[_member_name(group, settlement.payee)] -= settlement.amount

    return balances


def check_invariant(group):
    """
    Enforce: sum of all balances == 0. Returns the balances when it holds.

    Written as an explicit raise rather than an `assert` statement because
    `python -O` strips asserts, and this check must never be switched off.
    """
    balances = compute_balances(group)
    total = 0
    for name in balances:
        total += balances[name]
    if total != 0:
        raise AssertionError("Ledger invariant violated in " + repr(group.name)
                             + ": balances sum to " + str(total) + " paise, expected 0")
    return balances


# ----------------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------------

def create_expense(group, description, amount, paid_by, date, participants=None,
                   split_type=SPLIT_EQUAL, values=None, category=DEFAULT_CATEGORY,
                   audit=None):
    """
    Add an expense and return it.

    participants : member names sharing the cost; defaults to everyone.
    values       : per-person inputs for non-equal splits, as a dict
                   {name: value} or a list aligned with `participants`:
                   paise for exact, hundredths of a percent for percentage,
                   whole numbers for shares.
    """
    if participants is None:
        participants = group.member_names()
    expense = _build_expense(group, None, description, amount, paid_by, date,
                             participants, split_type, values, category)

    snapshot = list(group.expenses)
    group.add_expense(expense)
    _commit(group, snapshot)

    if audit is not None:
        audit.record(AUDIT_ADD, group.name, expense.expense_id, describe_expense(expense))
    return expense


def get_expense(group, expense_id):
    """Return the expense with this id, or raise ValidationError."""
    return group.expenses[_index_of(group, expense_id)]


def list_expenses(group, member=None, category=None):
    """
    Expenses in date order (then id). Optional filters:
      member   - expenses this member paid for or has a share in
      category - exact category match, case-insensitive
    """
    wanted_member = _member_name(group, member) if member is not None else None
    wanted_category = category.strip().lower() if category is not None else None

    result = []
    for expense in group.expenses:
        if wanted_member is not None and expense.paid_by != wanted_member \
                and wanted_member not in expense.shares:
            continue
        if wanted_category is not None and expense.category.lower() != wanted_category:
            continue
        result.append(expense)
    return sorted(result, key=lambda e: (date_sort_key(e.date), e.expense_id))


def update_expense(group, expense_id, description=_KEEP, amount=_KEEP, paid_by=_KEEP,
                   date=_KEEP, participants=_KEEP, split_type=_KEEP, values=_KEEP,
                   category=_KEEP, audit=None):
    """
    Change any fields of an expense; unspecified fields keep their value.

    Shares are always recomputed from the resulting fields. If `values` is not
    given, the stored split inputs are reused when the split type is unchanged,
    so e.g. a percentage split rescales automatically when the amount changes.
    The expense keeps its id. Returns the updated expense.
    """
    index = _index_of(group, expense_id)
    old = group.expenses[index]

    def pick(new_value, old_value):
        return old_value if new_value is _KEEP else new_value

    split_type = pick(split_type, old.split_type)
    if values is _KEEP:
        if split_type == SPLIT_EQUAL:
            values = None
        elif split_type == old.split_type:
            values = old.split_values
        else:
            raise ValidationError("Switching the split to " + repr(split_type)
                                  + " needs per-person values")

    new = _build_expense(group, old.expense_id,
                         pick(description, old.description),
                         pick(amount, old.amount),
                         pick(paid_by, old.paid_by),
                         pick(date, old.date),
                         pick(participants, old.participants()),
                         split_type, values,
                         pick(category, old.category))

    changes = _describe_changes(old, new)
    if len(changes) == 0:
        return old

    snapshot = list(group.expenses)
    group.expenses[index] = new
    _commit(group, snapshot)

    if audit is not None:
        audit.record(AUDIT_EDIT, group.name, new.expense_id, "; ".join(changes))
    return new


def delete_expense(group, expense_id, audit=None):
    """Remove an expense and return it. Its id is never reused."""
    index = _index_of(group, expense_id)
    expense = group.expenses[index]

    snapshot = list(group.expenses)
    del group.expenses[index]
    _commit(group, snapshot)

    if audit is not None:
        audit.record(AUDIT_DELETE, group.name, expense.expense_id, describe_expense(expense))
    return expense
