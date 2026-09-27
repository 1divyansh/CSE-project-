"""
report_generator.py - Terminal reports and text export for SplitSquad.

No formatting libraries (no textwrap, tabulate, csv, string): tables are built
with str.ljust() / str.rjust() and concatenation, and the export file is
comma-separated text assembled by hand.

Each report has a build_* function that returns the text (easy to test or
save) and a print_* wrapper that prints it.
"""

from models import format_paise
from validator import ValidationError, date_sort_key, format_hundredths
from ledger import check_invariant, list_expenses
from settlement_optimizer import plan_settlements
from split_calculator import split_shares


DEFAULT_EXPORT_FILE = "export.txt"
DEFAULT_REPORT_FILE = "report.txt"
MAX_CELL_WIDTH = 32
BAR_WIDTH = 20


# ----------------------------------------------------------------------
# Formatting primitives
# ----------------------------------------------------------------------

def _group_indian(digits):
    """'1234567' -> '12,34,567' (Indian grouping: last 3 digits, then pairs)."""
    if len(digits) <= 3:
        return digits
    head = digits[:-3]
    tail = digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head != "":
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def format_money(paise, signed=False):
    """
    Paise -> display string with digit grouping.
        format_money(123456789)          -> '12,34,567.89'
        format_money(5000, signed=True)  -> '+50.00'
    """
    sign = ""
    if paise < 0:
        sign = "-"
    elif signed and paise > 0:
        sign = "+"
    whole, frac = format_paise(abs(paise)).split(".")
    return sign + _group_indian(whole) + "." + frac


def _fit(text, width):
    """Truncate text longer than `width`, marking the cut with '...'."""
    if len(text) <= width:
        return text
    return text[:width - 3] + "..."


def format_table(headers, rows, align=None, footer=None, max_width=MAX_CELL_WIDTH):
    """
    Render rows as an ASCII table.

    headers : list of column titles
    rows    : list of lists (cells are converted with str())
    align   : string with one 'l' or 'r' per column (default all left)
    footer  : optional totals row, drawn below a separator
    """
    columns = len(headers)
    if align is None:
        align = "l" * columns
    if len(align) != columns:
        raise ValueError("align needs one character per column")

    body = []
    for row in rows:
        if len(row) != columns:
            raise ValueError("every row needs " + str(columns) + " cells")
        body.append([_fit(str(cell), max_width) for cell in row])
    head = [_fit(str(cell), max_width) for cell in headers]
    foot = [_fit(str(cell), max_width) for cell in footer] if footer is not None else None

    widths = []
    for index in range(columns):
        width = len(head[index])
        for row in body + ([foot] if foot is not None else []):
            if len(row[index]) > width:
                width = len(row[index])
        widths.append(width)

    def rule():
        return "+" + "+".join("-" * (width + 2) for width in widths) + "+"

    def line(cells):
        parts = []
        for index in range(columns):
            if align[index] == "r":
                parts.append(cells[index].rjust(widths[index]))
            else:
                parts.append(cells[index].ljust(widths[index]))
        return "| " + " | ".join(parts) + " |"

    out = [rule(), line(head), rule()]
    for row in body:
        out.append(line(row))
    out.append(rule())
    if foot is not None:
        out.append(line(foot))
        out.append(rule())
    return "\n".join(out)


def _title(text):
    return text + "\n" + "=" * len(text)


def _canonical(group, name):
    member = group.get_member(name)
    if member is None:
        raise ValidationError(repr(name) + " is not a member of " + repr(group.name))
    return member.name


# ----------------------------------------------------------------------
# Balance sheet
# ----------------------------------------------------------------------

