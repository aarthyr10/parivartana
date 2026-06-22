
from __future__ import annotations

import ast as pyast
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.evaluation.execution import ExecutionAccuracy, ExecutionResult
from src.evaluation.judge import JudgeScore, LlmJudge
from src.pipeline.stage1_parser.ast_nodes import (
    AstNode,
    DataItemNode,
    ParagraphNode,
)
from src.pipeline.stage3_llm.providers import get_provider
from src.utils.logging import get_logger

log = get_logger(__name__)


VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"
                                                               
                                                                  
VERDICT_STRUCTURAL_PASS = "STRUCTURAL_PASS"
HEADLINE_PASS_VERDICTS = {VERDICT_PASS, VERDICT_STRUCTURAL_PASS}


@dataclass
class CheckResult:

    name: str
    ran: bool
    passed: bool | None
    score: float | None = None                        
    detail: str = ""
    skipped_reason: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationReport:
    verdict: str                              
    checks: list[CheckResult]
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "summary": self.summary,
            "checks": [asdict(c) for c in self.checks],
        }

    def get(self, name: str) -> CheckResult | None:
        for c in self.checks:
            if c.name == name:
                return c
        return None


def _check_python_syntax(python_source: str) -> CheckResult:
    try:
        pyast.parse(python_source)
        return CheckResult(
            name="python_syntax_valid",
            ran=True,
            passed=True,
            score=1.0,
            detail="Python source parses cleanly.",
        )
    except SyntaxError as exc:
        return CheckResult(
            name="python_syntax_valid",
            ran=True,
            passed=False,
            score=0.0,
            detail=f"SyntaxError at line {exc.lineno}: {exc.msg}",
        )


def _snake(name: str) -> str:
    from src.pipeline.stage2_neural.rule_based import _snake as _translator_snake

    return _translator_snake(name)


def _check_paragraph_coverage(ast: AstNode | None, python_source: str) -> CheckResult:
    if ast is None:
        return CheckResult(
            name="paragraph_coverage",
            ran=False,
            passed=None,
            skipped_reason="No parsed AST supplied.",
        )
    paragraphs = [
        n.attributes.get("name", "")
        for n in ast.walk()
        if isinstance(n, ParagraphNode) and n.attributes.get("name")
    ]
    if not paragraphs:
        return CheckResult(
            name="paragraph_coverage",
            ran=True,
            passed=True,
            score=1.0,
            detail="COBOL program had no paragraphs to cover.",
        )

    missing: list[str] = []
    found: list[str] = []
    for raw in paragraphs:
        snake = _snake(raw)
                                                                          
        if re.search(rf"\bdef\s+{re.escape(snake)}\s*\(", python_source):
            found.append(raw)
        else:
            missing.append(raw)
    score = len(found) / len(paragraphs)
    return CheckResult(
        name="paragraph_coverage",
        ran=True,
        passed=score >= 0.9,
        score=round(score, 3),
        detail=(
            f"{len(found)}/{len(paragraphs)} paragraphs found as Python functions"
            + (f"; missing: {', '.join(missing[:5])}" if missing else "")
        ),
        extra={"found": found, "missing": missing, "total": len(paragraphs)},
    )


def _check_identifier_coverage(ast: AstNode | None, python_source: str) -> CheckResult:
    if ast is None:
        return CheckResult(
            name="identifier_coverage",
            ran=False,
            passed=None,
            skipped_reason="No parsed AST supplied.",
        )
    idents = [
        n.attributes.get("name", "")
        for n in ast.walk()
        if isinstance(n, DataItemNode) and n.attributes.get("name")
    ]
    if not idents:
        return CheckResult(
            name="identifier_coverage",
            ran=True,
            passed=True,
            score=1.0,
            detail="COBOL program had no data items to cover.",
        )

    found: list[str] = []
    missing: list[str] = []
    py_lower = python_source.lower()
    for raw in idents:
        snake = _snake(raw)
                                                                  
                                                 
        if snake and (snake in py_lower or raw.lower() in py_lower):
            found.append(raw)
        else:
            missing.append(raw)
    score = len(found) / len(idents) if idents else 1.0
    return CheckResult(
        name="identifier_coverage",
        ran=True,
        passed=score >= 0.8,
        score=round(score, 3),
        detail=(
            f"{len(found)}/{len(idents)} identifiers traced into the Python"
            + (f"; missing: {', '.join(missing[:5])}" if missing else "")
        ),
        extra={"found": found, "missing": missing, "total": len(idents)},
    )


