"""
validator.py - Input validation for SplitSquad, written from scratch.

Zero imports: no re, no datetime, no decimal. Every check is done with
string slicing, character comparisons and integer arithmetic.

Convention: each `parse_*` / `validate_*` function returns the cleaned value
on success and raises ValidationError with a user-friendly message on failure.
The `is_valid_*` helpers wrap them for simple True/False checks.
"""


class ValidationError(ValueError):
    """Raised when user input fails validation. The message is safe to show the user."""


MAX_AMOUNT_PAISE = 100000000000   # Rs. 1,000,000,000.00 - sanity ceiling
MIN_YEAR = 1900
MAX_YEAR = 2100
MAX_NAME_LENGTH = 30
PERCENT_SCALE = 100               # percentages stored as hundredths: 33.33% -> 3333
FULL_PERCENT = 100 * PERCENT_SCALE


# ----------------------------------------------------------------------
# Low-level helpers
# ----------------------------------------------------------------------

def is_ascii_digits(text):
    """
    True if `text` is non-empty and made only of '0'-'9'.

    str.isdigit() alone also accepts characters like '²' or Devanagari digits,
    which our manual conversion cannot handle, so both checks are applied.
    """
    if text == "" or not text.isdigit():
        return False
    for ch in text:
        if ch < "0" or ch > "9":
            return False
    return True


def digits_to_int(text):
    """Convert a string of ASCII digits to an int without calling int()."""
    value = 0
    for ch in text:
        value = value * 10 + (ord(ch) - ord("0"))
    return value


def _parse_fixed_point(text, decimals, label):
    """
    Parse a non-negative decimal string into an integer scaled by 10**decimals.
    e.g. _parse_fixed_point("12.5", 2, ...) -> 1250

    Accepts: "12", "12.5", "12.50", ".5", "12." and comma grouping like "1,250.50".
    Rejects: signs, exponents, spaces inside, more than `decimals` fraction digits.
    """
    if not isinstance(text, str):
        raise ValidationError(label + " must be text")
    text = text.strip()
    if text == "":
        raise ValidationError(label + " cannot be empty")
    if text[0] == "-":
        raise ValidationError(label + " cannot be negative")

    # Split on the decimal point - at most one allowed.
    dot_count = 0
    for ch in text:
        if ch == ".":
            dot_count += 1
    if dot_count > 1:
        raise ValidationError(label + " has more than one decimal point")

    if dot_count == 1:
        dot_at = text.index(".")
        whole_part = text[:dot_at]
        frac_part = text[dot_at + 1:]
    else:
        whole_part = text
        frac_part = ""

    if whole_part == "" and frac_part == "":
        raise ValidationError(label + " must contain digits")

    # Thousands separators: allowed only in the whole part, and every
    # comma-separated group must be non-empty digits ("1,,000" and ",5" fail).
    if "," in whole_part:
        groups = whole_part.split(",")
        for group in groups:
            if not is_ascii_digits(group):
                raise ValidationError(label + " has misplaced commas")
        whole_part = "".join(groups)

    if whole_part != "" and not is_ascii_digits(whole_part):
        raise ValidationError(label + " must contain only digits and one '.'")
    if frac_part != "" and not is_ascii_digits(frac_part):
        raise ValidationError(label + " must contain only digits after the '.'")
    if len(frac_part) > decimals:
        raise ValidationError(label + " can have at most " + str(decimals) + " decimal places")

    # Right-pad the fraction so "5" in "12.5" means 50 hundredths, not 5.
    while len(frac_part) < decimals:
        frac_part += "0"

    scale = 1
    for _ in range(decimals):
        scale *= 10

    whole_value = digits_to_int(whole_part) if whole_part != "" else 0
    frac_value = digits_to_int(frac_part) if frac_part != "" else 0
    return whole_value * scale + frac_value


# ----------------------------------------------------------------------
# Amounts
# ----------------------------------------------------------------------

