"""Ruff format compliance detector — checks if file is formatted with black-compatible style."""
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class RuffFormatDetector(Detector):
    name = "RuffFormat"
    severity = "MEDIA"
    penalty_per_finding = 1
    default_confidence = 0.85
    description = "Arquivo nao formatado conforme ruff/black-compatible style"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        try:
            proc = subprocess.run(
                ["ruff", "format", "--check", "--diff", ctx.filepath],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
            )
            if proc.returncode != 0:
                diff_output = proc.stdout.strip()
                diff_line_count = len(diff_output.split("\n")) if diff_output else 0
                findings.append(Finding(
                    criterion=self.name,
                    location="arquivo inteiro",
                    line=1,
                    severity="MEDIA",
                    issue=(
                        f"Arquivo nao esta formatado conforme padrao ruff/black. "
                        f"{diff_line_count} linha(s) precisam de formatacao."
                    ),
                    suggestion="Execute 'ruff format <filepath>' para formatar o arquivo.",
                    line_content="",
                ))
        except FileNotFoundError:
            pass
        except subprocess.TimeoutExpired:
            pass

        return findings
