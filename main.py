# main.py
# SplitSquad - a simple expense splitter that runs in the terminal.
# Run it with:  python main.py
#
# Everything is kept in memory in the global "group" dictionary below.
# Nothing is saved, so all the data is lost when the program closes.

from models import create_group, add_member, find_member, total_spent, format_paise
from validator import parse_amount, parse_percentage, parse_share_count, check_member_name
from validator import is_number_text, text_to_int
from split_calculator import calculate_split
from ledger import add_expense, calculate_balances
from settlement_optimizer import simplify_debts
from report_generator import print_balances, print_settlement_plan


# All the data for this session
group = create_group("My Group")


def plural(count, word):
    if count == 1:
        return str(count) + " " + word
    return str(count) + " " + word + "s"


def show_members():
    number = 1
    for member in group["members"]:
        print("  " + str(number) + ". " + member)
        number = number + 1


def choose_member(text):
    # The user can type a member's number from the list, or their name
    text = text.strip()
    members = group["members"]

    if is_number_text(text):
        number = text_to_int(text)
        if number >= 1 and number <= len(members):
            return members[number - 1]
        raise ValueError("There is no member number " + text)

    name = find_member(group, text)
    if name is None:
        raise ValueError(text + " is not in the group")
    return name


def menu_add_member():
    name = input("New member name: ")
    name = check_member_name(name, group)
    add_member(group, name)
    print("Added " + name + ". The group now has "
          + plural(len(group["members"]), "member") + ".")


def ask_split_values(split_type, people):
    # Asks each person for their amount / percentage / shares.
    # An equal split does not need anything, so it returns None.
    if split_type == "equal":
        return None

    values = {}
    for person in people:
        if split_type == "exact":
            text = input("  " + person + " owes (Rs.): ")
            values[person] = parse_amount(text, True)
        elif split_type == "percentage":
            text = input("  " + person + "'s percentage: ")
            values[person] = parse_percentage(text)
        else:
            text = input("  " + person + "'s shares (whole number): ")
            values[person] = parse_share_count(text)
    return values


def menu_add_expense():
    if len(group["members"]) < 2:
        print("Add at least two members first.")
        return

    description = input("Description: ")
    amount = parse_amount(input("Amount (Rs.): "))

    show_members()
    payer = choose_member(input("Who paid? (number or name): "))

    # Who shares this expense? Blank means everyone.
    text = input("Split between (numbers or names, comma-separated; blank = everyone): ")
    people = []
    if text.strip() == "":
        for member in group["members"]:
            people.append(member)
    else:
        for part in text.split(","):
            people.append(choose_member(part))

    print("Split type: 1. Equal  2. Exact amounts  3. Percentages  4. Shares")
    choice = input("Choose 1-4 (blank = equal): ").strip()
    if choice == "" or choice == "1":
        split_type = "equal"
    elif choice == "2":
        split_type = "exact"
    elif choice == "3":
        split_type = "percentage"
    elif choice == "4":
        split_type = "shares"
    else:
        raise ValueError("Split type must be 1, 2, 3 or 4")

    values = ask_split_values(split_type, people)

    # Show who owes what before saving
    shares = calculate_split(split_type, amount, people, values)
    print("Each person owes:")
    for person in shares:
        print("  " + person.ljust(15) + format_paise(shares[person]).rjust(12))

    answer = input("Save this expense? (y/n): ").strip().lower()
    if answer != "y" and answer != "yes":
        print("Expense discarded.")
        return

    add_expense(group, description, amount, payer, people, split_type, values)
    print("Saved. " + plural(len(group["expenses"]), "expense")
          + " so far, total Rs. " + format_paise(total_spent(group)) + ".")


def menu_view_balances():
    balances = calculate_balances(group)
    print_balances(balances, "Balances - " + group["name"])


def menu_settle_up():
    balances = calculate_balances(group)
    payments = simplify_debts(balances)
    print_settlement_plan(payments, "Settle-up plan - " + group["name"])


def menu_exit():
    # Returns True if the user really wants to quit
    print("Warning: SplitSquad keeps everything in memory only.")
    print("All members and expenses will be lost when you exit.")
    answer = input("Exit anyway? (y/n): ").strip().lower()
    return answer == "y" or answer == "yes"


def main():
    print("=== SplitSquad (in-memory session) ===")
    name = input("Group name (blank = 'My Group'): ").strip()
    if name != "":
        group["name"] = name

    while True:
        print()
        print("--- " + group["name"] + ": "
              + plural(len(group["members"]), "member") + ", "
              + plural(len(group["expenses"]), "expense") + " ---")
        print("1. Add Member")
        print("2. Add Expense")
        print("3. View Current Balances")
        print("4. Generate Settle-Up Plan")
        print("5. Exit")

        try:
            choice = input("Choose an option: ").strip()
            print()

            if choice == "1":
                menu_add_member()
            elif choice == "2":
                menu_add_expense()
            elif choice == "3":
                menu_view_balances()
            elif choice == "4":
                menu_settle_up()
            elif choice == "5":
                if menu_exit():
                    print("Goodbye! Session data discarded.")
                    break
            else:
                print("Please choose a number from 1 to 5.")

        except (EOFError, KeyboardInterrupt):
            # Input ran out or Ctrl+C was pressed. This has to come before
            # "except Exception", otherwise the loop would never end.
            print()
            print("Exiting. Session data discarded.")
            break
        except Exception as error:
            print("Error: " + str(error))
            print("Nothing was changed. Back to the menu.")


if __name__ == "__main__":
    main()
