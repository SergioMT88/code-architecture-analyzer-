"""Single Responsibility Principle detector."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class SRPDetector(Detector):
    default_confidence = 0.7
    name = "SRP"
    severity = "ALTA"
    description = "Single Responsibility Principle - each class should have only one reason to change"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        max_methods = ctx.threshold("max_methods_per_class", 10)
        max_lines = ctx.threshold("max_lines_per_class", 200)
        max_complexity = ctx.threshold("max_complexity", 10)
        findings: List[Finding] = []

        for cls_name, info in ctx.classes.items():
            if info["num_methods"] > max_methods:
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {info['lineno']}",
                    line=info["lineno"],
                    severity="ALTA",
                    issue=(
                        f"Classe '{cls_name}' tem {info['num_methods']} metodos "
                        f"(limite configurado: {max_methods})."
                    ),
                    suggestion=f"Divida '{cls_name}' em classes menores por responsabilidade.",
                    line_content=ctx.get_line(info["lineno"]),
                ))
            if info["lines"] > max_lines:
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linhas {info['lineno']}-{info['end_lineno']}",
                    line=info["lineno"],
                    severity="ALTA",
                    issue=(
                        f"Classe '{cls_name}' tem {info['lines']} linhas "
                        f"(limite configurado: {max_lines})."
                    ),
                    suggestion="Extraia grupos de metodos relacionados para novas classes.",
                    line_content=ctx.get_line(info["lineno"]),
                ))
            for method in info["methods"]:
                if method["complexity"] > max_complexity:
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {method['lineno']}",
                        line=method["lineno"],
                        severity="MEDIA",
                        issue=(
                            f"Metodo '{cls_name}.{method['name']}' tem complexidade "
                            f"{method['complexity']} (limite configurado: {max_complexity})."
                        ),
                        suggestion=f"Extraia logica de '{method['name']}' em metodos menores.",
                        line_content=ctx.get_line(method["lineno"]),
                    ))

        return findings
