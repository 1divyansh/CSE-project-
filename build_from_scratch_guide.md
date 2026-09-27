# Build SplitSquad from Scratch: A Step-by-Step Guide

This tutorial rebuilds the **in-memory SplitSquad** expense splitter from an empty folder. You end up with the same seven files that are in this repository, written in the order that lets you test each one before moving on.

**The rules of the project**
- **No `import` of standard or external libraries.** No `math`, `json`, `csv` or `dataclasses`. The only `import` statements load our own `.py` files.
- **Everything lives in memory.** There is no file saving or loading; when the program exits, the data is gone.
- **Built-in functions are fine.** `print`, `input`, `len`, `str`, `int`, `ord`, `min`, `range`, `sum` and `abs` are part of the language, not imports.

**What you need:** Python 3.7 or newer (the code relies on dicts keeping insertion order, which 3.7 guarantees), a terminal and a text editor. On Windows the command is usually `py` instead of `python3`.

**How to use this guide**
1. Read [§1](#1-conceptual-mental-model) before writing any code. The maths only makes sense once you understand the model.
2. Follow [§2](#2-development-order) for the order to create the files.
3. Work through [§3](#3-step-by-step-implementation) one step at a time. Each step ends with a **checkpoint** in [§4](#4-testing-strategy). Don't start the next file until the checkpoint passes.

---

## 1. Conceptual Mental Model

### 1.1 What an expense splitter actually tracks

Take a small trip to Goa with three friends:

| Expense | Paid by | Shared by | Amount |
|---|---|---|---|
| Dinner | Asha | Asha, Ravi, Meera | ₹300.00 |
| Cab | Ravi | Ravi, Meera | ₹10.00 |

Every expense records two separate facts:
1. **Who paid:** one person handed over money for the group.
2. **Who owes:** the people who shared the cost, each owing a **share**.

The shares of one expense must add up to its amount: dinner is ₹100 + ₹100 + ₹100 = ₹300.

### 1.2 Net balance: one number per person

You don't need to track who owes whom for each individual expense. Everything reduces to one number per person:

```
balance = (total this person paid)  -  (total of this person's shares)
```

| Person | Paid | Shares owed | Balance | Meaning |
|---|---|---|---|---|
| Asha | 300.00 | 100.00 | **+200.00** | the group owes her ₹200 |
| Ravi | 10.00 | 100.00 + 5.00 | **−95.00** | he owes ₹95 |
| Meera | 0.00 | 100.00 + 5.00 | **−105.00** | she owes ₹105 |

**Sign convention used throughout the project:**
- **Positive:** the person is owed money (a *creditor*).
- **Negative:** the person owes money (a *debtor*).

Ravi doesn't need to pay Asha for dinner and then get ₹5 back from Meera for the cab. Only the **net** position matters, and that's what makes it possible to settle with just a few payments.

### 1.3 The Zero-Sum invariant

Add up the balances above: `200 − 95 − 105 = 0`. That's always true, not a coincidence:

- Each expense adds **+amount** to the payer's balance.
- It subtracts the shares from the participants, and **the shares add up to the amount**.
- So each expense changes the overall total by `+amount − amount = 0`.
- Summing over all expenses, **the balances always add up to exactly 0.**

Money only moves between members; the group as a whole never gains or loses any. In programming terms this is an **invariant**: a statement that must be true at every moment. If it's ever false, some part of the code has a bug.

The project uses this invariant as an **alarm**:
- The ledger adds up the balances every time it calculates them and raises an error if the total isn't 0.
- The settlement optimizer refuses balances that don't add up to 0.
- The balance table prints a **Total** row that always shows `0.00`, visible proof on every screen.

**What would set the alarm off?** Mostly rounding. Split ₹100 three ways as `33.33 + 33.33 + 33.33` and you've collected ₹99.99, so one paisa has disappeared and the balances add up to +1 paisa instead of 0. Preventing that is the job of the split calculator.

### 1.4 Why money must be integers (paise), not floats

Computers store floats in binary, and most decimal fractions can't be stored exactly:

```text
>>> 0.1 + 0.2
0.30000000000000004
```

If balances were floats, the zero-sum check would fail because of tiny stray fractions. So **every amount is a whole number of paise**: ₹12.50 is stored as `1250`. Integer addition and subtraction are exact, so `total == 0` can be trusted. Python integers also never overflow.

That makes one decision unavoidable: **₹100 (10000 paise) can't be split exactly three ways.** Someone must pay 3334 paise. The project decides who, the same way every time, using two operators:

```
10000 // 3  = 3333      (floor division: the part that divides evenly)
10000 %  3  = 1         (modulo: what is left over)

and always:  a == (a // b) * b + (a % b)      ->  10000 == 3333*3 + 1
```

Give everyone `a // b`, then give the leftover `a % b` paise out one at a time. **The total comes back to exactly `a`.** That identity is the whole rounding strategy.

### 1.5 From balances to payments

Once you have balances, settling up means sending money from debtors to creditors until everyone is at 0. The project uses a **greedy** method:

1. Take the biggest creditor and the biggest debtor.
2. The debtor pays the smaller of the two amounts: `min(credit, debt)`.
3. That brings at least one of them to exactly 0. Repeat.

For the Goa example, Meera (−105) pays Asha (+200) ₹105, and then Ravi (−95) pays Asha (+95) ₹95. That's two payments and everyone is at 0. Each round clears at least one person, so **n people never need more than n − 1 payments.**

### 1.6 The whole pipeline in one picture

Each arrow is a function call, and each label is the **type of data** handed over. Settle these data shapes before writing any code.

```
 "300"            ──validator.parse_amount──────────►  30000                      int (paise)
 "1" / "asha"     ──main.pick_member / find_member──►  "Asha"                     str (stored name)
 "50","25","25"   ──validator.parse_percentage──────►  {"Asha": 5000, ...}        dict name -> int
                   ──split_calculator.calculate_split►  {"Asha": 15000, ...}       dict name -> paise, sums to amount
                   ──ledger.add_expense─────────────►  Expense appended to group.expenses (list)
                   ──ledger.calculate_balances──────►  {"Asha": 20000, ...}       dict name -> paise, sums to 0
                   ──settlement_optimizer───────────►  [Settlement, ...]          list of objects
                   ──report_generator───────────────►  text table on screen
```

### 1.7 The rules you will test

| # | Rule | Where it's checked |
|---|---|---|
| 1 | Parsed amounts are whole, non-negative numbers of paise | `validator.py` |
| 2 | For every expense, the shares add up to the amount | `split_calculator.py` |
| 3 | Each share is within 1 paisa of the exact fair share | `split_calculator.py` |
| 4 | All balances add up to 0 | `ledger.py` |
| 5 | After the settlement plan, everyone is at 0, using at most n − 1 payments | `settlement_optimizer.py` |

---

## 2. Development Order

### 2.1 The order

| Step | File | Imports | Why it comes here | What you can test once it exists |
|---|---|---|---|---|
| 1 | `models.py` | nothing | Every other file uses these classes (Member, Expense, Group), and `format_paise` makes test output readable | create objects, look members up |
| 2 | `validator.py` | nothing | All money enters the program here as text; the calculator reuses its checks | text to paise, rejecting bad input |
| 3 | `split_calculator.py` | models, validator | Pure maths: data in, dict out. The easiest place to prove the rounding | splits always add up to the total |
| 4 | `ledger.py` | models, validator, split_calculator | Needs working splits; produces balances | balances add up to 0; bad changes are undone |
| 5 | `settlement_optimizer.py` | models, validator | Needs balances to work on | plans bring everyone to 0 |
| 6 | `report_generator.py` | models | Displays balances and plans, so both must exist | table layout |
| 7 | `main.py` | all of the above | Only input and output: no maths of its own | the full app, by hand or with scripted input |

```
            main.py            (7)
   ┌───────┬───┴────┬──────────────┐
report(6) optimizer(5)  ledger(4)   │
   │         │      ┌───┴────┐     │
   │         │  calculator(3)│     │
   │         │      │        │     │
   └──── models(1) ─┴── validator(2)
```

### 2.2 Why this order matters for testing

1. **You can only test a module once everything it imports works.** Built bottom-up, every `import` in a new file points at code you've already tested.
2. **Bugs stay easy to find.** If a checkpoint fails in step 4, steps 1–3 have already passed, so the bug is in the new file.
3. **Logic first, input/output last.** Steps 1–6 contain no `input()` calls, so you can test them directly in the Python REPL (the interactive `>>>` prompt) with exact values. `main.py` has no maths at all. Starting with it would mean debugging keyboard handling and arithmetic at the same time.
4. **The rules are checked in layers.** Rule 2 is proven in step 3 before the ledger relies on it for rule 4, and rule 4 is proven in step 4 before the optimizer relies on it for rule 5.

### 2.3 Decide the data shapes before coding

Write these down first. They're the agreements between files, and keeping them is what lets each file be built and tested separately.

| Concept | Representation | Example |
|---|---|---|
| Money | `int` paise | `120050` means ₹1200.50 |
| Percentage | `int` hundredths of a percent | `3333` means 33.33%, `10000` means 100% |
| Member identity | `str`, the name as stored | `"Asha"` |
| Per-person inputs | `dict` name → `int` | `{"Asha": 2, "Ravi": 1}` |
| Shares of an expense | `dict` name → paise, **adds up to the amount** | `{"Asha": 3334, "Ravi": 3333, "Meera": 3333}` |
| Balances | `dict` name → paise, **adds up to 0** | `{"Asha": 20000, "Ravi": -9500, "Meera": -10500}` |
| Settlement plan | `list` of `Settlement` objects | `[Settlement(Meera pays Asha 105.00), ...]` |
| Bad input | raise `ValidationError(message)` | `ValidationError("Amount cannot be empty")` |

---

## 3. Step-by-Step Implementation

### Step 0: Set up

```text
mkdir splitsquad
cd splitsquad
python3 --version        # must be 3.7 or newer
```

Create each file as you reach its step. **Always start the REPL from inside this folder** (`python3`, or `py` on Windows) so that lines like `from models import Group` find your files.

---

### Step 1: `models.py`, the data model

**Goal:** four plain classes plus one formatting helper. No logic yet, and no imports.

**1a. Module docstring and split-type constants.** Named constants turn typos into immediate errors: `SPLIT_EQAUL` raises `NameError`, whereas `"eqaul"` would just quietly never match.

*`models.py`, lines 1–16:*

```python
"""
models.py - Data classes for SplitSquad (in-memory only).

No imports. Everything lives in ordinary Python lists and dicts for the
current session; nothing is saved when the program exits.

Money is always stored as an int in paise (1 rupee = 100 paise), so there
are no floating-point rounding errors.
"""


SPLIT_EQUAL = "equal"
SPLIT_EXACT = "exact"
SPLIT_PERCENTAGE = "percentage"
SPLIT_SHARES = "shares"
SPLIT_TYPES = (SPLIT_EQUAL, SPLIT_EXACT, SPLIT_PERCENTAGE, SPLIT_SHARES)
```

**1b. `format_paise`.** You need this before anything else, because every test prints money.

*`models.py`, lines 19–29:*

```python
def format_paise(paise):
    """Turn integer paise into a rupee string: 125050 -> '1250.50', -5 -> '-0.05'."""
    sign = ""
    if paise < 0:
        sign = "-"
        paise = -paise
    rupees = paise // 100
    cents = paise % 100
    if cents < 10:
        return sign + str(rupees) + ".0" + str(cents)
    return sign + str(rupees) + "." + str(cents)
```

How it works:
- `// 100` gives whole rupees and `% 100` gives the leftover paise.
- Pad paise under 10 with a zero, so 7 paise shows as `.07`, not `.7`.
- **Handle the sign first.** Python's `//` rounds towards negative infinity, so `-5 // 100 == -1` and `-5 % 100 == 95`. Without the sign handling, −5 paise would print as `-1.95`.

**1c. `Member`, `Expense` and `Settlement`.** Each has an `__init__` that stores fields and a `__repr__` that returns readable text.

*`models.py`, lines 32–39:*

```python
class Member:
    """A person in the group. Names are unique within a group (ignoring case)."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "Member(name=" + repr(self.name) + ")"
```

*`models.py`, lines 42–67:*

```python
class Expense:
    """
    One shared cost.

    amount     : total in paise
    paid_by    : name of the member who paid
    shares     : dict {member_name: paise they owe}; values add up to amount
    split_type : "equal", "exact", "percentage" or "shares"
    """

    def __init__(self, description, amount, paid_by, shares, split_type=SPLIT_EQUAL):
        self.description = description
        self.amount = amount
        self.paid_by = paid_by
        self.shares = shares
        self.split_type = split_type

    def __repr__(self):
        share_text = []
        for name in self.shares:
            share_text.append(name + ": " + format_paise(self.shares[name]))
        return ("Expense(description=" + repr(self.description)
                + ", amount=" + format_paise(self.amount)
                + ", paid_by=" + repr(self.paid_by)
                + ", split_type=" + repr(self.split_type)
                + ", shares={" + ", ".join(share_text) + "})")
```

*`models.py`, lines 70–80:*

```python
class Settlement:
    """A payment of `amount` paise from `payer` to `payee` that clears a debt."""

    def __init__(self, payer, payee, amount):
        self.payer = payer
        self.payee = payee
        self.amount = amount

    def __repr__(self):
        return ("Settlement(" + self.payer + " pays " + self.payee
                + " " + format_paise(self.amount) + ")")
```

Design decisions to understand:
- `Expense.paid_by` and the keys of `Expense.shares` are **names (strings)**, not `Member` objects. Strings work as dict keys and print easily, and names will be unique.
- `Expense.__init__` **doesn't check** that the shares add up to the amount. The split calculator guarantees that, and the ledger checks it again later. Keep the model simple.
- A `Settlement` is only a *suggested* payment. It isn't stored in the group.

**1d. `Group`.** It holds two plain lists: `members` and `expenses`.

*`models.py`, lines 83–124:*

```python
class Group:
    """A group of members and their expenses for the current session."""

    def __init__(self, name):
        self.name = name
        self.members = []    # list of Member
        self.expenses = []   # list of Expense

    def find_member(self, name):
        """Return the Member with this name (case-insensitive), or None."""
        wanted = name.strip().lower()
        for member in self.members:
            if member.name.lower() == wanted:
                return member
        return None

    def member_names(self):
        names = []
        for member in self.members:
            names.append(member.name)
        return names

    def add_member(self, name):
        member = Member(name)
        self.members.append(member)
        return member

    def add_expense(self, expense):
        self.expenses.append(expense)
        return expense

    def total_spent(self):
        total = 0
        for expense in self.expenses:
            total += expense.amount
        return total

    def __repr__(self):
        return ("Group(name=" + repr(self.name)
                + ", members=" + repr(self.member_names())
                + ", expenses=" + str(len(self.expenses))
                + ", total=" + format_paise(self.total_spent()) + ")")
```

- `find_member` is **case-insensitive** and ignores surrounding spaces, so `"  ASHA "` finds `Asha`. It returns `None` when nobody matches.
- `add_member` doesn't check for duplicates. The validator (step 2) does that before `main.py` calls it.

**Common mistakes:** using `/` (which returns a float) instead of `//`; forgetting the zero padding; not handling negative numbers.

**Checkpoint:** run [§4.2](#42-checkpoint-1-modelspy). **Done when** `format_paise(-5)` returns `'-0.05'` and `find_member("  ASHA ")` finds Asha.

---

### Step 2: `validator.py`, turning text into checked integers

**Goal:** convert raw text into integers or raise **one clear error message**. Every public function either **returns the cleaned value** or **raises `ValidationError`**.

**2a. The exception type.**

*`validator.py`, lines 1–11:*

```python
"""
validator.py - Manual input validation for SplitSquad.

No imports: every check uses string methods, loops and integer arithmetic.
Each function returns the cleaned value on success and raises
ValidationError (a ValueError) with a readable message on failure.
"""


class ValidationError(ValueError):
    """Bad user input. The message is meant to be shown to the user."""
```

Inheriting from `ValueError` means `except Exception` in `main.py` will catch it, and `str(error)` returns your message.

**2b. Digit helpers, written without `int()` or `isdigit()`.**

*`validator.py`, lines 14–29:*

```python
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
```

- `_is_digits` compares characters: `"0"` to `"9"` are consecutive character codes (48–57). It avoids `str.isdigit()`, which also accepts `"²"` and digits from other scripts.
- `_to_int` uses **Horner's method**: `value = value * 10 + digit`, where `ord(ch) - ord("0")` turns `"7"` into `7`. Tracing `"407"`: 0 → 4 → 40 → 407.

**2c. The decimal parser.** This is the core of the file. Write it carefully and check it line by line.

*`validator.py`, lines 32–60:*

```python
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
```

The plan behind it:
1. Strip spaces, then reject empty input, a leading `-`, and more than one `.`. The dot check **must** come before `split(".")`, or `"12.5.1"` would split into three pieces and the two-variable unpacking would crash.
2. Split into `whole` and `fraction`, and require both to be plain digits. This rejects `"1,000"`, `"+5"`, `"1e3"` and `"abc"`.
3. **Reject** more than two decimals rather than rounding. Silently rounding money is a bug.
4. **Pad the fraction on the right** to two digits: in `"12.5"` the 5 means *fifty* paise.
5. Return `whole * 100 + fraction`.

**2d. The error-message helper and `parse_amount`.**

*`validator.py`, lines 63–66:*

```python
def _hundredths_text(value):
    """1250 -> '12.50' (used in error messages)."""
    fraction = value % 100
    return str(value // 100) + "." + ("0" if fraction < 10 else "") + str(fraction)
```

*`validator.py`, lines 69–81:*

```python
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
```

`allow_zero=True` is for exact splits, where someone may legitimately owe ₹0. `_hundredths_text` is only ever called with non-negative numbers, since it has no sign handling.

**2e. Split-total checks.** These are the first code-level guards for rule 2.

*`validator.py`, lines 84–107:*

```python
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
```

*`validator.py`, lines 110–134:*

```python
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
```

Percentages reuse the same parser, so `"33.33"` becomes `3333` hundredths and 100% is `10000`. Users can type decimals while every comparison stays an exact integer check.

**2f. Member names.**

*`validator.py`, lines 137–157:*

```python
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
```

- `" ".join(name.split())` collapses any run of whitespace into one space and trims both ends.
- The function takes the `group` as a parameter and only calls `group.find_member`, so `validator.py` still imports nothing.

**Checkpoint:** run [§4.3](#43-checkpoint-2-validatorpy). **Done when** `parse_amount("99.9")` returns `9990` and every bad input produces a readable `ValidationError`.

---

### Step 3: `split_calculator.py`, dividing money without losing paise

**Goal:** four split types, each returning `{name: paise}` that **adds up to exactly the total**. Only `//`, `%`, `*` and `+` are used, with no `math` module.

**3a. Docstring, imports and shared checks.** Put these at the top of the file.

*`split_calculator.py`, lines 1–19:*

```python
"""
split_calculator.py - Work out how much each member owes for an expense.

No imports beyond our own modules: only //, %, * and + are used.
Money is integer paise, and every function returns a dict
{member_name: paise_owed} whose values add up to EXACTLY the total.

Rounding rule (no paisa is ever dropped):
  1. Everyone gets the rounded-down amount, found with //.
  2. The paise left over, found with %, are handed out one at a time
     to the first few members in the list.

      split_equal(10000, ["Asha", "Ravi", "Meera"])
      10000 // 3 = 3333 each,  10000 % 3 = 1 paisa left over
      -> {"Asha": 3334, "Ravi": 3333, "Meera": 3333}
"""

from models import SPLIT_EQUAL, SPLIT_EXACT, SPLIT_PERCENTAGE, SPLIT_SHARES
from validator import ValidationError, validate_exact_split, validate_percentages
```

*`split_calculator.py`, lines 22–45:*

```python
# ----------------------------------------------------------------------
# Checks shared by every split
# ----------------------------------------------------------------------

def _check_inputs(total, members):
    if total <= 0:
        raise ValidationError("Total must be greater than zero")
    if len(members) == 0:
        raise ValidationError("The split needs at least one person")
    seen = []
    for name in members:
        if name in seen:
            raise ValidationError(name + " is listed twice in the split")
        seen.append(name)


def _check_values_match(members, values, label):
    """Every member needs exactly one value, and no one else may have one."""
    for name in members:
        if name not in values:
            raise ValidationError("Missing " + label + " for " + name)
    for name in values:
        if name not in members:
            raise ValidationError(name + " has a " + label + " but is not in the split")
```

- `_check_inputs` rejects a total of zero or less, an empty list of people, and the same person listed twice.
- `_check_values_match` makes sure the per-person dict describes exactly the people in the split.

**3b. `split_equal`.** Write this first: it's the simplest place to see the `//` and `%` idea at work. (In the finished file it sits below `_split_by_weights`.)

*`split_calculator.py`, lines 78–101:*

```python
# ----------------------------------------------------------------------
# The four split types
# ----------------------------------------------------------------------

def split_equal(total, members):
    """
    Everyone pays the same; the first (total % n) people pay 1 paisa more.
        split_equal(10000, ["Asha", "Ravi", "Meera"])
            -> {"Asha": 3334, "Ravi": 3333, "Meera": 3333}
    """
    _check_inputs(total, members)
    count = len(members)
    base = total // count
    extra = total % count

    result = {}
    position = 0
    for name in members:
        if position < extra:
            result[name] = base + 1
        else:
            result[name] = base
        position += 1
    return result
```

- `base = total // count` is everyone's rounded-down share.
- `extra = total % count` is the leftover, and it's always less than `count`. The first `extra` people pay `base + 1`.
- Total: `base × count + extra`, which equals `total` exactly. For example, `10000` among 3 gives **3334, 3333, 3333**.

**3c. `split_exact`.** No maths is needed: the user typed every amount, and the validator confirms they add up.

*`split_calculator.py`, lines 104–117:*

```python
def split_exact(total, members, amounts):
    """
    Each person owes a stated amount in paise; they must add up to the total.
        split_exact(10000, ["Asha", "Ravi"], {"Asha": 7000, "Ravi": 3000})
            -> {"Asha": 7000, "Ravi": 3000}
    """
    _check_inputs(total, members)
    _check_values_match(members, amounts, "amount")
    validate_exact_split(total, amounts)

    result = {}
    for name in members:
        result[name] = amounts[name]
    return result
```

**3d. `_split_by_weights`, for proportional splits.** Put this **above** `split_equal`. Percentage and shares splits are both "divide in proportion to some whole-number weights", so one helper handles both.

*`split_calculator.py`, lines 48–75:*

```python
def _split_by_weights(total, members, weights):
    """
    Split `total` in proportion to whole-number `weights` {name: weight}.

    Each person first gets (total * weight) // sum_of_weights. Rounding down
    leaves a few paise unassigned, and those go one each to the first
    members in the list who were actually rounded down, i.e. whose
    (total * weight) % sum_of_weights is not 0. Anyone whose share came out
    exact (including a weight of 0) never receives a stray paisa, and there
    are always enough rounded-down members to absorb the leftover.
    """
    weight_sum = 0
    for name in members:
        weight_sum += weights[name]

    result = {}
    rounded_down = []
    assigned = 0
    for name in members:
        result[name] = (total * weights[name]) // weight_sum
        assigned += result[name]
        if (total * weights[name]) % weight_sum != 0:
            rounded_down.append(name)

    leftover = total - assigned
    for position in range(leftover):
        result[rounded_down[position]] += 1
    return result
```

The reasoning behind it:
1. **Multiply before dividing.** The exact share is `total × weight / W`, where `W` is the sum of all weights. Calculating `(total * weight) // W` loses only the final fraction. Dividing first (`weight // W`) would give 0 for almost everyone.
2. `(total * weight) % W` is the part that was cut off. If it's 0, the share was already exact, so that person is **not** added to `rounded_down`.
3. `leftover = total - assigned` counts the paise that are still missing. Hand them out one each to the first people in `rounded_down`.

**Why there are always enough rounded-down people.** Write `total·wᵢ = qᵢ·W + rᵢ`, where `qᵢ` is the `//` result and `rᵢ` is the `%` result. Adding up over everyone gives `Σrᵢ = W · leftover`. Each non-zero `rᵢ` is less than `W`, so if `k` people were rounded down, `leftover < k`. The loop never runs past the end of the list, and nobody ends up more than 1 paisa from their exact share.

Worked example: 10 paise split 2 : 1 : 1 shares, so W = 4.

| Person | weight | total×weight | `// 4` | `% 4` | rounded down? |
|---|---|---|---|---|---|
| Asha | 2 | 20 | 5 | 0 | no (exactly 5.00) |
| Ravi | 1 | 10 | 2 | 2 | yes |
| Meera | 1 | 10 | 2 | 2 | yes |

Assigned 9, leftover 1, which goes to Ravi. The result is `{Asha: 5, Ravi: 3, Meera: 2}`.

**3e. Percentage and shares splits.** Thin wrappers that check their inputs and call the helper.

*`split_calculator.py`, lines 120–153:*

```python
def split_percentage(total, members, percentages):
    """
    percentages: {name: hundredths of a percent}, as returned by
    validator.parse_percentage ("50" -> 5000, "33.33" -> 3333).
    They must add up to 10000 (100%).
        split_percentage(10000, ["Asha", "Ravi"], {"Asha": 7000, "Ravi": 3000})
            -> {"Asha": 7000, "Ravi": 3000}
    """
    _check_inputs(total, members)
    _check_values_match(members, percentages, "percentage")
    for name in members:
        if percentages[name] < 0:
            raise ValidationError(name + "'s percentage cannot be negative")
    validate_percentages(percentages)
    return _split_by_weights(total, members, percentages)


def split_shares(total, members, shares):
    """
    shares: {name: whole number of shares}, e.g. 2 for a couple, 1 for a single.
    A share of 0 means the person owes nothing.
        split_shares(10000, ["Asha", "Ravi", "Meera"], {"Asha": 2, "Ravi": 1, "Meera": 1})
            -> {"Asha": 5000, "Ravi": 2500, "Meera": 2500}
    """
    _check_inputs(total, members)
    _check_values_match(members, shares, "share count")
    share_total = 0
    for name in members:
        if shares[name] < 0:
            raise ValidationError(name + "'s shares cannot be negative")
        share_total += shares[name]
    if share_total == 0:
        raise ValidationError("At least one person must have more than 0 shares")
    return _split_by_weights(total, members, shares)
```

The all-zero shares check comes before the helper is called, because `W = 0` would mean dividing by zero.

**3f. The dispatcher.** One entry point, so the ledger and the menu only need to know one function name.

*`split_calculator.py`, lines 156–171:*

```python
def calculate_split(split_type, total, members, values=None):
    """
    Run the right split by name. `values` is the per-person dict needed by
    exact, percentage and shares splits; it is ignored for equal splits.
    """
    if split_type == SPLIT_EQUAL:
        return split_equal(total, members)
    if values is None:
        raise ValidationError("A " + split_type + " split needs a value for each person")
    if split_type == SPLIT_EXACT:
        return split_exact(total, members, values)
    if split_type == SPLIT_PERCENTAGE:
        return split_percentage(total, members, values)
    if split_type == SPLIT_SHARES:
        return split_shares(total, members, values)
    raise ValidationError("Unknown split type: " + str(split_type))
```

**Checkpoint:** run [§4.4](#44-checkpoint-3-split_calculatorpy), including the automated checks that loop over thousands of cases. **Done when** those checks report `0` problems.

---

### Step 4: `ledger.py`, the in-memory ledger

**Goal:** an `InMemoryLedger` class that adds expenses to and removes them from `group.expenses`, and **calculates balances on demand**, checking every time that they add up to 0.

**4a. Imports, class and name lookup.**

*`ledger.py`, lines 1–24:*

```python
"""
ledger.py - In-memory ledger for a SplitSquad group.

No standard-library imports and no file handling: expenses live only in
group.expenses (a plain Python list) for as long as the program runs.

Balance sign convention (integer paise):
    positive -> the group owes this member money
    negative -> this member owes the group money

Money only moves between members, so the balances must always add up to
exactly 0. calculate_balances() checks this every time it runs.
"""

from models import Expense, SPLIT_EQUAL
from validator import ValidationError
from split_calculator import calculate_split


class InMemoryLedger:
    """Adds, removes and balances the expenses of one Group."""

    def __init__(self, group):
        self.group = group
```

*`ledger.py`, lines 26–33:*

```python
    # ---- helpers -------------------------------------------------------

    def _member_name(self, name):
        """Return the member's stored spelling ('asha' -> 'Asha') or raise."""
        member = self.group.find_member(name)
        if member is None:
            raise ValidationError(name + " is not a member of " + self.group.name)
        return member.name
```

- **`self.group` is a reference, not a copy.** `main.py` and the ledger share one `Group` object, so a change made through the ledger is immediately visible everywhere else.
- `_member_name` converts any spelling (`"asha"`) to the stored one (`"Asha"`), so balance dict keys always match exactly.

**4b. `calculate_balances`. Write this before `add_expense`,** because `add_expense` relies on it to check each change.

*`ledger.py`, lines 97–122:*

```python
    # ---- balances ------------------------------------------------------

    def calculate_balances(self):
        """
        Work out every member's net balance from scratch:
            the payer gets +amount, each person in the split gets -their share.
        Returns {member_name: paise}.
        """
        balances = {}
        for member in self.group.members:
            balances[member.name] = 0

        for expense in self.group.expenses:
            balances[self._member_name(expense.paid_by)] += expense.amount
            for name in expense.shares:
                balances[self._member_name(name)] -= expense.shares[name]

        # Manual invariant check. Written as an explicit raise instead of an
        # `assert` statement because `python -O` silently removes asserts.
        total = 0
        for name in balances:
            total += balances[name]
        if total != 0:
            raise AssertionError("Balances add up to " + str(total)
                                 + " paise instead of 0 - the ledger is inconsistent")
        return balances
```

- Start everyone at 0, including members with no expenses yet.
- Each expense gives the payer `+amount` and each participant `−share`.
- Add the balances up and **raise** if the total isn't 0.
- It uses an explicit `raise AssertionError` rather than an `assert` statement, because running `python -O` removes `assert` statements.
- It recalculates everything each time instead of keeping a running total, so there's nothing that can drift out of step with the expense list.

**4c. `add_expense`: check the inputs, calculate the split, append, verify, and undo on failure.** Methods go inside the class, so keep the indentation.

*`ledger.py`, lines 35–76:*

```python
    # ---- expenses ------------------------------------------------------

    def add_expense(self, description, amount, paid_by, members=None,
                    split_type=SPLIT_EQUAL, values=None):
        """
        Create an expense, append it to group.expenses and return it.

        amount     : total in paise (from validator.parse_amount)
        paid_by    : name of the member who paid
        members    : names sharing the cost; None means everyone in the group
        split_type : "equal", "exact", "percentage" or "shares"
        values     : {name: value} for non-equal splits - paise for exact,
                     hundredths of a percent for percentage, share counts for shares
        """
        description = " ".join(description.split())
        if description == "":
            raise ValidationError("Description cannot be empty")
        paid_by = self._member_name(paid_by)

        if members is None:
            members = self.group.member_names()
        names = []
        for name in members:
            names.append(self._member_name(name))

        # Re-key values with the stored spellings so they match `names`.
        clean_values = None
        if values is not None:
            clean_values = {}
            for name in values:
                clean_values[self._member_name(name)] = values[name]

        shares = calculate_split(split_type, amount, names, clean_values)
        expense = Expense(description, amount, paid_by, shares, split_type)

        self.group.expenses.append(expense)
        try:
            self.calculate_balances()
        except AssertionError:
            self.group.expenses.remove(expense)   # undo, then report the problem
            raise
        return expense
```

- Every name is converted to its stored spelling first, **including the keys of `values`**. Otherwise `{"asha": 5000}` wouldn't match `"Asha"`.
- The ledger calls `calculate_split` itself rather than trusting whoever called it.
- The only line that changes data is `self.group.expenses.append(expense)`. If the check afterwards fails, the expense is removed again before the error is passed on. `list.remove` finds this exact object, because `Expense` doesn't define `__eq__`.

**4d. `delete_expense` and `list_expenses`.**

*`ledger.py`, lines 78–95:*

```python
    def delete_expense(self, index):
        """
        Remove the expense at position `index` (0-based) in group.expenses
        and return it.
        """
        expenses = self.group.expenses
        if index < 0 or index >= len(expenses):
            raise ValidationError("There is no expense number " + str(index + 1))
        expense = expenses.pop(index)
        try:
            self.calculate_balances()
        except AssertionError:
            expenses.insert(index, expense)       # put it back exactly where it was
            raise
        return expense

    def list_expenses(self):
        return self.group.expenses
```

`pop(index)` removes the item and returns it. If the check fails, `insert(index, expense)` puts it back in the same position.

**Checkpoint:** run [§4.5](#45-checkpoint-4-ledgerpy). That includes **deliberately breaking the zero-sum rule** to prove the alarm goes off and the change is undone.

---

### Step 5: `settlement_optimizer.py`, the greedy settle-up

**Goal:** turn a balances dict into a list of `Settlement` objects that brings everyone to 0.

**5a. Docstring, imports, and "find the largest" loops.** There's no `max()` with a key function and no `heapq` import, just a loop.

*`settlement_optimizer.py`, lines 1–17:*

```python
"""
settlement_optimizer.py - Turn net balances into a short list of payments.

Greedy algorithm:
  1. Find the member with the largest positive balance (biggest creditor)
     and the member with the most negative balance (biggest debtor).
  2. The debtor pays the creditor min(credit, debt), which brings at least
     one of them to exactly 0.
  3. Update both temporary balances and repeat until everyone is at 0.

Every round clears at least one person, so n members need at most n - 1
payments. No imports beyond our own modules; the "largest" searches are
simple loops. All amounts are integer paise, so nothing is rounded.
"""

from models import Settlement
from validator import ValidationError
```

*`settlement_optimizer.py`, lines 20–35:*

```python
def _largest_creditor(balances):
    """Name with the largest positive balance, or None. Ties go to whoever comes first."""
    best = None
    for name in balances:
        if balances[name] > 0 and (best is None or balances[name] > balances[best]):
            best = name
    return best


def _largest_debtor(balances):
    """Name with the most negative balance, or None. Ties go to whoever comes first."""
    best = None
    for name in balances:
        if balances[name] < 0 and (best is None or balances[name] < balances[best]):
            best = name
    return best
```

The comparison is strictly greater (`>`), so on a tie the member who comes first keeps the spot. That makes the results predictable, which matters for testing.

**5b. `simplify_debts`.**

*`settlement_optimizer.py`, lines 38–74:*

```python
def simplify_debts(balances):
    """
    balances: {name: paise} from InMemoryLedger.calculate_balances()
              (positive = is owed money, negative = owes money).

    Returns a list of Settlement objects: payer = debtor, payee = creditor.
    The balances dict passed in is not changed.

        simplify_debts({"Asha": -3000, "Ravi": 5000, "Meera": -2000})
            -> [Settlement(Asha pays Ravi 30.00), Settlement(Meera pays Ravi 20.00)]
    """
    remaining = {}
    total = 0
    for name in balances:
        remaining[name] = balances[name]
        total += balances[name]
    if total != 0:
        raise ValidationError("Balances must add up to 0 before settling (they add up to "
                              + str(total) + " paise)")

    plan = []
    while True:
        creditor = _largest_creditor(remaining)
        debtor = _largest_debtor(remaining)
        if creditor is None or debtor is None:
            break          # sum is 0, so no creditors left means no debtors left too
        amount = min(remaining[creditor], -remaining[debtor])
        plan.append(Settlement(debtor, creditor, amount))
        remaining[creditor] -= amount
        remaining[debtor] += amount

    # Manual check that the plan really clears everyone.
    for name in remaining:
        if remaining[name] != 0:
            raise AssertionError(name + " still has " + str(remaining[name])
                                 + " paise after settling")
    return plan
```

1. **Copy** the balances into `remaining`, so the caller's dict isn't changed.
2. Refuse balances that don't add up to 0 (rule 4 is the precondition).
3. Loop: find the biggest creditor and debtor, set `amount = min(credit, -debt)`, and record `Settlement(debtor, creditor, amount)`. The **debtor pays**. Then update both balances.
4. Stop when there's no creditor or no debtor left. Since the balances add up to 0, both run out together.
5. Check afterwards that everyone is exactly 0 (rule 5).

**Why the loop must stop:** `min(...)` exactly clears one of the two people every round, and nobody's balance crosses zero. The number of non-zero balances goes down each round, so there are at most n − 1 rounds.

**5c. A convenience wrapper for the menu.**

*`settlement_optimizer.py`, lines 77–79:*

```python
def plan_settlements(ledger):
    """Convenience: settlement plan for an InMemoryLedger's current balances."""
    return simplify_debts(ledger.calculate_balances())
```

**Checkpoint:** run [§4.6](#46-checkpoint-5-settlement_optimizerpy).

---

### Step 6: `report_generator.py`, terminal tables

**Goal:** readable tables built only with `ljust`, `rjust`, `*` repetition and `join`.

**6a. Import and money formatting.**

*`report_generator.py`, lines 1–15:*

```python
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
```

**6b. `format_table`.** It works in two passes: **measure** every column, then **draw** the table.

*`report_generator.py`, lines 18–62:*

```python
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
```

- **Pass 1:** each column's width is the length of its longest cell, checked across the headers, rows and footer.
- **Pass 2:** `"-" * (width + 2)` draws the separator lines. `ljust` pads text on the right (left-aligned) and `rjust` pads on the left (right-aligned).
- Money is right-aligned, and every amount has exactly two decimals, so the decimal points line up.
- `separator` and `line` are defined inside `format_table`, so they can read `widths` and `align` without being passed them.

**6c. Title and the two print functions.**

*`report_generator.py`, lines 65–120:*

```python
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
```

The balance table's footer adds up every balance. It should **always** show `0.00`, which puts the zero-sum rule on screen.

**Checkpoint:** run [§4.7](#47-checkpoint-6-report_generatorpy). It connects steps 1–6 for the first time, without any menu.

---

### Step 7: `main.py`, the menu

**Goal:** a `while True:` menu that reads input, calls the tested modules, and **never crashes**. There's no maths here, only input and output.

**7a. Imports and the split-type menu map.** Use `import module` style, so every call shows where it comes from (for example, `validator.parse_amount`).

*`main.py`, lines 1–27:*

```python
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
```

**7b. Input helpers.** `pick_member` accepts either a number from the printed list or a name.

*`main.py`, lines 30–59:*

```python
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
```

**7c. Adding members, and asking for per-person split values.**

*`main.py`, lines 62–88:*

```python
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
```

Always **validate first, then change the data**. If `validate_member_name` raises an error, `group.add_member` never runs.

**7d. `add_expense`: collect and check everything, show a preview, then make one change.**

*`main.py`, lines 91–129:*

```python
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
```

- Every input is turned into checked values before anything is saved.
- The preview calls `split_calculator` directly, so the user sees who owes what first.
- The **only** line that changes data is `the_ledger.add_expense(...)` at the end. A mistake anywhere earlier never leaves half an expense behind.

**7e. Viewing balances, the settle-up plan, and confirming exit.** Each one just passes data from one module to the next.

*`main.py`, lines 132–145:*

```python
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
```

**7f. The main loop and error handling.**

*`main.py`, lines 148–196:*

```python
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
```

- Create **one** `Group` and **one** `InMemoryLedger` sharing it. Together they are the whole in-memory "database".
- **The order of the `except` clauses matters.** Catch `(EOFError, KeyboardInterrupt)` first and exit.
  - `EOFError` (input has ended) is a kind of `Exception`. If `except Exception` caught it, the loop would call `input()` again, hit the same end of input, and loop forever.
  - `KeyboardInterrupt` (Ctrl+C) isn't an `Exception` at all, which is why it's listed explicitly.
- `except Exception as error` then prints any other error and returns to the menu.
- `if __name__ == "__main__":` runs `main()` only when you run this file directly, not when another file imports it.

**Checkpoint:** run [§4.8](#48-checkpoint-7-mainpy) and [§4.9](#49-final-acceptance-checks).

---

## 4. Testing Strategy

### 4.1 How to test in the Python REPL

1. `cd` into the project folder and start `python3` (or `py`).
2. Import only what you're testing: `from validator import parse_amount`.
3. Type an expression and the REPL prints its value. That value is your test result, so compare it with the expected output below.
4. **An error is sometimes the correct result.** When you feed in bad input, a `Traceback` ending in `validator.ValidationError: <message>` is exactly what should happen. Check that the message makes sense to a user.
5. **Restart the REPL after editing a file** (`exit()` and start `python3` again). Python loads each module once per session, so your edits won't appear until you restart.
6. For every function, test three kinds of input: **normal** (typical values), **boundary** (0, 1 paisa, one person, a tie) and **invalid** (text, negatives, duplicates).
7. Test rules with **loops**, not just a few examples: a `for` loop can check thousands of cases in a second. These loops use only built-ins, so they follow the no-imports rule too.

The sessions below were produced by running the actual project code, so your output should match them exactly. Tracebacks are shortened to `...`.

### 4.2 Checkpoint 1: `models.py`

```text
>>> from models import *
>>> format_paise(125050)
'1250.50'
>>> format_paise(7)
'0.07'
>>> format_paise(-5)
'-0.05'
>>> g = Group("Goa")
>>> g.add_member("Asha")
Member(name='Asha')
>>> g.add_member("Ravi")
Member(name='Ravi')
>>> g.find_member("  ASHA ")
Member(name='Asha')
>>> g.find_member("Bob") is None
True
>>> g.member_names()
['Asha', 'Ravi']
>>> e = Expense("Dinner", 30000, "Asha", {"Asha": 15000, "Ravi": 15000})
>>> e
Expense(description='Dinner', amount=300.00, paid_by='Asha', split_type='equal', shares={Asha: 150.00, Ravi: 150.00})
>>> g.expenses.append(e)
>>> g.total_spent()
30000
>>> g
Group(name='Goa', members=['Asha', 'Ravi'], expenses=1, total=300.00)
>>> Settlement("Ravi", "Asha", 15000)
Settlement(Ravi pays Asha 150.00)
```

**Check:** `format_paise(-5)` is `'-0.05'` (the sign is handled correctly), `find_member` works regardless of case and spacing, and `total_spent()` is an integer.

### 4.3 Checkpoint 2: `validator.py`

```text
>>> from validator import *
>>> from models import Group
>>> parse_amount("250")
25000
>>> parse_amount("99.9")
9990
>>> parse_amount(".5")
50
>>> parse_amount(" 12. ")
1200
>>> parse_amount("12.345")
Traceback (most recent call last):
  ...
validator.ValidationError: Amount can have at most 2 decimal places
>>> parse_amount("1,000")
Traceback (most recent call last):
  ...
validator.ValidationError: Amount must be a number, like 250 or 99.50
>>> parse_amount("-5")
Traceback (most recent call last):
  ...
validator.ValidationError: Amount cannot be negative
>>> parse_amount("0")
Traceback (most recent call last):
  ...
validator.ValidationError: Amount must be greater than zero
>>> parse_amount("0", allow_zero=True)
0
>>> parse_percentage("33.33")
3333
>>> parse_percentage("100.01")
Traceback (most recent call last):
  ...
validator.ValidationError: A percentage cannot be more than 100
>>> validate_exact_split(10000, {"Asha": 7000, "Ravi": 3000})
{'Asha': 7000, 'Ravi': 3000}
>>> validate_exact_split(10000, {"Asha": 7000, "Ravi": 2000})
Traceback (most recent call last):
  ...
validator.ValidationError: Amounts are Rs. 10.00 short of the total Rs. 100.00
>>> validate_percentages({"Asha": 5000, "Ravi": 4950})
Traceback (most recent call last):
  ...
validator.ValidationError: Percentages must add up to 100, but they add up to 99.50
>>> g = Group("Goa")
>>> g.add_member("Asha")
Member(name='Asha')
>>> validate_member_name("  Ravi   Kumar ", g)
'Ravi Kumar'
>>> validate_member_name("asha", g)
Traceback (most recent call last):
  ...
validator.ValidationError: Asha is already in Goa
>>> validate_member_name("R2|D2", g)
Traceback (most recent call last):
  ...
validator.ValidationError: Name can only use letters, numbers, spaces, - ' and .
```

**Check:** every good input returns an integer, and every bad input raises `ValidationError` with a message a user would understand, not a Python crash such as `IndexError`.

### 4.4 Checkpoint 3: `split_calculator.py`

Examples first, including the rounding cases:

```text
>>> from split_calculator import *
>>> names = ["Asha", "Ravi", "Meera"]
>>> split_equal(10000, names)
{'Asha': 3334, 'Ravi': 3333, 'Meera': 3333}
>>> split_equal(10001, names)
{'Asha': 3334, 'Ravi': 3334, 'Meera': 3333}
>>> split_equal(2, names)
{'Asha': 1, 'Ravi': 1, 'Meera': 0}
>>> split_exact(10000, ["Asha", "Ravi"], {"Asha": 7000, "Ravi": 3000})
{'Asha': 7000, 'Ravi': 3000}
>>> split_exact(10000, ["Asha", "Ravi"], {"Asha": 7000})
Traceback (most recent call last):
  ...
validator.ValidationError: Missing amount for Ravi
>>> split_percentage(999, names, {"Asha": 5000, "Ravi": 2500, "Meera": 2500})
{'Asha': 500, 'Ravi': 250, 'Meera': 249}
>>> split_shares(10, names, {"Asha": 2, "Ravi": 1, "Meera": 1})
{'Asha': 5, 'Ravi': 3, 'Meera': 2}
>>> split_shares(10000, names, {"Asha": 0, "Ravi": 1, "Meera": 1})
{'Asha': 0, 'Ravi': 5000, 'Meera': 5000}
>>> split_shares(10000, names, {"Asha": 0, "Ravi": 0, "Meera": 0})
Traceback (most recent call last):
  ...
validator.ValidationError: At least one person must have more than 0 shares
>>> split_equal(100, ["Asha", "Asha"])
Traceback (most recent call last):
  ...
validator.ValidationError: Asha is listed twice in the split
>>> calculate_split("percentage", 10000, names)
Traceback (most recent call last):
  ...
validator.ValidationError: A percentage split needs a value for each person
```

Then **prove the rules with loops.** The first check runs every total from 1 to 1000 paise for 1 to 6 people: equal splits must add up to the total, and nobody may differ from anyone else by more than 1 paisa.

```text
>>> from split_calculator import split_equal
>>> problems = 0
>>> for total in range(1, 1001):
...     for n in range(1, 7):
...         people = ["p" + str(i) for i in range(n)]
...         shares = split_equal(total, people)
...         if sum(shares.values()) != total:
...             problems += 1
...         if max(shares.values()) - min(shares.values()) > 1:
...             problems += 1
...
>>> problems
0
```

Next, check weighted splits across thousands of combinations of weights. Each result must add up to the total (rule 2), and each person must be within 1 paisa of their exact share (rule 3). The exact share is `total × w / W`, and "within 1 paisa" is written in integers as `|share × W − total × w| < W`.

```text
>>> from split_calculator import split_shares
>>> problems = 0
>>> for total in range(1, 400):
...     for a in range(0, 4):
...         for b in range(0, 4):
...             for c in range(1, 4):
...                 w = {"A": a, "B": b, "C": c}
...                 W = a + b + c
...                 shares = split_shares(total, ["A", "B", "C"], w)
...                 if sum(shares.values()) != total:
...                     problems += 1
...                 for p in w:
...                     if abs(shares[p] * W - total * w[p]) >= W:
...                         problems += 1
...
>>> problems
0
```

`problems` must be **0**. If it isn't, print the failing case inside the loop to find it.

### 4.5 Checkpoint 4: `ledger.py`

```text
>>> from models import Group, Expense
>>> from ledger import InMemoryLedger
>>> g = Group("Goa")
>>> for name in ["Asha", "Ravi", "Meera"]:
...     g.add_member(name)
...
Member(name='Asha')
Member(name='Ravi')
Member(name='Meera')
>>> L = InMemoryLedger(g)
>>> L.calculate_balances()
{'Asha': 0, 'Ravi': 0, 'Meera': 0}
>>> L.add_expense("Dinner", 30000, "asha")
Expense(description='Dinner', amount=300.00, paid_by='Asha', split_type='equal', shares={Asha: 100.00, Ravi: 100.00, Meera: 100.00})
>>> L.calculate_balances()
{'Asha': 20000, 'Ravi': -10000, 'Meera': -10000}
>>> L.add_expense("Cab", 1000, "Ravi", ["Ravi", "Meera"])
Expense(description='Cab', amount=10.00, paid_by='Ravi', split_type='equal', shares={Ravi: 5.00, Meera: 5.00})
>>> L.calculate_balances()
{'Asha': 20000, 'Ravi': -9500, 'Meera': -10500}
>>> sum(L.calculate_balances().values())
0
>>> L.add_expense("Tea", 300, "Ghost")
Traceback (most recent call last):
  ...
validator.ValidationError: Ghost is not a member of Goa
>>> L.add_expense("Tea", 300, "Ravi", split_type="exact", values={"Ravi": 100, "Meera": 100, "Asha": 50})
Traceback (most recent call last):
  ...
validator.ValidationError: Amounts are Rs. 0.50 short of the total Rs. 3.00
>>> len(g.expenses)
2
>>> g.expenses.append(Expense("Broken", 100, "Asha", {"Ravi": 99}))
>>> L.calculate_balances()
Traceback (most recent call last):
  ...
AssertionError: Balances add up to 1 paise instead of 0 - the ledger is inconsistent
>>> L.add_expense("Snacks", 300, "Meera")
Traceback (most recent call last):
  ...
AssertionError: Balances add up to 1 paise instead of 0 - the ledger is inconsistent
>>> len(g.expenses)
3
>>> g.expenses.pop()
Expense(description='Broken', amount=1.00, paid_by='Asha', split_type='equal', shares={Ravi: 0.99})
>>> L.delete_expense(1)
Expense(description='Cab', amount=10.00, paid_by='Ravi', split_type='equal', shares={Ravi: 5.00, Meera: 5.00})
>>> L.calculate_balances()
{'Asha': 20000, 'Ravi': -10000, 'Meera': -10000}
>>> L.delete_expense(7)
Traceback (most recent call last):
  ...
validator.ValidationError: There is no expense number 8
```

Things to notice:
- `"asha"` is stored as `"Asha"`.
- `sum(...)` of the balances is `0` after every change.
- Bad input (an unknown member, exact amounts that don't add up) is rejected **and the list length doesn't change**.
- We **deliberately inserted a broken expense** whose shares add up to 99 instead of 100. `calculate_balances` raised the alarm, and the next `add_expense` was **undone automatically**: the list still holds 3 items. Always test that your safety checks actually trigger; a check that can never fail isn't protecting anything.

### 4.6 Checkpoint 5: `settlement_optimizer.py`

```text
>>> from settlement_optimizer import simplify_debts
>>> balances = {"Asha": 5000, "Ravi": 1000, "Meera": -4000, "Kiran": -2000}
>>> plan = simplify_debts(balances)
>>> plan
[Settlement(Meera pays Asha 40.00), Settlement(Kiran pays Asha 10.00), Settlement(Kiran pays Ravi 10.00)]
>>> balances
{'Asha': 5000, 'Ravi': 1000, 'Meera': -4000, 'Kiran': -2000}
>>> simplify_debts({"Asha": 0, "Ravi": 0})
[]
>>> simplify_debts({"Asha": 100, "Ravi": -99})
Traceback (most recent call last):
  ...
validator.ValidationError: Balances must add up to 0 before settling (they add up to 1 paise)
```

With four people, this example includes a tie in round 2: Asha and Ravi are both at +1000, and Asha wins because she comes first. Notice that `balances` is **unchanged** after `simplify_debts`, because the function works on a copy.

Now check rule 5 over hundreds of four-person balance combinations: every plan must bring everyone to 0, use at most 3 payments, and never include a payment of zero or less.

```text
>>> from settlement_optimizer import simplify_debts
>>> problems = 0
>>> for a in range(-50, 51, 7):
...     for b in range(-50, 51, 11):
...         for c in range(-50, 51, 13):
...             bal = {"A": a, "B": b, "C": c, "D": -(a + b + c)}
...             left = dict(bal)
...             plan = simplify_debts(bal)
...             if len(plan) > 3:
...                 problems += 1
...             for s in plan:
...                 if s.amount <= 0:
...                     problems += 1
...                 left[s.payer] += s.amount
...                 left[s.payee] -= s.amount
...             for v in left.values():
...                 if v != 0:
...                     problems += 1
...
>>> problems
0
```

### 4.7 Checkpoint 6: `report_generator.py`

This connects steps 1–6 for the first time: the Goa trip from §1, from expenses through to a printed plan, still without the menu.

```text
>>> from models import Group
>>> from ledger import InMemoryLedger
>>> from settlement_optimizer import plan_settlements
>>> from report_generator import print_balances, print_settlement_plan
>>> g = Group("Goa")
>>> for name in ["Asha", "Ravi", "Meera"]:
...     g.add_member(name)
...
Member(name='Asha')
Member(name='Ravi')
Member(name='Meera')
>>> L = InMemoryLedger(g)
>>> e1 = L.add_expense("Dinner", 30000, "Asha")
>>> e2 = L.add_expense("Cab", 1000, "Ravi", ["Ravi", "Meera"])
>>> print_balances(L.calculate_balances(), "Balances - Goa")
Balances - Goa
==============
+--------+---------------+------------------+
| Member | Balance (Rs.) | Status           |
+--------+---------------+------------------+
| Asha   |       +200.00 | gets back 200.00 |
| Ravi   |        -95.00 | owes 95.00       |
| Meera  |       -105.00 | owes 105.00      |
+--------+---------------+------------------+
| Total  |          0.00 |                  |
+--------+---------------+------------------+
>>> print_settlement_plan(plan_settlements(L), "Settle-up plan - Goa")
Settle-up plan - Goa
====================
+---+-------+------+-------+--------------+
| # | From  |      | To    | Amount (Rs.) |
+---+-------+------+-------+--------------+
| 1 | Meera | pays | Asha  |       105.00 |
| 2 | Ravi  | pays | Asha  |        95.00 |
+---+-------+------+-------+--------------+
|   |       |      | Total |       200.00 |
+---+-------+------+-------+--------------+
2 payments settle every debt.
>>> print_settlement_plan([])
Settle-up plan
==============
Everyone is settled up. Nothing to pay.
```

**Check:** the balances match the table in §1.2, the **Total row reads 0.00**, the columns line up, and the plan matches §1.5.

### 4.8 Checkpoint 7: `main.py`

**Manual checklist.** Run `python3 main.py` and try each of these:

| Try this | Expected |
|---|---|
| Add Expense before adding any members | "Add at least two members first." |
| Add `Asha`, then `asha` | "Error: Asha is already in …" |
| Amount `abc`, `-5`, `12.345` or `0` | a clear error, then back to the menu |
| Payer `9` when there are only 3 members | "There is no member number 9" |
| Percentages adding up to 90 | "Percentages must add up to 100, but they add up to 90.00" |
| Answer `n` at "Save this expense?" | "Expense discarded." and the expense count is unchanged |
| View balances | the Total row shows 0.00 |
| Exit, then answer `n` | back to the menu |
| Ctrl+C at the menu | "Exiting. Session data discarded." with no traceback |

**Scripted run.** Typing the same answers over and over gets slow. Save them in a file, one answer per line, and send it to the program as input. Here's `session.txt`: the answer on each blank line is an empty answer (press Enter), which means "everyone" for the split prompt.

```text
Goa
2
1
Asha
1
Ravi
1
Meera
2
Dinner
300
1

1
y
2
Cab
10
Ravi
Ravi, Meera
4
1
1
y
2
Snacks
abc
1
asha
3
4
5
n
5
y
```

Run it with:
- `python3 main.py < session.txt` on macOS or Linux, or in Windows `cmd`
- `Get-Content session.txt | py main.py` in PowerShell

The answers you send aren't echoed back, so prompts and results appear on the same line. The repeated menu lines are trimmed below.

```text
$ python3 main.py < session.txt
=== SplitSquad (in-memory session) ===
Group name (blank = 'My Group'): 
--- Goa: 0 members, 0 expenses ---
1. Add Member
2. Add Expense
3. View Current Balances
4. Generate Settle-Up Plan
5. Exit
Choose an option: 
Add at least two members first.

--- Goa: 0 members, 0 expenses ---
Choose an option: 
New member name: Added Asha. The group now has 1 member.

--- Goa: 1 member, 0 expenses ---
Choose an option: 
New member name: Added Ravi. The group now has 2 members.

--- Goa: 2 members, 0 expenses ---
Choose an option: 
New member name: Added Meera. The group now has 3 members.

--- Goa: 3 members, 0 expenses ---
Choose an option: 
Description: Amount (Rs.):   1. Asha
  2. Ravi
  3. Meera
Who paid? (number or name): Split between (numbers or names, comma-separated; blank = everyone): Split type: 1. Equal  2. Exact amounts  3. Percentages  4. Shares
Choose 1-4 (blank = equal): Each person owes:
  Asha                 100.00
  Ravi                 100.00
  Meera                100.00
Save this expense? (y/n): Saved. 1 expense so far, total Rs. 300.00.

--- Goa: 3 members, 1 expense ---
Choose an option: 
Description: Amount (Rs.):   1. Asha
  2. Ravi
  3. Meera
Who paid? (number or name): Split between (numbers or names, comma-separated; blank = everyone): Split type: 1. Equal  2. Exact amounts  3. Percentages  4. Shares
Choose 1-4 (blank = equal):   Ravi's shares (whole number):   Meera's shares (whole number): Each person owes:
  Ravi                   5.00
  Meera                  5.00
Save this expense? (y/n): Saved. 2 expenses so far, total Rs. 310.00.

--- Goa: 3 members, 2 expenses ---
Choose an option: 
Description: Amount (Rs.): Error: Amount must be a number, like 250 or 99.50
Nothing was changed. Back to the menu.

--- Goa: 3 members, 2 expenses ---
Choose an option: 
New member name: Error: Asha is already in Goa
Nothing was changed. Back to the menu.

--- Goa: 3 members, 2 expenses ---
Choose an option: 
Balances - Goa
==============
+--------+---------------+------------------+
| Member | Balance (Rs.) | Status           |
+--------+---------------+------------------+
| Asha   |       +200.00 | gets back 200.00 |
| Ravi   |        -95.00 | owes 95.00       |
| Meera  |       -105.00 | owes 105.00      |
+--------+---------------+------------------+
| Total  |          0.00 |                  |
+--------+---------------+------------------+

--- Goa: 3 members, 2 expenses ---
Choose an option: 
Settle-up plan - Goa
====================
+---+-------+------+-------+--------------+
| # | From  |      | To    | Amount (Rs.) |
+---+-------+------+-------+--------------+
| 1 | Meera | pays | Asha  |       105.00 |
| 2 | Ravi  | pays | Asha  |        95.00 |
+---+-------+------+-------+--------------+
|   |       |      | Total |       200.00 |
+---+-------+------+-------+--------------+
2 payments settle every debt.

--- Goa: 3 members, 2 expenses ---
Choose an option: 
Warning: SplitSquad keeps everything in memory only.
All members and expenses will be lost when you exit.
Exit anyway? (y/n): 
--- Goa: 3 members, 2 expenses ---
Choose an option: 
Warning: SplitSquad keeps everything in memory only.
All members and expenses will be lost when you exit.
Exit anyway? (y/n): Goodbye! Session data discarded.
```

This one script checks that bad input is rejected without a crash (no members yet, amount `abc`, duplicate `asha`), that equal and shares splits both work, that the balances match §1.2 and the plan matches §1.5, and that exit asks for confirmation.

### 4.9 Final acceptance checks

**No library imports:** every `import` line should name one of your own files.
```text
grep -nE "^\s*(import|from) " *.py              # macOS / Linux
findstr /R /C:"^import" /C:"^from" *.py         # Windows
```
Expected: only `models`, `validator`, `split_calculator`, `ledger`, `settlement_optimizer` and `report_generator`.

**No file handling:** `grep -n "open(" *.py` should find nothing.

**Rules summary:**

| Rule | Proven in |
|---|---|
| 1. Parsed amounts are whole, non-negative paise | §4.3 |
| 2. Shares add up to the amount | §4.4 (both loops) |
| 3. Each share is within 1 paisa of exact | §4.4 (weighted loop) |
| 4. Balances add up to 0, and bad changes are undone | §4.5 |
| 5. The plan brings everyone to 0 with at most n − 1 payments | §4.6 (loop) |
| The program never crashes | §4.8 |

### 4.10 Optional: a re-runnable check script

Retyping REPL sessions after every edit gets tedious. You can collect the loop checks in a file, say `manual_checks.py`, that uses only your own modules and `assert`. Run it with `python3 manual_checks.py` after every change:

```python
from split_calculator import split_equal, split_shares
from models import Group
from ledger import InMemoryLedger
from settlement_optimizer import simplify_debts

for total in range(1, 1001):
    for n in range(1, 7):
        people = ["p" + str(i) for i in range(n)]
        assert sum(split_equal(total, people).values()) == total

for total in range(1, 400):
    for a in range(0, 4):
        for b in range(0, 4):
            for c in range(1, 4):
                w = {"A": a, "B": b, "C": c}
                assert sum(split_shares(total, ["A", "B", "C"], w).values()) == total

g = Group("Test")
for name in ["Asha", "Ravi", "Meera"]:
    g.add_member(name)
ledger = InMemoryLedger(g)
ledger.add_expense("Dinner", 30000, "Asha")
ledger.add_expense("Cab", 1000, "Ravi", ["Ravi", "Meera"])
balances = ledger.calculate_balances()
assert sum(balances.values()) == 0
left = dict(balances)
for s in simplify_debts(balances):
    left[s.payer] += s.amount
    left[s.payee] -= s.amount
assert all(v == 0 for v in left.values())

print("All checks passed.")
```

(Unlike the REPL, `assert` stops at the first failure. Don't run this with `python -O`, which removes `assert` statements.)

---

## Where to go next

Once everything passes, here are some small extensions that fit the same structure:
- Add a **Delete expense** menu option. `InMemoryLedger.delete_expense` already exists and is tested; it only needs a menu entry and a numbered expense list.
- Add a **Record payment** option that stores `Settlement` objects in the group and includes them in `calculate_balances`. That means updating rule 4 to include settlements, then testing it the same way.
- Validate the description in `main.py` **before** the preview, so a blank description is rejected straight away instead of after the user confirms.
