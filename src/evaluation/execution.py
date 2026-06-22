from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionResult:
    matched: bool
    cobol_stdout: str
    python_stdout: str
    cobol_returncode: int
    python_returncode: int
    error_type: str | None = None


def _resolve_cobc(explicit: str | None) -> str | None:
    for candidate in (explicit, os.getenv("GNUCOBOL_PATH")):
        if candidate and Path(candidate).is_file():
            return candidate
    return shutil.which("cobc")


class ExecutionAccuracy:
    def __init__(
        self,
        cobol_compiler: str | None = None,
        python_runtime: str = "python3",
        timeout_seconds: int = 30,
    ) -> None:
        self.cobol_compiler = _resolve_cobc(cobol_compiler)
        self.python_runtime = python_runtime
        self.timeout_seconds = timeout_seconds

    @property
    def available(self) -> bool:
        return self.cobol_compiler is not None

    def run_cobol(self, cobol_source: str, stdin: str = "") -> tuple[str, int]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "program.cob"
            src.write_text(cobol_source)
            binary = tmp_path / "program"
            compile_result = subprocess.run(
                [self.cobol_compiler, "-x", "-O", "-o", str(binary), str(src)],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            if compile_result.returncode != 0:
                return compile_result.stderr, compile_result.returncode
            run_result = subprocess.run(
                [str(binary)],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            return run_result.stdout, run_result.returncode

    def run_python(self, python_source: str, stdin: str = "") -> tuple[str, int]:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "program.py"
            src.write_text(python_source)
            run_result = subprocess.run(
                [self.python_runtime, str(src)],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            return run_result.stdout, run_result.returncode

    def compare(
        self,
        cobol_source: str,
        python_source: str,
        stdin: str = "",
        whitespace_tolerant: bool = True,
    ) -> ExecutionResult:
        try:
            c_out, c_rc = self.run_cobol(cobol_source, stdin=stdin)
        except FileNotFoundError:
            return ExecutionResult(False, "", "", -1, -1, error_type="cobol_compiler_not_found")
        except subprocess.TimeoutExpired:
            return ExecutionResult(False, "", "", -1, -1, error_type="cobol_timeout")

        try:
            p_out, p_rc = self.run_python(python_source, stdin=stdin)
        except subprocess.TimeoutExpired:
            return ExecutionResult(False, c_out, "", c_rc, -1, error_type="python_timeout")

        a, b = c_out, p_out
        if whitespace_tolerant:
            a = "\n".join(line.rstrip() for line in a.splitlines()).strip()
            b = "\n".join(line.rstrip() for line in b.splitlines()).strip()

        return ExecutionResult(
            matched=(a == b),
            cobol_stdout=c_out,
            python_stdout=p_out,
            cobol_returncode=c_rc,
            python_returncode=p_rc,
            error_type=None if a == b else "stdout_mismatch",
        )
