
from __future__ import annotations

from dataclasses import dataclass

from src.pipeline.stage1_parser.ast_nodes import (
    AstNode,
    DataItemNode,
    DivisionNode,
    ParagraphNode,
    ProgramNode,
    SectionNode,
    StatementNode,
)
from src.pipeline.stage1_parser.complexity import ComplexityTier

SPECIAL_TOKENS: tuple[str, ...] = ("[DIV]", "[SEC]", "[PARA]", "[STMT]", "[EXPR]")

                                                                      
_NODE_TOKEN: dict[type, str] = {
    DivisionNode: "[DIV]",
    SectionNode: "[SEC]",
    ParagraphNode: "[PARA]",
    StatementNode: "[STMT]",
    DataItemNode: "[EXPR]",
}


@dataclass
class BuiltPrompt:

    text: str
    tier_tag: str
    token_count: int


class PromptBuilder:

    def __init__(
        self,
        max_tokens: int = 1024,
        tier_tag_prefix: str = "<tier=",
    ) -> None:
        self.max_tokens = max_tokens
        self.tier_tag_prefix = tier_tag_prefix

    def build(self, ast: AstNode, tier: ComplexityTier) -> BuiltPrompt:
        body = self._linearise(ast)
        tier_tag = f"{self.tier_tag_prefix}{tier.value}>"
        full = f"{tier_tag} {body}".strip()
        tokens = full.split()
        if len(tokens) > self.max_tokens:
                                                                      
            tokens = tokens[: self.max_tokens]
            full = " ".join(tokens)
        return BuiltPrompt(text=full, tier_tag=tier_tag, token_count=len(tokens))

    def _linearise(self, node: AstNode) -> str:
        out: list[str] = []
        self._walk(node, out)
        return " ".join(out)

    def _walk(self, node: AstNode, out: list[str]) -> None:
        tag = _NODE_TOKEN.get(type(node), "[STMT]")
        out.append(tag)
        if isinstance(node, ProgramNode):
            pid = node.attributes.get("program_id")
            if pid:
                out.append(f"name={pid}")
        elif isinstance(node, DivisionNode | SectionNode | ParagraphNode):
            name = node.attributes.get("name")
            if name:
                out.append(f"name={name}")
        elif isinstance(node, StatementNode):
            verb = node.attributes.get("verb", "")
            out.append(f"verb={verb}")
            operands = node.attributes.get("operands") or []
            for op in operands:
                out.append(f"op={op}")
        elif isinstance(node, DataItemNode):
            attrs = node.attributes
            if "name" in attrs:
                out.append(f"name={attrs['name']}")
            if "level" in attrs:
                out.append(f"level={attrs['level']}")
            if "pic" in attrs:
                out.append(f"pic={attrs['pic']}")
            if "value" in attrs:
                out.append(f"value={attrs['value']}")

        for child in node.children:
            self._walk(child, out)

                                                                         
        out.append(tag.replace("[", "[/"))
