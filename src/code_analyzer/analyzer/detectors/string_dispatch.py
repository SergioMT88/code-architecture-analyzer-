"""StringDispatch detector — identifies manual dispatch on self attributes or method parameters."""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_MIN_PARAM_BRANCHES = 3


def _string_attrs_compared(method_node: ast.FunctionDef) -> Set[str]:
    """Return self.attr names compared to string literals in *method_node*."""
    attrs: Set[str] = set()
    for node in ast.walk(method_node):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, ast.Eq) for op in node.ops):
            continue
        left = node.left
        if (
            isinstance(left, ast.Attribute)
            and isinstance(left.value, ast.Name)
            and left.value.id == "self"
        ):
            for cmp in node.comparators:
                if isinstance(cmp, ast.Constant) and isinstance(cmp.value, str):
                    attrs.add(left.attr)
        if isinstance(left, ast.Constant) and isinstance(left.value, str):
            for cmp in node.comparators:
                if (
                    isinstance(cmp, ast.Attribute)
                    and isinstance(cmp.value, ast.Name)
                    and cmp.value.id == "self"
                ):
                    attrs.add(cmp.attr)
    return attrs


def _param_string_dispatches(method_node: ast.FunctionDef) -> List[Tuple[str, str, int]]:
    """
    Detect param.attr == "literal" dispatch with 3+ branches in a single method.
    Returns list of (param_name, attr_name, first_lineno).
    """
    counts: Counter = Counter()
    first_line: Dict[Tuple[str, str], int] = {}
    for node in ast.walk(method_node):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, ast.Eq) for op in node.ops):
            continue
        left = node.left
        if (
            isinstance(left, ast.Attribute)
            and isinstance(left.value, ast.Name)
            and left.value.id != "self"
        ):
            param, attr = left.value.id, left.attr
            for cmp in node.comparators:
                if isinstance(cmp, ast.Constant) and isinstance(cmp.value, str):
                    key = (param, attr)
                    counts[key] += 1
                    if key not in first_line:
                        first_line[key] = node.lineno
    return [
        (param, attr, first_line[(param, attr)])
        for (param, attr), cnt in counts.items()
        if cnt >= _MIN_PARAM_BRANCHES
    ]


@register
class StringDispatchDetector(Detector):
    name = "StringDispatch"
    severity = "MEDIA"
    description = (
        "String dispatch — comparing attributes to string literals is a Strategy Pattern candidate"
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

            # Pattern 1: self.X == "literal" across multiple methods
            attr_methods: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for attr in _string_attrs_compared(item):
                    attr_methods[attr].append((item.name, item.lineno))

                # Pattern 2: param.attr == "literal" with 3+ branches in one method
                for param, attr, lineno in _param_string_dispatches(item):
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"classe '{node.name}', metodo '{item.name}', linha {lineno}",
                        line=lineno,
                        severity=self.severity,
                        issue=(
                            f"Metodo '{item.name}' usa dispatch manual em '{param}.{attr}' "
                            f"com {_MIN_PARAM_BRANCHES}+ ramificacoes string. "
                            "Cada novo tipo exige modificar este metodo (violacao OCP)."
                        ),
                        suggestion=(
                            f"Aplique Strategy: mapeie '{attr}' para handlers via dict ou subclasses, "
                            "eliminando o if/elif."
                        ),
                        line_content=ctx.get_line(lineno),
                    ))

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
