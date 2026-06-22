
from __future__ import annotations

import ast as _pyast
import keyword
import re
from dataclasses import dataclass, field

from src.pipeline.stage1_parser.ast_nodes import (
    AstNode,
    DataItemNode,
    DivisionNode,
    ParagraphNode,
    ProgramNode,
    SectionNode,
    StatementNode,
)

_INDENT = "    "

_OPTIONS: dict = {}


def _make_parseable(source: str, warnings: list[str]) -> tuple[str, int]:
                                   
    try:
        _pyast.parse(source)
        return source, 0
    except SyntaxError:
        pass

    lines = source.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []

    def _is_top_level_header(line: str) -> bool:
        stripped = line.lstrip(" ")
        if line.startswith(" "):                                   
            return False
        return (
            stripped.startswith("def ")
            or stripped.startswith("class ")
            or stripped.startswith("if __name__")
        )

                                                                       
    for line in lines:
        if _is_top_level_header(line) and current and any(
            l.strip() for l in current
        ):
            blocks.append(current)
            current = []
        current.append(line)
    if current:
        blocks.append(current)

    repaired = 0
    rebuilt: list[str] = []
    for block in blocks:
        text = "\n".join(block)
        try:
            _pyast.parse(text)
            rebuilt.append(text)
            continue
        except SyntaxError:
            pass

                                                                        
        header_idx = None
        for i, line in enumerate(block):
            s = line.lstrip(" ")
            if s.startswith("def ") or s.startswith("class ") or s.startswith("if __name__"):
                header_idx = i
                break
        if header_idx is None:
                                                                 
                                        
            note = text.strip().splitlines()[0] if text.strip() else "(empty)"
            if len(note) > 100:
                note = note[:97] + "..."
            rebuilt.append(f"pass  # TODO: malformed Stage-1 output ({note})")
            repaired += 1
            warnings.append(f"module-level block replaced with pass+TODO")
            continue

        header = block[header_idx]
                                                                    
                                                                 
        header_indent_len = len(header) - len(header.lstrip(" "))
        body_indent = " " * (header_indent_len + 4)
                                                                        
                                                                  
        body_lines = [l for l in block[header_idx + 1 :] if l.strip()]
        snippet = body_lines[0].strip() if body_lines else "(empty body)"
        if len(snippet) > 100:
            snippet = snippet[:97] + "..."
        rebuilt_block = "\n".join(
            block[: header_idx + 1]
            + [f"{body_indent}pass  # TODO: malformed Stage-1 output ({snippet})"]
        )
        rebuilt.append(rebuilt_block)
        repaired += 1
        warnings.append(
            f"function {header.strip()!r}: body replaced with pass+TODO"
        )

    result = "\n".join(rebuilt)
    if source.endswith("\n"):
        result += "\n"

                                                                      
    try:
        _pyast.parse(result)
    except SyntaxError:
        warnings.append("rebuilt module still unparseable; emitting empty body")
        return 'pass  # TODO: Stage-1 output could not be repaired\n', repaired
    return result, repaired


def _snake(name: str) -> str:
    name = name.replace("-", "_").replace(".", "")
    name = re.sub(r"[^0-9a-zA-Z_]", "", name)
    out = name.lower() or "para"
    if out[0].isdigit():
        out = "p_" + out
    if keyword.iskeyword(out) or keyword.issoftkeyword(out):
        out = out + "_"
    return out


_PY_BUILTINS = frozenset({
    "len", "max", "min", "abs", "ord", "chr", "int", "float", "str",
    "bool", "bytes", "bytearray", "print", "round", "sum", "sorted",
    "range", "enumerate", "zip", "tuple", "list", "dict", "set",
    "divmod", "pow", "any", "all", "map", "filter",
})
_STDLIB_MODULES = frozenset({"math", "statistics", "random", "decimal"})


def _is_python_builtin_name(tok: str) -> bool:
    if not tok:
        return False
    t = tok.strip().lower()
    if t in _PY_BUILTINS or t in _STDLIB_MODULES:
        return True
    if "." in t and re.fullmatch(r"[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+", t):
        head = t.split(".", 1)[0]
        if head in _STDLIB_MODULES:
            return True
    return False


def _operand(token: str) -> str:
    if token is None:
        return "None"
    tok = token.strip()
    if not tok:
        return "''"
    if tok.upper() in {"TRUE", "FALSE"}:
        return tok.capitalize()
                                                         
    if (tok.startswith('"') and tok.endswith('"')) or (tok.startswith("'") and tok.endswith("'")):
        return tok
                                                                      
    if re.fullmatch(r"[+-]?\d+(\.\d+)?", tok):
        return _strip_leading_zeros(tok)
                                                                          
                                                                            
    _fig = tok.upper()
    if _fig in {"SPACE", "SPACES"}:
        return "' '"
    if _fig in {"ZERO", "ZEROS", "ZEROES"}:
        return "0"
    if _fig in {"QUOTE", "QUOTES"}:
        return "'\"'"
    if _fig in {"HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES",
                "NULL", "NULLS"}:
        return "''"
                                                                 
    if _is_python_builtin_name(tok):
        return tok.strip().lower()
    return _snake(tok)


