from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AstNode:
    node_type: str
    line: int = 0
    children: list["AstNode"] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def add(self, child: "AstNode") -> "AstNode":
        self.children.append(child)
        return child

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_type": self.node_type,
            "line": self.line,
            "attributes": self.attributes,
            "children": [c.to_dict() for c in self.children],
        }

    def depth(self) -> int:
        if not self.children:
            return 1
        return 1 + max(c.depth() for c in self.children)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass
class ProgramNode(AstNode):
    pass


@dataclass
class DivisionNode(AstNode):
    pass


@dataclass
class SectionNode(AstNode):
    pass


@dataclass
class ParagraphNode(AstNode):
    pass


@dataclass
class StatementNode(AstNode):
    pass


@dataclass
class DataItemNode(AstNode):
    pass


def linearise_prefix(node: AstNode) -> list[str]:
    tokens: list[str] = []
    _linearise(node, tokens)
    return tokens


def _linearise(node: AstNode, out: list[str]) -> None:
    out.append(f"[{node.node_type}]")
    if "verb" in node.attributes:
        out.append(node.attributes["verb"])
    if "name" in node.attributes:
        out.append(node.attributes["name"])
    if "value" in node.attributes:
        out.append(str(node.attributes["value"]))
    for child in node.children:
        _linearise(child, out)
    out.append(f"[/{node.node_type}]")
