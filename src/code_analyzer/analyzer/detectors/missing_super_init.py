"""Missing super().__init__() call in subclass detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class MissingSuperInitDetector(Detector):
    name = "MissingSuperInit"
    severity = "ALTA"
    description = "MissingSuperInit - subclass __init__ that never calls super().__init__() risks incomplete initialization"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
        for name, node in classes.items():
            if not node.bases:
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
                base_repr = ast.unparse(node.bases[0])
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