def _strip_leading_zeros(num: str) -> str:
    sign = ""
    body = num
    if body.startswith(("+", "-")):
        sign, body = body[0], body[1:]
    if "." in body:
        int_part, dec_part = body.split(".", 1)
        int_part = int_part.lstrip("0") or "0"
        return f"{sign}{int_part}.{dec_part}"
    body = body.lstrip("0") or "0"
    return f"{sign}{body}"


_OCCURS_MARKER_RE = re.compile(r"__OCCURS_(\d+)__")


def _occurs_count_from_attrs(attrs: dict) -> int | None:
    for key in ("pic", "value", "raw", "occurs_marker"):
        v = attrs.get(key)
        if isinstance(v, str):
            m = _OCCURS_MARKER_RE.search(v)
            if m:
                return int(m.group(1))
    return None


def _default_for_pic(pic: str | None, value: str | None) -> str:
    if value is not None and value != "":
        upper = value.upper()
                                                                       
                                                                      
        pic_is_numeric = False
        try:
            from src.pipeline.stage1_parser.pic_decoder import decode_pic

            if pic:
                decoded = decode_pic(pic)
                if decoded is not None:
                    pic_is_numeric = decoded.type in {"int", "float", "Decimal"}
        except Exception:                
            pass
        if upper in {"ZEROS", "ZEROES", "ZERO"}:
            return "0" if pic_is_numeric else "''"
        if upper in {"SPACES", "SPACE"}:
            return "''"
        if upper in {"HIGH-VALUE", "HIGH-VALUES"}:
            return "''"
        if upper in {"LOW-VALUE", "LOW-VALUES"}:
            return "''"
        if upper in {"NULL", "NULLS"}:
            return "''"
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            return value
        if re.fullmatch(r"[+-]?\d+(\.\d+)?", value):
            return _strip_leading_zeros(value)
        return repr(value)
    if pic is None:
        return "None"
                                                                    
    try:
        from src.pipeline.stage1_parser.pic_decoder import decode_pic

        d = decode_pic(pic)
        if d is not None:
            return d.default_literal
    except Exception:                
        pass
                                                                  
    p = pic.upper()
    if p.startswith("X") or "X(" in p or p.startswith("A"):
        return "''"
    return "0"


