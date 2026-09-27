"""
validator.py - Manual input validation for SplitSquad.

No imports: every check uses string methods, loops and integer arithmetic.
Each function returns the cleaned value on success and raises
ValidationError (a ValueError) with a readable message on failure.
"""


class ValidationError(ValueError):
    """Bad user input. The message is meant to be shown to the user."""


def _is_digits(text):
    """True if text is non-empty and only contains the characters 0-9."""
    if text == "":
        return False
    for ch in text:
        if ch < "0" or ch > "9":
            return False
    return True


def _to_int(text):
    """Convert a string of digits to an int by hand: '407' -> 407."""
    value = 0
    for ch in text:
        value = value * 10 + (ord(ch) - ord("0"))
    return value


def _parse_two_decimals(text, label):
    """
    Parse a non-negative number with up to 2 decimal places into an int
    scaled by 100:  "12" -> 1200,  "12.5" -> 1250,  "0.07" -> 7.
    """
    text = text.strip()
    if text == "":
        raise ValidationError(label + " cannot be empty")
    if text.startswith("-"):
        raise ValidationError(label + " cannot be negative")
    if text.count(".") > 1:
        raise ValidationError(label + " can only have one decimal point")

    if "." in text:
        whole, fraction = text.split(".")
    else:
        whole, fraction = text, ""
    if whole == "" and fraction == "":
        raise ValidationError(label + " must contain digits")
    if whole != "" and not _is_digits(whole):
        raise ValidationError(label + " must be a number, like 250 or 99.50")
    if fraction != "" and not _is_digits(fraction):
        raise ValidationError(label + " must be a number, like 250 or 99.50")
    if len(fraction) > 2:
        raise ValidationError(label + " can have at most 2 decimal places")

    fraction = fraction + "0" * (2 - len(fraction))   # "5" -> "50"
    whole_value = _to_int(whole) if whole != "" else 0
    return whole_value * 100 + _to_int(fraction)


def _hundredths_text(value):
    """1250 -> '12.50' (used in error messages)."""
    fraction = value % 100
    return str(value // 100) + "." + ("0" if fraction < 10 else "") + str(fraction)


# ----------------------------------------------------------------------
# Amounts
# ----------------------------------------------------------------------

def parse_amount(text, allow_zero=False):
    """
    Convert a rupee string to integer paise.
        "250" -> 25000     "99.9" -> 9990     "0.05" -> 5
    """
    paise = _parse_two_decimals(text, "Amount")
    if paise == 0 and not allow_zero:
        raise ValidationError("Amount must be greater than zero")
    return paise


# ----------------------------------------------------------------------
# Splits
# ----------------------------------------------------------------------

def validate_exact_split(total, amounts):
    """
    amounts: {name: paise}. Each must be >= 0 and together they must equal
    `total` exactly. Returns amounts.
    """
    if len(amounts) == 0:
        raise ValidationError("The split needs at least one person")
    running = 0
    for name in amounts:
        if amounts[name] < 0:
            raise ValidationError(name + "'s amount cannot be negative")
        running += amounts[name]
    if running != total:
        difference = total - running
        if difference > 0:
            raise ValidationError("Amounts are Rs. " + _hundredths_text(difference)
                                  + " short of the total Rs. " + _hundredths_text(total))
        raise ValidationError("Amounts are Rs. " + _hundredths_text(-difference)
                              + " more than the total Rs. " + _hundredths_text(total))
    return amounts


def parse_percentage(text):
    """
    Convert a percentage string to hundredths of a percent, so decimals stay
    exact:  "50" -> 5000,  "33.33" -> 3333.
    """
    value = _parse_two_decimals(text, "Percentage")
    if value > 10000:
        raise ValidationError("A percentage cannot be more than 100")
    return value


def validate_percentages(percentages):
    """
    percentages: {name: hundredths of a percent} (from parse_percentage).
    They must add up to exactly 100%. Returns percentages.
    """
    if len(percentages) == 0:
        raise ValidationError("The split needs at least one person")
    running = 0
    for name in percentages:
        running += percentages[name]
    if running != 10000:
        raise ValidationError("Percentages must add up to 100, but they add up to "
                              + _hundredths_text(running))
    return percentages


# ----------------------------------------------------------------------
# Member names
# ----------------------------------------------------------------------

def validate_member_name(name, group):
    """
    Check a new member's name against the group's current members.
    Returns the cleaned name (extra spaces removed).
    """
    cleaned = " ".join(name.split())
    if cleaned == "":
        raise ValidationError("Name cannot be empty")
    if len(cleaned) > 30:
        raise ValidationError("Name must be 30 characters or fewer")
    for ch in cleaned:
        if not (ch.isalnum() or ch in " -'."):
            raise ValidationError("Name can only use letters, numbers, spaces, - ' and .")
    existing = group.find_member(cleaned)
    if existing is not None:
        raise ValidationError(existing.name + " is already in " + group.name)
    return cleaned
