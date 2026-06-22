
from __future__ import annotations

import ast as pyast


_INTERESTING = (
    pyast.Module,
    pyast.FunctionDef,
    pyast.AsyncFunctionDef,
    pyast.ClassDef,
    pyast.If,
    pyast.For,
    pyast.While,
    pyast.Try,
    pyast.With,
    pyast.Return,
    pyast.Assign,
    pyast.AugAssign,
    pyast.Expr,
    pyast.Call,
    pyast.Raise,
    pyast.Break,
    pyast.Continue,
    pyast.Pass,
    pyast.Import,
    pyast.ImportFrom,
)


def parse_python_or_none(source: str) -> pyast.AST | None:
    try:
        return pyast.parse(source)
    except SyntaxError:
        return None


def render_python_ast(source: str, max_depth: int = 6) -> str:
    try:
        tree = pyast.parse(source)
    except SyntaxError as exc:
        return (
            f"(Python source does not parse — SyntaxError at line {exc.lineno}: "
            f"{exc.msg})"
        )
    lines: list[str] = []
    _walk(tree, prefix="", is_last=True, depth=0, max_depth=max_depth, out=lines)
    return "\n".join(lines)


def _summary(node: pyast.AST) -> str:
    cls = type(node).__name__

    if isinstance(node, pyast.Module):
        return f"{cls}"
    if isinstance(node, pyast.FunctionDef | pyast.AsyncFunctionDef):
        args = [a.arg for a in node.args.args]
        return f"{cls}  name={node.name}  args=({', '.join(args)})"
    if isinstance(node, pyast.ClassDef):
        return f"{cls}  name={node.name}"
    if isinstance(node, pyast.If):
        return f"{cls}  test={_short(node.test)}"
    if isinstance(node, pyast.For):
        return f"{cls}  target={_short(node.target)}  iter={_short(node.iter)}"
    if isinstance(node, pyast.While):
        return f"{cls}  test={_short(node.test)}"
    if isinstance(node, pyast.Try):
        return f"{cls}  handlers={len(node.handlers)}"
    if isinstance(node, pyast.With):
        items = ", ".join(_short(it.context_expr) for it in node.items)
        return f"{cls}  items=({items})"
    if isinstance(node, pyast.Return):
        return f"{cls}  value={_short(node.value) if node.value else 'None'}"
    if isinstance(node, pyast.Assign):
        targets = ", ".join(_short(t) for t in node.targets)
        return f"{cls}  {targets} = {_short(node.value)}"
    if isinstance(node, pyast.AugAssign):
        return f"{cls}  {_short(node.target)} {_op(node.op)}= {_short(node.value)}"
    if isinstance(node, pyast.Expr):
        return f"{cls}  {_short(node.value)}"
    if isinstance(node, pyast.Call):
        func = _short(node.func)
        n_args = len(node.args)
        return f"{cls}  {func}(…{n_args})"
    if isinstance(node, pyast.Raise):
        return f"{cls}  {_short(node.exc) if node.exc else ''}"
    if isinstance(node, pyast.Import):
        return f"{cls}  {', '.join(a.name for a in node.names)}"
    if isinstance(node, pyast.ImportFrom):
        return f"{cls}  from {node.module}  {', '.join(a.name for a in node.names)}"
    if isinstance(node, pyast.Pass | pyast.Break | pyast.Continue):
        return cls
    return cls


def _short(node: pyast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, pyast.Name):
        return node.id
    if isinstance(node, pyast.Constant):
        v = node.value
        if isinstance(v, str):
            short = v if len(v) < 24 else v[:24] + "…"
            return f"{short!r}"
        return repr(v)
    if isinstance(node, pyast.Attribute):
        return f"{_short(node.value)}.{node.attr}"
    if isinstance(node, pyast.Subscript):
        return f"{_short(node.value)}[{_short(node.slice)}]"
    if isinstance(node, pyast.Call):
        return f"{_short(node.func)}(…)"
    if isinstance(node, pyast.BinOp):
        return f"{_short(node.left)} {_op(node.op)} {_short(node.right)}"
    if isinstance(node, pyast.Compare):
        ops = " ".join(_op(op) for op in node.ops)
        comparators = " ".join(_short(c) for c in node.comparators)
        return f"{_short(node.left)} {ops} {comparators}"
    return type(node).__name__


def _op(op: pyast.AST) -> str:
    return {
        "Add": "+", "Sub": "-", "Mult": "*", "Div": "/",
        "Mod": "%", "Pow": "**", "FloorDiv": "//",
        "Eq": "==", "NotEq": "!=", "Lt": "<", "LtE": "<=",
        "Gt": ">", "GtE": ">=", "And": "and", "Or": "or",
    }.get(type(op).__name__, type(op).__name__)


def _walk(
    node: pyast.AST,
    prefix: str,
    is_last: bool,
    depth: int,
    max_depth: int,
    out: list[str],
) -> None:
    if not isinstance(node, _INTERESTING) and depth > 0:
        return

    branch = "└─ " if is_last else "├─ "
    out.append(f"{prefix}{branch}{_summary(node)}")

    if depth >= max_depth:
        return

    ext = "   " if is_last else "│  "
    children = [c for c in pyast.iter_child_nodes(node) if isinstance(c, _INTERESTING)]
    for i, child in enumerate(children):
        _walk(
            child,
            prefix=prefix + ext,
            is_last=(i == len(children) - 1),
            depth=depth + 1,
            max_depth=max_depth,
            out=out,
        )
