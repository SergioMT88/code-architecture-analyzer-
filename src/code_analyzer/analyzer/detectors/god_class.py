"""God Class detector."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class GodClassDetector(Detector):
    name = "GodClass"
    severity = "ALTA"
    penalty_per_finding = 3
    description = "God Class - class that concentrates too many responsibilities"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        max_methods = ctx.threshold("max_methods_per_class", 10)
        max_lines = ctx.threshold("max_lines_per_class", 200)
        findings: List[Finding] = []

        for cls_name, info in ctx.classes.items():
            attrs = info.get("attributes", [])
            reasons = []
            if info["lines"] > max_lines * 1.5:
                reasons.append(f"{info['lines']} linhas")
            if info["num_methods"] > max_methods + 5:
                reasons.append(f"{info['num_methods']} metodos")
            if len(attrs) > max_methods:
                reasons.append(f"{len(attrs)} atributos")
            if reasons:
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linhas {info['lineno']}-{info['end_lineno']}",
                    line=info["lineno"],
                    severity="ALTA",
                    issue=(
                        f"Classe '{cls_name}' concentra muitas responsabilidades "
                        f"({', '.join(reasons)})."
                    ),
                    suggestion=f"Aplique decomposicao e extraia responsabilidades de '{cls_name}'.",
                    line_content=ctx.get_line(info["lineno"]),
                ))

        return findings
