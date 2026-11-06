"""A small TOML writer for the subset Jobforge emits.

`tomllib` reads TOML but cannot write it, and the runtime is stdlib only
(D-13, D-41). Jobforge only ever writes flat tables of scalars and string
lists, plus one level of nested array-of-tables (an atom's phrasings), so
this covers exactly that and refuses anything else rather than guessing.

Writers in Jobforge append to files and never rewrite a file the user may
have edited by hand, so comments survive (SOW 0.2). This module only turns
values into text; the append-only rule lives in the callers.
"""
from __future__ import annotations

import datetime as _dt
import re

_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def _key(k: str) -> str:
    if not isinstance(k, str) or not k:
        raise TypeError(f"TOML keys must be non-empty strings, got {k!r}")
    return k if _BARE_KEY.match(k) else _string(k)


def _string(s: str) -> str:
    out = ['"']
    for ch in s:
        code = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif code < 0x20 or code == 0x7F:
            out.append(f"\\u{code:04X}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def value(v: object) -> str:
    """Render one TOML value. Supports str, bool, int, float, date, list."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return _string(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("NaN and infinity are not written")
        return repr(v)
    if isinstance(v, _dt.datetime):
        raise TypeError("datetimes are not written; use a date")
    if isinstance(v, _dt.date):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        if any(isinstance(i, (dict, list, tuple)) for i in v):
            raise TypeError("nested lists and tables inside lists are not written")
        return "[" + ", ".join(value(i) for i in v) + "]"
    raise TypeError(f"cannot write {type(v).__name__} as TOML")


def table_array_entry(name: str, fields: dict, children: dict[str, list[dict]] | None = None) -> str:
    """Render one `[[name]]` entry, its scalar fields, then any nested
    `[[name.child]]` entries. Returns text ending in a newline."""
    lines = [f"[[{_key(name)}]]"]
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, dict) or (isinstance(v, list) and v and isinstance(v[0], dict)):
            raise TypeError(
                f"field {k!r} is a table; pass it in `children` instead")
        lines.append(f"{_key(k)} = {value(v)}")
    for child_name, entries in (children or {}).items():
        for entry in entries:
            lines.append("")
            lines.append(f"[[{_key(name)}.{_key(child_name)}]]")
            for k, v in entry.items():
                if v is None:
                    continue
                lines.append(f"{_key(k)} = {value(v)}")
    return "\n".join(lines) + "\n"