@dataclass
class TranslatedProgram:
    code: str
    data_items: dict[str, str] = field(default_factory=dict)
    paragraphs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class RuleBasedTranslator:

    def translate(self, ast: AstNode, options: dict | None = None) -> TranslatedProgram:
        global _OPTIONS
        _OPTIONS = dict(options or {})
        try:
            return self._translate(ast)
        finally:
            _OPTIONS = {}

    def _translate(self, ast: AstNode) -> TranslatedProgram:
        if not isinstance(ast, ProgramNode):
            raise TypeError(f"Expected ProgramNode, got {type(ast).__name__}")

        data_items: dict[str, str] = {}
        paragraphs_src: list[str] = []
        paragraph_names: list[str] = []
        warnings: list[str] = []

                                                                         
        for div in ast.children:
            if not isinstance(div, DivisionNode):
                continue
            has_data_items = any(isinstance(n, DataItemNode) for n in div.walk())
            has_paragraphs = any(isinstance(n, ParagraphNode) for n in div.children) or any(
                isinstance(n, ParagraphNode)
                for sec in div.children
                if isinstance(sec, SectionNode)
                for n in sec.children
            )
            if has_data_items:
                self._collect_data_items(div, data_items)
            if has_paragraphs:
                for para in self._iter_paragraphs(div):
                    py = self._translate_paragraph(para, warnings)
                    paragraphs_src.append(py)
                    paragraph_names.append(_snake(para.attributes.get("name", "para")))

        program_id = ast.attributes.get("program_id", "program")
        module_doc = f'"""Translated from COBOL program {program_id}.\n\nGenerated by parivartana Stage 2 (rule-based baseline).\n"""'

        state_src = self._render_state_block(data_items)
        body = "\n\n".join(paragraphs_src) if paragraphs_src else "pass"
        entry = self._render_entrypoint(paragraph_names, program_id=ast.attributes.get("program_id", ""))

                                                                         
        needs_decimal = any(
            isinstance(v, str) and "Decimal(" in v for v in data_items.values()
        )
        prelude = "from decimal import Decimal\n\n" if needs_decimal else ""

        code = f"{module_doc}\n\n{prelude}{state_src}\n\n{body}\n\n{entry}\n"
                                                                      
                                                                     
        code, repaired = _make_parseable(code, warnings)
        return TranslatedProgram(
            code=code,
            data_items=data_items,
            paragraphs=paragraph_names,
            warnings=warnings + [f"repaired {repaired} unparseable line(s)"] if repaired else warnings,
        )

                                                                        
    def _collect_data_items(self, div: DivisionNode, out: dict[str, str]) -> None:
        for node in div.walk():
            if isinstance(node, DataItemNode):
                name = node.attributes.get("name")
                if not name:
                    continue
                default = _default_for_pic(
                    node.attributes.get("pic"),
                    node.attributes.get("value"),
                )
                                                                    
                                                                     
                attrs = node.attributes
                occurs_n = attrs.get("occurs") or _occurs_count_from_attrs(attrs)
                if occurs_n:
                    default = f"[{default}] * {occurs_n}"
                out[_snake(name)] = default

    def _render_state_block(self, data_items: dict[str, str]) -> str:
        runtime_helper = (
            "class _State(dict):\n"
            f"{_INDENT}def __missing__(self, key):\n"
            f"{_INDENT}{_INDENT}value = 0 if key.startswith(('ws_num', 'ws_count', 'ws_idx', 'ws_i', 'ws_n', 'ws_total', 'ws_sum', 'sub')) else ''\n"
            f"{_INDENT}{_INDENT}self[key] = value\n"
            f"{_INDENT}{_INDENT}return value\n"
        )
        if _OPTIONS.get("pythonic"):
            runtime_helper += (
                f"{_INDENT}def __getattr__(self, key):\n"
                f"{_INDENT}{_INDENT}return self[key]\n"
                f"{_INDENT}def __setattr__(self, key, value):\n"
                f"{_INDENT}{_INDENT}self[key] = value\n"
            )
        if not data_items:
            return runtime_helper + "\nstate: _State = _State()"
        lines = [runtime_helper, "", "state: _State = _State({"]
        for name, default in data_items.items():
            lines.append(f"{_INDENT}{name!r}: {default},")
        lines.append("})")
        return "\n".join(lines)

                                                                        
    def _iter_paragraphs(self, div: DivisionNode):
        for child in div.children:
            if isinstance(child, ParagraphNode):
                yield child
            elif isinstance(child, SectionNode):
                for sub in child.children:
                    if isinstance(sub, ParagraphNode):
                        yield sub

    def _translate_paragraph(self, para: ParagraphNode, warnings: list[str]) -> str:
        fn_name = _snake(para.attributes.get("name", "para"))
        items = self._flatten_paragraph_items(para)
        body = self._render_block(items, 0, len(items), depth=1, warnings=warnings)
        if not body.strip():
            body = f"{_INDENT}pass"
        header = f"def {fn_name}() -> None:"
        return header + "\n" + body

    @staticmethod
    def _flatten_paragraph_items(para: ParagraphNode) -> list[dict]:
        terminator_keywords = {"END-IF", "END-PERFORM", "END-READ", "END-EVALUATE"}
        items: list[dict] = []
        for child in para.children:
            if not isinstance(child, StatementNode):
                continue
            verb = (child.attributes.get("verb") or "").upper()
            operands = list(child.attributes.get("operands") or [])
            tail_markers: list[str] = []
            while operands and str(operands[-1]).upper() in terminator_keywords:
                tail_markers.insert(0, str(operands.pop()).upper())
            items.append({"kind": "stmt", "verb": verb, "operands": operands})
            for marker in tail_markers:
                items.append({"kind": "marker", "verb": marker, "operands": []})
        return items

    def _render_block(
        self,
        items: list[dict],
        start: int,
        end: int,
        depth: int,
        warnings: list[str],
    ) -> str:
        indent = _INDENT * depth
        lines: list[str] = []
        i = start
        while i < end:
            item = items[i]
            if item["kind"] == "marker":
                i += 1
                continue
            verb = item["verb"]
            operands = item["operands"]

            if verb == "IF":
                cond = _translate_condition(operands) or "True"
                else_at, end_at = self._find_if_bounds(items, i + 1, end)
                then_end = else_at if else_at is not None else (end_at if end_at is not None else end)
                then_body = self._render_block(items, i + 1, then_end, depth + 1, warnings)
                if not then_body.strip():
                    then_body = f"{_INDENT * (depth + 1)}pass"
                lines.append(f"{indent}if {cond}:")
                lines.append(then_body)
                if else_at is not None:
                    else_end = end_at if end_at is not None else end
                    else_body = self._render_block(items, else_at + 1, else_end, depth + 1, warnings)
                    if not else_body.strip():
                        else_body = f"{_INDENT * (depth + 1)}pass"
                    lines.append(f"{indent}else:")
                    lines.append(else_body)
                i = (end_at + 1) if end_at is not None else end
                continue

            if verb == "ELSE":
                warnings.append("orphan ELSE skipped")
                i += 1
                continue

            if verb == "PERFORM" and self._is_inline_perform(operands):
                end_at = self._find_perform_end(items, i + 1, end)
                header = self._inline_perform_header(operands)
                body_end = end_at if end_at is not None else end
                inner = self._render_block(items, i + 1, body_end, depth + 1, warnings)
                if not inner.strip():
                    inner = f"{_INDENT * (depth + 1)}pass"
                lines.append(f"{indent}{header}")
                lines.append(inner)
                i = (end_at + 1) if end_at is not None else end
                continue

            rendered = self._render_statement_parts(verb, operands, warnings)
            for line in rendered.splitlines():
                lines.append(f"{indent}{line}")
            i += 1

        return "\n".join(lines)

    @staticmethod
    def _find_if_bounds(items: list[dict], start: int, end: int) -> tuple[int | None, int | None]:
        depth_if = 1
        else_at: int | None = None
        end_at: int | None = None
        j = start
        while j < end:
            it = items[j]
            if it["kind"] == "stmt" and it["verb"] == "IF":
                depth_if += 1
            elif it["kind"] == "stmt" and it["verb"] == "ELSE" and depth_if == 1 and else_at is None:
                else_at = j
            elif it["kind"] == "marker" and it["verb"] == "END-IF":
                depth_if -= 1
                if depth_if == 0:
                    end_at = j
                    break
            j += 1
        return else_at, end_at

    def _find_perform_end(self, items: list[dict], start: int, end: int) -> int | None:
        depth_p = 1
        j = start
        while j < end:
            it = items[j]
            if it["kind"] == "stmt" and it["verb"] == "PERFORM" and self._is_inline_perform(it["operands"]):
                depth_p += 1
            elif it["kind"] == "marker" and it["verb"] == "END-PERFORM":
                depth_p -= 1
                if depth_p == 0:
                    return j
            j += 1
        return None

    @staticmethod
    def _is_inline_perform(operands: list[str]) -> bool:
        if not operands:
            return True
        first = str(operands[0]).upper()
        if first in {"UNTIL", "VARYING", "WITH"}:
            return True
        if (
            len(operands) >= 2
            and str(operands[1]).upper() == "TIMES"
            and re.fullmatch(r"[+-]?\d+", str(operands[0]))
        ):
            return True
        return False

    @staticmethod
    def _inline_perform_header(operands: list[str]) -> str:
        if not operands:
            return "while True:"
        upper = [str(o).upper() for o in operands]
        if "UNTIL" in upper:
            ui = upper.index("UNTIL")
            cond_tokens = operands[ui + 1 :]
            cond = _translate_condition(cond_tokens) or "True"
            return f"while not ({cond}):"
        if "TIMES" in upper:
            ti = upper.index("TIMES")
            count = operands[ti - 1] if ti > 0 else "1"
            return f"for _ in range({_ref(count)}):"
        if "VARYING" in upper:
            vi = upper.index("VARYING")
            var = operands[vi + 1] if vi + 1 < len(operands) else "i"
            from_val = "0"
            by_val = "1"
            cond = "True"
            if "FROM" in upper:
                fi = upper.index("FROM")
                if fi + 1 < len(operands):
                    from_val = str(operands[fi + 1])
            if "BY" in upper:
                bi = upper.index("BY")
                if bi + 1 < len(operands):
                    by_val = str(operands[bi + 1])
            if "UNTIL" in upper:
                ui = upper.index("UNTIL")
                cond = _translate_condition(operands[ui + 1 :]) or "True"
            init = f"{_state(var)} = {_ref(from_val)}"
            step = f"{_state(var)} = {_state(var)} + {_ref(by_val)}"
            return f"{init}\nwhile not ({cond}):"
        return "while True:"

    def _render_statement(self, stmt: StatementNode, warnings: list[str]) -> str:
        verb = (stmt.attributes.get("verb") or "").upper()
        operands = list(stmt.attributes.get("operands") or [])
        return self._render_statement_parts(verb, operands, warnings)

    @staticmethod
    def _render_statement_parts(verb: str, operands: list[str], warnings: list[str]) -> str:
        handler = _VERB_TABLE.get(verb)
        if handler is None:
            warnings.append(f"unsupported verb: {verb}")
            return f"pass  # TODO: unsupported COBOL verb {verb} {' '.join(operands)}"
        return handler(operands)

                                                                        
    def _render_entrypoint(self, paragraph_names: list[str], *, program_id: str = "") -> str:
        if not paragraph_names:
            return 'if __name__ == "__main__":\n    pass'
        if _OPTIONS.get("entry_fallthrough"):
            calls = "\n".join(f"{_INDENT}{_INDENT}{n}()" for n in paragraph_names)
        else:
            main = self._pick_entry_paragraph(paragraph_names, program_id=program_id)
            calls = f"{_INDENT}{_INDENT}{main}()"
        return (
            'if __name__ == "__main__":\n'
            f'{_INDENT}try:\n'
            f'{calls}\n'
            f'{_INDENT}except Exception as _exc:\n'
            f'{_INDENT}{_INDENT}import sys\n'
            f'{_INDENT}{_INDENT}print(f"runtime: {{type(_exc).__name__}}: {{_exc}}", file=sys.stderr)\n'
        )

    @staticmethod
    def _pick_entry_paragraph(names: list[str], *, program_id: str = "") -> str:
        preferred = (
            "main_para", "main", "begin", "start", "start_para",
            "driver", "mainline", "main_line",
        )
        lowered = {n.lower(): n for n in names}

                                     
        for candidate in preferred:
            if candidate in lowered:
                return lowered[candidate]

                                                         
        if program_id:
            pid_lower = _snake(program_id).lower()
            for suffix in ("_control", "_main", "_mainline", "_begin", "_start", "_driver"):
                target = pid_lower + suffix
                if target in lowered:
                    return lowered[target]

                                                                         
        for n in names:
            if n.lower() not in {"declaratives", "declarative"}:
                return n

                                                     
        return names[0]


