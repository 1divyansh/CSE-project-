# split_calculator.py
# Works out how much each person owes for one expense.
#
# Every function returns a dict like {"Rahul": 3334, "Aman": 3333, ...}
# and the numbers ALWAYS add up to exactly the total, so no paisa is lost.
#
# The trick for rounding uses only // and %:
#   Rs. 100 between 3 people = 10000 paise
#   10000 // 3 = 3333   -> everyone pays this much
#   10000 % 3  = 1      -> 1 paisa is left over
#   The left over paise are given out one by one to the first people,
#   so the result is 3334, 3333, 3333 (adds up to 10000).

from validator import check_exact_split, check_percentages


def check_people(total, people):
    # Checks that are the same for every type of split
    if total <= 0:
        raise ValueError("Total must be greater than zero")
    if len(people) == 0:
        raise ValueError("The split needs at least one person")

    already_seen = []
    for person in people:
        if person in already_seen:
            raise ValueError(person + " is listed twice in the split")
        already_seen.append(person)


def check_everyone_has_a_value(people, values, what):
    # Every person in the split needs a value, and nobody else should have one
    for person in people:
        if person not in values:
            raise ValueError("Missing " + what + " for " + person)
    for person in values:
        if person not in people:
            raise ValueError(person + " has a " + what + " but is not in the split")


def split_equal(total, people):
    check_people(total, people)

    number_of_people = len(people)
    each_pays = total // number_of_people
    left_over = total % number_of_people

    result = {}
    position = 0
    for person in people:
        if position < left_over:
            # The first few people pay one extra paisa
            result[person] = each_pays + 1
        else:
            result[person] = each_pays
        position = position + 1
    return result


def split_exact(total, people, amounts):
    # The user already typed how much each person owes
    check_people(total, people)
    check_everyone_has_a_value(people, amounts, "amount")
    check_exact_split(total, amounts)

    result = {}
    for person in people:
        result[person] = amounts[person]
    return result


def split_by_weights(total, people, weights):
    # Used by both percentage and shares splits.
    # Each person pays total * their_weight / all_weights, rounded down.
    # We multiply first and divide last so we only lose the tiny fraction
    # at the very end.
    all_weights = 0
    for person in people:
        all_weights = all_weights + weights[person]

    result = {}
    given_out = 0
    people_rounded_down = []

    for person in people:
        top = total * weights[person]
        result[person] = top // all_weights
        given_out = given_out + result[person]

        # If there is a remainder, this person's share got rounded down
        if top % all_weights != 0:
            people_rounded_down.append(person)

    # Hand out the missing paise one each, to the first people who were
    # rounded down. Someone whose share was already exact never gets one.
    # (There are always more rounded-down people than missing paise.)
    missing_paise = total - given_out
    position = 0
    while position < missing_paise:
        person = people_rounded_down[position]
        result[person] = result[person] + 1
        position = position + 1

    return result


def split_percentage(total, people, percentages):
    # percentages are in hundredths, e.g. 50% is 5000
    check_people(total, people)
    check_everyone_has_a_value(people, percentages, "percentage")
    for person in people:
        if percentages[person] < 0:
            raise ValueError(person + "'s percentage cannot be negative")
    check_percentages(percentages)
    return split_by_weights(total, people, percentages)


def split_shares(total, people, shares):
    # shares are whole numbers, e.g. a couple = 2, a single person = 1
    check_people(total, people)
    check_everyone_has_a_value(people, shares, "share count")

    total_shares = 0
    for person in people:
        if shares[person] < 0:
            raise ValueError(person + "'s shares cannot be negative")
        total_shares = total_shares + shares[person]

    if total_shares == 0:
        raise ValueError("At least one person must have more than 0 shares")
    return split_by_weights(total, people, shares)


def calculate_split(split_type, total, people, values):
    # Picks the right split function. values is None for an equal split.
    if split_type == "equal":
        return split_equal(total, people)

    if values is None:
        raise ValueError("A " + split_type + " split needs a value for each person")

    if split_type == "exact":
        return split_exact(total, people, values)
    if split_type == "percentage":
        return split_percentage(total, people, values)
    if split_type == "shares":
        return split_shares(total, people, values)

    raise ValueError("Unknown split type: " + split_type)