def _check_body_non_trivial(ast: AstNode | None, python_source: str) -> CheckResult:
    if ast is None:
        return CheckResult(
            name="body_non_trivial",
            ran=False,
            passed=None,
            skipped_reason="No parsed AST supplied.",
        )

                                                                       
    para_stmt_counts: dict[str, int] = {}
    from src.pipeline.stage1_parser.ast_nodes import StatementNode                             

    for node in ast.walk():
        if isinstance(node, ParagraphNode) and node.attributes.get("name"):
            name = node.attributes["name"]
            stmts = [c for c in node.walk() if isinstance(c, StatementNode)]
            para_stmt_counts[name] = len(stmts)

    if not para_stmt_counts:
        return CheckResult(
            name="body_non_trivial",
            ran=True,
            passed=True,
            score=1.0,
            detail="No paragraphs to check.",
        )

                                                                     
    func_bodies: dict[str, str] = {}
    lines = python_source.splitlines()
    current_name: str | None = None
    current_indent = 0
    current_lines: list[str] = []
    def_re = re.compile(r"^(\s*)def\s+(\w+)\s*\(")
    for ln in lines:
        m = def_re.match(ln)
        if m:
            if current_name is not None:
                func_bodies[current_name] = "\n".join(current_lines)
            current_name = m.group(2)
            current_indent = len(m.group(1))
            current_lines = []
            continue
        if current_name is None:
            continue
                                                                      
        stripped = ln.rstrip()
        if stripped and len(ln) - len(ln.lstrip()) <= current_indent and not ln.startswith(" " * (current_indent + 1)):
                                                      
            func_bodies[current_name] = "\n".join(current_lines)
            current_name = None
            current_lines = []
            continue
        current_lines.append(ln)
    if current_name is not None:
        func_bodies[current_name] = "\n".join(current_lines)

    def _is_trivial(body: str) -> bool:
                                                                               
        sigificant: list[str] = []
        for raw in body.splitlines():
            s = raw.strip()
            if not s:
                continue
            if s.startswith("#"):
                continue
            if s in ("pass", "...", "return", "return None"):
                continue
            if s.startswith('"""') or s.startswith("'''"):
                                                                   
                continue
            sigificant.append(s)
        return len(sigificant) == 0

    trivial: list[str] = []
    exempt: list[str] = []
    non_trivial: list[str] = []
    eligible_total = 0

    for raw_name, stmt_count in para_stmt_counts.items():
                                                                   
        if stmt_count <= 1:
            exempt.append(raw_name)
            continue
        eligible_total += 1
        body = func_bodies.get(_snake(raw_name), "")
        if not body or _is_trivial(body):
            trivial.append(raw_name)
        else:
            non_trivial.append(raw_name)

    if eligible_total == 0:
        return CheckResult(
            name="body_non_trivial",
            ran=True,
            passed=True,
            score=1.0,
            detail=f"All {len(exempt)} paragraph(s) were <=1 statement; nothing to score.",
            extra={"exempt": exempt},
        )

    score = len(non_trivial) / eligible_total
    return CheckResult(
        name="body_non_trivial",
        ran=True,
        passed=score >= 0.9,
        score=round(score, 3),
        detail=(
            f"{len(non_trivial)}/{eligible_total} paragraphs have non-trivial bodies"
            + (f"; stubbed: {', '.join(trivial[:5])}" if trivial else "")
            + (f" (+{len(trivial) - 5} more)" if len(trivial) > 5 else "")
        ),
        extra={
            "non_trivial": non_trivial,
            "trivial": trivial,
            "exempt": exempt,
            "total_eligible": eligible_total,
        },
    )


