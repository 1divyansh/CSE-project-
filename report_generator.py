"""
report_generator.py - Terminal tables for SplitSquad.

Terminal output only (no files) and no imports beyond our own modules.
Tables are built with str.ljust() / str.rjust() and plain concatenation.
"""

from models import format_paise


def _money(paise, signed=False):
    """Paise -> '1250.50'; with signed=True positive values get a '+'."""
    if signed and paise > 0:
        return "+" + format_paise(paise)
    return format_paise(paise)


def format_table(headers, rows, align, footer=None):
    """
    Build an ASCII table as a string.

    headers : list of column titles
    rows    : list of rows, each a list of strings
    align   : one letter per column, 'l' (left) or 'r' (right), e.g. "lrl"
    footer  : optional totals row, drawn under its own separator
    """
    all_rows = [headers] + rows
    if footer is not None:
        all_rows = all_rows + [footer]

    # Column width = longest cell in that column.
    widths = []
    for col in range(len(headers)):
        width = 0
        for row in all_rows:
            if len(row[col]) > width:
                width = len(row[col])
        widths.append(width)

    def separator():
        parts = []
        for width in widths:
            parts.append("-" * (width + 2))
        return "+" + "+".join(parts) + "+"

    def line(cells):
        parts = []
        for col in range(len(cells)):
            if align[col] == "r":
                parts.append(" " + cells[col].rjust(widths[col]) + " ")
            else:
                parts.append(" " + cells[col].ljust(widths[col]) + " ")
        return "|" + "|".join(parts) + "|"

    lines = [separator(), line(headers), separator()]
    for row in rows:
        lines.append(line(row))
    lines.append(separator())
    if footer is not None:
        lines.append(line(footer))
        lines.append(separator())
    return "\n".join(lines)


def _heading(text):
    return text + "\n" + "=" * len(text)


def print_balances(balances, title="Balances"):
    """
    Print each member's net balance.
    balances: {name: paise} from InMemoryLedger.calculate_balances().
    """
    print(_heading(title))
    if len(balances) == 0:
        print("No members yet.")
        return

    rows = []
    total = 0
    for name in balances:
        amount = balances[name]
        if amount > 0:
            status = "gets back " + format_paise(amount)
        elif amount < 0:
            status = "owes " + format_paise(-amount)
        else:
            status = "settled up"
        rows.append([name, _money(amount, signed=True), status])
        total += amount

    print(format_table(["Member", "Balance (Rs.)", "Status"], rows, "lrl",
                       footer=["Total", _money(total), ""]))


def print_settlement_plan(settlements, title="Settle-up plan"):
    """
    Print who pays whom.
    settlements: list of Settlement objects from settlement_optimizer.simplify_debts().
    """
    print(_heading(title))
    if len(settlements) == 0:
        print("Everyone is settled up. Nothing to pay.")
        return

    rows = []
    total = 0
    number = 1
    for settlement in settlements:
        rows.append([str(number), settlement.payer, "pays", settlement.payee,
                     _money(settlement.amount)])
        total += settlement.amount
        number += 1

    print(format_table(["#", "From", "", "To", "Amount (Rs.)"], rows, "rlllr",
                       footer=["", "", "", "Total", _money(total)]))
    if len(settlements) == 1:
        print("1 payment settles every debt.")
    else:
        print(str(len(settlements)) + " payments settle every debt.")
