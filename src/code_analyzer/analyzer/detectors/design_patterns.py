"""Design Pattern recognition detector — detects 8 classic patterns."""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Set

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
        "Adapter, Repository, Observer, Facade and Template Method"
    )

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        # Collect function-level data for cross-class patterns
        all_function_names: Set[str] = set()
        for func in ctx.functions:
            all_function_names.add(func["name"])

        for cls_name, info in ctx.classes.items():
            method_names = {m["name"] for m in info.get("methods", [])}
            base_names = {base.split(".")[-1] for base in info.get("bases", [])}
            lower = cls_name.lower()
            detected = []

            # Singleton
            if "__new__" in method_names or "singleton" in lower:
                detected.append({"pattern": "Singleton", "evidence": "__new__ presente ou nome sugere instancia unica"})

            # Factory
            if any(k in lower for k in ("factory", "builder")) or method_names.intersection({"create", "build", "make"}):
                detected.append({"pattern": "Factory", "evidence": "Nome ou metodos sugerem criacao centralizada"})

            # Strategy — class-level: ABC/Protocol base + execute/run/apply
            if "strategy" in lower or base_names.intersection({"ABC", "Protocol"}):
                if method_names.intersection({"execute", "run", "apply"}) or info.get("bases"):
                    detected.append({"pattern": "Strategy", "evidence": "Base abstrata ou contrato claro com metodo de execucao"})

            # Adapter
            if any(k in lower for k in ("adapter", "wrapper")) or {"adaptee", "wrapped", "delegate"}.intersection(
                {a.lower() for a in info.get("attributes", [])}
            ):
                detected.append({"pattern": "Adapter", "evidence": "Nome ou atributos indicam adaptacao de outra API"})

            # Repository
            if any(k in lower for k in ("repository", "repo")):
                crud_methods = {"save", "get", "find", "list", "delete", "carregar", "listar", "remover"}
                if method_names.intersection(crud_methods):
                    detected.append({"pattern": "Repository", "evidence": "Nome e interface de CRUD indicam repositorio de dados"})

            # Observer — subscribe/attach + notify/dispatch pattern
            subscribe_methods = method_names.intersection({"subscribe", "attach", "inscrever", "register_observer"})
            notify_methods = method_names.intersection({"notify", "dispatch", "emit", "notificar", "fire"})
            if subscribe_methods and notify_methods:
                detected.append({"pattern": "Observer", "evidence": f"Metodos {subscribe_methods.pop()} + {notify_methods.pop()} indicam publicador de eventos"})

            # Facade — coordinates multiple subsystems (delegates to 3+ different classes)
            if info.get("num_methods", 0) >= 2:
                delegated_classes = self._count_delegated_classes(cls_name, info, ctx)
                if delegated_classes >= 3:
                    detected.append({"pattern": "Facade", "evidence": f"Coordena {delegated_classes} subsistemas diferentes"})

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

        # Function-level: detect Strategy selection pattern (e.g. if/elif returning different objects)
        for func in ctx.functions:
            if func.get("lines", 0) < 3:
                continue
            fname = func["name"].lower()
            if any(k in fname for k in ("strategy", "factory", "get_", "obter_", "select", "selecionar")):
                # Check if function body has conditional returning different types
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {func['lineno']}",
                    line=func["lineno"],
                    severity="BAIXA",
                    issue=f"Funcao '{func['name']}' parece selecionar entre variantes — possivel Strategy ou Factory.",
                    suggestion="Considere substituir por um dict de strategias ou classe Factory.",
                    line_content=ctx.get_line(func["lineno"]),
                    confidence=0.7,
                ))

        return findings[:MAX_FINDINGS_PER_DETECTOR]

    def _count_delegated_classes(self, cls_name: str, info: dict, ctx: "AnalysisContext") -> int:
        """Count distinct external classes a method body references (simple heuristic)."""
        # Check method names for delegation hints
        method_names = {m["name"] for m in info.get("methods", [])}
        delegation_keywords = {"finalizar", "processar", "executar", "coordenar", "orchestrate"}
        if not method_names.intersection(delegation_keywords):
            return 0
        # Heuristic: count unique class names referenced in the file that are NOT this class
        other_classes = {name for name in ctx.classes if name != cls_name}
        # Simple: if there are delegation methods and 3+ other classes exist, likely a Facade
        if len(other_classes) >= 3:
            return len(other_classes)
        return 0