def _check_python_smoke(
    python_source: str,
    *,
    timeout_seconds: int = 5,
    python_runtime: str = "python3",
    ast: AstNode | None = None,
) -> CheckResult:
                                                                
                                                                   
    needs_env, env_reason = _program_needs_runtime_env(ast)
    if needs_env:
        return CheckResult(
            name="python_smoke",
            ran=False,
            passed=None,
            skipped_reason=env_reason,
            detail=f"skipped: {env_reason}",
        )

    import subprocess as _sp                                               
    import tempfile as _tf

                                                                        
    scratch = _tf.mkdtemp(prefix="smoke_")
    src_path = str(Path(scratch) / "translated.py")
    with open(src_path, "w", encoding="utf-8") as fh:
        fh.write(python_source)
    try:
        try:
            result = _sp.run(
                [python_runtime, src_path],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                cwd=scratch,
                stdin=_sp.DEVNULL,
            )
        except FileNotFoundError:
            return CheckResult(
                name="python_smoke",
                ran=False,
                passed=None,
                skipped_reason=f"{python_runtime} not on PATH",
                detail=f"skipped: {python_runtime} not on PATH",
            )
        except _sp.TimeoutExpired:
            return CheckResult(
                name="python_smoke",
                ran=True,
                passed=False,
                score=0.0,
                detail=f"timeout after {timeout_seconds}s",
                extra={"timeout": True},
            )

        stderr = result.stderr or ""
                                                                  
                                                                       
        has_traceback = "Traceback" in stderr or "runtime:" in stderr
        crashed = result.returncode != 0
        passed = (not crashed) and (not has_traceback)
        detail = (
            "ran cleanly"
            if passed
            else (
                f"exit={result.returncode}, "
                f"stderr_head={stderr.splitlines()[0][:120] if stderr else '(empty)'}"
            )
        )
        return CheckResult(
            name="python_smoke",
            ran=True,
            passed=passed,
            score=1.0 if passed else 0.0,
            detail=detail,
            extra={
                "exit_code": result.returncode,
                "stdout_bytes": len(result.stdout or ""),
                "stderr_bytes": len(stderr),
                "stderr_head": stderr[:400],
            },
        )
    finally:
        try:
            import shutil as _shutil
            _shutil.rmtree(scratch, ignore_errors=True)
        except OSError:
            pass


_IO_VERBS_NEEDING_ENV = {
    "READ", "REWRITE", "DELETE", "START", "ACCEPT"
}


def _program_needs_runtime_env(ast: AstNode | None) -> tuple[bool, str]:
    if ast is None:
        return False, ""
    from src.pipeline.stage1_parser.ast_nodes import StatementNode         

    triggers: set[str] = set()
    for node in ast.walk():
        if isinstance(node, StatementNode):
            verb = (node.attributes.get("verb") or "").upper()
            if verb in _IO_VERBS_NEEDING_ENV:
                triggers.add(verb)
    if triggers:
        return True, f"uses I/O verbs requiring environment ({', '.join(sorted(triggers))})"
    return False, ""


def _check_execution(
    cobol_source: str,
    python_source: str,
    stdin: str = "",
    timeout_seconds: int = 15,
    ast: AstNode | None = None,
) -> CheckResult:
                                                                     
                                                                
    runner = ExecutionAccuracy(timeout_seconds=timeout_seconds)
    if not runner.available:
        return CheckResult(
            name="execution_match",
            ran=False,
            passed=None,
            skipped_reason="GnuCOBOL (cobc) not found on PATH.",
        )
    try:
        result: ExecutionResult = runner.compare(cobol_source, python_source, stdin=stdin)
    except Exception as exc:                
        return CheckResult(
            name="execution_match",
            ran=False,
            passed=None,
            skipped_reason=f"Execution check failed to run: {exc}",
        )

                                                                      
    if result.error_type in {"cobol_compiler_not_found", "cobol_timeout"} or result.cobol_returncode not in (0, -1):
        skipped_reason = (
            f"cobol side could not be executed ({result.error_type or 'compile_failed'}; "
            f"rc={result.cobol_returncode})"
        )
        return CheckResult(
            name="execution_match",
            ran=False,
            passed=None,
            skipped_reason=skipped_reason,
            detail=f"skipped: {skipped_reason}",
            extra={
                "cobol_stdout": result.cobol_stdout[:400],
                "cobol_returncode": result.cobol_returncode,
            },
        )

    return CheckResult(
        name="execution_match",
        ran=True,
        passed=bool(result.matched),
        score=1.0 if result.matched else 0.0,
        detail=(
            "stdout matched" if result.matched else f"stdout mismatch ({result.error_type})"
        ),
        extra={
            "cobol_stdout": result.cobol_stdout,
            "python_stdout": result.python_stdout,
            "cobol_returncode": result.cobol_returncode,
            "python_returncode": result.python_returncode,
        },
    )


