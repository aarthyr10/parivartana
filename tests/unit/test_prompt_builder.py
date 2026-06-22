from __future__ import annotations

from src.pipeline.stage1_parser.ast_nodes import (
    DataItemNode,
    DivisionNode,
    ParagraphNode,
    ProgramNode,
    SectionNode,
    StatementNode,
)
from src.pipeline.stage1_parser.complexity import ComplexityTier
from src.pipeline.stage2_neural.prompt_builder import SPECIAL_TOKENS, PromptBuilder


def _rich_ast() -> ProgramNode:
    prog = ProgramNode(node_type="Program", attributes={"program_id": "RICH"})

    data_div = DivisionNode(node_type="Division", attributes={"name": "DIVISION"})
    section = SectionNode(node_type="Section", attributes={"name": "WORKING-STORAGE"})
    item = DataItemNode(
        node_type="DataItem",
        attributes={"level": 1, "name": "WS-X", "pic": "9", "value": "0"},
    )
    section.add(item)
    data_div.add(section)
    prog.add(data_div)

    proc_div = DivisionNode(node_type="Division", attributes={"name": "DIVISION"})
    para = ParagraphNode(node_type="Paragraph", attributes={"name": "MAIN-PARA"})
    stmt = StatementNode(node_type="Statement", attributes={"verb": "DISPLAY", "operands": ['"HI"']})
    para.add(stmt)
    proc_div.add(para)
    prog.add(proc_div)

    return prog


def _minimal_ast() -> ProgramNode:
    prog = ProgramNode(node_type="Program", attributes={"program_id": "HELLO"})
    div = DivisionNode(node_type="Division", attributes={"name": "DIVISION"})
    para = ParagraphNode(node_type="Paragraph", attributes={"name": "MAIN"})
    stmt = StatementNode(node_type="Statement", attributes={"verb": "DISPLAY", "operands": ['"HI"']})
    para.add(stmt)
    div.add(para)
    prog.add(div)
    return prog


def test_emits_every_structural_token():
    builder = PromptBuilder()
    prompt = builder.build(_rich_ast(), ComplexityTier.SIMPLE)
    for tok in SPECIAL_TOKENS:
        assert tok in prompt.text, f"missing {tok}"


def test_tier_tag_is_present_and_first():
    builder = PromptBuilder()
    prompt = builder.build(_minimal_ast(), ComplexityTier.MEDIUM)
    assert prompt.tier_tag == "<tier=medium>"
    assert prompt.text.startswith("<tier=medium>")


def test_truncation_respects_max_tokens():
    builder = PromptBuilder(max_tokens=5)
    prompt = builder.build(_minimal_ast(), ComplexityTier.SIMPLE)
    assert prompt.token_count == 5


def test_closing_tags_match_opening():
    builder = PromptBuilder()
    prompt = builder.build(_minimal_ast(), ComplexityTier.SIMPLE)
    assert "[/DIV]" in prompt.text
    assert "[/PARA]" in prompt.text
    assert "[/STMT]" in prompt.text