def _strip_noise(operands: list[str]) -> list[str]:
    drop = {"TO", "FROM", "BY", "GIVING", "OF", "IN", ".", ",", ";", "(", ")"}
    return [o for o in operands if o.upper() not in drop]


def _valid_attr(name: str) -> bool:
    import keyword
    return name.isidentifier() and not keyword.iskeyword(name)


def _state(ref: str) -> str:
    name = _snake(ref)
    if _OPTIONS.get("pythonic") and _valid_attr(name):
        return f"state.{name}"
    return f"state[{name!r}]"


def _move(operands: list[str]) -> str:
    operands = [o for o in operands if o not in {"(", ")"}]
    if "TO" in [o.upper() for o in operands]:
        idx = [o.upper() for o in operands].index("TO")
        src = operands[idx - 1] if idx > 0 else operands[0]
        targets = operands[idx + 1 :]
    else:
        src, *targets = operands or [""]
    rhs = _operand(src) if _is_literal(src) else _state(src)
    lines = [f"{_state(t)} = {rhs}" for t in targets] or [f"pass  # MOVE {src}"]
    return "\n".join(lines)


def _is_literal(tok: str) -> bool:
    if tok is None:
        return False
    t = tok.strip()
    if not t:
        return False
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        return True
    if re.fullmatch(r"[+-]?\d+(\.\d+)?", t):
        return True
    if t.upper() in {
        "ZERO", "ZEROS", "ZEROES", "SPACE", "SPACES", "TRUE", "FALSE",
        "QUOTE", "QUOTES", "HIGH-VALUE", "HIGH-VALUES",
        "LOW-VALUE", "LOW-VALUES", "NULL", "NULLS",
    }:
        return True
    return False