def _check_llm_judge(
    cobol_source: str,
    python_source: str,
    provider: str | list[str] = "openai",
    pass_threshold: float = 0.70,
    model: str | None = None,
) -> CheckResult:
    providers: list[str] = [provider] if isinstance(provider, str) else list(provider)
    if not providers:
        msg = "No providers specified."
        return CheckResult(
            name="llm_judge",
            ran=False,
            passed=None,
            skipped_reason=msg,
            detail=f"skipped: {msg}",
        )

    last_reason = ""
    attempts: list[str] = []
    for name in providers:
        try:
            prov = get_provider(name, **({"model": model} if model else {}))
        except Exception as exc:                
            last_reason = f"{name}: provider unavailable ({exc})"
            attempts.append(last_reason)
            continue
        if not prov.is_available():
            last_reason = f"{name}: no API key in env"
            attempts.append(last_reason)
            continue

        judge = LlmJudge(provider=prov)
        try:
            score: JudgeScore = judge.score(cobol_source, python_source)
        except Exception as exc:                
            last_reason = f"{name}: judge call failed ({exc})"
            attempts.append(last_reason)
            continue

        detail = (
            f"[{name}] correctness={score.correctness:.2f}, "
            f"readability={score.readability:.2f}, "
            f"pep8={score.pep8_compliance:.2f}, "
            f"pythonic={score.pythonic_idioms:.2f}, "
            f"types={score.type_annotations:.2f}"
        )
        return CheckResult(
            name="llm_judge",
            ran=True,
            passed=score.weighted >= pass_threshold,
            score=round(score.weighted, 3),
            detail=detail,
            extra={
                "rationale": score.rationale,
                "components": asdict(score),
                "provider_used": name,
                "providers_tried": attempts + [f"{name}: ok"],
            },
        )

                                                                     
    summary = " | ".join(attempts) if attempts else "no providers available"
    return CheckResult(
        name="llm_judge",
        ran=False,
        passed=None,
        skipped_reason=summary,
        detail=f"skipped: {summary}"[:480],
        extra={"providers_tried": attempts},
    )


