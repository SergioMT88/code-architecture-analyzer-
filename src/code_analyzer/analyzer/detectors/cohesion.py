"""Cohesion detector."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class CohesionDetector(Detector):
    name = "Cohesion"
    severity = "MEDIA"
    description = "Cohesion - methods and attributes of a class should be closely related"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        max_methods = ctx.threshold("max_methods_per_class", 10)
        findings: List[Finding] = []

        for cls_name, info in ctx.classes.items():
            attrs = info.get("attributes", [])
            public_methods = [m for m in info["methods"] if not m["name"].startswith("_")]
            if (
                len(attrs) > max(5, max_methods // 2)
                and len(public_methods) > max(5, max_methods // 2)
            ):
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {info['lineno']}",
                    line=info["lineno"],
                    severity="MEDIA",
                    issue=(
                        f"Classe '{cls_name}' pode ter baixa coesao: {len(attrs)} atributos "
                        f"e {len(public_methods)} metodos publicos."
                    ),
                    suggestion="Agrupe atributos e metodos relacionados em classes menores.",
                    line_content=ctx.get_line(info["lineno"]),
                ))

        return findings