def build_balance_sheet(group):
    """
    Per member: what they paid, their share of costs, net settlements
    (paid out minus received) and the resulting balance.
        balance = paid - share + settled
    """
    balances = check_invariant(group)

    paid = {}
    share = {}
    settled = {}
    for name in balances:
        paid[name] = 0
        share[name] = 0
        settled[name] = 0
    for expense in group.expenses:
        paid[_canonical(group, expense.paid_by)] += expense.amount
        for name in expense.shares:
            share[_canonical(group, name)] += expense.shares[name]
    for settlement in group.settlements:
        settled[_canonical(group, settlement.payer)] += settlement.amount
        settled[_canonical(group, settlement.payee)] -= settlement.amount

    rows = []
    totals = [0, 0, 0]
    for name in balances:
        balance = balances[name]
        if paid[name] - share[name] + settled[name] != balance:
            raise AssertionError("Balance sheet does not reconcile for " + repr(name))
        if balance > 0:
            status = "gets back " + format_money(balance)
        elif balance < 0:
            status = "owes " + format_money(-balance)
        else:
            status = "settled up"
        rows.append([name, format_money(paid[name]), format_money(share[name]),
                     format_money(settled[name], signed=True),
                     format_money(balance, signed=True), status])
        totals[0] += paid[name]
        totals[1] += share[name]
        totals[2] += settled[name]

    footer = ["Total", format_money(totals[0]), format_money(totals[1]),
              format_money(totals[2], signed=True), format_money(0), ""]
    table = format_table(["Member", "Paid", "Share", "Settled", "Balance", "Status"],
                         rows, align="lrrrrl", footer=footer)
    return _title("Balance sheet - " + group.name) + "\n" + table


def print_balance_sheet(group):
    print(build_balance_sheet(group))


# ----------------------------------------------------------------------
# Settle-up plan
# ----------------------------------------------------------------------

def build_settle_up_plan(group, plan=None):
    """Table of who pays whom. Uses settlement_optimizer unless a plan is passed in."""
    if plan is None:
        plan = plan_settlements(group)
    heading = _title("Settle-up plan - " + group.name)
    if len(plan) == 0:
        return heading + "\nEveryone is settled up. Nothing to pay."

    rows = []
    total = 0
    for index in range(len(plan)):
        settlement = plan[index]
        rows.append([str(index + 1), settlement.payer, "->", settlement.payee,
                     format_money(settlement.amount)])
        total += settlement.amount
    table = format_table(["#", "From", "", "To", "Amount"], rows, align="rlllr",
                         footer=["", "", "", "Total", format_money(total)])
    count = str(len(plan)) + (" payment settles" if len(plan) == 1 else " payments settle")
    return heading + "\n" + table + "\n" + count + " every debt in the group."


def print_settle_up_plan(group, plan=None):
    print(build_settle_up_plan(group, plan))


# ----------------------------------------------------------------------
# Category-wise spending
# ----------------------------------------------------------------------

def build_category_spending(group):
    """
    Total spent per category, largest first, with its share of all spending.

    Percentages are distributed with split_calculator's largest-remainder
    method, so the column always adds up to exactly 100.00%.
    """
    heading = _title("Spending by category - " + group.name)
    if len(group.expenses) == 0:
        return heading + "\nNo expenses recorded yet."

    # Group case-insensitively, displaying the first spelling seen.
    labels = {}
    counts = {}
    amounts = {}
    for expense in group.expenses:
        key = expense.category.lower()
        if key not in labels:
            labels[key] = expense.category
            counts[key] = 0
            amounts[key] = 0
        counts[key] += 1
        amounts[key] += expense.amount

    keys = sorted(labels, key=lambda k: (-amounts[k], labels[k].lower()))
    weights = [amounts[k] for k in keys]
    hundredths = split_shares(100 * 100, keys, weights)

    rows = []
    total = 0
    for key in keys:
        bar_length = (hundredths[key] * BAR_WIDTH + 5000) // 10000   # rounded
        if bar_length == 0 and amounts[key] > 0:
            bar_length = 1   # keep small categories visible
        rows.append([labels[key], str(counts[key]), format_money(amounts[key]),
                     format_hundredths(hundredths[key]) + "%", "#" * bar_length])
        total += amounts[key]

    footer = ["Total", str(len(group.expenses)), format_money(total), "100.00%", ""]
    table = format_table(["Category", "Count", "Amount", "Share", ""], rows,
                         align="lrrrl", footer=footer)
    return heading + "\n" + table


def print_category_spending(group):
    print(build_category_spending(group))


# ----------------------------------------------------------------------
# Expense list and full group report
# ----------------------------------------------------------------------

def build_expense_list(group):
    """All expenses in date order."""
    heading = _title("Expenses - " + group.name)
    expenses = list_expenses(group)
    if len(expenses) == 0:
        return heading + "\nNo expenses recorded yet."
    rows = []
    for expense in expenses:
        rows.append([str(expense.expense_id), expense.date, expense.description,
                     expense.category, expense.paid_by, format_money(expense.amount),
                     expense.split_type + " (" + str(len(expense.shares)) + ")"])
    return heading + "\n" + format_table(
        ["#", "Date", "Description", "Category", "Paid by", "Amount", "Split (people)"],
        rows, align="rllllrl")


