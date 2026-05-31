"""Design Pattern recognition detector."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.limits import MAX_FINDINGS_PER_DETECTOR

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class DesignPatternsDetector(Detector):
    name = "DesignPatterns"
    severity = "MEDIA"
    penalty_per_finding = 0
    default_confidence = 0.65
    description = (
        "Design Patterns - recognition of Singleton, Factory, Strategy, "
        "Adapter and Repository when explicitly evident"
    )

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for cls_name, info in ctx.classes.items():
            method_names = {m["name"] for m in info.get("methods", [])}
            base_names = {base.split(".")[-1] for base in info.get("bases", [])}
            lower = cls_name.lower()
            detected = []

            if "__new__" in method_names or "singleton" in lower:
                detected.append({"pattern": "Singleton", "evidence": "__new__ presente ou nome sugere instancia unica"})

            if any(k in lower for k in ("factory", "builder")) or method_names.intersection({"create", "build", "make"}):
                detected.append({"pattern": "Factory", "evidence": "Nome ou metodos sugerem criacao centralizada"})

            if "strategy" in lower or base_names.intersection({"ABC", "Protocol"}):
                if method_names.intersection({"execute", "run", "apply"}) or info.get("bases"):
                    detected.append({"pattern": "Strategy", "evidence": "Base abstrata ou contrato claro com metodo de execucao"})

            if any(k in lower for k in ("adapter", "wrapper")) or {"adaptee", "wrapped", "delegate"}.intersection(
                {a.lower() for a in info.get("attributes", [])}
            ):
                detected.append({"pattern": "Adapter", "evidence": "Nome ou atributos indicam adaptacao de outra API"})

            if any(k in lower for k in ("repository", "repo")) or method_names.intersection({"save", "get", "find", "list", "delete"}):
                detected.append({"pattern": "Repository", "evidence": "Nome ou metodos indicam isolamento de acesso a dados"})

            if detected:
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {info['lineno']}",
                    line=info["lineno"],
                    severity="BAIXA",
                    issue=(
                        f"Padroes de design identificados em '{cls_name}': "
                        + ", ".join(item["pattern"] for item in detected)
                    ),
                    suggestion="Documente a intencao do padrao e mantenha a interface pequena e consistente.",
                    line_content=ctx.get_line(info["lineno"]),
                ))

        return findings[:MAX_FINDINGS_PER_DETECTOR]
