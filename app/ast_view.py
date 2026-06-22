
from __future__ import annotations

from src.pipeline.stage1_parser.ast_nodes import (
    AstNode,
    DataItemNode,
    DivisionNode,
    ParagraphNode,
    ProgramNode,
    SectionNode,
    StatementNode,
)


def _summary(node: AstNode) -> str:
    attrs = node.attributes or {}
    label = type(node).__name__.replace("Node", "")

    if isinstance(node, ProgramNode):
        pid = attrs.get("program_id")
        return f"{label}  id={pid}" if pid else label

    if isinstance(node, DivisionNode | SectionNode | ParagraphNode):
        name = attrs.get("name") or "(unnamed)"
        return f"{label}  name={name}"

    if isinstance(node, StatementNode):
        verb = attrs.get("verb") or "?"
        ops = attrs.get("operands") or []
        ops_str = ", ".join(str(o) for o in ops[:6])
        if len(ops) > 6:
            ops_str += ", …"
        return f"{label}  verb={verb}  ops=({ops_str})"

    if isinstance(node, DataItemNode):
        bits = []
        if "level" in attrs:
            bits.append(f"lvl={attrs['level']}")
        if "name" in attrs:
            bits.append(f"name={attrs['name']}")
        if "pic" in attrs:
            bits.append(f"pic={attrs['pic']}")
        if "value" in attrs:
            bits.append(f"value={attrs['value']}")
        return f"{label}  " + "  ".join(bits)

    return label


def ast_tree_lines(node: AstNode, max_depth: int = 6) -> list[str]:
    lines: list[str] = []
    _walk(node, prefix="", is_last=True, depth=0, max_depth=max_depth, out=lines)
    return lines


def _walk(
    node: AstNode,
    prefix: str,
    is_last: bool,
    depth: int,
    max_depth: int,
    out: list[str],
) -> None:
    branch = "└─ " if is_last else "├─ "
    out.append(f"{prefix}{branch}{_summary(node)}")

    if depth >= max_depth:
        if node.children:
            ext = "   " if is_last else "│  "
            out.append(f"{prefix}{ext}└─ … ({len(node.children)} more)")
        return

    ext = "   " if is_last else "│  "
    children = list(node.children)
    for i, child in enumerate(children):
        _walk(
            child,
            prefix=prefix + ext,
            is_last=(i == len(children) - 1),
            depth=depth + 1,
            max_depth=max_depth,
            out=out,
        )


def render_ast_tree(node: AstNode, max_depth: int = 6) -> str:
    return "\n".join(ast_tree_lines(node, max_depth=max_depth))
