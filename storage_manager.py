"""
storage_manager.py - Plain-text persistence for SplitSquad.

No json, csv or os: files are read and written with open() and parsed by hand
with str.split('|').

group_data.txt layout (one record per line, '#' lines are comments):

    SplitSquad|1
    Group|<name>|<next_expense_id>|<next_settlement_id>
    Member|<id>|<name>
    Expense|<id>|<payer>|<amount>|<name:share,...>|<category>|<date>|<split_type>|<name:value,...>|<description>
    Settlement|<id>|<payer>|<payee>|<amount>|<date>

  * Records after a Group line belong to that group; a file can hold many groups.
  * Amounts are integer paise. The participant field stores each person's
    computed share, so exact/percentage/shares splits reload byte-for-byte.
  * <name:value,...> holds the original split inputs (empty for equal splits).

Escaping: text may contain the separator characters, so they are replaced by
backslash codes that contain no separators. That keeps split('|'), split(',')
and split(':') safe; each piece is unescaped only after splitting.

    \\ -> \      \p -> |      \c -> ,      \k -> :      \n -> newline   \r -> CR

audit_log.txt is append-only (opened in 'a' mode, never rewritten):

    <seq>|<ADD|EDIT|DELETE>|<group>|<expense_id>|<details>
"""

from models import Group, Member, Expense, Settlement, SPLIT_TYPES
from validator import (is_ascii_digits, digits_to_int,
                       validate_date, validate_member_name)


DEFAULT_DATA_FILE = "group_data.txt"
DEFAULT_AUDIT_FILE = "audit_log.txt"
FORMAT_NAME = "SplitSquad"
FORMAT_VERSION = "1"

AUDIT_ADD = "ADD"
AUDIT_EDIT = "EDIT"
AUDIT_DELETE = "DELETE"
AUDIT_ACTIONS = (AUDIT_ADD, AUDIT_EDIT, AUDIT_DELETE)


class StorageError(ValueError):
    """The data file is malformed or inconsistent. Message includes the line number."""


# ----------------------------------------------------------------------
# Escaping
# ----------------------------------------------------------------------

_FIELD_ESCAPES = {"\\": "\\\\", "|": "\\p", "\n": "\\n", "\r": "\\r"}
_ITEM_ESCAPES = {"\\": "\\\\", "|": "\\p", "\n": "\\n", "\r": "\\r", ",": "\\c", ":": "\\k"}
_UNESCAPES = {"\\": "\\", "p": "|", "n": "\n", "r": "\r", "c": ",", "k": ":"}


def _escape_with(text, table):
    out = []
    for ch in text:
        out.append(table.get(ch, ch))
    return "".join(out)


def escape_field(text):
    """Make text safe to sit between '|' separators."""
    return _escape_with(text, _FIELD_ESCAPES)


def escape_item(text):
    """Make text safe inside a 'name:value,name:value' list (also hides ',' and ':')."""
    return _escape_with(text, _ITEM_ESCAPES)


def unescape(text):
    """Reverse escape_field / escape_item. Rejects unknown or dangling escapes."""
    out = []
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= length:
            raise StorageError("text ends with a lone backslash")
        code = text[i + 1]
        if code not in _UNESCAPES:
            raise StorageError("unknown escape sequence \\" + code)
        out.append(_UNESCAPES[code])
        i += 2
    return "".join(out)


# ----------------------------------------------------------------------
# Field helpers
# ----------------------------------------------------------------------

def _parse_int(text, field, minimum=0):
    if not is_ascii_digits(text):
        raise StorageError(field + " must be a whole number, got " + repr(text))
    value = digits_to_int(text)
    if value < minimum:
        raise StorageError(field + " must be at least " + str(minimum))
    return value


def _expect_fields(fields, count, layout):
    if len(fields) != count:
        raise StorageError(fields[0] + " record needs " + str(count) + " fields ("
                           + layout + "), found " + str(len(fields)))


def _encode_pairs(pairs):
    """{name: int} -> 'name:int,name:int'. None encodes as an empty field."""
    if pairs is None:
        return ""
    items = []
    for name in pairs:
        items.append(escape_item(name) + ":" + str(pairs[name]))
    return ",".join(items)


