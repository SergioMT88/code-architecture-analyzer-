"""StringDispatch detector — identifies manual dispatch on self attributes."""
from __future__ import annotations

import ast
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _string_attrs_compared(method_node: ast.FunctionDef) -> Set[str]:
    """Return attribute names compared to string literals via == inside *method_node*."""
    attrs: Set[str] = set()
    for node in ast.walk(method_node):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, ast.Eq) for op in node.ops):
            continue
        left = node.left
        # self.X == "literal"
        if (
            isinstance(left, ast.Attribute)
            and isinstance(left.value, ast.Name)
            and left.value.id == "self"
        ):
            for cmp in node.comparators:
                if isinstance(cmp, ast.Constant) and isinstance(cmp.value, str):
                    attrs.add(left.attr)
        # "literal" == self.X
        if isinstance(left, ast.Constant) and isinstance(left.value, str):
            for cmp in node.comparators:
                if (
                    isinstance(cmp, ast.Attribute)
                    and isinstance(cmp.value, ast.Name)
                    and cmp.value.id == "self"
                ):
                    attrs.add(cmp.attr)
    return attrs


@register
class StringDispatchDetector(Detector):
    name = "StringDispatch"
    severity = "MEDIA"
    description = (
        "String dispatch — comparing self attribute to string literals across methods "
        "is a Strategy Pattern candidate"
    )
    penalty_per_finding = 3

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        if ctx.tree is None:
            return []

        findings: List[Finding] = []

        for node in ast.walk(ctx.tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # attr -> [(method_name, lineno)]
            attr_methods: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for attr in _string_attrs_compared(item):
                    attr_methods[attr].append((item.name, item.lineno))

            for attr, method_list in attr_methods.items():
                if len(method_list) < 2:
                    continue
                names = ", ".join(f"'{m}'" for m, _ in method_list)
                first_line = method_list[0][1]
                findings.append(Finding(
                    criterion=self.name,
                    location=f"classe '{node.name}', metodos {names}",
                    line=first_line,
                    severity=self.severity,
                    issue=(
                        f"Classe '{node.name}' compara 'self.{attr}' com strings literais em "
                        f"{len(method_list)} metodos ({names}). "
                        "Dispatch manual — o tipo e verificado em varios lugares."
                    ),
                    suggestion=(
                        f"Aplique Strategy: crie subclasses ou um dict de handlers indexado "
                        f"por '{attr}', eliminando os ifs repetidos."
                    ),
                    line_content=ctx.get_line(first_line),
                ))

        return findings
