"""OrmInLoop detector — N+1 query pattern: ORM access inside a loop."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List, Set

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.analyzer.detectors._utils import build_parent_map

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_ORM_CALL_ATTRS = frozenset({
    "filter", "get", "all", "first", "last", "count", "exclude",
    "values", "values_list", "aggregate", "annotate", "exists",
    "bulk_create", "bulk_update", "create", "update", "delete",
})

_DJANGO_ROOTS = {"django", "rest_framework", "drf"}


def _has_django_import(ctx: "AnalysisContext") -> bool:
    return any(
        imp.startswith("django") or imp.startswith("rest_framework")
        for imp in ctx.imports
    )


def _enclosing_loop(node: ast.AST, parent_map: dict):
    node_id = id(node)
    while node_id in parent_map:
        parent = parent_map[node_id]
        if isinstance(parent, (ast.For, ast.While)):
            return parent
        node_id = id(parent)
    return None


def _is_orm_node(node: ast.AST, has_django: bool) -> bool:
    if isinstance(node, ast.Attribute) and node.attr == "objects":
        return True
    if has_django and isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _ORM_CALL_ATTRS:
            return True
    return False


@register
class OrmInLoopDetector(Detector):
    name = "OrmInLoop"
    severity = "ALTA"
    penalty_per_finding = 4
    description = "N+1 query — ORM access inside a loop without select_related/prefetch_related"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        reported: Set[int] = set()
        has_django = _has_django_import(ctx)
        parent_map = build_parent_map(ctx.tree)

        for node in ast.walk(ctx.tree):
            if not _is_orm_node(node, has_django):
                continue
            loop = _enclosing_loop(node, parent_map)
            if loop is None:
                continue
            lineno = getattr(node, "lineno", loop.lineno)
            if lineno in reported:
                continue
            line_content = ctx.get_line(lineno)
            if "select_related" in line_content or "prefetch_related" in line_content:
                continue
            reported.add(lineno)
            findings.append(Finding(
                criterion=self.name,
                location=f"linha {lineno}",
                line=lineno,
                severity="ALTA",
                issue=(
                    "Acesso ORM dentro de loop detectado — padrao N+1 query. "
                    "Cada iteracao pode disparar uma query separada ao banco de dados, "
                    "causando degradacao exponencial de performance."
                ),
                suggestion=(
                    "Use select_related() para FK/OneToOne ou prefetch_related() para M2M/reverse FK "
                    "antes do loop para buscar os dados relacionados em uma unica query."
                ),
                line_content=line_content,
            ))
        return findings