def _decode_pairs(text, field):
    """'name:int,name:int' -> {name: int}, preserving order. Empty field -> None."""
    if text == "":
        return None
    result = {}
    for item in text.split(","):
        parts = item.split(":")
        if len(parts) != 2:
            raise StorageError(field + " entry " + repr(item) + " must look like name:number")
        name = unescape(parts[0])
        if name in result:
            raise StorageError(field + " lists " + repr(name) + " twice")
        result[name] = _parse_int(parts[1], field + " value for " + repr(name))
    return result


# ----------------------------------------------------------------------
# Serialisation
# ----------------------------------------------------------------------

def _record(*fields):
    return "|".join(fields)


def _serialize_group(group, lines):
    lines.append(_record("Group", escape_field(group.name),
                         str(group.next_expense_id), str(group.next_settlement_id)))
    for member in group.members:
        lines.append(_record("Member", str(member.member_id), escape_field(member.name)))
    for e in group.expenses:
        lines.append(_record("Expense", str(e.expense_id), escape_field(e.paid_by),
                             str(e.amount), _encode_pairs(e.shares),
                             escape_field(e.category), e.date, e.split_type,
                             _encode_pairs(e.split_values), escape_field(e.description)))
    for s in group.settlements:
        lines.append(_record("Settlement", str(s.settlement_id), escape_field(s.payer),
                             escape_field(s.payee), str(s.amount), s.date))


def serialize_groups(groups):
    """Return the full file contents for a list of groups."""
    seen = {}
    lines = ["# SplitSquad data file. Fields are separated by '|'; amounts are in paise.",
             _record(FORMAT_NAME, FORMAT_VERSION)]
    for group in groups:
        key = group.name.lower()
        if key in seen:
            raise StorageError("Two groups are named " + repr(group.name))
        seen[key] = True
        lines.append("")
        _serialize_group(group, lines)
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# Deserialisation
# ----------------------------------------------------------------------

def _parse_header(fields):
    if fields[0] != FORMAT_NAME:
        raise StorageError("not a SplitSquad data file (missing '"
                           + FORMAT_NAME + "|" + FORMAT_VERSION + "' header)")
    _expect_fields(fields, 2, "SplitSquad|version")
    if fields[1] != FORMAT_VERSION:
        raise StorageError("unsupported file version " + repr(fields[1]))


def _parse_group(fields):
    _expect_fields(fields, 4, "Group|name|next_expense_id|next_settlement_id")
    group = Group(unescape(fields[1]))
    group.next_expense_id = _parse_int(fields[2], "next expense id", 1)
    group.next_settlement_id = _parse_int(fields[3], "next settlement id", 1)
    return group


def _parse_member(fields):
    _expect_fields(fields, 3, "Member|id|name")
    member_id = _parse_int(fields[1], "member id", 1)
    return Member(validate_member_name(unescape(fields[2])), member_id)


def _parse_expense(fields):
    _expect_fields(fields, 10, "Expense|id|payer|amount|shares|category|date|"
                               "split_type|split_values|description")
    expense_id = _parse_int(fields[1], "expense id", 1)
    payer = unescape(fields[2])
    amount = _parse_int(fields[3], "amount", 1)
    shares = _decode_pairs(fields[4], "shares")
    if shares is None:
        raise StorageError("expense " + str(expense_id) + " has no participants")
    category = unescape(fields[5])
    date = validate_date(fields[6])
    split_type = fields[7]
    if split_type not in SPLIT_TYPES:
        raise StorageError("unknown split type " + repr(split_type))
    split_values = _decode_pairs(fields[8], "split values")
    description = unescape(fields[9])
    return Expense(expense_id, description, amount, payer, date, split_type,
                   shares, category, split_values)


def _parse_settlement(fields):
    _expect_fields(fields, 6, "Settlement|id|payer|payee|amount|date")
    return Settlement(unescape(fields[2]), unescape(fields[3]),
                      _parse_int(fields[4], "amount", 1), validate_date(fields[5]),
                      _parse_int(fields[1], "settlement id", 1))


