from __future__ import annotations

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
from src.pipeline.stage1_parser.fixed_format import FixedFormatPreprocessor
from src.pipeline.stage1_parser.lexer import CobolLexer, Token, TokenType
from src.utils.logging import get_logger

log = get_logger(__name__)


_ID_METADATA_KEYWORDS = frozenset(
    {
        "AUTHOR",
        "DATE-WRITTEN",
        "DATE-COMPILED",
        "INSTALLATION",
        "SECURITY",
        "REMARKS",
    }
)


@dataclass
class ParseError:
    line: int
    column: int
    message: str


@dataclass
class ParseResult:
    ast: ProgramNode | None
    tokens: list[Token]
    errors: list[ParseError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    program_id: str = ""
    division_count: int = 0
    paragraph_count: int = 0

    @property
    def ok(self) -> bool:
        return self.ast is not None and not self.errors


class CobolParser:
    def __init__(self) -> None:
        self.preprocessor = FixedFormatPreprocessor()
        self.lexer = CobolLexer()
        self._tokens: list[Token] = []
        self._pos: int = 0
        self._errors: list[ParseError] = []
        self._warnings: list[str] = []
        self._current_division_kind: str = ""

    def parse(self, source: str) -> ParseResult:
        self._errors = []
        self._warnings = []
        self._current_division_kind = ""
        try:
            lines = self.preprocessor.preprocess(source)
            code = self.preprocessor.join_code(lines)
            tokens = self.lexer.tokenise(code)
        except Exception as exc:
            log.error(f"Lexer crashed: {type(exc).__name__}: {exc}")
            self._errors.append(ParseError(0, 0, f"lexer crashed: {type(exc).__name__}: {exc}"))
            return ParseResult(ast=None, tokens=[], errors=self._errors, warnings=self._warnings)
        self._tokens = tokens
        self._pos = 0

        try:
            program = self._parse_program()
        except _ParseAbort as exc:
            log.error(f"Parser aborted: {exc}")
            return ParseResult(ast=None, tokens=tokens, errors=self._errors, warnings=self._warnings)
        except Exception as exc:
            log.error(f"Parser crashed: {type(exc).__name__}: {exc}")
            self._errors.append(ParseError(0, 0, f"parser crashed: {type(exc).__name__}: {exc}"))
            return ParseResult(ast=None, tokens=tokens, errors=self._errors, warnings=self._warnings)

        return ParseResult(
            ast=program,
            tokens=tokens,
            errors=self._errors,
            warnings=self._warnings,
            program_id=program.attributes.get("program_id", ""),
            division_count=sum(1 for n in program.walk() if isinstance(n, DivisionNode)),
            paragraph_count=sum(1 for n in program.walk() if isinstance(n, ParagraphNode)),
        )

    def _peek(self, offset: int = 0) -> Token:
        idx = self._pos + offset
        if idx >= len(self._tokens):
            return self._tokens[-1]
        return self._tokens[idx]

    def _consume(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, type_: TokenType, value: str | None = None) -> Token:
        tok = self._peek()
        if tok.type != type_ or (value is not None and tok.value.upper() != value.upper()):
            self._error(tok, f"expected {type_.value} '{value or ''}', got {tok.type.value} '{tok.value}'")
            raise _ParseAbort(f"expected {type_.value} at line {tok.line}")
        return self._consume()

    def _accept(self, type_: TokenType, value: str | None = None) -> Token | None:
        tok = self._peek()
        if tok.type == type_ and (value is None or tok.value.upper() == value.upper()):
            return self._consume()
        return None

    def _error(self, tok: Token, message: str) -> None:
        self._errors.append(ParseError(tok.line, tok.column, message))

    def _at_eof(self) -> bool:
        return self._peek().type == TokenType.EOF

    def _parse_program(self) -> ProgramNode:
        program = ProgramNode(node_type="Program", line=1)
        while not self._at_eof():
            tok = self._peek()
            if tok.type == TokenType.DIVISION_HEADER:
                self._current_division_kind = self._prev_division_kind()
                program.add(self._parse_division(program))
            else:
                self._consume()
        return program

    def _prev_division_kind(self) -> str:
        idx = self._pos - 1
        while idx >= 0:
            t = self._tokens[idx]
            if t.type == TokenType.KEYWORD and t.value in {
                "PROCEDURE", "DATA", "IDENTIFICATION", "ENVIRONMENT", "LINKAGE",
            }:
                return t.value
            if t.type in {TokenType.DIVISION_HEADER, TokenType.PERIOD}:
                if t.type == TokenType.PERIOD:
                    idx -= 1
                    continue
                break
            idx -= 1
        return ""

    def _parse_division(self, program: ProgramNode) -> DivisionNode:
        header = self._consume()
        division = DivisionNode(
            node_type="Division",
            line=header.line,
            attributes={"name": header.value, "kind": self._current_division_kind},
        )
        self._accept(TokenType.PERIOD)

        while not self._at_eof() and self._peek().type != TokenType.DIVISION_HEADER:
            tok = self._peek()
            if tok.type == TokenType.SECTION_HEADER:
                division.add(self._parse_section())
            elif tok.type == TokenType.KEYWORD and tok.value == "PROGRAM-ID":
                self._parse_program_id(program)
            elif tok.type == TokenType.KEYWORD and tok.value in _ID_METADATA_KEYWORDS:
                                                                        
                                                                        
                self._parse_id_metadata(program, tok.value)
            elif tok.type == TokenType.LEVEL_NUMBER:
                division.add(self._parse_data_item())
            elif tok.type == TokenType.IDENTIFIER and self._looks_like_paragraph(tok):
                division.add(self._parse_paragraph())
            elif tok.type == TokenType.VERB:
                paragraph = ParagraphNode(node_type="Paragraph", line=tok.line, attributes={"name": "MAIN"})
                self._collect_statements(paragraph)
                division.add(paragraph)
            else:
                self._consume()

        return division

    def _parse_section(self) -> SectionNode:
        header = self._consume()
        self._accept(TokenType.PERIOD)
        section = SectionNode(
            node_type="Section",
            line=header.line,
            attributes={"name": header.value},
        )
        while not self._at_eof():
            tok = self._peek()
            if tok.type in {TokenType.DIVISION_HEADER, TokenType.SECTION_HEADER}:
                break
            if tok.type == TokenType.LEVEL_NUMBER:
                section.add(self._parse_data_item())
            elif tok.type == TokenType.IDENTIFIER and self._looks_like_paragraph(tok):
                section.add(self._parse_paragraph())
            else:
                self._consume()
        return section

    def _parse_program_id(self, program: ProgramNode) -> None:
        self._consume()
        self._accept(TokenType.OPERATOR, ".")
        if self._peek().type == TokenType.PERIOD:
            self._consume()
        name_tok = self._peek()
        if name_tok.type in {TokenType.IDENTIFIER, TokenType.LITERAL_STR}:
            program.attributes["program_id"] = name_tok.value
            self._consume()
        self._accept(TokenType.PERIOD)

    def _parse_id_metadata(self, program: ProgramNode, keyword: str) -> None:
        self._consume()                            
        self._accept(TokenType.PERIOD)
        parts: list[str] = []
        while not self._at_eof():
            tok = self._peek()
            if tok.type == TokenType.PERIOD:
                self._consume()
                next_tok = self._peek()
                if next_tok.type in {TokenType.DIVISION_HEADER, TokenType.SECTION_HEADER}:
                    break
                if next_tok.type == TokenType.KEYWORD and (
                    next_tok.value == "PROGRAM-ID" or next_tok.value in _ID_METADATA_KEYWORDS
                ):
                    break
                if next_tok.type == TokenType.LEVEL_NUMBER:
                    break
                if next_tok.type == TokenType.EOF:
                    break
                continue
            if tok.type in {TokenType.DIVISION_HEADER, TokenType.SECTION_HEADER}:
                break
            if tok.type == TokenType.KEYWORD and (
                tok.value == "PROGRAM-ID" or tok.value in _ID_METADATA_KEYWORDS
            ):
                break
            if tok.type in {
                TokenType.IDENTIFIER,
                TokenType.LITERAL_STR,
                TokenType.LITERAL_NUM,
                TokenType.KEYWORD,
            }:
                parts.append(tok.value)
            self._consume()
        meta = program.attributes.setdefault("metadata", {})
        meta[keyword.lower()] = " ".join(parts).strip()

    def _parse_data_item(self) -> DataItemNode:
        level_tok = self._consume()
        attrs: dict = {"level": int(level_tok.value)}
        if self._peek().type == TokenType.IDENTIFIER:
            attrs["name"] = self._consume().value

        while not self._at_eof() and self._peek().type != TokenType.PERIOD:
            tok = self._peek()
            if tok.type == TokenType.KEYWORD and tok.value in {"PIC", "PICTURE"}:
                self._consume()
                pic_tok = self._peek()
                if pic_tok.type in {TokenType.PIC_CLAUSE, TokenType.IDENTIFIER, TokenType.LITERAL_NUM}:
                    attrs["pic"] = pic_tok.value
                    self._consume()
            elif tok.type == TokenType.KEYWORD and tok.value in {"VALUE", "VALUES"}:
                self._consume()
                while (
                    self._peek().type == TokenType.KEYWORD
                    and self._peek().value in {"IS", "ARE"}
                ):
                    self._consume()
                val_tok = self._peek()
                if val_tok.type in {TokenType.LITERAL_NUM, TokenType.LITERAL_STR, TokenType.KEYWORD}:
                    if val_tok.type == TokenType.LITERAL_STR:
                        attrs["value"] = f'"{val_tok.value}"'
                    else:
                        attrs["value"] = val_tok.value
                    self._consume()
            elif tok.type == TokenType.KEYWORD and tok.value == "USAGE":
                self._consume()
                usage_tok = self._peek()
                if usage_tok.type in {TokenType.IDENTIFIER, TokenType.KEYWORD}:
                    attrs["usage"] = usage_tok.value
                    self._consume()
            else:
                self._consume()

        self._accept(TokenType.PERIOD)
        return DataItemNode(node_type="DataItem", line=level_tok.line, attributes=attrs)

    def _looks_like_paragraph(self, tok: Token) -> bool:
        next_tok = self._peek(1)
        if next_tok.type != TokenType.PERIOD:
            return False
        if self._current_division_kind and self._current_division_kind != "PROCEDURE":
            return False
        return True

    def _parse_paragraph(self) -> ParagraphNode:
        name_tok = self._consume()
        self._accept(TokenType.PERIOD)
        paragraph = ParagraphNode(
            node_type="Paragraph",
            line=name_tok.line,
            attributes={"name": name_tok.value},
        )
        self._collect_statements(paragraph)
        return paragraph

    def _collect_statements(self, paragraph: ParagraphNode) -> None:
        while not self._at_eof():
            tok = self._peek()
            if tok.type == TokenType.DIVISION_HEADER or tok.type == TokenType.SECTION_HEADER:
                break
            if tok.type == TokenType.IDENTIFIER and self._looks_like_paragraph(tok):
                break
            if tok.type == TokenType.VERB:
                paragraph.add(self._parse_statement())
            elif tok.type == TokenType.PERIOD:
                self._consume()
            else:
                self._consume()

    def _parse_statement(self) -> StatementNode:
        verb_tok = self._consume()
        operands: list[str] = []
        while not self._at_eof():
            tok = self._peek()
            if tok.type == TokenType.PERIOD:
                self._consume()
                break
            if tok.type == TokenType.VERB:
                break
            if tok.type == TokenType.LITERAL_STR:
                                                                       
                                                                   
                operands.append(f'"{tok.value}"')
            elif tok.type in {
                TokenType.IDENTIFIER,
                TokenType.LITERAL_NUM,
                TokenType.KEYWORD,
                TokenType.OPERATOR,
            }:
                operands.append(tok.value)
            elif tok.type == TokenType.LPAREN:
                operands.append("(")
            elif tok.type == TokenType.RPAREN:
                operands.append(")")
            self._consume()

        return StatementNode(
            node_type="Statement",
            line=verb_tok.line,
            attributes={"verb": verb_tok.value, "operands": operands},
        )


class _ParseAbort(Exception):
    pass