def parse_amount(text, allow_zero=False):
    """
    Convert a rupee string to integer paise.

        parse_amount("250")      -> 25000
        parse_amount("99.9")     -> 9990
        parse_amount("1,250.05") -> 125005
    """
    paise = _parse_fixed_point(text, 2, "Amount")
    if paise == 0 and not allow_zero:
        raise ValidationError("Amount must be greater than zero")
    if paise > MAX_AMOUNT_PAISE:
        raise ValidationError("Amount is unrealistically large")
    return paise


def is_valid_amount(text, allow_zero=False):
    try:
        parse_amount(text, allow_zero)
        return True
    except ValidationError:
        return False


# ----------------------------------------------------------------------
# Dates  (DD-MM-YYYY)
# ----------------------------------------------------------------------

def is_leap_year(year):
    return (year % 4 == 0 and year % 100 != 0) or year % 400 == 0


def days_in_month(month, year):
    if month == 2:
        return 29 if is_leap_year(year) else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


def validate_date(text):
    """
    Validate a "DD-MM-YYYY" date string and return it stripped.

    Checks layout by slicing, digits with isdigit(), then real calendar
    rules (month range, days per month, leap years).
    """
    if not isinstance(text, str):
        raise ValidationError("Date must be text")
    text = text.strip()
    if len(text) != 10:
        raise ValidationError("Date must be in DD-MM-YYYY format (e.g. 05-03-2025)")
    if text[2] != "-" or text[5] != "-":
        raise ValidationError("Date must use '-' separators: DD-MM-YYYY")

    day_str = text[0:2]
    month_str = text[3:5]
    year_str = text[6:10]
    if not (is_ascii_digits(day_str) and is_ascii_digits(month_str)
            and is_ascii_digits(year_str)):
        raise ValidationError("Day, month and year must be numbers: DD-MM-YYYY")

    day = digits_to_int(day_str)
    month = digits_to_int(month_str)
    year = digits_to_int(year_str)

    if year < MIN_YEAR or year > MAX_YEAR:
        raise ValidationError("Year must be between " + str(MIN_YEAR) + " and " + str(MAX_YEAR))
    if month < 1 or month > 12:
        raise ValidationError("Month must be between 01 and 12")
    max_day = days_in_month(month, year)
    if day < 1 or day > max_day:
        raise ValidationError("Day must be between 01 and " + str(max_day)
                              + " for " + month_str + "-" + year_str)
    return text


def is_valid_date(text):
    try:
        validate_date(text)
        return True
    except ValidationError:
        return False


def date_sort_key(text):
    """(year, month, day) tuple so "DD-MM-YYYY" strings can be sorted chronologically."""
    return (digits_to_int(text[6:10]), digits_to_int(text[3:5]), digits_to_int(text[0:2]))


# ----------------------------------------------------------------------
# Free text (descriptions, categories)
# ----------------------------------------------------------------------

def validate_text(text, label, max_length=60):
    """Trim, collapse whitespace (including newlines) and length-check free text."""
    if not isinstance(text, str):
        raise ValidationError(label + " must be text")
    cleaned = " ".join(text.split())
    if cleaned == "":
        raise ValidationError(label + " cannot be empty")
    if len(cleaned) > max_length:
        raise ValidationError(label + " must be at most " + str(max_length) + " characters")
    return cleaned


# ----------------------------------------------------------------------
# Member names
# ----------------------------------------------------------------------

def validate_member_name(name):
    """Return a cleaned name: trimmed, inner whitespace collapsed, allowed chars only."""
    if not isinstance(name, str):
        raise ValidationError("Name must be text")
    cleaned = " ".join(name.split())
    if cleaned == "":
        raise ValidationError("Name cannot be empty")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValidationError("Name must be at most " + str(MAX_NAME_LENGTH) + " characters")
    for ch in cleaned:
        if not (ch.isalnum() or ch in " -_.'"):
            raise ValidationError("Name contains an invalid character: " + repr(ch))
    return cleaned