def _ref(tok: str) -> str:
                                                                        
                                                              
    if _is_literal(tok) or _is_python_builtin_name(tok):
        return _operand(tok)
    return _state(tok)


def _arithmetic(op_symbol: str):
    def render(operands: list[str]) -> str:
        ops = _strip_noise(operands)
        if len(ops) < 2:
            return f"pass  # {op_symbol} {' '.join(operands)}"
        lhs, *rest = ops
                                                            
        target = rest[-1]
        rest_terms = rest[:-1] or [lhs]
        if rest_terms == [lhs]:
                                 
            expr = f"{_state(target)} {op_symbol} {_ref(lhs)}"
        else:
            terms = " ".join(_ref(t) for t in [lhs, *rest_terms])
            expr = f"{terms} {op_symbol} {_ref(target)}".strip()
        return f"{_state(target)} = {expr}"
    return render


def _compute(operands: list[str]) -> str:
                                        
    if "=" not in operands:
        return f"pass  # COMPUTE {' '.join(operands)}"
    idx = operands.index("=")
    target = operands[idx - 1]
    rhs_tokens = operands[idx + 1 :]
    rendered = " ".join(_ref(t) if t not in {"+", "-", "*", "/", "(", ")"} else t for t in rhs_tokens)
    return f"{_state(target)} = {rendered}"


def _display(operands: list[str]) -> str:
    parts = [_ref(o) for o in operands] or ['""']
    if _OPTIONS.get("pythonic") and len(parts) > 1:
        return "print(" + ", ".join(parts) + ', sep="")'
    return "print(" + ", ".join(parts) + ")"


def _perform(operands: list[str]) -> str:
    if not operands:
        return "pass  # PERFORM <missing>"
    target = operands[0]
    upper = [o.upper() for o in operands]
    if "UNTIL" in upper:
        ui = upper.index("UNTIL")
        cond_tokens = operands[ui + 1 :]
        cond = _translate_condition(cond_tokens)
        return f"while not ({cond}):\n{_INDENT}{_snake(target)}()"
    if "TIMES" in upper:
        ti = upper.index("TIMES")
        count = operands[ti - 1] if ti > 0 else "1"
        return f"for _ in range({_ref(count)}):\n{_INDENT}{_snake(target)}()"
    return f"{_snake(target)}()"


