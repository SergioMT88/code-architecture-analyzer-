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
        if ctx.tree is None:
            return findings

        TYPING_NAMES = {
            "Dict", "List", "Tuple", "Set", "Union", "Optional", "Any", "Callable",
            "Iterable", "Sequence", "Mapping", "Type", "TypeVar", "Generic",
            "dict", "list", "tuple", "set", "type"
        }

        # Construir node_role mantendo o papel do nó em relação ao pai
        parent_map = ctx.parents
        node_role: dict = {}
        for parent in ctx._walk_cache or []:
            for field, value in ast.iter_fields(parent):
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, ast.AST):
                            node_role[item] = field
                elif isinstance(value, ast.AST):
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

        # Only flag names whose origin is provably EXTERNAL (user input, parsed JSON,
        # request data, env vars). Internal dicts have known keys — flagging them is noise.
        EXTERNAL_FUNCS = {"loads", "load", "json", "safe_load"}
        EXTERNAL_ATTRS = {
            "data", "POST", "GET", "FILES", "COOKIES", "body",
            "form", "args", "headers", "environ",
        }

        def _is_external_source(value: ast.AST) -> bool:
            if isinstance(value, ast.Call):
                f = value.func
                if isinstance(f, ast.Attribute) and f.attr in EXTERNAL_FUNCS:
                    return True
            if isinstance(value, ast.Attribute) and value.attr in EXTERNAL_ATTRS:
                return True
            if isinstance(value, ast.Subscript):
                base = value.value
                if isinstance(base, ast.Attribute) and base.attr == "environ":
                    return True
            return False

        external_dict_names: set = set()
        for n in ctx.get_nodes_by_type(ast.Assign, ast.AnnAssign):
            value = n.value
            if value is None or not _is_external_source(value):
                continue
            targets = [n.target] if isinstance(n, ast.AnnAssign) else n.targets
            for t in targets:
                if isinstance(t, ast.Name):
                    external_dict_names.add(t.id)

        # Direct subscript on external source: `os.environ["KEY"]`, `request.POST["x"]`
        # — these patterns are themselves the access, no intermediate name involved.

        names_with_dot_get: set = set()
        names_with_subscript: set = set()
        # Track subscripts that look like array/list access (numeric index, loop var)
        # to avoid false positives on numpy arrays and lists
        array_like_names: set = set()
        for node in ctx.get_nodes_by_type(ast.Call, ast.Subscript):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "get" and isinstance(node.func.value, ast.Name):
                    names_with_dot_get.add(node.func.value.id)
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name) and isinstance(node.ctx, ast.Load):
                    if node.value.id in TYPING_NAMES:
                        continue
                    if _is_in_type_annotation_or_base(node):
                        continue
                    # Check if subscript looks like array access (numeric index or loop variable)
                    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, (int, float)):
                        array_like_names.add(node.value.id)
                        continue
                    if isinstance(node.slice, ast.Num):
                        array_like_names.add(node.value.id)
                        continue
                    if isinstance(node.slice, ast.Name) and node.slice.id in {"i", "j", "k", "idx", "index", "n", "x", "y", "row", "col"}:
                        array_like_names.add(node.value.id)
                        continue
                    names_with_subscript.add(node.value.id)

        # Remove array-like names from subscript set
        names_with_subscript -= array_like_names

        for name in sorted(names_with_subscript):
            if name in names_with_dot_get:
                continue
            if name not in external_dict_names:
                continue
            findings.append(Finding(
                criterion=self.name,
                location=f"references to '{name}'",
                line=0,
                severity="BAIXA",
                issue=f"Access to '{name}[key]' without fallback. If the key may be missing, use .get().",
                suggestion=f"Use '{name}.get(key)' or '{name}.get(key, default)' instead of '{name}[key]'.",
                line_content="",
                confidence=0.9,
            ))

        return findings