def print_expense_list(group):
    print(build_expense_list(group))


def build_group_report(group):
    """Balance sheet, settle-up plan, category spending and expense list together."""
    sections = [build_balance_sheet(group), build_settle_up_plan(group),
                build_category_spending(group), build_expense_list(group)]
    return "SplitSquad report\n\n" + "\n\n".join(sections) + "\n"


def export_group_report(group, path=DEFAULT_REPORT_FILE):
    """Write the full table report to a text file. Returns the path."""
    text = build_group_report(group)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


# ----------------------------------------------------------------------
# Per-member statement export
# ----------------------------------------------------------------------

def _csv_field(value):
    """Quote a field if it contains a comma, quote or line break (doubling inner quotes)."""
    text = str(value)
    needs_quotes = False
    for ch in text:
        if ch == "," or ch == '"' or ch == "\n" or ch == "\r":
            needs_quotes = True
            break
    if not needs_quotes:
        return text
    return '"' + text.replace('"', '""') + '"'


def _csv_line(fields):
    return ",".join(_csv_field(field) for field in fields)


def build_member_statement(group, member):
    """Statement text for `member`; see _member_statement for the layout."""
    return _member_statement(group, member)[0]


def _member_statement(group, member):
    """
    Returns (text, transaction_row_count).

    Comma-separated statement of every transaction touching `member`, in date
    order, with a running balance. Amounts are plain paise-exact decimals
    (no digit grouping, which would clash with the comma separator).

    Effect is the change to the member's balance:
        expense    : paid - share
        settlement : +amount when they paid someone, -amount when repaid
    """
    name = _canonical(group, member)
    balances = check_invariant(group)

    entries = []   # (sort key, row cells, paid, share, effect) - money in paise
    for expense in group.expenses:
        is_payer = _canonical(group, expense.paid_by) == name
        owed = 0
        involved = is_payer
        for participant in expense.shares:
            if _canonical(group, participant) == name:
                owed += expense.shares[participant]
                involved = True
        if not involved:
            continue
        paid = expense.amount if is_payer else 0
        entries.append(((date_sort_key(expense.date), 0, expense.expense_id),
                        [expense.date, "Expense", expense.description, expense.category,
                         format_paise(paid), format_paise(owed)],
                        paid, owed, paid - owed))

    for settlement in group.settlements:
        payer = _canonical(group, settlement.payer)
        payee = _canonical(group, settlement.payee)
        if payer == name:
            description, effect = "Paid " + payee, settlement.amount
        elif payee == name:
            description, effect = "Received from " + payer, -settlement.amount
        else:
            continue
        entries.append(((date_sort_key(settlement.date), 1, settlement.settlement_id),
                        [settlement.date, "Settlement", description, "", "", ""],
                        0, 0, effect))

    # Same-day expenses come before settlements, then by id.
    entries.sort(key=lambda entry: entry[0])

    lines = [_csv_line(["Group", group.name]),
             _csv_line(["Member", name]),
             "",
             _csv_line(["Date", "Type", "Description", "Category",
                        "Paid", "Share", "Effect", "Balance"])]
    running = 0
    total_paid = 0
    total_share = 0
    for sort_key, cells, paid, owed, effect in entries:
        running += effect
        total_paid += paid
        total_share += owed
        lines.append(_csv_line(cells + [format_paise(effect), format_paise(running)]))

    if running != balances[name]:
        raise AssertionError("Statement for " + repr(name) + " ends at " + str(running)
                             + " paise but the ledger says " + str(balances[name]))

    lines.append(_csv_line(["Total", "", "", "", format_paise(total_paid),
                            format_paise(total_share), format_paise(running), ""]))
    if running > 0:
        status = "Gets back " + format_paise(running)
    elif running < 0:
        status = "Owes " + format_paise(-running)
    else:
        status = "Settled up"
    lines.append(_csv_line(["Closing balance", format_paise(running), status]))
    return "\n".join(lines) + "\n", len(entries)


def export_member_statement(group, member, path=DEFAULT_EXPORT_FILE):
    """
    Write `member`'s statement to `path` (default export.txt), replacing any
    previous export. Returns the number of transaction rows written.
    """
    text, rows = _member_statement(group, member)   # build first: errors never truncate the file
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return rows
