from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass
class PreprocessedLine:
    line_number: int
    sequence_area: str
    indicator: str
    area_a: str
    area_b: str
    is_comment: bool
    is_continuation: bool
    code: str


class FixedFormatPreprocessor:
    SEQUENCE_END = 6
    INDICATOR_COL = 6
    AREA_A_END = 11
    AREA_B_END = 72

    COMMENT_INDICATORS = {"*", "/"}
    CONTINUATION_INDICATOR = "-"
    DEBUG_INDICATOR = "D"

    def __init__(self, source_encoding: str = "utf-8", normalise: bool = True) -> None:
        self.source_encoding = source_encoding
        self.normalise = normalise

    def decode(self, raw_bytes: bytes) -> str:
        return raw_bytes.decode(self.source_encoding, errors="replace")

    def normalise_text(self, text: str) -> str:
        if not self.normalise:
            return text
        return unicodedata.normalize("NFKC", text)

    def preprocess(self, text: str) -> list[PreprocessedLine]:
        text = self.normalise_text(text)
        lines = text.splitlines()
        preprocessed: list[PreprocessedLine] = []

        for idx, line in enumerate(lines, start=1):
            padded = line.ljust(self.AREA_B_END)

            sequence_area = padded[: self.SEQUENCE_END]
            indicator = padded[self.INDICATOR_COL] if len(padded) > self.INDICATOR_COL else " "
            area_a = padded[self.SEQUENCE_END + 1 : self.AREA_A_END]
            area_b = padded[self.AREA_A_END : self.AREA_B_END]

            is_comment = indicator in self.COMMENT_INDICATORS
            is_continuation = indicator == self.CONTINUATION_INDICATOR

            code = "" if is_comment else (area_a + area_b).rstrip()

            preprocessed.append(
                PreprocessedLine(
                    line_number=idx,
                    sequence_area=sequence_area,
                    indicator=indicator,
                    area_a=area_a.rstrip(),
                    area_b=area_b.rstrip(),
                    is_comment=is_comment,
                    is_continuation=is_continuation,
                    code=code,
                )
            )

        return preprocessed

    def join_code(self, lines: list[PreprocessedLine]) -> str:
        return "\n".join(line.code for line in lines if not line.is_comment)
