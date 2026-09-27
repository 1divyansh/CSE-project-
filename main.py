"""
main.py - SplitSquad terminal application.

Run with:  python main.py

Only the project's own modules are imported. Error handling happens in
two layers:

  * Field level - every prompt goes through ask(), which catches the
    ValueError (validator.ValidationError is a subclass) raised by the
    parser, prints it and asks the same question again.
  * Action level - each menu action runs inside run_action(), which catches
    anything that escapes (ledger rejections, file errors, a failed
    consistency check), prints it and returns to the menu. The program only
    exits when the user chooses Quit or input ends.

Type 'cancel' at any prompt (or press Ctrl+C) to abandon the current action.
Data is saved to group_data.txt after every change.
"""

import models
import validator
import split_calculator
import ledger
import storage_manager
import settlement_optimizer
import report_generator


CANCEL_WORD = "cancel"
GROUP_NAME_MAX_LENGTH = 40

SPLIT_CHOICES = [
    ("1", models.SPLIT_EQUAL, "Equal"),
    ("2", models.SPLIT_EXACT, "Exact amounts"),
    ("3", models.SPLIT_PERCENTAGE, "Percentages"),
    ("4", models.SPLIT_SHARES, "Shares (e.g. 2 for a couple, 1 for a single)"),
]


class Cancelled(Exception):
    """The user typed 'cancel': abandon the current action and return to the menu."""


# ----------------------------------------------------------------------
# Console helpers
# ----------------------------------------------------------------------

def print_error(message):
    print("  ! " + str(message))


def plural(count, word):
    return str(count) + " " + word + ("" if count == 1 else "s")


def print_heading(text):
    print()
    print(text)
    print("-" * len(text))


def read_line(prompt):
    """input() that turns the cancel word into a Cancelled exception."""
    text = input(prompt)
    if text.strip().lower() == CANCEL_WORD:
        raise Cancelled()
    return text


def ask(prompt, parse=None, default=None, allow_blank=False):
    """
    Keep asking until the answer is accepted.

    parse       : function turning the raw text into a value; any ValueError it
                  raises (including validator.ValidationError) is printed and
                  the question is asked again.
    default     : raw text used when the answer is blank; shown in [brackets].
    allow_blank : blank input (with no default) returns None instead of re-asking.
    """
    label = prompt
    if default is not None:
        label += " [" + default + "]"
    label += ": "

    while True:
        raw = read_line(label).strip()
        if raw == "":
            if default is not None:
                raw = default
            elif allow_blank:
                return None
            else:
                print_error("Please enter a value (or 'cancel' to go back).")
                continue
        if parse is None:
            return raw
        try:
            return parse(raw)
        except ValueError as err:
            print_error(err)


def ask_yes_no(prompt, default):
    def parse(text):
        answer = text.lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        raise validator.ValidationError("Please answer y or n")
    return ask(prompt + " (y/n)", parse, "y" if default else "n")


# ----------------------------------------------------------------------
# The application
# ----------------------------------------------------------------------

