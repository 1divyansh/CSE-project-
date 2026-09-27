"""
main.py - SplitSquad: a single-session, in-memory expense splitter.

Run with:  python main.py

Everything lives in memory. Nothing is saved: when the program exits,
all members and expenses are gone.

Error handling is deliberately simple: each menu action runs inside a
try/except. If anything goes wrong (bad amount, unknown member, splits that
don't add up...), the error is printed and you're back at the menu.
"""

import models
import validator
import split_calculator
import ledger
import settlement_optimizer
import report_generator


SPLIT_CHOICES = {
    "1": models.SPLIT_EQUAL,
    "2": models.SPLIT_EXACT,
    "3": models.SPLIT_PERCENTAGE,
    "4": models.SPLIT_SHARES,
}


# ----------------------------------------------------------------------
# Small input helpers
# ----------------------------------------------------------------------

def plural(count, word):
    return str(count) + " " + word + ("" if count == 1 else "s")


def ask(prompt):
    return input(prompt).strip()


def pick_member(group, text):
    """Accept a member's number (from the printed list) or their name."""
    if text.isdigit():
        number = int(text)
        if 1 <= number <= len(group.members):
            return group.members[number - 1].name
        raise validator.ValidationError("There is no member number " + text)
    member = group.find_member(text)
    if member is None:
        raise validator.ValidationError(text + " is not in the group")
    return member.name


def show_members(group):
    number = 1
    for member in group.members:
        print("  " + str(number) + ". " + member.name)
        number += 1


# ----------------------------------------------------------------------
# Menu actions
# ----------------------------------------------------------------------

def add_member(group):
    name = validator.validate_member_name(ask("New member name: "), group)
    group.add_member(name)
    print("Added " + name + ". The group now has " + plural(len(group.members), "member") + ".")


def ask_split_values(split_type, amount, members):
    """Ask each person for their value. Returns {name: value} or None for equal splits."""
    if split_type == models.SPLIT_EQUAL:
        return None
    values = {}
    for name in members:
        if split_type == models.SPLIT_EXACT:
            values[name] = validator.parse_amount(ask("  " + name + " owes (Rs.): "),
                                                  allow_zero=True)
        elif split_type == models.SPLIT_PERCENTAGE:
            values[name] = validator.parse_percentage(ask("  " + name + "'s percentage: "))
        else:
            text = ask("  " + name + "'s shares (whole number): ")
            if not text.isdigit():
                raise validator.ValidationError("Shares must be a whole number like 1 or 2")
            values[name] = int(text)
    return values


def add_expense(group, the_ledger):
    if len(group.members) < 2:
        print("Add at least two members first.")
        return

    description = ask("Description: ")
    amount = validator.parse_amount(ask("Amount (Rs.): "))

    show_members(group)
    payer = pick_member(group, ask("Who paid? (number or name): "))

    text = ask("Split between (numbers or names, comma-separated; blank = everyone): ")
    if text == "":
        members = group.member_names()
    else:
        members = []
        for part in text.split(","):
            members.append(pick_member(group, part.strip()))

    print("Split type: 1. Equal  2. Exact amounts  3. Percentages  4. Shares")
    choice = ask("Choose 1-4 (blank = equal): ") or "1"
    if choice not in SPLIT_CHOICES:
        raise validator.ValidationError("Split type must be 1, 2, 3 or 4")
    split_type = SPLIT_CHOICES[choice]

    values = ask_split_values(split_type, amount, members)

    # Preview who owes what before saving.
    shares = split_calculator.calculate_split(split_type, amount, members, values)
    print("Each person owes:")
    for name in shares:
        print("  " + name.ljust(15) + models.format_paise(shares[name]).rjust(12))
    if ask("Save this expense? (y/n): ").lower() not in ("y", "yes"):
        print("Expense discarded.")
        return

    the_ledger.add_expense(description, amount, payer, members, split_type, values)
    print("Saved. " + plural(len(group.expenses), "expense") + " so far, total Rs. "
          + models.format_paise(group.total_spent()) + ".")


def view_balances(the_ledger):
    report_generator.print_balances(the_ledger.calculate_balances(),
                                    "Balances - " + the_ledger.group.name)


def settle_up_plan(the_ledger):
    plan = settlement_optimizer.plan_settlements(the_ledger)
    report_generator.print_settlement_plan(plan, "Settle-up plan - " + the_ledger.group.name)


def confirm_exit():
    print("Warning: SplitSquad keeps everything in memory only.")
    print("All members and expenses will be lost when you exit.")
    return ask("Exit anyway? (y/n): ").lower() in ("y", "yes")


# ----------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------

def main():
    print("=== SplitSquad (in-memory session) ===")
    name = ask("Group name (blank = 'My Group'): ") or "My Group"
    group = models.Group(name)
    the_ledger = ledger.InMemoryLedger(group)

    while True:
        print()
        print("--- " + group.name + ": " + plural(len(group.members), "member") + ", "
              + plural(len(group.expenses), "expense") + " ---")
        print("1. Add Member")
        print("2. Add Expense")
        print("3. View Current Balances")
        print("4. Generate Settle-Up Plan")
        print("5. Exit")

        try:
            choice = ask("Choose an option: ")
            print()
            if choice == "1":
                add_member(group)
            elif choice == "2":
                add_expense(group, the_ledger)
            elif choice == "3":
                view_balances(the_ledger)
            elif choice == "4":
                settle_up_plan(the_ledger)
            elif choice == "5":
                if confirm_exit():
                    print("Goodbye! Session data discarded.")
                    break
            else:
                print("Please choose a number from 1 to 5.")
        except (EOFError, KeyboardInterrupt):
            # Input stream closed or Ctrl+C: leave instead of looping forever.
            print()
            print("Exiting. Session data discarded.")
            break
        except Exception as error:
            print("Error: " + str(error))
            print("Nothing was changed. Back to the menu.")


if __name__ == "__main__":
    main()
