"""God Class detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Dict, List, Optional

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

# A class with this many methods whose attribute usage splits into this many
# disjoint clusters is concentrating unrelated responsibilities (DB + email + UI…),
# even if it doesn't cross the raw method-count threshold.
_CLUSTER_MIN_METHODS = 8
_CLUSTER_MIN_GROUPS = 3


def _class_node(ctx: "AnalysisContext", name: str) -> Optional[ast.ClassDef]:
    for node in ctx.get_nodes_by_type(ast.ClassDef):
        if node.name == name:
            return node
    return None


def _method_attr_sets(class_node: ast.ClassDef, attrs: List[str]) -> List[set]:
    """For each method, the set of `self.<attr>` it accesses (only known attrs)."""
    attr_set = set(attrs)
    out: List[set] = []
    for node in class_node.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == "__init__":
            continue
        accessed = {
            n.attr
            for n in ast.walk(node)
            if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == "self"
            and n.attr in attr_set
        }
        if accessed:
            out.append(accessed)
    return out


def _count_responsibility_clusters(method_attr_sets: List[set]) -> int:
    """Union-find over attributes: methods that share an attribute belong to the
    same responsibility cluster. Returns the number of disjoint clusters."""
    parent: Dict[str, str] = {}

    def find(a: str) -> str:
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    for accessed in method_attr_sets:
        accessed = list(accessed)
        for attr in accessed:
            find(attr)
        for other in accessed[1:]:
            union(accessed[0], other)

    roots = set()
    for accessed in method_attr_sets:
        if accessed:
            roots.add(find(next(iter(accessed))))
    return len(roots)


@register
class GodClassDetector(Detector):
    name = "GodClass"
    severity = "ALTA"
    penalty_per_finding = 3
    default_confidence = 0.7
    description = "God Class - class that concentrates too many responsibilities"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        max_methods = ctx.threshold("max_methods_per_class", 10)
        max_lines = ctx.threshold("max_lines_per_class", 200)
        findings: List[Finding] = []

        for cls_name, info in ctx.classes.items():
            attrs = info.get("attributes", [])
            reasons = []
            if info["lines"] > max_lines * 1.5:
                reasons.append(f"{info['lines']} linhas")
            if info["num_methods"] > max_methods + 5:
                reasons.append(f"{info['num_methods']} metodos")
            if len(attrs) > max_methods:
                reasons.append(f"{len(attrs)} atributos")

            # Responsibility-cluster signal: many methods that touch disjoint groups
            # of attributes = unrelated concerns bundled together (DB + email + UI…).
            if not reasons and info["num_methods"] >= _CLUSTER_MIN_METHODS and attrs:
                node = _class_node(ctx, cls_name)
                if node is not None:
                    clusters = _count_responsibility_clusters(_method_attr_sets(node, attrs))
                    if clusters >= _CLUSTER_MIN_GROUPS:
                        reasons.append(
                            f"{clusters} grupos de responsabilidade disjuntos "
                            f"em {info['num_methods']} metodos"
                        )

            if reasons:
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linhas {info['lineno']}-{info['end_lineno']}",
                    line=info["lineno"],
                    severity="ALTA",
                    issue=(
                        f"Classe '{cls_name}' concentra muitas responsabilidades "
                        f"({', '.join(reasons)})."
                    ),
                    suggestion=f"Aplique decomposicao e extraia responsabilidades de '{cls_name}'.",
                    line_content=ctx.get_line(info["lineno"]),
                ))

        return findings