class SplitSquadApp:

    def __init__(self, data_path=storage_manager.DEFAULT_DATA_FILE,
                 audit_path=storage_manager.DEFAULT_AUDIT_FILE):
        self.data_path = data_path
        self.audit = storage_manager.AuditLog(audit_path)
        self.groups = storage_manager.load_groups(data_path)
        self.group = self.groups[0] if len(self.groups) == 1 else None
        self.last_date = None

        # menu key -> (label, handler, needs a selected group)
        self.actions = [
            ("1", "Create / select group", self.select_group, False),
            ("2", "Add member", self.add_members, True),
            ("3", "Add expense", self.add_expense, True),
            ("4", "View balances", self.view_balances, True),
            ("5", "Generate settle-up plan", self.settle_up_plan, True),
            ("6", "Export reports", self.export_reports, True),
        ]

    # ---- persistence ---------------------------------------------------

    def save(self):
        storage_manager.save_groups(self.groups, self.data_path)

    # ---- main loop -----------------------------------------------------

    def run(self):
        print("=" * 44)
        print("  SplitSquad - split expenses with friends")
        print("=" * 44)
        print("Type '" + CANCEL_WORD + "' at any prompt to go back to the menu.")

        while True:
            self.show_menu()
            try:
                choice = read_line("Choose an option: ").strip()
            except Cancelled:
                continue
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if choice == "0":
                break

            for key, _label, handler, needs_group in self.actions:
                if key == choice:
                    try:
                        self.run_action(handler, needs_group)
                    except EOFError:            # input ended mid-action
                        print()
                        self.quit()
                        return
                    break
            else:
                print_error("Please choose one of the numbers shown.")

        self.quit()

    def show_menu(self):
        print()
        if self.group is None:
            print("Current group: (none selected)")
        else:
            print("Current group: " + self.group.name + "  ("
                  + plural(len(self.group.members), "member") + ", "
                  + plural(len(self.group.expenses), "expense") + ", total "
                  + report_generator.format_money(self.group.total_spent()) + ")")
        for key, label, _handler, _needs_group in self.actions:
            print("  " + key + ". " + label)
        print("  0. Save and quit")

    def run_action(self, handler, needs_group):
        """Run one menu action; no exception except EOFError gets past this."""
        if needs_group and self.group is None:
            print_error("Create or select a group first (option 1).")
            return
        try:
            handler()
        except Cancelled:
            print("  Cancelled.")
        except KeyboardInterrupt:
            print()
            print("  Cancelled.")
        except ValueError as err:         # ValidationError, StorageError, model checks
            print_error(err)
        except AssertionError as err:     # ledger invariant; the ledger already rolled back
            print_error("Consistency check failed, so the change was undone: " + str(err))
        except EOFError:                  # input ended: let run() save and exit
            raise
        except OSError as err:            # disk full, permission denied, bad file name...
            print_error("File problem: " + str(err))
            print_error("Your changes are kept in memory and will be saved next time.")
        except Exception as err:          # last resort: report, never crash
            print_error("Unexpected error (" + type(err).__name__ + "): " + str(err))

    def quit(self):
        try:
            self.save()
            print("Saved " + plural(len(self.groups), "group") + " to "
                  + self.data_path + ". Goodbye!")
        except OSError as err:
            print_error("Could not save before quitting: " + str(err))

    # ---- shared pickers ------------------------------------------------

    def show_members(self):
        for index in range(len(self.group.members)):
            print("    " + str(index + 1) + ". " + self.group.members[index].name)

    def resolve_member(self, text):
        """Member number (from the list shown) or name -> stored member name."""
        text = text.strip()
        members = self.group.members
        if validator.is_ascii_digits(text):
            number = validator.digits_to_int(text)
            if 1 <= number <= len(members):
                return members[number - 1].name
            raise validator.ValidationError("Choose a number from 1 to " + str(len(members)))
        member = self.group.get_member(text)
        if member is None:
            raise validator.ValidationError(repr(text) + " is not in this group")
        return member.name

    def resolve_members(self, text):
        """Comma-separated numbers/names -> list of names; 'all' means everyone."""
        if text.strip().lower() == "all":
            return self.group.member_names()
        names = []
        for part in text.split(","):
            if part.strip() == "":
                raise validator.ValidationError("Remove the empty entry between commas")
            names.append(self.resolve_member(part))
        validator.validate_split_members(names, self.group.member_names())
        return names

    def ask_date(self):
        date = ask("Date (DD-MM-YYYY)", validator.validate_date, self.last_date)
        self.last_date = date
        return date

    # ---- 1. create / select group -------------------------------------

    def select_group(self):
        print_heading("Create / select group")
        if len(self.groups) == 0:
            print("  No groups yet - let's create one.")
        else:
            for index in range(len(self.groups)):
                group = self.groups[index]
                print("    " + str(index + 1) + ". " + group.name
                      + "  (" + plural(len(group.members), "member") + ")")

        def parse(text):
            if validator.is_ascii_digits(text):
                number = validator.digits_to_int(text)
                if 1 <= number <= len(self.groups):
                    return self.groups[number - 1]
                raise validator.ValidationError("No group number " + text)
            return validator.validate_text(text, "Group name", GROUP_NAME_MAX_LENGTH)

        answer = ask("Group number to select, or a new group name", parse)
        if isinstance(answer, models.Group):
            self.group = answer
            print("  Selected '" + answer.name + "'.")
            return

        for group in self.groups:
            if group.name.lower() == answer.lower():
                self.group = group
                print("  A group called '" + group.name + "' already exists - selected it.")
                return

        def parse_names(text):
            return validator.validate_unique_names(text.split(","))

        names = ask("Member names, separated by commas (blank to add later)",
                    parse_names, allow_blank=True)
        group = models.Group(answer, names)
        self.groups.append(group)
        self.group = group
        self.save()
        print("  Created group '" + group.name + "' with "
              + plural(len(group.members), "member") + ".")

    # ---- 2. add member -------------------------------------------------

    def add_members(self):
        print_heading("Add members to " + self.group.name)
        if len(self.group.members) > 0:
            print("  Current members: " + ", ".join(self.group.member_names()))

        def parse(text):
            return validator.validate_new_member(text, self.group.member_names())

        while True:
            name = ask("New member name (blank to finish)", parse, allow_blank=True)
            if name is None:
                return
            self.group.add_member(name)
            self.save()
            print("  Added " + name + ".")

    # ---- 3. add expense ------------------------------------------------

    def add_expense(self):
        group = self.group
        if len(group.members) < 2:
            print_error("Add at least two members before recording expenses (option 2).")
            return
        print_heading("Add expense to " + group.name)

        description = ask("Description",
                          lambda t: validator.validate_text(t, "Description",
                                                            ledger.DESCRIPTION_MAX_LENGTH))
        amount = ask("Amount (Rs.)", validator.parse_amount)
        date = self.ask_date()

        print("  Members:")
        self.show_members()
        payer = ask("Who paid? (number or name)", self.resolve_member)
        participants = ask("Split between (numbers or names, comma-separated)",
                           self.resolve_members, "all")

        for key, _split, label in SPLIT_CHOICES:
            print("    " + key + ". " + label)
        split_type = ask("Split type", self.parse_split_type, "1")

        values, shares = self.collect_split(split_type, amount, participants)

        categories = self.known_categories()
        if len(categories) > 0:
            print("  Categories used so far: " + ", ".join(categories))
        category = ask("Category",
                       lambda t: validator.validate_text(t, "Category",
                                                         ledger.CATEGORY_MAX_LENGTH),
                       ledger.DEFAULT_CATEGORY)

        rows = []
        for name in shares:
            rows.append([name, report_generator.format_money(shares[name])])
        print()
        print("  " + description + " - Rs. " + report_generator.format_money(amount)
              + " paid by " + payer + " on " + date + " [" + category + "]")
        print(report_generator.format_table(["Member", "Owes"], rows, align="lr"))
        if not ask_yes_no("Save this expense?", True):
            print("  Discarded.")
            return

        expense = ledger.create_expense(group, description, amount, payer, date,
                                        participants, split_type, values, category,
                                        audit=self.audit)
        self.save()
        print("  Saved expense #" + str(expense.expense_id) + ".")

    def parse_split_type(self, text):
        answer = text.strip().lower()
        for key, split_type, label in SPLIT_CHOICES:
            if answer == key or answer == split_type or answer == label.lower():
                return split_type
        raise validator.ValidationError("Choose 1, 2, 3 or 4")

    def known_categories(self):
        seen = {}
        result = []
        for expense in self.group.expenses:
            if expense.category.lower() not in seen:
                seen[expense.category.lower()] = True
                result.append(expense.category)
        return result

    def collect_split(self, split_type, amount, participants):
        """
        Ask for each person's value (if the split type needs one) and return
        (values, shares). If the values don't add up, say why and ask again.
        """
        if split_type == models.SPLIT_EQUAL:
            return None, split_calculator.split_equal(amount, participants)

        while True:
            values = {}
            if split_type == models.SPLIT_EXACT:
                self.ask_exact_amounts(amount, participants, values)
            elif split_type == models.SPLIT_PERCENTAGE:
                self.ask_percentages(participants, values)
            else:
                for name in participants:
                    values[name] = ask("  " + name + "'s shares",
                                       lambda t: validator.parse_whole_number(t, "Shares"), "1")
            try:
                if split_type == models.SPLIT_EXACT:
                    validator.validate_exact_split(amount, values)
                shares = split_calculator.calculate_split(split_type, amount,
                                                          participants, values)
                return values, shares
            except ValueError as err:
                print_error(err)
                print("  Let's enter those again.")

    def ask_exact_amounts(self, amount, participants, values):
        remaining = amount
        for index in range(len(participants)):
            name = participants[index]
            is_last = index == len(participants) - 1
            default = models.format_paise(remaining) if is_last and remaining >= 0 else None
            values[name] = ask("  " + name + " owes (Rs. "
                               + report_generator.format_money(remaining) + " left)",
                               lambda t: validator.parse_amount(t, allow_zero=True), default)
            remaining -= values[name]

    def ask_percentages(self, participants, values):
        remaining = validator.FULL_PERCENT
        for index in range(len(participants)):
            name = participants[index]
            is_last = index == len(participants) - 1
            default = validator.format_hundredths(remaining) if is_last and remaining >= 0 else None
            values[name] = ask("  " + name + "'s % (" + validator.format_hundredths(remaining)
                               + "% left)", validator.parse_percentage, default)
            remaining -= values[name]

    # ---- 4. view balances ----------------------------------------------

    def view_balances(self):
        print()
        report_generator.print_balance_sheet(self.group)
        print()
        report_generator.print_expense_list(self.group)

    # ---- 5. settle-up plan ---------------------------------------------

    def settle_up_plan(self):
        plan = settlement_optimizer.plan_settlements(self.group)
        print()
        report_generator.print_settle_up_plan(self.group, plan)
        if len(plan) == 0:
            return
        if not ask_yes_no("Mark all of these payments as done?", False):
            return
        date = self.ask_date()
        recorded = settlement_optimizer.settle_up(self.group, date)
        self.save()
        print("  Recorded " + plural(len(recorded), "payment") + ". Everyone is settled up.")

    # ---- 6. export reports ---------------------------------------------

    def export_reports(self):
        print_heading("Export reports")
        print("    1. Member statement (comma-separated text)")
        print("    2. Full group report (balance sheet, plan, categories, expenses)")
        print("    3. Show category-wise spending on screen")

        def parse(text):
            if text in ("1", "2", "3"):
                return text
            raise validator.ValidationError("Choose 1, 2 or 3")
        choice = ask("Report", parse, "1")

        if choice == "3":
            print()
            report_generator.print_category_spending(self.group)
            return

        if choice == "1":
            print("  Members:")
            self.show_members()
            member = ask("Statement for (number or name)", self.resolve_member)
            path = ask("File name", None, report_generator.DEFAULT_EXPORT_FILE)
            rows = report_generator.export_member_statement(self.group, member, path)
            print("  Wrote " + plural(rows, "transaction") + " for " + member + " to " + path + ".")
        else:
            path = ask("File name", None, report_generator.DEFAULT_REPORT_FILE)
            report_generator.export_group_report(self.group, path)
            print("  Wrote the full report for " + self.group.name + " to " + path + ".")


def main():
    try:
        app = SplitSquadApp()
    except ValueError as err:           # storage_manager.StorageError: corrupt data file
        print_error("Could not read " + storage_manager.DEFAULT_DATA_FILE + ": " + str(err))
        print_error("Fix or move that file, then start SplitSquad again. "
                    "Nothing has been overwritten.")
        return 1
    except OSError as err:
        print_error("Could not open data file: " + str(err))
        return 1
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
