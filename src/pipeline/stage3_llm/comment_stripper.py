
from __future__ import annotations

import re


_COMMENT_LINE_RE = re.compile(r"^\s*#")


def strip_comments(source: str) -> str:
    if not source:
        return source
    out_lines: list[str] = []
    for line in source.splitlines():
        if _COMMENT_LINE_RE.match(line):
            continue
        if "#" not in line:
            out_lines.append(line)
            continue
        new_line = _strip_inline_comment(line)
        if new_line.strip() or not line.strip():
            out_lines.append(new_line)
    while out_lines and not out_lines[-1].strip():
        out_lines.pop()
    result = "\n".join(out_lines)
    if source.endswith("\n"):
        result += "\n"
    return result


def _strip_inline_comment(line: str) -> str:
    quote: str | None = None
    escape = False
    for i, ch in enumerate(line):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in ('"', "'"):
            quote = ch
            continue
        if ch == "#":
            return line[:i].rstrip()
    return line