def _translate_condition(tokens: list[str]) -> str:
    out: list[str] = []
                                                                           
    _NEG = {"==": "!=", "!=": "==", ">": "<=", "<": ">=", ">=": "<", "<=": ">"}
    pending_not = False                                                              

    def _emit(op: str) -> None:
        nonlocal pending_not
        if pending_not:
            out.append(_NEG.get(op, f"not {op}"))
            pending_not = False
        else:
            out.append(op)

                                                                       
    _FILLER = {"IS", "ARE", "WAS", "WERE", "BEING", "BE", "THEN"}

                                                                    
    _BODY_STARTERS = {
        "GO", "MOVE", "DISPLAY", "COMPUTE", "ADD", "SUBTRACT", "MULTIPLY",
        "DIVIDE", "PERFORM", "IF", "ACCEPT", "STOP", "EXIT", "READ", "WRITE",
        "OPEN", "CLOSE", "CALL", "RETURN", "SET", "GOBACK", "CONTINUE",
        "INITIALIZE", "INSPECT", "STRING", "UNSTRING", "EVALUATE", "SEARCH",
        "REWRITE", "DELETE", "START", "REPLACE", "SORT", "MERGE", "RELEASE",
    }

    i = 0
    while i < len(tokens):
        t = tokens[i].upper()
        if t in _BODY_STARTERS and out:
                                                                       
                                                              
            break
        if t in _FILLER:
            i += 1
            continue
                                                                     
                                                                      
        if tokens[i] in {"(", ")"}:
            out.append(tokens[i])
            i += 1
            continue
                                                                    
                                                                       
        if tokens[i] in {",", ".", ";", ":"}:
            i += 1
            continue
        if t in {"GREATER", ">"} and i + 1 < len(tokens) and tokens[i + 1].upper() == "THAN":
            _emit(">")
            i += 2
            continue
        if t in {"LESS", "<"} and i + 1 < len(tokens) and tokens[i + 1].upper() == "THAN":
            _emit("<")
            i += 2
            continue
        if t in {"EQUAL", "EQUALS"}:
            _emit("==")
            i += 1
            continue
        if t == "TO" and out and out[-1] in _NEG:
                                                                          
            i += 1
            continue
        if t == "NOT":
                                                                        
                                                                         
            nxt = tokens[i + 1].upper() if i + 1 < len(tokens) else ""
            if nxt in {"EQUAL", "EQUALS", "GREATER", "LESS", "=", ">", "<", "==", "!=", ">=", "<="}:
                pending_not = True
            else:
                out.append("not")
            i += 1
            continue
        if t in {"AND", "OR"}:
            out.append(t.lower())
            i += 1
            continue
        if t in {">", "<", ">=", "<=", "==", "!="}:
            _emit(t)
            i += 1
            continue
        if t == "=":
                                                                        
            _emit("==")
            i += 1
            continue
        out.append(_ref(tokens[i]))
        i += 1

    expr = " ".join(out).strip()
    return expr or "False"


def _stop(operands: list[str]) -> str:
    return "return"


def _if_(operands: list[str]) -> str:
    cond = _translate_condition(operands) or "True"
    return f"if {cond}:\n{_INDENT}pass"


def _accept(operands: list[str]) -> str:
    if not operands:
        return "pass  # ACCEPT"
    target = operands[0]
    return f"{_state(target)} = input()"


def _goback(operands: list[str]) -> str:
    return "return"


def _exit(operands: list[str]) -> str:
    if operands and operands[0].upper() == "PROGRAM":
        return "return"
    return "return"


def _continue(operands: list[str]) -> str:
                                                                
                                                                     
    return "pass"


def _initialize(operands: list[str]) -> str:
    targets = [o for o in _strip_noise(operands) if o.upper() not in {"REPLACING", "ALL", "BY"}]
    if not targets:
        return "pass  # INITIALIZE"
    lines = [f"{_state(t)} = 0 if isinstance({_state(t)}, (int, float)) else ''" for t in targets]
    return "\n".join(lines)


def _open(operands: list[str]) -> str:
    ops = [o for o in operands if o.upper() not in {"."}]
    mode_map = {"INPUT": "r", "OUTPUT": "w", "I-O": "r+", "EXTEND": "a"}
    lines: list[str] = []
    mode = "r"
    i = 0
    while i < len(ops):
        tok = ops[i].upper()
        if tok in mode_map:
            mode = mode_map[tok]
            i += 1
            continue
        name = _snake(ops[i])
        lines.append(f"state[{name!r}] = open({name!r}, {mode!r})")
        i += 1
    return "\n".join(lines) or "pass  # OPEN"


def _close(operands: list[str]) -> str:
    ops = [o for o in operands if o.upper() not in {"."}]
    lines = []
    for o in ops:
        lines.append(f"if hasattr({_state(o)}, 'close'): {_state(o)}.close()")
    return "\n".join(lines) or "pass  # CLOSE"


_AT_END_MARKER = "__AT_END__"
_NOT_AT_END_MARKER = "__NOT_AT_END__"
_INVALID_KEY_MARKER = "__INVALID_KEY__"
_NOT_INVALID_KEY_MARKER = "__NOT_INVALID_KEY__"
_IO_MARKERS = {
    _AT_END_MARKER, _NOT_AT_END_MARKER,
    _INVALID_KEY_MARKER, _NOT_INVALID_KEY_MARKER,
}