def validate_unique_names(names):
    """
    Validate every name and ensure none repeat (case-insensitive:
    "Asha" and "asha" collide). Returns the cleaned list in original order.
    """
    cleaned_names = []
    seen = {}
    for raw in names:
        cleaned = validate_member_name(raw)
        key = cleaned.lower()
        if key in seen:
            raise ValidationError("Duplicate member name: " + repr(cleaned)
                                  + " (already added as " + repr(seen[key]) + ")")
        seen[key] = cleaned
        cleaned_names.append(cleaned)
    if len(cleaned_names) == 0:
        raise ValidationError("At least one member name is required")
    return cleaned_names


def validate_new_member(name, existing_names):
    """Check a single name against names already in a group. Returns the cleaned name."""
    cleaned = validate_member_name(name)
    for existing in existing_names:
        if existing.lower() == cleaned.lower():
            raise ValidationError("Member " + repr(existing) + " already exists")
    return cleaned


# ----------------------------------------------------------------------
# Splits
# ----------------------------------------------------------------------

def validate_exact_split(total_paise, shares):
    """
    shares: dict {name: paise_int}. Every share must be a non-negative int and
    the shares must add up to exactly `total_paise`. Returns `shares`.
    """
    if len(shares) == 0:
        raise ValidationError("Split must include at least one person")
    running = 0
    for name in shares:
        value = shares[name]
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValidationError("Share for " + repr(name) + " must be in whole paise")
        if value < 0:
            raise ValidationError("Share for " + repr(name) + " cannot be negative")
        running += value
    if running != total_paise:
        diff = total_paise - running
        word = "short by" if diff > 0 else "over by"
        raise ValidationError("Exact split must equal the total: shares are "
                              + word + " " + _paise_str(abs(diff)))
    return shares


def parse_exact_split(total_paise, share_texts):
    """Like validate_exact_split, but takes {name: "amount string"} straight from input."""
    shares = {}
    for name in share_texts:
        try:
            shares[name] = parse_amount(share_texts[name], allow_zero=True)
        except ValidationError as err:
            raise ValidationError("Share for " + repr(name) + ": " + str(err))
    return validate_exact_split(total_paise, shares)


def parse_percentage(text):
    """
    Convert a percentage string to hundredths of a percent.
        "50" -> 5000, "33.33" -> 3333, "12.5" -> 1250
    """
    value = _parse_fixed_point(text, 2, "Percentage")
    if value > FULL_PERCENT:
        raise ValidationError("Percentage cannot exceed 100")
    return value


def validate_percentage_split(percent_texts):
    """
    percent_texts: dict {name: "percentage string"}.
    Percentages must each be valid and sum to exactly 100 (to two decimals).
    Returns {name: hundredths_of_percent}.
    """
    if len(percent_texts) == 0:
        raise ValidationError("Split must include at least one person")
    parsed = {}
    running = 0
    for name in percent_texts:
        try:
            parsed[name] = parse_percentage(percent_texts[name])
        except ValidationError as err:
            raise ValidationError("Percentage for " + repr(name) + ": " + str(err))
        running += parsed[name]
    if running != FULL_PERCENT:
        raise ValidationError("Percentages must add up to 100, but they add up to "
                              + format_hundredths(running))
    return parsed


def validate_split_members(split_names, group_names):
    """Every name in a split must belong to the group, and appear only once."""
    known = {}
    for name in group_names:
        known[name.lower()] = name
    seen = {}
    for name in split_names:
        key = name.strip().lower()
        if key not in known:
            raise ValidationError(repr(name) + " is not a member of this group")
        if key in seen:
            raise ValidationError(repr(name) + " is listed more than once in the split")
        seen[key] = True
    return True


# ----------------------------------------------------------------------
# Formatting helpers for error messages (kept local so validator has no deps)
# ----------------------------------------------------------------------

def format_hundredths(value):
    whole = value // 100
    frac = value % 100
    return str(whole) + "." + ("0" if frac < 10 else "") + str(frac)


def _paise_str(paise):
    return "Rs. " + format_hundredths(paise)
