
from __future__ import annotations

import re
from dataclasses import dataclass

from src.pipeline.stage1_parser.complexity import ComplexityTier
from src.pipeline.stage3_llm.providers import LLMProvider
from src.utils.logging import get_logger

log = get_logger(__name__)


DOCSTRING_SYSTEM = (
    "You are an expert Python documentation writer. Given a Python "
    "function and the COBOL paragraph it was translated from, write a "
    "concise Google-style docstring. Describe purpose, args, and return "
    "value. Do not invent behaviour the code does not implement. "
    "Reply with just the docstring body, no triple quotes."
)


HIGH_TIER_BANNER = (
    '"""HUMAN REVIEW REQUIRED — complexity tier = HIGH.\n\n'
    'This translation contains constructs (OCCURS DEPENDING, GO TO,\n'
    'REDEFINES, EXEC, SORT/MERGE, etc.) that the rule-based and\n'
    'neural paths cannot fully cover. Review carefully before use.\n'
    '"""\n\n'
)


@dataclass
class DocstringInsertion:
    function_name: str
    docstring: str


class DocstringSynthesiser:

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def synthesise(self, python_code: str, cobol_paragraph: str | None = None) -> list[DocstringInsertion]:
        if not self.provider.is_available():
            log.info("Docstring synthesiser: provider unavailable; skipping")
            return []
        functions = _find_functions(python_code)
        out: list[DocstringInsertion] = []
        for fn_name, fn_body in functions:
            user = self._build_prompt(fn_name, fn_body, cobol_paragraph)
            try:
                response = self.provider.complete(DOCSTRING_SYSTEM, user)
            except Exception as exc:                
                log.warning(f"Docstring synthesis for {fn_name} failed: {exc}")
                continue
            doc = response.text.strip().strip('"').strip("'")
            if doc:
                out.append(DocstringInsertion(function_name=fn_name, docstring=doc))
        return out

    def _build_prompt(self, fn_name: str, fn_body: str, cobol: str | None) -> str:
        parts = [f"Python function `{fn_name}`:", "```python", fn_body.strip(), "```"]
        if cobol:
            parts += ["", "Original COBOL paragraph:", "```", cobol.strip(), "```"]
        return "\n".join(parts)


def insert_docstrings(python_code: str, insertions: list[DocstringInsertion]) -> str:
    by_name = {ins.function_name: ins.docstring for ins in insertions}
    out_lines: list[str] = []
    i = 0
    lines = python_code.splitlines()
    while i < len(lines):
        line = lines[i]
        out_lines.append(line)
        match = re.match(r"^(\s*)def\s+(\w+)\s*\(.*\)\s*(?:->\s*[^:]+)?:\s*$", line)
        if match and match.group(2) in by_name:
            indent = match.group(1) + "    "
                                                           
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            if next_line.lstrip().startswith(('"""', "'''")):
                pass
            else:
                doc = by_name[match.group(2)]
                out_lines.append(f'{indent}"""{doc}"""')
        i += 1
    return "\n".join(out_lines)


def annotate_high_tier(python_code: str, tier: ComplexityTier) -> str:
    if tier != ComplexityTier.HIGH:
        return python_code
    if "HUMAN REVIEW REQUIRED" in python_code:
        return python_code
    return HIGH_TIER_BANNER + python_code


def _find_functions(source: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)def\s+(\w+)\s*\(", lines[i])
        if not m:
            i += 1
            continue
        base_indent = len(m.group(1))
        name = m.group(2)
        body = [lines[i]]
        i += 1
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped:
                body.append(lines[i])
                i += 1
                continue
            current_indent = len(lines[i]) - len(lines[i].lstrip())
            if current_indent <= base_indent and stripped:
                break
            body.append(lines[i])
            i += 1
        out.append((name, "\n".join(body)))
    return out
