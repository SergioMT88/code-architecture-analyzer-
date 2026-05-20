"""Cohesion detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List, Optional

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _find_class_node(tree: ast.AST, name: str) -> Optional[ast.ClassDef]:
    if not tree:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _get_accessed_attrs(func_node: ast.AST, attrs_list: List[str]) -> set:
    accessed = set()
    for node in ast.walk(func_node):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            if node.attr in attrs_list:
                accessed.add(node.attr)
    return accessed


@register
class CohesionDetector(Detector):
    name = "Cohesion"
    severity = "MEDIA"
    description = "Cohesion - methods and attributes of a class should be closely related"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        min_methods = ctx.threshold("min_cohesion_methods", 5)
        findings: List[Finding] = []

        for cls_name, info in ctx.classes.items():
            attrs = info.get("attributes", [])
            public_method_names = [m["name"] for m in info["methods"] if not m["name"].startswith("_")]
            
            if len(public_method_names) < min_methods:
                continue

            class_node = _find_class_node(ctx.tree, cls_name)
            if not class_node:
                continue

            # Mapear os métodos públicos para os nós AST reais correspondentes
            method_nodes = []
            for node in class_node.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name in public_method_names:
                        method_nodes.append(node)

            M = len(method_nodes)
            A = len(attrs)

            if M <= 1 or A == 0:
                continue

            # Para cada atributo, ver em quantos métodos públicos ele é acessado
            attr_access_counts = {attr: 0 for attr in attrs}
            for func_node in method_nodes:
                accessed = _get_accessed_attrs(func_node, attrs)
                for attr in accessed:
                    attr_access_counts[attr] += 1

            sum_m_a = sum(attr_access_counts.values())
            # Cálculo de LCOM Henderson-Sellers
            lcom = (M - (sum_m_a / A)) / (M - 1)

            if lcom > 0.7:
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {info['lineno']}",
                    line=info["lineno"],
                    severity="MEDIA",
                    issue=(
                        f"Classe '{cls_name}' possui baixa coesao (LCOM = {lcom:.2f}): "
                        f"seus metodos acessam conjuntos muito disjuntos de atributos."
                    ),
                    suggestion="Agrupe atributos e metodos relacionados em classes menores ou divida a classe.",
                    line_content=ctx.get_line(info["lineno"]),
                ))

        return findings
