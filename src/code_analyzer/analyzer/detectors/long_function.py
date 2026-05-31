"""Long function detector — flags module-level functions exceeding a line threshold."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class LongFunctionDetector(Detector):
    name = "LongFunction"
    severity = "MEDIA"
    penalty_per_finding = 2
    default_confidence = 0.8
    description = "Funcao com muitas linhas — dificulta legibilidade e manutencao"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        max_lines = ctx.threshold("max_lines_per_function", 50)

        for func in ctx.functions:
            line_count = func.get("lines", 0)
            if line_count > max_lines:
                severity = "ALTA" if line_count > max_lines * 2 else "MEDIA"
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {func['lineno']}",
                    line=func["lineno"],
                    severity=severity,
                    issue=(
                        f"Funcao '{func['name']}' tem {line_count} linhas "
                        f"(limite configurado: {max_lines})."
                    ),
                    suggestion=(
                        f"Extraia blocos coesos em funcoes menores para melhorar "
                        f"a legibilidade de '{func['name']}'."
                    ),
                    line_content=ctx.get_line(func["lineno"]),
                ))

        return findings
