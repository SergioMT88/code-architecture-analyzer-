"""LSP detector — Liskov Substitution Principle violations in subclasses."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List, Set

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.limits import MAX_FINDINGS_PER_DETECTOR

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _self_attrs_assigned(method_node: ast.FunctionDef) -> Set[str]:
    """Return names of self.X attributes assigned (stored) in a method."""
    attrs: Set[str] = set()
    for node in ast.walk(method_node):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and isinstance(node.ctx, ast.Store)
        ):
            attrs.add(node.attr)
    return attrs


@register
class LSPDetector(Detector):
    name = "LSP"
    severity = "ALTA"
    penalty_per_finding = 3
    description = "Liskov Substitution Principle — subclass changes parent contract"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        if ctx.tree is None:
            return []

        findings: List[Finding] = []

        for class_node in ctx.get_nodes_by_type(ast.ClassDef):
            if not class_node.bases:
                continue

            for item in class_node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                # Check 1: set_X assigns self.Y where Y ≠ X — unexpected side effect
                name = item.name
                if name.startswith("set_") and len(name) > 4:
                    expected_attr = name[4:]
                    assigned = _self_attrs_assigned(item)
                    unexpected = assigned - {expected_attr}
                    if unexpected:
                        extra = ", ".join(f"self.{a}" for a in sorted(unexpected))
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"classe '{class_node.name}', metodo '{name}', linha {item.lineno}",
                            line=item.lineno,
                            severity=self.severity,
                            issue=(
                                f"'{class_node.name}.{name}' modifica atributos extras ({extra}) "
                                f"alem de 'self.{expected_attr}'. Subclasse quebra o contrato do pai "
                                "(violacao LSP): substituir o pai por esta subclasse muda o comportamento."
                            ),
                            suggestion=(
                                f"Remova os efeitos colaterais em {extra}. Se o comportamento e "
                                "fundamentalmente diferente, reavalie a hierarquia — talvez Square nao "
                                "deva herdar Rectangle (composicao sobre heranca)."
                            ),
                            line_content=ctx.get_line(item.lineno),
                        ))


        return findings[:MAX_FINDINGS_PER_DETECTOR]
