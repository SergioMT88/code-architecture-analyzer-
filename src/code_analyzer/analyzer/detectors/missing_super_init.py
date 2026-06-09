"""Missing super().__init__() call in subclass detector."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.analyzer.detectors._utils import node_unparse

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_MOCK_BASES = frozenset({"Mock", "MagicMock", "AsyncMock", "NonCallableMock"})


def _base_name(base: ast.AST) -> str:
    return base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")


def _is_test_double(class_node: ast.ClassDef, filepath: str) -> bool:
    """True if the class is a test double / internal stub — calling super().__init__
    is not a meaningful expectation for these."""
    if class_node.name.startswith("_"):
        return True
    if "test" in Path(filepath).name.lower():
        return True
    return any(_base_name(b) in _MOCK_BASES for b in class_node.bases)


def _base_has_init(class_node: ast.ClassDef, classes: Dict[str, ast.ClassDef]) -> bool:
    """True if a base (resolvable in-file) has an __init__ worth calling, OR a base
    is external/unknown (be conservative — it may need initialization)."""
    for base in class_node.bases:
        parent = classes.get(_base_name(base))
        if parent is None:
            return True  # external base (e.g. django.db.models.Model) — keep flagging
        if any(
            isinstance(n, ast.FunctionDef) and n.name == "__init__"
            for n in parent.body
        ):
            return True
        if _base_has_init(parent, classes):  # walk further up the in-file chain
            return True
    return False


@register
class MissingSuperInitDetector(Detector):
    default_confidence = 0.9
    name = "MissingSuperInit"
    severity = "ALTA"
    description = "MissingSuperInit - subclass __init__ that never calls super().__init__() risks incomplete initialization"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        classes = {n.name: n for n in ctx.get_nodes_by_type(ast.ClassDef)}
        for name, node in classes.items():
            if not node.bases:
                continue
            # Skip test doubles/stubs and cases where no in-file base has an
            # __init__ worth calling (nothing to initialize → not a bug).
            if _is_test_double(node, ctx.filepath):
                continue
            if not _base_has_init(node, classes):
                continue
            has_init = any(
                isinstance(n, ast.FunctionDef) and n.name == "__init__"
                for n in node.body
            )
            if not has_init:
                continue
            init_node = next(
                n for n in node.body
                if isinstance(n, ast.FunctionDef) and n.name == "__init__"
            )
            calls_super_init = any(
                isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Attribute)
                and isinstance(n.value.func.value, ast.Call)
                and isinstance(n.value.func.value.func, ast.Name)
                and n.value.func.value.func.id == "super"
                and n.value.func.attr == "__init__"
                for n in ast.walk(init_node)
            )
            if not calls_super_init:
                base_repr = node_unparse(node.bases[0])
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="ALTA",
                    issue=f"Class '{name}' inherits from {base_repr} but does not call super().__init__() in its __init__.",
                    suggestion="Add super().__init__() at the start of __init__ to ensure parent class initialization.",
                    line_content=ctx.get_line(node.lineno),
                ))

        return findings
