# validator.py
# Checks the things the user types in. No imports are used - every check
# is done with loops and simple string methods.
#
# Every function either returns the cleaned value, or raises a ValueError
# with a message that can be shown straight to the user.

from models import find_member

DIGITS = "0123456789"


def is_number_text(text):
    # True only if text is not empty and every character is 0-9
    if text == "":
        return False
    for ch in text:
        if ch not in DIGITS:
            return False
    return True


def text_to_int(text):
    # Converts a string of digits into an int by hand, e.g. "407" -> 407.
    # For each digit we move the old value one place left (times 10)
    # and add the new digit.
    value = 0
    for ch in text:
        digit = DIGITS.index(ch)
        value = value * 10 + digit
    return value


def parse_two_decimal_number(text, label):
    # Reads a number with up to 2 decimal places and returns it times 100.
    #   "12"    -> 1200
    #   "12.5"  -> 1250
    #   "0.07"  -> 7
    text = text.strip()

    if text == "":
        raise ValueError(label + " cannot be empty")
    if text[0] == "-":
        raise ValueError(label + " cannot be negative")
    if text.count(".") > 1:
        raise ValueError(label + " can only have one decimal point")

    # Split the number into the part before and after the dot
    if "." in text:
        dot_position = text.index(".")
        whole_part = text[:dot_position]
        decimal_part = text[dot_position + 1:]
    else:
        whole_part = text
        decimal_part = ""

    if whole_part == "" and decimal_part == "":
        raise ValueError(label + " must contain digits")
    if whole_part != "" and not is_number_text(whole_part):
        raise ValueError(label + " must be a number, like 250 or 99.50")
    if decimal_part != "" and not is_number_text(decimal_part):
        raise ValueError(label + " must be a number, like 250 or 99.50")
    if len(decimal_part) > 2:
        raise ValueError(label + " can have at most 2 decimal places")

    # "12.5" means 12 rupees 50 paise, so pad the decimal part to 2 digits
    while len(decimal_part) < 2:
        decimal_part = decimal_part + "0"

    whole_value = 0
    if whole_part != "":
        whole_value = text_to_int(whole_part)
    decimal_value = text_to_int(decimal_part)

    return whole_value * 100 + decimal_value


def hundredths_to_text(value):
    # 1250 -> "12.50". Only used for error messages (value is never negative).
    before_dot = value // 100
    after_dot = value % 100
    if after_dot < 10:
        return str(before_dot) + ".0" + str(after_dot)
    return str(before_dot) + "." + str(after_dot)


def parse_amount(text, allow_zero=False):
    # Rupee text -> paise. "250" -> 25000, "99.9" -> 9990
    paise = parse_two_decimal_number(text, "Amount")
    if paise == 0 and not allow_zero:
        raise ValueError("Amount must be greater than zero")
    return paise


def parse_percentage(text):
    # Percentage text -> hundredths of a percent, so "33.33" -> 3333.
    # That way 100% is 10000 and we can still compare with whole numbers.
    value = parse_two_decimal_number(text, "Percentage")
    if value > 10000:
        raise ValueError("A percentage cannot be more than 100")
    return value


def parse_share_count(text):
    # Shares must be a whole number like 1, 2 or 3
    text = text.strip()
    if not is_number_text(text):
        raise ValueError("Shares must be a whole number like 1 or 2")
    return text_to_int(text)


def check_exact_split(total, amounts):
    # amounts is a dict like {"Rahul": 30000, "Aman": 20000}.
    # They must add up to exactly the total.
    if len(amounts) == 0:
        raise ValueError("The split needs at least one person")

    added_up = 0
    for name in amounts:
        if amounts[name] < 0:
            raise ValueError(name + "'s amount cannot be negative")
        added_up = added_up + amounts[name]

    if added_up < total:
        missing = total - added_up
        raise ValueError("Amounts are Rs. " + hundredths_to_text(missing)
                         + " short of the total Rs. " + hundredths_to_text(total))
    if added_up > total:
        extra = added_up - total
        raise ValueError("Amounts are Rs. " + hundredths_to_text(extra)
                         + " more than the total Rs. " + hundredths_to_text(total))


def check_percentages(percentages):
    # percentages is a dict like {"Rahul": 5000, "Aman": 5000} (hundredths).
    # They must add up to exactly 10000, which is 100%.
    if len(percentages) == 0:
        raise ValueError("The split needs at least one person")

    added_up = 0
    for name in percentages:
        added_up = added_up + percentages[name]

    if added_up != 10000:
        raise ValueError("Percentages must add up to 100, but they add up to "
                         + hundredths_to_text(added_up))


def check_member_name(name, group):
    # Cleans up a new member's name and makes sure it is allowed.
    name = name.strip()

    if name == "":
        raise ValueError("Name cannot be empty")
    if len(name) > 30:
        raise ValueError("Name must be 30 characters or fewer")

    for ch in name:
        if not ch.isalnum() and ch not in " -'.":
            raise ValueError("Name can only use letters, numbers, spaces, - ' and .")

    existing_name = find_member(group, name)
    if existing_name is not None:
        raise ValueError(existing_name + " is already in " + group["name"])

    return name
