from __future__ import annotations

from app.python_ast_view import parse_python_or_none, render_python_ast


GOOD = """\
def add(a, b):
    return a + b

def main():
    x = add(1, 2)
    if x > 0:
        print(x)

if __name__ == "__main__":
    main()
"""


def test_renders_module_and_functions():
    tree = render_python_ast(GOOD)
    assert "Module" in tree
    assert "FunctionDef" in tree
    assert "name=add" in tree
    assert "name=main" in tree


def test_renders_control_flow():
    tree = render_python_ast(GOOD)
    assert "If" in tree
    assert "Return" in tree


def test_uses_box_drawing_chars():
    tree = render_python_ast(GOOD)
    assert any(ch in tree for ch in ("├", "└", "│"))


def test_handles_invalid_source_gracefully():
    tree = render_python_ast("def main(:\n    pass")
    assert "SyntaxError" in tree
    assert "line" in tree.lower()


def test_parse_python_or_none_returns_none_on_invalid():
    assert parse_python_or_none("def x(:\n  pass") is None


def test_call_summary_includes_function_name():
    tree = render_python_ast("def f():\n    print('hi')\n")
    assert "Call" in tree
    assert "print" in tree


def test_assign_summary_shows_target_and_value():
    tree = render_python_ast("x = 1\n")
    assert "Assign" in tree
    assert "x = 1" in tree
