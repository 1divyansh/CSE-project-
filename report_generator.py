# report_generator.py
# Prints tables on the screen using only ljust() and rjust().
# Nothing is written to a file.

from models import format_paise


def get_column_widths(headers, rows):
    # Each column is as wide as the longest text in it
    widths = []
    for column in range(len(headers)):
        widest = len(headers[column])
        for row in rows:
            if len(row[column]) > widest:
                widest = len(row[column])
        widths.append(widest)
    return widths


def make_border(widths):
    # Makes a line like +--------+---------+
    line = "+"
    for width in widths:
        line = line + "-" * (width + 2) + "+"
    return line


def make_row(cells, widths, alignments):
    # Makes a line like | Rahul  |  250.00 |
    # alignments has one letter per column: "l" = left, "r" = right
    line = "|"
    for column in range(len(cells)):
        if alignments[column] == "r":
            text = cells[column].rjust(widths[column])
        else:
            text = cells[column].ljust(widths[column])
        line = line + " " + text + " |"
    return line


def print_table(headers, rows, alignments, total_row):
    # Measure every row (including the total row) so the columns line up
    all_rows = []
    for row in rows:
        all_rows.append(row)
    all_rows.append(total_row)
    widths = get_column_widths(headers, all_rows)

    border = make_border(widths)
    print(border)
    print(make_row(headers, widths, alignments))
    print(border)
    for row in rows:
        print(make_row(row, widths, alignments))
    print(border)
    print(make_row(total_row, widths, alignments))
    print(border)


def print_title(title):
    print(title)
    print("=" * len(title))


def print_balances(balances, title):
    print_title(title)

    if len(balances) == 0:
        print("No members yet.")
        return

    rows = []
    total = 0
    for person in balances:
        amount = balances[person]

        if amount > 0:
            balance_text = "+" + format_paise(amount)
            status = "gets back " + format_paise(amount)
        elif amount < 0:
            balance_text = format_paise(amount)
            status = "owes " + format_paise(-amount)
        else:
            balance_text = format_paise(amount)
            status = "settled up"

        rows.append([person, balance_text, status])
        total = total + amount

    # The total should always be 0.00 (the zero-sum rule)
    total_row = ["Total", format_paise(total), ""]
    print_table(["Member", "Balance (Rs.)", "Status"], rows, "lrl", total_row)


def print_settlement_plan(payments, title):
    print_title(title)

    if len(payments) == 0:
        print("Everyone is settled up. Nothing to pay.")
        return

    rows = []
    total = 0
    number = 1
    for payment in payments:
        rows.append([str(number), payment["payer"], "pays", payment["payee"],
                     format_paise(payment["amount"])])
        total = total + payment["amount"]
        number = number + 1

    total_row = ["", "", "", "Total", format_paise(total)]
    print_table(["#", "From", "", "To", "Amount (Rs.)"], rows, "rlllr", total_row)

    if len(payments) == 1:
        print("1 payment settles every debt.")
    else:
        print(str(len(payments)) + " payments settle every debt.")
