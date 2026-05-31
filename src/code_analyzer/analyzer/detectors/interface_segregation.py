"""Interface Segregation Principle detector."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.constants import MODERATE_CONFIDENCE
from code_analyzer.limits import MAX_FINDINGS_PER_DETECTOR

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class InterfaceSegregationDetector(Detector):
    name = "InterfaceSegregation"
    severity = "MEDIA"
    description = "Interface Segregation - specific interfaces are better than general ones"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        threshold = max(5, ctx.threshold("max_methods_per_class", 10) // 2)
        findings: List[Finding] = []

        for cls_name, info in ctx.classes.items():
            if cls_name.startswith("Test") or cls_name.endswith("Tests"):
                continue
            public_methods = [m for m in info.get("methods", []) if not m["name"].startswith("_")]
            if len(public_methods) >= threshold and len(info.get("bases", [])) == 0:
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {info['lineno']}",
                    line=info["lineno"],
                    severity="MEDIA",
                    issue=(
                        f"Classe '{cls_name}' expoe {len(public_methods)} metodos publicos. "
                        "Pode haver responsabilidade de interface ampla demais."
                    ),
                    suggestion=(
                        "Divida a API em interfaces menores e exponha apenas os metodos "
                        "que cada consumidor realmente precisa."
                    ),
                    confidence=MODERATE_CONFIDENCE,
                    line_content=ctx.get_line(info["lineno"]),
                ))

        return findings[:MAX_FINDINGS_PER_DETECTOR]
