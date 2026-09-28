# models.py
# The data for SplitSquad. There are no classes here - everything is a
# plain Python dictionary or list, and it only lives in memory while the
# program is running.
#
# All money is stored as whole paise (an int). For example Rs. 12.50 is
# stored as 1250. This way we never have float rounding problems.
#
# What the dictionaries look like:
#
#   group   = {"name": "Goa Trip",
#              "members": ["Rahul", "Aman"],
#              "expenses": [ ...expense dicts... ]}
#
#   expense = {"description": "Dinner",
#              "amount": 50000,
#              "payer": "Rahul",
#              "participants": ["Rahul", "Aman"],
#              "split_type": "equal",
#              "shares": {"Rahul": 25000, "Aman": 25000}}
#
#   settlement = {"payer": "Aman", "payee": "Rahul", "amount": 25000}


# The four ways an expense can be split
SPLIT_TYPES = ["equal", "exact", "percentage", "shares"]


def create_group(name):
    group = {
        "name": name,
        "members": [],
        "expenses": [],
    }
    return group


def create_expense(description, amount, payer, shares, split_type):
    # The participants are just the people who have a share
    participants = []
    for name in shares:
        participants.append(name)

    expense = {
        "description": description,
        "amount": amount,
        "payer": payer,
        "participants": participants,
        "split_type": split_type,
        "shares": shares,
    }
    return expense


def create_settlement(payer, payee, amount):
    settlement = {
        "payer": payer,
        "payee": payee,
        "amount": amount,
    }
    return settlement


def find_member(group, name):
    # Look for a member without caring about capital letters or extra spaces.
    # Returns the name the way it was saved (e.g. "rahul" -> "Rahul"),
    # or None if there is no such member.
    wanted = name.strip().lower()
    for member in group["members"]:
        if member.lower() == wanted:
            return member
    return None


def add_member(group, name):
    group["members"].append(name)


def total_spent(group):
    total = 0
    for expense in group["expenses"]:
        total = total + expense["amount"]
    return total


def format_paise(paise):
    # Turns paise into a rupee string, e.g. 125050 -> "1250.50"
    sign = ""
    if paise < 0:
        # Handle the minus sign first. Python's // and % work differently
        # with negative numbers (-5 // 100 is -1), which would print wrong.
        sign = "-"
        paise = -paise

    rupees = paise // 100
    leftover_paise = paise % 100

    if leftover_paise < 10:
        # 7 paise should print as ".07", not ".7"
        return sign + str(rupees) + ".0" + str(leftover_paise)
    return sign + str(rupees) + "." + str(leftover_paise)
