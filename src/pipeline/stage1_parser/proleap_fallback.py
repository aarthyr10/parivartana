
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


_JVM_STARTED = False
_JVM_START_LOCK = threading.Lock()
_PROLEAP_PARSER = None                               

                                                             
_DEFAULT_JAR_REL = Path("artifacts/jars/proleap-cobol-parser.jar")


@dataclass
class ProleapStatus:
    available: bool
    reason: str = ""
    jar_path: str = ""


def status(jar_path: Path | str | None = None) -> ProleapStatus:
    try:
        import jpype              
    except ImportError:
        return ProleapStatus(
            available=False,
            reason="jpype1 not installed (pip install jpype1)",
        )

    jar = _resolve_jar(jar_path)
    if not jar or not jar.exists():
        return ProleapStatus(
            available=False,
            reason=f"ProLeap jar not found at {jar}",
            jar_path=str(jar) if jar else "",
        )
    return ProleapStatus(available=True, jar_path=str(jar))


def _resolve_jar(explicit: Path | str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.getenv("PARIVARTANA_PROLEAP_JAR")
    if env:
        return Path(env).expanduser().resolve()
                                                                     
    from src.utils.paths import ARTIFACTS_DIR                             

    return (ARTIFACTS_DIR / "jars" / "proleap-cobol-parser.jar").resolve()


def _ensure_jvm(jar_path: Path) -> None:
    global _JVM_STARTED
    if _JVM_STARTED:
        return
    with _JVM_START_LOCK:
        if _JVM_STARTED:
            return
        try:
            import jpype
        except ImportError as exc:
            raise RuntimeError("jpype1 is required for ProLeap fallback") from exc
        if not jpype.isJVMStarted():
            jpype.startJVM(classpath=[str(jar_path)], convertStrings=True)
        _JVM_STARTED = True


@dataclass
class ProleapParseResult:
    ok: bool
    paragraph_count: int = 0
    paragraph_names: list[str] = None                            
    raw_ast_dump: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if self.paragraph_names is None:
            self.paragraph_names = []


def parse_via_proleap(
    cobol_source: str,
    jar_path: Path | str | None = None,
    *,
    format: str = "FIXED",                                   
) -> ProleapParseResult:
    st = status(jar_path)
    if not st.available:
        return ProleapParseResult(ok=False, error=st.reason)

    try:
        _ensure_jvm(Path(st.jar_path))
        import jpype
        import jpype.imports                                            

                                                                   
        from io.proleap.cobol.asg.params import CobolParserParams                                  
        from io.proleap.cobol.asg.runner.impl import (                                  
            CobolParserRunnerImpl,
        )
        from io.proleap.cobol.preprocessor import CobolPreprocessor                                  
    except Exception as exc:                
        return ProleapParseResult(ok=False, error=f"JVM/ProLeap setup failed: {exc}")

    try:
        params = CobolParserParams()
                                                   
        from io.proleap.cobol.preprocessor import CobolPreprocessor as _CP                                  

        fmt_map = {
            "FIXED": _CP.CobolSourceFormatEnum.FIXED,
            "TANDEM": _CP.CobolSourceFormatEnum.TANDEM,
            "VARIABLE": _CP.CobolSourceFormatEnum.VARIABLE,
        }
        params.setFormat(fmt_map.get(format.upper(), _CP.CobolSourceFormatEnum.FIXED))

        runner = CobolParserRunnerImpl()
        program = runner.analyzeCode(cobol_source, "in-memory", params)

                                                              
        paragraph_names: list[str] = []
        for unit in program.getCompilationUnits():
            for prog_unit in unit.getProgramUnits():
                pdu = prog_unit.getProcedureDivision()
                if pdu is None:
                    continue
                for para in pdu.getParagraphs():
                    name = str(para.getName())
                    if name:
                        paragraph_names.append(name.upper())
        return ProleapParseResult(
            ok=True,
            paragraph_count=len(paragraph_names),
            paragraph_names=paragraph_names,
            raw_ast_dump="",                                        
        )
    except Exception as exc:                
        return ProleapParseResult(ok=False, error=f"ProLeap parse failed: {exc}")


def coverage_vs_ours(cobol_source: str, our_ast) -> dict[str, Any]:
    from src.pipeline.stage1_parser.ast_nodes import ParagraphNode         

    our_names: set[str] = set()
    if our_ast is not None:
        for node in our_ast.walk():
            if isinstance(node, ParagraphNode) and node.attributes.get("name"):
                our_names.add(node.attributes["name"].upper())

    result = parse_via_proleap(cobol_source)
    if not result.ok:
        return {
            "proleap_available": False,
            "reason": result.error,
            "our_paragraph_count": len(our_names),
        }
    proleap_names = set(result.paragraph_names)
    return {
        "proleap_available": True,
        "our_paragraph_count": len(our_names),
        "proleap_paragraph_count": len(proleap_names),
        "missed_by_us": sorted(proleap_names - our_names)[:20],
        "missed_by_proleap": sorted(our_names - proleap_names)[:20],
    }
