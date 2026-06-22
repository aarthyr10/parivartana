
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.pipeline.stage1_parser.normaliser import parse_pic as _regex_parse_pic


@dataclass
class PicDecoding:
    type: str                                                         
    default_literal: str
    scale: int = 0
    signed: bool = False
    length: int = 0
    usage: str = "DISPLAY"
    backend: str = "regex"                                              


def _try_stingray(picture: str) -> PicDecoding | None:
    try:
                                                                    
                                                                 
        from stingray import cobol_parser as _cp                                  
    except Exception:                
        try:
            from stingray.cobol import parser as _cp                                  
        except Exception:                
            return None

    parse_fn = getattr(_cp, "pic_parser", None) or getattr(_cp, "parse_picture", None)
    if parse_fn is None:
        return None

    try:
        node = parse_fn(picture)
    except Exception:                
        return None

                                                                       
    is_numeric = bool(getattr(node, "numeric", False))
    is_signed = bool(getattr(node, "sign", False))
    integer_digits = int(getattr(node, "digits", 0) or 0)
    fractional_digits = int(getattr(node, "decimals", 0) or 0)
    char_length = int(getattr(node, "size", 0) or 0)
    usage = str(getattr(node, "usage", "DISPLAY")).upper()

    return _build_decoding(
        is_numeric=is_numeric,
        is_signed=is_signed,
        integer_digits=integer_digits,
        fractional_digits=fractional_digits,
        char_length=char_length,
        usage=usage,
        backend="stingray",
    )


def _via_regex(picture: str) -> PicDecoding | None:
    info = _regex_parse_pic(picture)
    if info is None:
        return None
    return _build_decoding(
        is_numeric=info.is_numeric,
        is_signed=info.is_signed,
        integer_digits=info.integer_digits,
        fractional_digits=info.fractional_digits,
        char_length=info.char_length,
        usage=info.usage,
        backend="regex",
    )


def _build_decoding(
    *,
    is_numeric: bool,
    is_signed: bool,
    integer_digits: int,
    fractional_digits: int,
    char_length: int,
    usage: str,
    backend: str,
) -> PicDecoding:
    if not is_numeric:
                                                                      
        n = max(char_length, 1)
        return PicDecoding(
            type="str",
            default_literal=f'" " * {n}' if n > 1 else '" "',
            scale=0,
            signed=False,
            length=n,
            usage=usage,
            backend=backend,
        )

                                                               
    if fractional_digits > 0:
        zeros = "0" * fractional_digits
        return PicDecoding(
            type="Decimal",
            default_literal=f'Decimal("0.{zeros}")',
            scale=fractional_digits,
            signed=is_signed,
            length=integer_digits + fractional_digits,
            usage=usage,
            backend=backend,
        )
    if usage in {"COMP-3", "PACKED-DECIMAL"}:
        return PicDecoding(
            type="Decimal",
            default_literal='Decimal("0")',
            scale=0,
            signed=is_signed,
            length=integer_digits,
            usage=usage,
            backend=backend,
        )
    return PicDecoding(
        type="int",
        default_literal="0",
        scale=0,
        signed=is_signed,
        length=integer_digits,
        usage=usage,
        backend=backend,
    )


def decode_pic(picture: str) -> PicDecoding | None:
    via_stingray = _try_stingray(picture)
    if via_stingray is not None:
        return via_stingray
    return _via_regex(picture)


def needed_imports_for(decodings: list[PicDecoding]) -> set[str]:
    imports: set[str] = set()
    for d in decodings:
        if d.type == "Decimal":
            imports.add("decimal.Decimal")
    return imports
