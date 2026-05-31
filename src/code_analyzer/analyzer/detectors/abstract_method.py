"""Concrete subclass that does not implement all abstract methods detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Dict, List, Set

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.limits import MAX_FINDINGS_PER_DETECTOR

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class AbstractMethodNotImplementedDetector(Detector):
    default_confidence = 0.85
    name = "AbstractMethodNotImplemented"
    severity = "ALTA"
    description = "AbstractMethod - concrete class inherits abstract class but does not implement all abstract methods"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        abstract_methods: Dict[str, List[str]] = {}
        abstract_classes: Set[str] = set()

        class_nodes = ctx.get_nodes_by_type(ast.ClassDef)
        for node in class_nodes:
            is_abstract = any(
                ast.unparse(b) in ("ABC", "Protocol") for b in node.bases
            )
            abstr_methods: List[str] = []
            for n in node.body:
                if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for d in n.decorator_list:
                    is_abstractmethod = (
                        (isinstance(d, ast.Attribute) and d.attr == "abstractmethod")
                        or (isinstance(d, ast.Name) and d.id == "abstractmethod")
                    )
                    if is_abstractmethod:
                        abstr_methods.append(n.name)
                        is_abstract = True
            if not is_abstract:
                continue
            abstract_classes.add(node.name)
            if abstr_methods:
                abstract_methods[node.name] = abstr_methods

        for node in class_nodes:
            if node.name in abstract_classes:
                continue
            for base in node.bases:
                base_name = ast.unparse(base)
                if base_name not in abstract_methods:
                    continue
                implemented = {
                    n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                missing = [m for m in abstract_methods[base_name] if m not in implemented]
                if missing:
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {node.lineno}",
                        line=node.lineno,
                        severity="ALTA",
                        issue=(
                            f"Class '{node.name}' inherits from '{base_name}' but does not "
                            f"implement abstract methods: {', '.join(missing)}."
                        ),
                        suggestion=f"Implement {', '.join(missing)} in class '{node.name}'.",
                        line_content=ctx.get_line(node.lineno),
                    ))

        return findings[:MAX_FINDINGS_PER_DETECTOR]