def deserialize_groups(text):
    """
    Parse file contents into a list of Group objects.

    Every record is rebuilt through the normal model methods, so the same
    rules apply as when the data was first entered (known members, shares
    summing to the amount, unique ids). Any problem raises StorageError
    naming the offending line.
    """
    groups = []
    names_seen = {}
    current = None
    saw_header = False

    # split("\n") rather than splitlines(): splitlines() also breaks on
    # characters like U+2028 that may legitimately appear inside descriptions.
    lines = text.split("\n")
    for index in range(len(lines)):
        line = lines[index]
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip() == "" or line.startswith("#"):
            continue

        fields = line.split("|")
        kind = fields[0]
        try:
            if not saw_header:
                _parse_header(fields)
                saw_header = True
            elif kind == "Group":
                current = _parse_group(fields)
                if current.name.lower() in names_seen:
                    raise StorageError("group " + repr(current.name) + " appears twice")
                names_seen[current.name.lower()] = True
                groups.append(current)
            elif current is None:
                raise StorageError(kind + " record appears before any Group record")
            elif kind == "Member":
                current.add_member(_parse_member(fields))
            elif kind == "Expense":
                current.add_expense(_parse_expense(fields))
            elif kind == "Settlement":
                current.add_settlement(_parse_settlement(fields))
            else:
                raise StorageError("unknown record type " + repr(kind))
        except (ValueError, TypeError) as err:   # includes StorageError, ValidationError
            raise StorageError("line " + str(index + 1) + ": " + str(err))

    return groups


# ----------------------------------------------------------------------
# File I/O
# ----------------------------------------------------------------------

def save_groups(groups, path=DEFAULT_DATA_FILE):
    """Overwrite `path` with every group."""
    # Serialise completely before opening the file: if anything goes wrong
    # here, the existing file has not been truncated yet.
    text = serialize_groups(groups)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def load_groups(path=DEFAULT_DATA_FILE):
    """Read every group from `path`. A missing file simply means no groups yet."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except FileNotFoundError:
        return []
    return deserialize_groups(text)


def load_group(name, path=DEFAULT_DATA_FILE):
    """Return the group called `name` (case-insensitive), or None."""
    for group in load_groups(path):
        if group.name.lower() == name.strip().lower():
            return group
    return None


def save_group(group, path=DEFAULT_DATA_FILE):
    """Insert or replace one group in the file, keeping all other groups intact."""
    groups = load_groups(path)
    for index in range(len(groups)):
        if groups[index].name.lower() == group.name.lower():
            groups[index] = group
            break
    else:
        groups.append(group)
    save_groups(groups, path)


# ----------------------------------------------------------------------
# Append-only audit log
# ----------------------------------------------------------------------

class AuditLog:
    """
    Append-only record of expense changes.

    Entries are numbered with a sequence counter rather than a timestamp:
    reading the clock needs the time/datetime modules, which are off-limits.
    The file is only ever opened in 'a' (append) or 'r' mode.
    """

    def __init__(self, path=DEFAULT_AUDIT_FILE):
        self.path = path
        self._next_seq = None   # found lazily from the existing file

    def record(self, action, group_name, expense_id, details):
        """Append one entry and return its sequence number."""
        if action not in AUDIT_ACTIONS:
            raise ValueError("Unknown audit action: " + repr(action))
        if self._next_seq is None:
            self._next_seq = 1
            for entry in self.read_entries():
                if entry["seq"] >= self._next_seq:
                    self._next_seq = entry["seq"] + 1

        seq = self._next_seq
        line = _record(str(seq), action, escape_field(group_name),
                       str(expense_id), escape_field(details))
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        self._next_seq += 1
        return seq

    def read_entries(self, group_name=None, expense_id=None):
        """
        Parse the log into dicts: {seq, action, group, expense_id, details}.
        Optionally filter by group name (case-insensitive) and/or expense id.
        """
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except FileNotFoundError:
            return []

        entries = []
        lines = text.split("\n")
        for index in range(len(lines)):
            line = lines[index]
            if line.endswith("\r"):
                line = line[:-1]
            if line.strip() == "":
                continue
            fields = line.split("|")
            try:
                if len(fields) != 5:
                    raise StorageError("audit entry needs 5 fields, found " + str(len(fields)))
                if fields[1] not in AUDIT_ACTIONS:
                    raise StorageError("unknown audit action " + repr(fields[1]))
                entry = {
                    "seq": _parse_int(fields[0], "sequence number", 1),
                    "action": fields[1],
                    "group": unescape(fields[2]),
                    "expense_id": _parse_int(fields[3], "expense id", 1),
                    "details": unescape(fields[4]),
                }
            except StorageError as err:
                raise StorageError(self.path + " line " + str(index + 1) + ": " + str(err))

            if group_name is not None and entry["group"].lower() != group_name.lower():
                continue
            if expense_id is not None and entry["expense_id"] != expense_id:
                continue
            entries.append(entry)
        return entries
