
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PreflightResult:
    available: bool                             
    accepted: bool | None                                                       
    stderr: str = ""
    returncode: int | None = None
    cobc_path: str = ""

    @property
    def status(self) -> str:
        if not self.available:
            return "skipped"
        if self.accepted is True:
            return "accepted"
        if self.accepted is False:
            return "rejected"
        return "unknown"


_COBC_CHECKED: bool | None = None                            


def is_cobc_available() -> bool:
    global _COBC_CHECKED
    if _COBC_CHECKED is None:
        _COBC_CHECKED = shutil.which("cobc") is not None
    return _COBC_CHECKED


def cobc_preflight(
    cobol_source: str,
    *,
    timeout_seconds: float = 8.0,
    force_format: str | None = None,
) -> PreflightResult:
    cobc = shutil.which("cobc")
    if not cobc:
        return PreflightResult(available=False, accepted=None)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".cob", delete=False, encoding="utf-8", errors="replace"
    ) as fh:
        fh.write(cobol_source)
        src_path = Path(fh.name)

    try:
        cmd = [cobc, "-fsyntax-only"]
        if force_format == "free":
            cmd.append("-free")
        elif force_format == "fixed":
            cmd.append("-fixed")
        cmd.append(str(src_path))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return PreflightResult(
                available=True,
                accepted=False,
                stderr=f"cobc timed out after {timeout_seconds}s",
                returncode=None,
                cobc_path=cobc,
            )
        except OSError as exc:
            return PreflightResult(
                available=True,
                accepted=False,
                stderr=f"cobc invocation failed: {exc}",
                returncode=None,
                cobc_path=cobc,
            )
        return PreflightResult(
            available=True,
            accepted=(result.returncode == 0),
            stderr=(result.stderr or "")[:4000],                           
            returncode=result.returncode,
            cobc_path=cobc,
        )
    finally:
        try:
            src_path.unlink(missing_ok=True)
        except OSError:
            pass