def _consume_io_clauses(operands: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    clauses: dict[str, list[str]] = {}
    main: list[str] = []
    current: list[str] | None = None
    current_key: str | None = None
    for tok in operands:
        if tok in _IO_MARKERS:
            if current_key is not None and current is not None:
                clauses[current_key] = current
            current_key = tok
            current = []
            continue
        if current is None:
            main.append(tok)
        else:
            current.append(tok)
    if current_key is not None and current is not None:
        clauses[current_key] = current
    return main, clauses


def _clause_body_to_python(clause_operands: list[str]) -> str:
    if not clause_operands:
        return "pass"
    head = clause_operands[0].upper()
    rest = clause_operands[1:]
    handler = _VERB_TABLE.get(head)
    if handler is None:
        return f"pass  # {' '.join(clause_operands)}"
    try:
        return handler(rest)
    except Exception:                
        return f"pass  # {' '.join(clause_operands)}"


def _wrap_io_with_clauses(
    primary: str,
    target: str,
    clauses: dict[str, list[str]],
    *,
    exception_type: str = "EOFError",
) -> str:
    if not clauses:
        return primary
    at_end = clauses.get(_AT_END_MARKER) or clauses.get(_INVALID_KEY_MARKER)
    not_at_end = clauses.get(_NOT_AT_END_MARKER) or clauses.get(_NOT_INVALID_KEY_MARKER)
    lines = ["try:"]
    for ln in primary.splitlines():
        lines.append("    " + ln)
    if not_at_end:
        body = _clause_body_to_python(not_at_end)
        for ln in body.splitlines():
            lines.append("    " + ln)
    if at_end is not None:
        lines.append(f"except {exception_type}:")
        body = _clause_body_to_python(at_end) if at_end else "pass"
        for ln in body.splitlines():
            lines.append("    " + ln)
    else:
        lines.append(f"except {exception_type}:")
        lines.append("    pass")
    return "\n".join(lines)


def _read(operands: list[str]) -> str:
    main, clauses = _consume_io_clauses(operands)
    if not main:
        return "pass  # READ"
    target = main[0]
    primary = (
        f"{_state(target)} = "
        f"{_state(target)}.readline() if hasattr({_state(target)}, 'readline') else ''"
    )
    return _wrap_io_with_clauses(primary, target, clauses, exception_type="EOFError")


def _write(operands: list[str]) -> str:
    main, clauses = _consume_io_clauses(operands)
    ops = _strip_noise(main)
    if not ops:
        return "pass  # WRITE"
    rec = ops[0]
    src = None
    upper = [o.upper() for o in main]
    if "FROM" in upper:
        fi = upper.index("FROM")
        if fi + 1 < len(main):
            src = main[fi + 1]
    value = _ref(src) if src else _state(rec)
    primary = f"print({value})"
    return _wrap_io_with_clauses(primary, rec, clauses, exception_type="OSError")


def _call(operands: list[str]) -> str:
    if not operands:
        return "state['_call_target'] = None  # CALL (no target given)"
    target = operands[0].strip('"').strip("'")
    return (
        f"state['_call_target'] = {target!r}  # CALL {target}"
    )


def _set(operands: list[str]) -> str:
    upper = [o.upper() for o in operands]
    if "TO" in upper:
        ti = upper.index("TO")
        target = operands[ti - 1] if ti > 0 else None
        value = operands[ti + 1] if ti + 1 < len(operands) else None
        if target is not None and value is not None:
            if value.upper() in {"TRUE", "FALSE"}:
                return f"{_state(target)} = {value.capitalize()}"
            return f"{_state(target)} = {_ref(value)}"
    return f"pass  # SET {' '.join(operands)}"


def _evaluate(operands: list[str]) -> str:
    ops = _strip_noise(operands)
    subject = _ref(ops[0]) if ops else "True"
    return f"_eval_subject = {subject}"


def _when(operands: list[str]) -> str:
    ops = _strip_noise(operands)
    if not ops or ops[0].upper() == "OTHER":
        return "else:"
    val = _ref(ops[0])
    return f"if _eval_subject == {val}:"


def _search(operands: list[str]) -> str:
    if not operands:
        return "pass  # SEARCH"
    target = operands[0]
    return f"for _entry in {_state(target)} if isinstance({_state(target)}, (list, tuple)) else []:\n{_INDENT}pass  # SEARCH body"


def _sort(operands: list[str]) -> str:
    if not operands:
        return "pass  # SORT"
    target = operands[0]
    return f"{_state(target)} = sorted({_state(target)}) if isinstance({_state(target)}, (list, tuple)) else {_state(target)}"


def _merge(operands: list[str]) -> str:
    return "state['_file_status'] = '00'  # MERGE (file merge)"


def _release(operands: list[str]) -> str:
    if not operands:
        return "state['_release_record'] = None  # RELEASE"
    return f"state['_release_record'] = {_state(operands[0])}  # RELEASE {operands[0]}"


def _return(operands: list[str]) -> str:
    if not operands:
        return "return"
    return f"# RETURN {operands[0]}\nreturn"


def _string(operands: list[str]) -> str:
    ops = _strip_noise(operands)
    upper = [o.upper() for o in operands]
    if "INTO" in upper:
        idx = upper.index("INTO")
        target = operands[idx + 1] if idx + 1 < len(operands) else None
        parts = operands[:idx]
        if target:
            joined = " + ".join(_ref(p) for p in parts if p.upper() not in {"DELIMITED", "BY", "SIZE"})
            return f"{_state(target)} = str({joined})" if joined else f"pass  # STRING"
    return "pass  # STRING (incomplete)"


def _unstring(operands: list[str]) -> str:
    return "pass  # UNSTRING (split — needs operand inspection)"


def _inspect(operands: list[str]) -> str:
    if not operands:
        return "state['_inspect_target'] = None  # INSPECT"
    target = operands[0]
    return f"state['_inspect_target'] = {_state(target)}  # INSPECT {target}"


def _cancel(operands: list[str]) -> str:
    return "state['_call_target'] = None  # CANCEL (no-op in Python)"


def _alter(operands: list[str]) -> str:
    return "state['_alter_seen'] = True  # ALTER (deprecated COBOL feature)"


def _use(operands: list[str]) -> str:
    return "state['_declarative_active'] = True  # USE (declarative)"


def _invoke(operands: list[str]) -> str:
    if not operands:
        return "state['_invoke_target'] = None  # INVOKE"
    return f"state['_invoke_target'] = {operands[0]!r}  # INVOKE {operands[0]}"


def _generate(operands: list[str]) -> str:
    return "state['_report_generated'] = True  # GENERATE (Report Writer)"


def _initiate(operands: list[str]) -> str:
    return "state['_report_active'] = True  # INITIATE (Report Writer)"


def _terminate(operands: list[str]) -> str:
    return "state['_report_active'] = False  # TERMINATE (Report Writer)"


def _suppress(operands: list[str]) -> str:
    return "state['_suppress'] = True  # SUPPRESS"


def _send(operands: list[str]) -> str:
    return "state['_cd_sent'] = True  # SEND (communication)"


def _receive(operands: list[str]) -> str:
    return "state['_cd_received'] = True  # RECEIVE (communication)"


def _rewrite(operands: list[str]) -> str:
    main, clauses = _consume_io_clauses(operands)
    if not main:
        return "state['_file_status'] = '00'  # REWRITE"
    primary = f"state['_file_status'] = '00'  # REWRITE {main[0]}"
    return _wrap_io_with_clauses(primary, main[0], clauses, exception_type="OSError")


def _delete_(operands: list[str]) -> str:
    main, clauses = _consume_io_clauses(operands)
    if not main:
        return "state['_file_status'] = '00'  # DELETE"
    primary = f"state['_file_status'] = '00'  # DELETE {main[0]}"
    return _wrap_io_with_clauses(primary, main[0], clauses, exception_type="OSError")


def _start(operands: list[str]) -> str:
    main, clauses = _consume_io_clauses(operands)
    if not main:
        return "state['_file_status'] = '00'  # START"
    primary = f"state['_file_status'] = '00'  # START {main[0]}"
    return _wrap_io_with_clauses(primary, main[0], clauses, exception_type="OSError")


def _go(operands: list[str]) -> str:
    ops = _strip_noise(operands)
    ops = [o for o in ops if o.upper() not in {"TO", "DEPENDING", "ON"}]
    if not ops:
        return "pass  # GO TO"
    if len(ops) == 1:
        target = ops[0]
        return f"{_snake(target)}()\nreturn"
    targets = ", ".join(_snake(t) for t in ops[:-1])
    selector = ops[-1]
    return (
        f"_branches = ({targets},)\n"
        f"try:\n"
        f"{_INDENT}_branches[int({_ref(selector)}) - 1]()\n"
        f"except (IndexError, TypeError, ValueError):\n"
        f"{_INDENT}pass\n"
        f"return"
    )


def _enter(operands: list[str]) -> str:
    return "pass  # ENTER (obsolete COBOL feature)"


_VERB_TABLE = {
    "MOVE": _move,
    "ADD": _arithmetic("+"),
    "SUBTRACT": _arithmetic("-"),
    "MULTIPLY": _arithmetic("*"),
    "DIVIDE": _arithmetic("/"),
    "COMPUTE": _compute,
    "DISPLAY": _display,
    "PERFORM": _perform,
    "STOP": _stop,
    "IF": _if_,
    "ACCEPT": _accept,
    "GOBACK": _goback,
    "EXIT": _exit,
    "CONTINUE": _continue,
    "INITIALIZE": _initialize,
    "OPEN": _open,
    "CLOSE": _close,
    "READ": _read,
    "WRITE": _write,
    "CALL": _call,
    "SET": _set,
    "EVALUATE": _evaluate,
    "WHEN": _when,
    "SEARCH": _search,
    "SORT": _sort,
    "MERGE": _merge,
    "RELEASE": _release,
    "RETURN": _return,
    "STRING": _string,
    "UNSTRING": _unstring,
    "INSPECT": _inspect,
    "CANCEL": _cancel,
    "ALTER": _alter,
    "USE": _use,
    "INVOKE": _invoke,
    "GENERATE": _generate,
    "INITIATE": _initiate,
    "TERMINATE": _terminate,
    "SUPPRESS": _suppress,
    "SEND": _send,
    "RECEIVE": _receive,
    "REWRITE": _rewrite,
    "DELETE": _delete_,
    "START": _start,
    "GO": _go,
    "ENTER": _enter,
}