def verify(
    cobol_source: str,
    python_source: str,
    ast: AstNode | None = None,
    *,
    run_execution: bool = True,
    run_llm_judge: bool = True,
    run_python_smoke: bool = False,
    run_llm_rescue: bool = False,
    run_llm_promote: bool = False,
    llm_provider: str | list[str] = "openai",
    llm_pass_threshold: float = 0.70,
    llm_model: str | None = None,
    stdin: str = "",
) -> VerificationReport:
    checks: list[CheckResult] = [
        _check_python_syntax(python_source),
        _check_paragraph_coverage(ast, python_source),
        _check_identifier_coverage(ast, python_source),
        _check_body_non_trivial(ast, python_source),
    ]
    if run_python_smoke:
        checks.append(_check_python_smoke(python_source, ast=ast))
    if run_execution:
        checks.append(_check_execution(cobol_source, python_source, stdin=stdin, ast=ast))
    if run_llm_judge:
        checks.append(
            _check_llm_judge(
                cobol_source,
                python_source,
                provider=llm_provider,
                pass_threshold=llm_pass_threshold,
                model=llm_model,
            )
        )

    ran = [c for c in checks if c.ran]
    failed = [c for c in ran if c.passed is False]
    passed = [c for c in ran if c.passed is True]

                                                                       
    STRUCTURAL = {
        "python_syntax_valid",
        "paragraph_coverage",
        "identifier_coverage",
        "body_non_trivial",
    }
    BEHAVIOURAL = {"python_smoke", "execution_match", "llm_judge"}

    structural_ran = [c for c in ran if c.name in STRUCTURAL]
    structural_passed = [c for c in passed if c.name in STRUCTURAL]
    behavioural_attempted = any(c.name in BEHAVIOURAL for c in checks)
    behavioural_skipped_env = [
        c for c in checks
        if c.name in BEHAVIOURAL and not c.ran and c.skipped_reason
    ]
    behavioural_passed = [c for c in passed if c.name in BEHAVIOURAL]

    if failed:
        verdict = VERDICT_FAIL
    elif not ran:
        verdict = VERDICT_INCONCLUSIVE
    elif behavioural_passed:
                                                                 
        verdict = VERDICT_PASS
    elif (
        len(structural_passed) == len(structural_ran)
        and len(structural_ran) >= 4
        and behavioural_attempted
        and behavioural_skipped_env
        and not any(c.name in BEHAVIOURAL and c.ran for c in checks)
    ):
                                                                  
                                                                      
        verdict = VERDICT_STRUCTURAL_PASS
    else:
                                                                 
                                                               
        verdict = VERDICT_INCONCLUSIVE

                                                                     
    rescued_python: str | None = None
    rescue_provenance: dict | None = None
    rescue_attempts: list[str] = []                                                 
    if run_llm_rescue and verdict == VERDICT_FAIL and failed:
        from src.pipeline.stage3_llm.verdict_rescue import rescue_verdict

        providers_list: list[str] = (
            [llm_provider] if isinstance(llm_provider, str) else list(llm_provider)
        )
        for prov_name in providers_list:
            try:
                prov = get_provider(prov_name, **({"model": llm_model} if llm_model else {}))
            except Exception as exc:                
                rescue_attempts.append(f"{prov_name}: provider construction failed ({exc})")
                continue
            res = rescue_verdict(
                cobol_source=cobol_source,
                failing_python=python_source,
                failing_checks=[{"name": c.name, "detail": c.detail} for c in failed],
                provider=prov,
            )
            if res.rescued and res.new_python:
                rescued_python = res.new_python
                rescue_provenance = {
                    "provider": res.provider_used,
                    "rounds": res.rounds,
                    "original_verdict": VERDICT_FAIL,
                    "original_failed_checks": [c.name for c in failed],
                }
                break
            else:
                rescue_attempts.append(
                    f"{prov_name}: {res.error or 'no rescue produced'}"
                )

                                                                       
    rescue_failed_check: CheckResult | None = None
    if run_llm_rescue and verdict == VERDICT_FAIL and rescue_attempts and not rescued_python:
        rescue_failed_check = CheckResult(
            name="llm_rescue",
            ran=False,
            passed=None,
            skipped_reason=" | ".join(rescue_attempts)[:480],
            detail=f"skipped: {' | '.join(rescue_attempts)[:300]}",
            extra={
                "attempted": True,
                "rescued": False,
                "providers_tried": rescue_attempts,
                "original_failed_checks": [c.name for c in failed],
            },
        )

    if rescued_python:
                                                                    
                                                                     
        rescued_checks: list[CheckResult] = [
            _check_python_syntax(rescued_python),
            _check_paragraph_coverage(ast, rescued_python),
            _check_identifier_coverage(ast, rescued_python),
            _check_body_non_trivial(ast, rescued_python),
        ]
                                                        
        if run_python_smoke:
            rescued_checks.append(_check_python_smoke(rescued_python, ast=ast))
                              
        rescued_ran = [c for c in rescued_checks if c.ran]
        rescued_failed = [c for c in rescued_ran if c.passed is False]
        rescued_passed = [c for c in rescued_ran if c.passed is True]
        rescued_behavioural_passed = [
            c for c in rescued_passed if c.name in BEHAVIOURAL
        ]
        if rescued_failed:
            new_verdict = VERDICT_FAIL
        elif rescued_behavioural_passed:
            new_verdict = VERDICT_PASS
        elif behavioural_attempted and behavioural_skipped_env:
            new_verdict = VERDICT_STRUCTURAL_PASS
        else:
            new_verdict = VERDICT_INCONCLUSIVE

        if new_verdict in {VERDICT_PASS, VERDICT_STRUCTURAL_PASS}:
                                                                 
                                                                     
            checks = list(rescued_checks) + [
                CheckResult(
                    name="llm_rescue",
                    ran=True,
                    passed=True,
                    score=1.0,
                    detail=(
                        f"rescued from {rescue_provenance['original_verdict']} "
                        f"(failed: {', '.join(rescue_provenance['original_failed_checks'])}) "
                        f"via {rescue_provenance['provider']}"
                    ),
                    extra=rescue_provenance,
                )
            ]
            ran = rescued_ran
            failed = rescued_failed
            verdict = new_verdict

                                                                     
    if rescue_failed_check is not None and rescued_python is None:
        checks = list(checks) + [rescue_failed_check]

                                                                         
    if run_llm_promote and verdict == VERDICT_STRUCTURAL_PASS:
        from src.evaluation.llm_promote import llm_promote

        providers_list = [llm_provider] if isinstance(llm_provider, str) else list(llm_provider)
        promote_attempts: list[str] = []
        promoted = False
        last_reason = ""
        last_provider_used = ""
        for prov_name in providers_list:
            try:
                prov = get_provider(prov_name, **({"model": llm_model} if llm_model else {}))
            except Exception as exc:                
                promote_attempts.append(f"{prov_name}: provider construction failed ({exc})")
                continue
            res = llm_promote(cobol_source, python_source, prov)
            last_provider_used = res.provider or prov_name
            if res.promoted:
                promoted = True
                last_reason = res.reason
                promote_attempts.append(f"{prov_name}: YES — {res.reason[:80]}")
                break
            elif res.answered:
                                                                     
                                                          
                last_reason = res.reason
                promote_attempts.append(f"{prov_name}: NO — {res.reason[:80]}")
                break
            else:
                promote_attempts.append(f"{prov_name}: {res.error or 'no answer'}")
        if promoted:
            verdict = VERDICT_PASS
            checks = list(checks) + [
                CheckResult(
                    name="llm_promote",
                    ran=True,
                    passed=True,
                    score=1.0,
                    detail=f"promoted via {last_provider_used}: YES — {last_reason[:120]}",
                    extra={
                        "promoted": True,
                        "provider": last_provider_used,
                        "reason": last_reason,
                        "attempts": promote_attempts,
                    },
                )
            ]
        else:
            checks = list(checks) + [
                CheckResult(
                    name="llm_promote",
                    ran=bool(promote_attempts and any(': NO ' in a for a in promote_attempts)),
                    passed=False if promote_attempts and any(': NO ' in a for a in promote_attempts) else None,
                    score=0.0 if promote_attempts and any(': NO ' in a for a in promote_attempts) else None,
                    detail=(
                        f"not promoted: {' | '.join(promote_attempts)[:300]}"
                        if promote_attempts
                        else "no providers available"
                    ),
                    skipped_reason=(
                        " | ".join(promote_attempts)[:480]
                        if not any(': NO ' in a for a in promote_attempts)
                        else ""
                    ),
                    extra={
                        "promoted": False,
                        "attempts": promote_attempts,
                    },
                )
            ]

    summary = _summarise(verdict, ran, failed, behavioural_skipped_env)
    return VerificationReport(verdict=verdict, checks=checks, summary=summary)


def _summarise(
    verdict: str,
    ran: list[CheckResult],
    failed: list[CheckResult],
    behavioural_skipped: list[CheckResult] | None = None,
) -> str:
    if verdict == VERDICT_PASS:
        return f"All {len(ran)} active check(s) passed."
    if verdict == VERDICT_STRUCTURAL_PASS:
        reasons = ", ".join(c.name for c in (behavioural_skipped or []))
        return (
            f"{len(ran)} structural check(s) passed; behavioural checks "
            f"skipped due to environment ({reasons or 'unspecified'})."
        )
    if verdict == VERDICT_FAIL:
        names = ", ".join(c.name for c in failed)
        return f"{len(failed)} check(s) failed: {names}."
    if verdict == VERDICT_INCONCLUSIVE:
        if ran:
            return (
                f"{len(ran)} structural check(s) passed, but no behavioural "
                "signal (execution_match / llm_judge) was available."
            )
        return "No checks could be run."
    return ""
