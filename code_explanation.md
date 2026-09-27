# SplitSquad: Line-by-Line Code Explanation

A study guide for the project viva. It explains every file of the **in-memory SplitSquad** project, in the order the files depend on each other:

1. [`models.py`](#1-modelspy): the data classes
2. [`validator.py`](#2-validatorpy): turning raw text into checked integers
3. [`split_calculator.py`](#3-split_calculatorpy): dividing money with `//` and `%`
4. [`ledger.py`](#4-ledgerpy): storing expenses and computing balances
5. [`settlement_optimizer.py`](#5-settlement_optimizerpy): the greedy "who pays whom" algorithm
6. [`report_generator.py`](#6-report_generatorpy): terminal tables
7. [`main.py`](#7-mainpy): the menu that ties it together

Line numbers (`L12`, `L25–29`) refer to the files as they are in the repository. The sections at the end cover the known limitations and the questions an examiner is likely to ask.

---

## 0. The big picture

### 0.1 What the program does
SplitSquad is a terminal app for splitting shared expenses among friends during **one session**. You add members, record who paid for what and how it should be split, see everyone's balance, and get a short plan of payments that settles all debts. Nothing is saved to disk. When the program exits, the data is gone, and that is intentional.

### 0.2 How the files depend on each other

```
main.py                         (menu: input / output only)
 ├── report_generator.py   ──►  models
 ├── settlement_optimizer  ──►  models, validator
 ├── ledger.py             ──►  models, validator, split_calculator
 ├── split_calculator.py   ──►  models, validator
 ├── validator.py               (imports nothing)
 └── models.py                  (imports nothing)
```

Arrows point only downwards: higher-level files use lower-level ones, never the reverse. `models.py` and `validator.py` import nothing, so there can never be a **circular import** (A imports B while B imports A).

### 0.3 How one expense moves through the program

```
 user types "1200.50"        validator.parse_amount          -> 120050   (int paise)
 user types "1" / "Asha"     main.pick_member + Group.find_member -> "Asha" (str name)
 user types "50", "30"...    validator.parse_percentage      -> {"Asha": 5000, ...} (dict)
                             split_calculator.calculate_split -> {"Asha": 60025, ...} (dict of paise)
                             ledger.InMemoryLedger.add_expense
                                   -> models.Expense object
                                   -> appended to group.expenses (list)
                             ledger.calculate_balances        -> {"Asha": +3000, ...} (dict)
                             settlement_optimizer.simplify_debts -> [Settlement, ...] (list)
                             report_generator.print_*         -> text on the screen
```

**Data is passed between files only as plain Python values:** `int`, `str`, `dict`, `list`, and the four model objects. There is no shared global state. Each function receives what it needs as arguments and returns its result.

### 0.4 The three rules the whole codebase follows

1. **Money is always an integer number of paise.** ₹12.50 is stored as `1250`.
   - Why: floats can't store most decimal fractions exactly. In Python, `0.1 + 0.2` gives `0.30000000000000004`.
   - Integers are exact, so checks such as `total == 0` or `sum == amount` are always reliable.
   - Python integers also never overflow; they grow as large as needed.
2. **Check input where it enters the program, then trust it.**
   - Raw text from `input()` is converted into checked integers at the edge of the program (`main.py` calls `validator.py`).
   - Every file below that works with integers only.
3. **Everything is in memory.** The only storage is ordinary Python lists and dicts inside one `Group` object that `main()` creates at startup.

### 0.5 Built-in functions versus imports
The rule was "no `import` of standard or external libraries". The code still uses **built-in functions**: `print`, `input`, `len`, `str`, `int`, `ord`, `repr`, `min`, `range`. Built-ins are part of the Python language and are always available without `import`, so they're not library imports. The only `import` statements in the project load **our own** files.

---

### 0.6 The `//` and `%` toolkit (read this first)

Almost every calculation in the project relies on two operators.

| Operator | Name | Meaning | Example |
|---|---|---|---|
| `a // b` | floor (integer) division | how many whole times `b` fits into `a` | `10000 // 3 = 3333` |
| `a % b` | modulo | what's left over after that | `10000 % 3 = 1` |

They are linked by one identity that always holds for positive whole numbers:

```
a == (a // b) * b + (a % b)        and        0 <= a % b < b
```

For example, `10000 == 3333 * 3 + 1`. **This identity is why no paisa is ever lost.** `//` gives the part that divides evenly, and `%` counts exactly what's left, so if the leftover is handed out, the total adds back up to `a`.

Where the project uses them:

| File | Line | Use |
|---|---|---|
| `models.py` | L25–26 | split paise into rupees (`// 100`) and paise (`% 100`) for display |
| `validator.py` | L65–66 | the same, for error messages |
| `split_calculator.py` | L90–91 | equal split: base amount per person and leftover paise |
| `split_calculator.py` | L67, L69 | weighted split: each person's rounded-down share, and whether they were rounded down |

**Negative numbers:** Python's `//` rounds towards negative infinity, so `-5 // 100 == -1` and `-5 % 100 == 95`. That's mathematically consistent (`-1*100 + 95 == -5`) but wrong for display. That's why `format_paise` removes the sign first ([§1.3](#13-l1929-format_paisepaise)).

---

## 1. `models.py`

**Purpose:** it defines the four kinds of object the program works with: `Member`, `Expense`, `Settlement` and `Group`. It holds data only, has almost no logic, and imports nothing.

### 1.1 L1–9: module docstring
A triple-quoted string at the top of a file is that module's documentation. It states the rules: in-memory only, and money as integer paise.

### 1.2 L12–16: split-type constants
```python
SPLIT_EQUAL = "equal"
SPLIT_EXACT = "exact"
SPLIT_PERCENTAGE = "percentage"
SPLIT_SHARES = "shares"
SPLIT_TYPES = (SPLIT_EQUAL, SPLIT_EXACT, SPLIT_PERCENTAGE, SPLIT_SHARES)
```
- **What:** named constants for the four ways of splitting.
- **Why:** if you mistype a constant (`SPLIT_EQAUL`), Python raises a `NameError` immediately. If you mistype a string (`"eqaul"`), the comparison just quietly fails and you get a hidden bug. Every other file uses these names instead of typing the strings.
- `SPLIT_TYPES` (L16) collects them into a tuple. *To be honest, no file currently reads it.* It only documents the allowed values.

### 1.3 L19–29: `format_paise(paise)`
It turns an integer number of paise into rupee text, for example `125050 → "1250.50"`.

```python
sign = ""                      # L21
if paise < 0:                  # L22
    sign = "-"                 # L23
    paise = -paise             # L24  work with the positive value
rupees = paise // 100          # L25  whole rupees
cents = paise % 100            # L26  leftover paise (0-99)
if cents < 10:                 # L27
    return sign + str(rupees) + ".0" + str(cents)   # L28  pad: 7 -> ".07"
return sign + str(rupees) + "." + str(cents)        # L29
```

Tracing `125050`: `rupees = 1250`, `cents = 50`, result `"1250.50"`.
Tracing `-5`: the sign is removed first, so `paise = 5`, `rupees = 0` and `cents = 5`. L28 pads the cents, giving `"-0.05"`.

- **Why handle the sign first (L22–24):** without it, `-5 // 100 = -1` and `-5 % 100 = 95` would display as `"-1.95"`.
- **Why pad (L27–28):** 7 paise must display as `.07`. Without padding it would display as `.7`, which reads as 70 paise.
- **Why not `f"{p/100:.2f}"`:** dividing by 100 creates a float, which is exactly what the project avoids.
- **Used by:** every `__repr__` in this file, `report_generator.py` and `main.py`.

### 1.4 L32–39: `class Member`
```python
def __init__(self, name):        # L35  runs on Member("Asha")
    self.name = name             # L36  store the name on this object
def __repr__(self):              # L38
    return "Member(name=" + repr(self.name) + ")"   # L39
```
- `__init__` is the **constructor**: it sets up a new object's attributes.
- `__repr__` returns the object's printable description, which Python uses when displaying objects, for example `print(group.members)`. `repr(self.name)` wraps the name in quotes (`'Asha'`) so it's clear it's a string.
- **Why so small:** in this version a member is only a name. Names are unique within a group (the validator enforces this), so the name itself acts as the member's ID.

### 1.5 L42–67: `class Expense`
```python
def __init__(self, description, amount, paid_by, shares, split_type=SPLIT_EQUAL):  # L52
    self.description = description   # L53  e.g. "Dinner"
    self.amount = amount             # L54  total in paise, e.g. 120050
    self.paid_by = paid_by           # L55  payer's NAME, e.g. "Asha"
    self.shares = shares             # L56  dict {name: paise owed}
    self.split_type = split_type     # L57  one of the constants
```
- **Default argument:** `split_type=SPLIT_EQUAL` means that if the caller leaves it out, the expense is an equal split.
- **Design choice: members are referenced by name (a string), not by `Member` object.** Names work well as dict keys and print easily. It's safe because names are unique and can't be changed later.
- **Design choice: the constructor doesn't validate anything.** The rule "the shares add up to the amount" is guaranteed by whoever builds the `Expense`: `split_calculator` computes the shares, and `ledger` runs a zero-sum check as a safety net. The trade-off is that a hand-built, broken `Expense` is possible, but the ledger's check would catch it ([§4.8](#48-l99122-calculate_balances)).
- **L59–67, `__repr__`:** it builds a list of `"Asha: 400.17"` strings (L60–62), then joins them with `", ".join(...)` (L67). Joining a list avoids a stray comma after the last item.

### 1.6 L70–80: `class Settlement`
It stores one payment: `payer` (who pays), `payee` (who receives) and `amount` (paise). Its `__repr__` prints as `Settlement(Ravi pays Asha 50.00)`.
- **Important:** settlements are **not stored** in the `Group`. `settlement_optimizer` creates them as a *plan*, and `report_generator` prints them. This version doesn't record actual payments.

### 1.7 L83–124: `class Group`
It holds everything for the session.

| Lines | Method | What / why |
|---|---|---|
| L86–89 | `__init__` | A `name` and two **empty lists**, `members` and `expenses`. Lists keep things in order. Order matters: the menu numbers members 1, 2, 3…, and in an equal split the leftover paise go to the *first* members. |
| L91–97 | `find_member(name)` | Removes surrounding spaces and lowercases the name (L93), checks each member in turn (L94–96), and returns the `Member` or `None` (L97). **Case-insensitive**, so `"ASHA"` finds `Asha`. Checking one by one is slower for big groups; a dict would be instant, but the brief asked for lists, and for a handful of friends the difference doesn't matter. |
| L99–103 | `member_names()` | Builds a plain list of name strings. Used as the default "split between everyone". |
| L105–108 | `add_member(name)` | Creates a `Member` and appends it. **It doesn't check for duplicates**: `main.py` calls `validator.validate_member_name` first. |
| L110–112 | `add_expense(expense)` | Appends to the list. *To be honest, the app never calls it*: `InMemoryLedger.add_expense` appends to `group.expenses` directly. |
| L114–118 | `total_spent()` | Adds up the integer amounts, so the total is exact. Shown in `main.py` after saving an expense. |
| L120–124 | `__repr__` | A one-line summary. |

### 1.8 How `models.py` connects to the rest
- **Who imports it:**
  - `split_calculator` uses the constants.
  - `ledger` uses `Expense` and `SPLIT_EQUAL`.
  - `settlement_optimizer` uses `Settlement`.
  - `report_generator` uses `format_paise`.
  - `main` uses `Group`, the constants and `format_paise`.
- **`validator.py` uses a `Group` without importing `models`.** It only calls `group.find_member(...)` and reads `group.name`. This is **duck typing**: any object with those attributes would work.

---

## 2. `validator.py`

**Purpose:** convert raw user text into checked integers, or raise **one clear, readable error**. It imports nothing.

**Pattern used by every public function:** it either **returns the cleaned value** or **raises `ValidationError`** with a message fit to show the user.

### 2.1 L10–11: `class ValidationError(ValueError)`
- **What:** a custom exception type. A class body can consist of just a docstring.
- **Why inherit from `ValueError`:** "the value the user typed is wrong" is exactly what `ValueError` means. The class also inherits normal exception behaviour, so `str(error)` returns the message.
- Code can catch it specifically, or broadly with `except Exception`. `main.py` does the latter, which is why every bad input prints a message instead of crashing.

### 2.2 L14–21: `_is_digits(text)`
```python
if text == "":                 # L16
    return False               # L17
for ch in text:                # L18
    if ch < "0" or ch > "9":   # L19  compares characters by their code numbers
        return False           # L20
return True                    # L21
```
- The leading underscore is a naming convention for "internal helper, not for use outside this file".
- **L16–17:** without this check, `""` would skip the loop and return `True`.
- **L19:** characters are compared by their Unicode code numbers. `"0"` to `"9"` are the consecutive codes 48 to 57, so anything outside that range isn't a digit.
- **Why not `str.isdigit()`:** `"²".isdigit()` is `True`, and so are digits from other scripts. The manual conversion in §2.3 would produce garbage from those, so only the ten plain digits are accepted.

### 2.3 L24–29: `_to_int(text)`, text to number with no `int()`
```python
value = 0
for ch in text:
    value = value * 10 + (ord(ch) - ord("0"))   # L28
return value
```
- `ord(ch)` gives a character's code number. `ord("7") - ord("0") = 55 - 48 = 7`, which turns a digit character into its value.
- **Horner's method:** multiply what you have by 10 to shift it one place left, then add the new digit.

| step | char | value |
|---|---|---|
| start | | 0 |
| 1 | `"4"` | 0×10 + 4 = **4** |
| 2 | `"0"` | 4×10 + 0 = **40** |
| 3 | `"7"` | 40×10 + 7 = **407** |

- **Why manual:** the brief asked for manual conversion. (The built-in `int()` isn't an import, so it would also have been allowed. Be ready to say so if asked.)
- It is only called on text that `_is_digits` has already checked.

### 2.4 L32–60: `_parse_two_decimals(text, label)`, the core parser
It converts "a number with up to 2 decimals" into an integer **multiplied by 100**. Amounts and percentages both use it. `label` lets the error say "Amount …" or "Percentage …".

| Lines | Code | Why |
|---|---|---|
| L37 | `text = text.strip()` | `" 250 "` should be accepted |
| L38–39 | reject empty | |
| L40–41 | reject a leading `-` | money here is never negative |
| L42–43 | reject more than one `.` | **must come before L46**: `"12.5.1".split(".")` gives 3 pieces, and `whole, fraction = ...` would crash with a confusing error |
| L45–48 | split into `whole` and `fraction` | tuple unpacking; no dot means fraction `""` |
| L49–50 | reject `"."` on its own | nothing to parse |
| L51–54 | both parts must be plain digits | this rejects `"+5"`, `"1,000"`, `"1e3"`, `"12 .5"` and `"abc"` |
| L55–56 | reject more than 2 decimals | paise is the smallest unit. **Rounding money silently would be a bug**, so the input is rejected instead. |
| L58 | `fraction + "0" * (2 - len(fraction))` | pads on the right: `"5"` → `"50"`, `""` → `"00"`. **Key idea:** in `"12.5"` the 5 means *fifty* paise. |
| L59 | `_to_int(whole) if whole != "" else 0` | `".5"` has an empty whole part, which counts as 0 |
| L60 | `whole_value * 100 + _to_int(fraction)` | combines them into one integer |

Results: `"12"`→`1200`, `"12.5"`→`1250`, `".5"`→`50`, `"12."`→`1200`, `"0.07"`→`7`, `"007"`→`700`.
There's no upper limit, because Python integers can be any size.

### 2.5 L63–66: `_hundredths_text(value)`
It turns a number back into text for error messages (`1250 → "12.50"`), using the same `// 100` and `% 100` idea as `format_paise`.
- **Limitation:** it doesn't handle negative numbers (`_hundredths_text(-5)` gives `"-1.95"`). The callers never pass one: L105 negates the difference first.
- It's duplicated instead of importing `models.format_paise` so that this file still imports nothing.

### 2.6 L73–81: `parse_amount(text, allow_zero=False)`
It calls the parser with the label `"Amount"`, then rejects `0` unless `allow_zero=True`.
- `main.py` passes `allow_zero=True` when asking each person's amount in an exact split, because someone may legitimately owe ₹0.

### 2.7 L88–107: `validate_exact_split(total, amounts)`
`amounts` is a dict of name → paise.
- **L93–94:** an empty split is invalid.
- **L95–99:** keep a running total, rejecting negatives on the way. `parse_amount` already prevents negatives, but `split_calculator` can be called directly, so this check is a safeguard.
- **L100–106:** if the total doesn't match, `difference = total - running`. A positive difference means the amounts are *short*, and a negative one means they are *over*. L105 passes `-difference` so that `_hundredths_text` always receives a positive number.
- **L107:** it returns `amounts`, so the call can be used inline.
- **Why `!=` is safe:** these are integers. With floats you would need a tolerance.

### 2.8 L110–118: `parse_percentage(text)`
It reuses the same parser, so a percentage becomes **hundredths of a percent**: `"50"` → `5000`, `"33.33"` → `3333`, and 100% = `10000`. L116 rejects anything above 100%.

### 2.9 L121–134: `validate_percentages(percentages)`
It adds up the values, which must equal exactly `10000`.
- **Why hundredths:** the user can type `33.33`, while the check stays an exact integer comparison.

### 2.10 L141–157: `validate_member_name(name, group)`
- **L146:** `" ".join(name.split())`. With no arguments, `split()` splits on any run of whitespace (including tabs) and drops the ends. So `"  Mary   Jane "` becomes `"Mary Jane"`.
- **L147–150:** the name can't be empty, and is limited to 30 characters to keep the tables readable.
- **L151–153:** allowed characters are letters and digits (`isalnum()` accepts accented letters, so `"José"` works) plus space, `-`, `'` and `.`. That allows O'Brien, Mary-Jane and Dr. Rao.
- **L154–156:** a case-insensitive duplicate check through `group.find_member`. The error shows the **existing** spelling: "Asha is already in Goa".
- **L157:** it returns the cleaned name, which `main.py` then passes to `group.add_member`.

### 2.11 How `validator.py` connects to the rest
| Caller | Uses |
|---|---|
| `main.py` | `parse_amount`, `parse_percentage`, `validate_member_name`, `ValidationError` |
| `split_calculator.py` | `validate_exact_split`, `validate_percentages`, `ValidationError` |
| `ledger.py`, `settlement_optimizer.py` | `ValidationError` |

Every `ValidationError` ends up in `main.py`'s `except Exception`, which prints the message and returns to the menu.

---

## 3. `split_calculator.py`

**Purpose:** given a total in paise and a list of member names, return `{name: paise_owed}` where **the values add up to exactly the total**. It uses only `//`, `%`, `*` and `+`, with no `math` module.

### 3.1 L1–16: docstring
It states the rounding rule: everyone gets the rounded-down amount (`//`), then the leftover paise (`%`) go one at a time to the first members.

### 3.2 L18–19: imports
```python
from models import SPLIT_EQUAL, SPLIT_EXACT, SPLIT_PERCENTAGE, SPLIT_SHARES
from validator import ValidationError, validate_exact_split, validate_percentages
```
Only our own modules are imported. `from X import Y` brings those names in directly, so the code can write `SPLIT_EQUAL` instead of `models.SPLIT_EQUAL`.

### 3.3 L26–35: `_check_inputs(total, members)`
Shared checks for every split type:
- **L27–28:** the total must be positive.
- **L29–30:** there must be at least one person.
- **L31–35:** no one may be listed twice. It keeps a `seen` list and checks `name in seen`. A duplicate would make the same person owe twice, and since dict keys are unique, one of the two entries would silently overwrite the other.

### 3.4 L38–45: `_check_values_match(members, values, label)`
It ensures the per-person values dict and the members list describe **the same people**:
- **L40–42:** every member has a value; otherwise "Missing percentage for Ravi".
- **L43–45:** nobody outside the split has a value.

### 3.5 L48–75: `_split_by_weights(total, members, weights)`, the main algorithm
Percentage and shares splits both mean "split the total **in proportion** to some whole-number weights":
- **Percentage:** the weights are hundredths of a percent, such as 5000/3000/2000.
- **Shares:** the weights are share counts, such as 2/1/1.

One function handles both.

```python
weight_sum = 0                                        # L59
for name in members:                                  # L60
    weight_sum += weights[name]                       # L61   W = total weight

result = {}                                           # L63
rounded_down = []                                     # L64
assigned = 0                                          # L65
for name in members:                                  # L66
    result[name] = (total * weights[name]) // weight_sum          # L67  floor of exact share
    assigned += result[name]                                      # L68
    if (total * weights[name]) % weight_sum != 0:                 # L69  was anything cut off?
        rounded_down.append(name)                                 # L70

leftover = total - assigned                           # L72  paise not yet handed out
for position in range(leftover):                      # L73
    result[rounded_down[position]] += 1               # L74  one paisa each, first come first served
return result                                         # L75
```

**Why multiply before dividing (L67):** a person's exact share is `total × w / W`. Dividing first (`w // W`) would give 0 for everyone with less than the full weight. Multiplying first keeps everything as whole numbers and loses only the final fraction.

**What L69 tests:** `% weight_sum` gives the part that `//` cut off. If it's 0, the person's share was already exact and they lost nothing to rounding. Only people who **did** lose something go into `rounded_down`.

**Worked example 1, a percentage split:** ₹9.99 (999 paise) split 50% / 25% / 25%. The weights are 5000/2500/2500, so W = 10000.

| Member | weight | total×weight | `// 10000` | `% 10000` | rounded down? |
|---|---|---|---|---|---|
| Asha | 5000 | 4,995,000 | 499 | 5000 | yes |
| Ravi | 2500 | 2,497,500 | 249 | 7500 | yes |
| Meera | 2500 | 2,497,500 | 249 | 7500 | yes |

`assigned = 997`, so `leftover = 2`. Asha and Ravi, the first two in `rounded_down`, get +1 each.
**Result: `{Asha: 500, Ravi: 250, Meera: 249}`**, which adds up to 999.

**Worked example 2, a shares split:** 10 paise split 2 : 1 : 1 shares, so W = 4.

| Member | weight | total×weight | `// 4` | `% 4` | rounded down? |
|---|---|---|---|---|---|
| Asha | 2 | 20 | 5 | 0 | **no**, 5.00 is exact |
| Ravi | 1 | 10 | 2 | 2 | yes |
| Meera | 1 | 10 | 2 | 2 | yes |

`assigned = 9`, so `leftover = 1`, which goes to Ravi. **Result: `{Asha: 5, Ravi: 3, Meera: 2}`.**
Asha is skipped even though she comes first. Her share was exactly 5, and giving her a sixth paisa would make her overpay while Meera underpays.

**Why no paisa is lost, and why L74 never goes out of range.** For each person *i*, write `total·wᵢ = qᵢ·W + rᵢ`, where `qᵢ` is the `//` result, `rᵢ` is the `%` result, and `0 ≤ rᵢ < W`. Adding these up for everyone:

```
total · W  =  (Σ qᵢ) · W  +  Σ rᵢ          (because Σ wᵢ = W)
  ⇒  Σ rᵢ  =  W · (total − Σ qᵢ)  =  W · leftover
  ⇒  leftover = Σ rᵢ / W
```

Suppose `k` people have `rᵢ > 0`. Each such `rᵢ` is less than `W`, so `Σ rᵢ < k·W`, which means **`leftover < k`**. There are always more rounded-down people than leftover paise, so `rounded_down[position]` always exists.
Everyone ends at `qᵢ` or `qᵢ + 1`, so **nobody is more than 1 paisa away from their exact share**, and the total is exact.

**Honest note on fairness:** this gives the extra paisa to the *first* rounded-down person, as the brief specified. Another method, "largest remainder", would favour the person with the biggest cut-off amount; in example 1 that's Ravi and Meera (7500 each), not Asha (5000). Both methods keep the total exact and everyone within 1 paisa. We followed the brief.

### 3.6 L82–101: `split_equal(total, members)`
```python
_check_inputs(total, members)       # L88
count = len(members)                # L89
base = total // count               # L90  everyone's rounded-down share
extra = total % count               # L91  paise left over (always < count)

result = {}
position = 0
for name in members:                # L95
    if position < extra:            # L96  the first `extra` people...
        result[name] = base + 1     # L97  ...pay one paisa more
    else:
        result[name] = base         # L99
    position += 1                   # L100
return result
```
This is the direct application of the identity `total == base × count + extra`:
- ₹100 (10000 paise) among 3 people: `base = 3333`, `extra = 1`, so the result is **3334, 3333, 3333**.
- 10001 among 3: `extra = 2`, so the result is **3334, 3334, 3333**.
- 2 paise among 3: `base = 0`, `extra = 2`, so the result is **1, 1, 0**.

Since `extra < count`, there are always enough people for the extra paise. The total is `base·count + extra`, which equals `total` exactly.

It doesn't use `_split_by_weights`: everyone has equal weight, so the simpler code is clearer, and it gives the same answer.

### 3.7 L104–117: `split_exact(total, members, amounts)`
The user has typed each person's amount.
- **L110–112:** it checks the inputs, checks that the values match the members, then calls `validator.validate_exact_split` to confirm they add up to the total.
- **L114–117:** it copies the values into a new dict **in the order of `members`**, so every split type returns its keys in the same order.

No rounding is needed, because the user supplied exact paise.

### 3.8 L120–134: `split_percentage(total, members, percentages)`
- Percentages arrive already converted to hundredths by `validator.parse_percentage`.
- **L130–132:** negative percentages are rejected.
- **L133:** `validate_percentages` confirms they add up to 10000.
- **L134:** the work is done by `_split_by_weights`, with the percentages as the weights.

### 3.9 L137–153: `split_shares(total, members, shares)`
- **L146–150:** negative share counts are rejected, and the shares are added up.
- **L151–152:** all shares being zero is rejected, since that would mean dividing by zero in `_split_by_weights`.
- A share of 0 is allowed for an individual; that person owes 0 and, as shown above, never receives a leftover paisa.

### 3.10 L156–171: `calculate_split(split_type, total, members, values=None)`
A **dispatcher**: one entry point that picks the right function by name.
- **L161–162:** equal splits don't need `values`.
- **L163–164:** every other type needs `values`.
- **L171:** an unknown type raises an error instead of returning nothing.

**Why a dispatcher:** `main.py` and `ledger.py` only need to know one function name. Adding a fifth split type would change only this file.

### 3.11 How it connects
- **Called by:** `main.py` for the preview, and `ledger.py` for the stored result.
- **Calls:** `validator.py` for the "adds up" checks.
- **Receives:** `total` (int paise), `members` (list of names) and `values` (a dict or `None`).
- **Returns:** a dict of `{name: int paise}`.

---

## 4. `ledger.py`

**Purpose:** the `InMemoryLedger` class adds and removes expenses in `group.expenses`, and computes each member's **net balance** on demand, checking every time that the balances add up to zero.

### 4.1 L1–13: docstring and the sign convention
- **Positive balance:** the group owes this member money; they paid more than their share.
- **Negative balance:** this member owes money.

**Why the total must be 0:** every expense adds `+amount` to the payer and subtracts shares totalling `amount` from the participants. Each expense therefore changes the overall total by exactly 0. Money only moves between members; it's never created or destroyed.

### 4.2 L15–17: imports
It imports `Expense` and `SPLIT_EQUAL` from models, `ValidationError`, and `calculate_split`. The ledger is the only file that **combines** the calculator with the data.

### 4.3 L20–24: the class and its constructor
```python
class InMemoryLedger:
    def __init__(self, group):
        self.group = group        # L24  a reference to the ONE Group created in main.py
```
- **This stores a reference, not a copy.** `main.py`'s `group` and the ledger's `self.group` are the **same object**.
- When the ledger appends to `self.group.expenses`, `main.py` sees the change straight away (for example, in the menu's "2 expenses" count).
- This shared object is how data moves between the ledger and the menu without any global variables.

### 4.4 L28–33: `_member_name(name)`
It looks the name up with `group.find_member` (case-insensitive) and returns the **stored spelling**, so `"asha"` becomes `"Asha"`. Unknown names raise `ValidationError`.
- **Why:** balance dict keys must match exactly. Converting every name to its stored spelling guarantees one key per person.

### 4.5 L37–76: `add_expense(...)`
| Lines | What | Why |
|---|---|---|
| L49–51 | collapse whitespace in the description and reject it if empty | the description is text, and this is the one place it's checked |
| L52 | convert the payer to their stored name | raises if the payer isn't a member |
| L54–55 | `members=None` means everyone | a convenient default |
| L56–58 | convert every participant to their stored name | same reason as L52 |
| L60–65 | rebuild `values` with stored names as keys | `{"asha": 5000}` must match the name `"Asha"`, or the calculator would report "Missing percentage for Asha" |
| L67 | `shares = calculate_split(...)` | **the ledger recomputes the shares itself** instead of trusting `main.py`'s preview, so it never stores a split it hasn't checked |
| L68 | build the `Expense` | |
| L70 | `self.group.expenses.append(expense)` | the actual update to the in-memory data |
| L71–75 | run `calculate_balances()`; if it raises `AssertionError`, remove the expense and re-raise | **roll back**: a bad expense is never left in the list |
| L76 | return the expense | |

`list.remove(expense)` (L74) finds the item with `==`. `Expense` doesn't define `__eq__`, so `==` means "the same object". It removes exactly the expense just added, even if another one looks identical.

### 4.6 L78–92: `delete_expense(index)`
- **L84–85:** check the position is within range (positions start at 0). The message shows `index + 1` because people count from 1.
- **L86:** `list.pop(index)` removes the item and returns it.
- **L87–91:** run the zero-sum check; if it fails, `insert(index, expense)` puts the expense back exactly where it was.
- *This method works but isn't on the menu yet* (see [Known limitations](#9-known-limitations-be-ready-to-discuss-these)).

### 4.7 L94–95: `list_expenses()`
It returns `group.expenses`.

### 4.8 L99–122: `calculate_balances()`
```python
balances = {}
for member in self.group.members:          # L106
    balances[member.name] = 0              # L107  everyone starts at 0, even with no expenses

for expense in self.group.expenses:        # L109
    balances[self._member_name(expense.paid_by)] += expense.amount     # L110  payer: +amount
    for name in expense.shares:                                        # L111
        balances[self._member_name(name)] -= expense.shares[name]      # L112  each: -share

total = 0
for name in balances:                      # L117
    total += balances[name]                # L118
if total != 0:                             # L119
    raise AssertionError(...)              # L120
return balances                            # L122
```
**Worked example:** members Asha, Ravi and Meera.
1. Dinner ₹300 (30000) paid by Asha, split equally among all three:
   - Asha: +30000 − 10000 = **+20000**
   - Ravi: **−10000**
   - Meera: **−10000**
2. Cab ₹10 (1000) paid by Ravi, split equally between Ravi and Meera:
   - Ravi: −10000 + 1000 − 500 = **−9500**
   - Meera: −10000 − 500 = **−10500**
   - Asha stays at +20000.

Check: 20000 − 9500 − 10500 = **0**.

- **Why recompute from scratch every time:** there's no stored running balance that could drift out of step with the list. The list of expenses is the only source of truth, and balances are always derived from it.
- **Why `raise AssertionError` instead of `assert`:** running Python with `-O` removes `assert` statements. An explicit `raise` always runs. This is a **program-consistency** check (it should never fail if the code is correct), which is why it's an `AssertionError` rather than a `ValidationError`.
- **Why dict iteration order is reliable:** since Python 3.7, dicts keep insertion order. Balances therefore always appear in member order.

### 4.9 How it connects
- **Created once in `main.py`** with the group, then passed into the functions that need it.
- **Calls:** `split_calculator.calculate_split` and `Group.find_member`.
- **Provides:** `calculate_balances()`, used by `main.view_balances` and `settlement_optimizer.plan_settlements`.

---

## 5. `settlement_optimizer.py`

**Purpose:** turn the balances into a short list of payments, such as "Meera pays Asha ₹105.00", that brings everyone to zero.

### 5.1 L1–14: the algorithm in words
It uses a **greedy** approach: at each step, match the biggest creditor with the biggest debtor. The debtor pays the smaller of the two amounts, which brings at least one of them to exactly zero. Repeat until everyone is at zero.

### 5.2 L16–17: imports
`Settlement` (the objects it creates) and `ValidationError`.

### 5.3 L20–26 and L29–35: `_largest_creditor` and `_largest_debtor`
```python
best = None
for name in balances:
    if balances[name] > 0 and (best is None or balances[name] > balances[best]):
        best = name
return best
```
- A simple "find the maximum" loop, with no `max()` call or `heapq` import needed.
- The condition `best is None or …` handles the first candidate found.
- **Ties:** the comparison is strictly greater (`>`), so in a tie the member who comes first keeps the spot. That makes the result predictable.
- The debtor version is the same, but looks for the most **negative** value (`< 0` and `<`).
- Both return `None` when there's nobody left on that side.

### 5.4 L38–74: `simplify_debts(balances)`
| Lines | What | Why |
|---|---|---|
| L49–53 | copy the balances into `remaining` and add them up | copying means the caller's dict is **not changed** |
| L54–56 | refuse balances that don't add up to 0 | otherwise the loop could never finish cleanly |
| L58–59 | `plan = []` and a `while True` loop | the loop repeats until the break on L63 |
| L60–61 | find the biggest creditor and the biggest debtor | the greedy choice |
| L62–63 | stop when either is `None` | since the sum is 0, no creditors left means no debtors left |
| L64 | `amount = min(remaining[creditor], -remaining[debtor])` | pay the smaller amount, so nobody's balance crosses zero |
| L65 | `Settlement(debtor, creditor, amount)` | the **debtor is the payer** |
| L66–67 | creditor − amount, debtor + amount | both move towards 0 |
| L69–73 | check afterwards that everyone is exactly 0 | a safety check, like the ledger's |

**Worked example:** `{Asha: +5000, Ravi: +1000, Meera: −4000, Kiran: −2000}`

| Round | creditor | debtor | amount | after |
|---|---|---|---|---|
| 1 | Asha (5000) | Meera (−4000) | 4000 | Asha 1000, Meera **0** |
| 2 | Asha (1000, tie with Ravi, Asha comes first) | Kiran (−2000) | 1000 | Asha **0**, Kiran −1000 |
| 3 | Ravi (1000) | Kiran (−1000) | 1000 | Ravi **0**, Kiran **0** |

The result is **Meera pays Asha 40.00, Kiran pays Asha 10.00, Kiran pays Ravi 10.00**, which is 3 payments for 4 people.

**Why the loop always ends, and why there are at most n−1 payments:**
- Each round sets at least one person to exactly 0. The payment is `min(...)`, so it exactly clears whichever balance is smaller.
- Nobody's balance ever crosses zero.
- So the number of people with a non-zero balance goes down every round. The last round clears two people at once, giving at most **n − 1** payments.

**Honest note:** finding the true *minimum* number of payments is a much harder problem that's too slow to solve exactly for larger groups. The greedy method is the standard practical choice, and it's often optimal for small groups.

**No rounding happens here.** Every step only adds or subtracts integers.

### 5.5 L77–79: `plan_settlements(ledger)`
A convenience wrapper: it gets the ledger's balances and runs `simplify_debts` on them. `main.py` calls it.

### 5.6 How it connects
- **Receives** a balances dict from `InMemoryLedger.calculate_balances()` (via `plan_settlements`).
- **Returns** a `list` of `Settlement` objects.
- `main.py` passes that list to `report_generator.print_settlement_plan`.

---

## 6. `report_generator.py`

**Purpose:** print neat tables to the terminal using only string methods: `.ljust()`, `.rjust()`, `*` repetition and `.join()`. It writes no files.

### 6.1 L8: import
`format_paise` is its only dependency. It receives data (dicts and lists) and doesn't need to know about the ledger or the group.

### 6.2 L11–15: `_money(paise, signed=False)`
It wraps `format_paise` and adds a `+` for positive numbers when `signed=True`, so balances read `+5899.83` or `-3699.67`. Negative numbers already carry their `-` from `format_paise`.

### 6.3 L18–62: `format_table(headers, rows, align, footer=None)`
It builds a complete ASCII table as **one string**.

- **L27–29:** gather every row that will be printed (header, body and optional footer) into `all_rows`, for measuring.
- **L31–38, column widths:** for each column, find the longest text in any row. `range(len(headers))` loops over the column numbers.
- **L40–44, `separator()`:** builds a line such as `+--------+---------+`.
  - `"-" * (width + 2)` repeats the dash. The `+ 2` makes room for one space on each side of the text.
  - `"+".join(parts)` puts `+` between the columns.
- **L46–53, `line(cells)`:** one row, such as `| Asha   | +200.00 |`.
  - `ljust(w)` pads text on the **right** up to width `w`, which left-aligns it.
  - `rjust(w)` pads on the **left**, which right-aligns it.
  - The `align` string holds one letter per column, e.g. `"lrl"`.
- **Why right-align money:** every amount has exactly two decimals, so right-aligning them lines up the decimal points.
- **Nested functions (L40, L46):** `separator` and `line` are defined inside `format_table`, so they can read `widths` and `align` directly without being passed them. (A function defined inside another like this is called a closure.)
- **L55–62:** put the lines together as separator, header, separator, rows, separator, then the optional footer and a final separator. `"\n".join(lines)` makes it one string.

Example output:
```
+--------+---------+
| Member |     Amt |
+--------+---------+
| Asha   | +200.00 |
| Ravi   | -100.00 |
+--------+---------+
| Total  |    0.00 |
+--------+---------+
```

### 6.4 L65–66: `_heading(text)`
It underlines a title with `=` repeated `len(text)` times.

### 6.5 L69–93: `print_balances(balances, title)`
- **L75–77:** with no members, it prints a short message instead of an empty table.
- **L81–90:** for each member it builds a status: "gets back X", "owes X" (using `format_paise(-amount)` so the owed amount shows as positive) or "settled up". It adds a row and keeps a running total.
- **L92–93:** prints the table with a **Total** footer. That total always shows `0.00`, which is visible proof of the ledger's zero-sum rule.

### 6.6 L96–120: `print_settlement_plan(settlements, title)`
- **L102–104:** an empty plan prints "Everyone is settled up".
- **L108–113:** it numbers the rows (1, 2, 3…) and reads `settlement.payer`, `.payee` and `.amount` from each `Settlement` object.
- **L115–116:** the table has a blank header over the "pays" column, plus a Total footer.
- **L117–120:** it prints "1 payment…" or "N payments…" with correct grammar.

### 6.7 How it connects
`main.py` calls both print functions. The data they receive comes from the ledger (the balances dict) and the optimizer (the list of `Settlement` objects). This file only formats; it doesn't calculate anything.

---

## 7. `main.py`

**Purpose:** the user interface. It reads input, calls the other files in the right order, prints the results, and keeps running when something goes wrong.

### 7.1 L14–19: imports
```python
import models
import validator
...
```
This file uses `import module` (then `validator.parse_amount(...)`) instead of `from module import name`. In the menu code, the prefix makes it obvious where each function lives. Both styles import only our own files.

### 7.2 L22–27: `SPLIT_CHOICES`
A dict mapping the menu keys `"1"`–`"4"` to the split constants. **Why a dict:** a single lookup replaces a chain of `if/elif`, and `choice not in SPLIT_CHOICES` checks the input in one step (L112).

### 7.3 L34–39: small helpers
- **`plural(count, word)`:** `"1 member"` versus `"2 members"`. It uses a one-line conditional: `"" if count == 1 else "s"`.
- **`ask(prompt)`:** `input(prompt).strip()`. Every answer has surrounding spaces removed.

### 7.4 L42–52: `pick_member(group, text)`
It accepts either a **number from the printed list** or a **name**.
- **L44–48:** if the text is all digits, convert it with `int()`, check it's between 1 and the number of members, and return `group.members[number - 1].name`. The `- 1` is there because the list starts at 0 but people count from 1.
- **L49–52:** otherwise, look the name up case-insensitively.
- `1 <= number <= len(...)` is Python's **chained comparison**, equivalent to `1 <= number and number <= len(...)`.

### 7.5 L55–59: `show_members(group)`
It prints the numbered list that `pick_member` expects.

### 7.6 L66–69: `add_member(group)`
**Validate first, then change the data:** `validate_member_name` (strip spaces, check characters, reject duplicates), then `group.add_member(name)`. If validation raises an error, `add_member` is never reached, so the group isn't changed.

### 7.7 L72–88: `ask_split_values(split_type, amount, members)`
It asks each person for their value, depending on the split type:
- **Equal:** returns `None`; there's nothing to ask (L74–75).
- **Exact:** `parse_amount(..., allow_zero=True)` gives paise (L78–80).
- **Percentage:** `parse_percentage(...)` gives hundredths (L81–82).
- **Shares:** must be a whole number, so `isdigit()` then `int()` (L84–87).

It returns a dict `{name: int}`. The names come from `pick_member`, so they already use the stored spelling.

### 7.8 L91–129: `add_expense(group, the_ledger)`, the main flow
| Lines | Step |
|---|---|
| L92–94 | need at least 2 members |
| L96–97 | description, then `parse_amount` turns the text into paise |
| L99–100 | show members, then pick the payer |
| L102–108 | blank means everyone; otherwise split the text on commas and pick each member |
| L110–114 | choose the split type with the `SPLIT_CHOICES` dict. `ask(...) or "1"`: an empty string counts as false, so a blank answer means "1" |
| L116 | ask for the per-person values |
| L119–122 | **preview**: `calculate_split` shows who owes what, aligned with `ljust(15)` and `rjust(12)` |
| L123–125 | confirm; anything other than y/yes discards the expense |
| L127 | `the_ledger.add_expense(...)` is the only line that changes data |
| L128–129 | a confirmation message with the new total |

**Why a preview and then a second calculation in the ledger:** the preview lets the user see the result before committing to it. The ledger recalculates because it doesn't rely on its caller to have checked the data. Every input is checked *before* L127, so a mistake part-way through never leaves half an expense behind.

### 7.9 L132–139: `view_balances` and `settle_up_plan`
Each passes data from one file to the next:
```
the_ledger.calculate_balances()  ──►  report_generator.print_balances(...)
settlement_optimizer.plan_settlements(the_ledger)  ──►  report_generator.print_settlement_plan(...)
```

### 7.10 L142–145: `confirm_exit()`
It warns that everything is in memory and will be lost, then returns `True` only for y/yes.

### 7.11 L152–192: `main()`, the program loop
- **L154:** `ask(...) or "My Group"` uses a default name when the input is blank.
- **L155–156:** create the **single** `Group` and the **single** `InMemoryLedger` that shares it. These two objects are the whole "database".
- **L158:** `while True:` repeats the menu until a `break`.
- **L159–166:** print a status line (`plural(...)` counts) and the menu.
- **L168–184:** read the choice and call the matching function. Only option 5 can `break` (L182).
- **L185–189: `except (EOFError, KeyboardInterrupt)`**
  - `EOFError` happens when input runs out (for example, piped input), and `KeyboardInterrupt` when the user presses Ctrl+C.
  - Both end the program with a message.
  - **This must come before `except Exception`:** `EOFError` is a kind of `Exception`. If it were caught by the general handler, the loop would call `input()` again, hit the end of input again, and loop forever. (`KeyboardInterrupt` isn't an `Exception`, which is why it's named explicitly.)
- **L190–192: `except Exception as error`:** any other error (a `ValidationError`, a `ValueError`, or a failed consistency check) is printed as `Error: <message>`, and the loop returns to the menu. This keeps error handling simple, as the brief asked.

### 7.12 L195–196: `if __name__ == "__main__":`
Python sets `__name__` to `"__main__"` only for the file you run directly. This guard means `main()` runs for `python main.py`, but not if another file imports `main`.

---

## 8. End-to-end trace: one complete session

```
$ python main.py
Group name: Goa                         -> Group("Goa") + InMemoryLedger(group)       [main L154-156]
1 -> Asha, 1 -> Ravi, 1 -> Meera         -> validate_member_name -> group.members.append   [main L66-69]
2 -> "Dinner", "300", payer 1, blank, 1  -> parse_amount("300") = 30000                  [validator L73]
                                         -> split_equal(30000, 3 names)
                                              base = 30000 // 3 = 10000, extra = 30000 % 3 = 0
                                              -> {Asha: 10000, Ravi: 10000, Meera: 10000}  [calc L82-101]
                                         -> y -> ledger.add_expense -> Expense -> list.append
                                         -> calculate_balances: sum = 0 OK               [ledger L99-122]
3                                        -> {Asha: +20000, Ravi: -10000, Meera: -10000}
                                         -> print_balances table, Total 0.00             [report L69-93]
4                                        -> simplify_debts:
                                              Ravi pays Asha 100.00, Meera pays Asha 100.00
                                         -> print_settlement_plan table                   [report L96-120]
5 -> y                                   -> "Goodbye! Session data discarded."            [main L179-182]
```
(Ravi and Meera tie at −10000, so Ravi goes first because he comes first in the list.)

---

## 9. Known limitations (be ready to discuss these)

Being upfront about these in a viva shows you understand the code:

1. **Code that exists but isn't used:**
   - `Group.add_expense` isn't called; the ledger appends directly.
   - `SPLIT_TYPES` isn't read anywhere.
   - `InMemoryLedger.delete_expense` and `list_expenses` work but aren't on the menu.
2. **The description is checked late:** a blank description is only rejected in `ledger.add_expense`, *after* the user has entered everything and confirmed.
3. **`main.py` uses the built-in `int()` for member numbers and share counts** instead of the manual converter. Input like `"²"` passes `isdigit()` and then `int()` raises a `ValueError`. The menu catches it and prints Python's own message, which isn't as friendly as the others.
4. **Leftover paise go to the first rounded-down member,** not the one with the largest cut-off amount. This follows the brief, and everyone is still within 1 paisa of their exact share ([§3.5](#35-l4875-_split_by_weightstotal-members-weights-the-main-algorithm)).
5. **`_hundredths_text` doesn't handle negative numbers**, but none of its callers ever pass one.
6. **Some lookups check items one by one** (`find_member`, and the `seen` list in `_check_inputs`). That's fine for a group of friends, and a dict or set would be faster for thousands of people. Lists were chosen because the brief asked for them.
7. **The settlement plan is only printed.** Recording that payments were actually made isn't a feature of this version.
8. **The greedy plan uses at most n−1 payments** but isn't guaranteed to be the absolute minimum.
9. **The preview column is 15 characters wide** (`ljust(15)`), so names longer than that push their amount out of line. This is cosmetic only.

---

## 10. Likely viva questions, with short answers

**Q: Why store money as integers?**
Floats can't store decimals such as 0.1 exactly: `0.1 + 0.2 == 0.30000000000000004`. With integer paise every sum is exact, so "shares equal the total" and "balances add up to 0" can be checked with a simple `==`.

**Q: How do you split ₹100 three ways without losing a paisa?**
`10000 // 3 = 3333` each and `10000 % 3 = 1` left over. The first person gets +1, so the result is 3334 + 3333 + 3333 = 10000. This works because `a == (a // b) * b + a % b` always holds.

**Q: How do percentage splits avoid decimals?**
Percentages are stored as hundredths (`33.33% → 3333`, 100% → 10000). Each share is `(total × weight) // 10000`, with multiplication done before division so only the final fraction is lost. `%` shows who was rounded down, and the leftover paise go to those people. [§3.5](#35-l4875-_split_by_weightstotal-members-weights-the-main-algorithm) proves there are always enough of them.

**Q: Did you use any library functions?**
No imports except our own files. We used built-ins such as `len`, `ord`, `min`, `int` and `print`, which are part of the language and need no import.

**Q: How did you convert "12.5" to a number without `float()`?**
Split on `.`, pad the fraction on the right to 2 digits (`"5"` → `"50"`), convert each part digit by digit with `value * 10 + (ord(ch) - ord("0"))`, and combine them as `whole * 100 + fraction`, giving 1250.

**Q: What guarantees the balances add up to zero?**
Mathematically, each expense adds `+amount` to the payer and subtracts shares totalling `amount`. In the code, `calculate_balances` adds them up and raises an error if the total isn't 0, and `add_expense` and `delete_expense` undo their change if that check fails.

**Q: Why `raise AssertionError` instead of `assert`?**
`python -O` removes `assert` statements. The explicit `raise` always runs.

**Q: Explain the settlement algorithm and its complexity.**
It's greedy: the biggest debtor pays the biggest creditor `min(credit, debt)`, which clears at least one person per round, so there are at most n−1 payments. Each round scans all n balances twice, so the total work is O(n²). That's trivial for a group of friends.

**Q: How is data passed between modules?**
As plain values: text becomes an `int` (validator), names are `str`, splits are dicts, the `Expense` is appended to the group's list (ledger), balances are a dict, and the plan is a list of `Settlement` objects. `main.py` creates one `Group` and one `InMemoryLedger` holding a **reference** to it, so both always see the same data.

**Q: What happens if the user types "abc" as an amount?**
`parse_amount` raises `ValidationError("Amount must be a number, like 250 or 99.50")`. The menu's `except Exception` prints it and shows the menu again. Nothing was changed, because the data is only changed at the very last step.

**Q: Why is the `EOFError` handler before `except Exception`?**
`EOFError` is a kind of `Exception`. If the general handler caught it, the loop would call `input()` again at the end of input and never stop.

**Q: Why not use `dataclasses`?**
It's a standard-library module, so it wasn't allowed. Our hand-written `__init__` and `__repr__` are what `@dataclass` would generate automatically.
