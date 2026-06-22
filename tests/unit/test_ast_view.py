from __future__ import annotations

from app.ast_view import ast_tree_lines, render_ast_tree
from src.pipeline.stage1_parser.ast_nodes import (
    DivisionNode,
    ParagraphNode,
    ProgramNode,
    StatementNode,
)


def _tiny_ast() -> ProgramNode:
    prog = ProgramNode(node_type="Program", attributes={"program_id": "HELLO"})
    div = DivisionNode(node_type="Division", attributes={"name": "DIVISION"})
    para = ParagraphNode(node_type="Paragraph", attributes={"name": "MAIN-PARA"})
    para.add(StatementNode(node_type="Statement", attributes={"verb": "DISPLAY", "operands": ['"HI"']}))
    para.add(StatementNode(node_type="Statement", attributes={"verb": "STOP", "operands": ["RUN"]}))
    div.add(para)
    prog.add(div)
    return prog


def test_tree_root_is_program():
    text = render_ast_tree(_tiny_ast())
    first = text.splitlines()[0]
    assert "Program" in first
    assert "id=HELLO" in first


def test_tree_uses_box_drawing_chars():
    text = render_ast_tree(_tiny_ast())
                                                            
    assert any(ch in text for ch in ("├", "└", "│"))


def test_tree_includes_every_node():
    lines = ast_tree_lines(_tiny_ast())
    joined = "\n".join(lines)
    assert "Program" in joined
    assert "Division" in joined
    assert "Paragraph" in joined
    assert "verb=DISPLAY" in joined
    assert "verb=STOP" in joined


def test_tree_truncates_at_max_depth():
                                                                   
    prog = ProgramNode(node_type="Program", attributes={"program_id": "DEEP"})
    cur = prog
    for i in range(8):
        child = StatementNode(node_type="Statement", attributes={"verb": f"V{i}", "operands": []})
        cur.add(child)
        cur = child

    text = render_ast_tree(prog, max_depth=3)
                                                                
    assert "…" in text or "more" in text
