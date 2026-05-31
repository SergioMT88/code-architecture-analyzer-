"""Long function detector — flags functions/methods exceeding a line threshold."""
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

        # Module-level functions
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

        # Methods inside classes
        for cls_name, cls_info in ctx.classes.items():
            for method in cls_info.get("methods", []):
                line_count = method.get("lines", 0)
                if line_count > max_lines:
                    severity = "ALTA" if line_count > max_lines * 2 else "MEDIA"
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {method['lineno']}",
                        line=method["lineno"],
                        severity=severity,
                        issue=(
                            f"Metodo '{cls_name}.{method['name']}' tem {line_count} linhas "
                            f"(limite configurado: {max_lines})."
                        ),
                        suggestion=(
                            f"Extraia blocos coesos em funcoes menores para melhorar "
                            f"a legibilidade de '{cls_name}.{method['name']}'."
                        ),
                        line_content=ctx.get_line(method["lineno"]),
                    ))

        return findings
