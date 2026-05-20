"""dict[key] without .get() fallback detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class DictGetDetector(Detector):
    name = "DictGet"
    severity = "BAIXA"
    description = "DictGet - dict[key] without .get() may raise KeyError; prefer .get() for optional keys"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        TYPING_NAMES = {
            "Dict", "List", "Tuple", "Set", "Union", "Optional", "Any", "Callable", 
            "Iterable", "Sequence", "Mapping", "Type", "TypeVar", "Generic", 
            "dict", "list", "tuple", "set", "type"
        }

        # Construir mapeamento de pais e do papel do nó em relação ao pai
        parent_map = {}
        node_role = {}
        for parent in ast.walk(tree):
            for field, value in ast.iter_fields(parent):
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, ast.AST):
                            parent_map[item] = parent
                            node_role[item] = field
                elif isinstance(value, ast.AST):
                    parent_map[value] = parent
                    node_role[value] = field

        def _is_in_type_annotation_or_base(sub_node: ast.Subscript) -> bool:
            curr = sub_node
            while curr in parent_map:
                parent = parent_map[curr]
                field = node_role.get(curr)
                if isinstance(parent, ast.arg) and field == "annotation":
                    return True
                if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) and field == "returns":
                    return True
                if isinstance(parent, ast.AnnAssign) and field == "annotation":
                    return True
                if isinstance(parent, ast.ClassDef) and field == "bases":
                    return True
                curr = parent
            return False

        names_with_dot_get: set = set()
        names_with_subscript: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "get" and isinstance(node.func.value, ast.Name):
                    names_with_dot_get.add(node.func.value.id)
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name) and isinstance(node.ctx, ast.Load):
                    if node.value.id in TYPING_NAMES:
                        continue
                    if _is_in_type_annotation_or_base(node):
                        continue
                    names_with_subscript.add(node.value.id)

        for name in sorted(names_with_subscript):
            if name in names_with_dot_get:
                continue
            findings.append(Finding(
                criterion=self.name,
                location=f"references to '{name}'",
                line=0,
                severity="BAIXA",
                issue=f"Access to '{name}[key]' without fallback. If the key may be missing, use .get().",
                suggestion=f"Use '{name}.get(key)' or '{name}.get(key, default)' instead of '{name}[key]'.",
                line_content="",
            ))

        return findings
