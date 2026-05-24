"""Dependency Inversion Principle detector."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class DIPDetector(Detector):
    name = "DIP"
    severity = "ALTA"
    description = "Dependency Inversion Principle - depend on abstractions, not implementations"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        max_methods = ctx.threshold("max_methods_per_class", 10)
        findings: List[Finding] = []

        for cls_name, info in ctx.classes.items():
            if cls_name.startswith("Test") or cls_name.endswith("Tests"):
                continue
            if not info["bases"] and info["num_methods"] > max(5, max_methods // 2):
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {info['lineno']}",
                    line=info["lineno"],
                    severity="MEDIA",
                    issue=(
                        f"Classe '{cls_name}' depende apenas de implementacao concreta. "
                        "Considere depender de abstracoes."
                    ),
                    suggestion=f"Crie uma interface/ABC para '{cls_name}' e injete a dependencia.",
                    line_content=ctx.get_line(info["lineno"]),
                    confidence=0.55,
                ))

        return findings
