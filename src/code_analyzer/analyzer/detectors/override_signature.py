"""Override method with different parameter names than parent detector (LSP)."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.analyzer.detectors._utils import node_unparse

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class OverrideSignatureMismatchDetector(Detector):
    default_confidence = 0.85
    name = "OverrideSignatureMismatch"
    severity = "MEDIA"
    description = "OverrideSignature - overriding method with different parameter names violates LSP"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        classes = {n.name: n for n in ctx.get_nodes_by_type(ast.ClassDef)}
        for name, node in classes.items():
            if not node.bases:
                continue
            for base in node.bases:
                base_name = node_unparse(base)
                parent = classes.get(base_name)
                if parent is None:
                    continue
                child_methods = {
                    n.name: n for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                parent_methods = {
                    n.name: n for n in parent.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                for mname, cm in child_methods.items():
                    if mname not in parent_methods:
                        continue
                    # Constructors legitimately take different parameters in a
                    # subclass (extra config, dependencies). Not an LSP concern.
                    if mname in ("__init__", "__new__"):
                        continue
                    pm = parent_methods[mname]
                    c_params = [a.arg for a in cm.args.args if a.arg not in ("self", "cls")]
                    p_params = [a.arg for a in pm.args.args if a.arg not in ("self", "cls")]
                    if c_params != p_params:
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {cm.lineno}",
                            line=cm.lineno,
                            severity="MEDIA",
                            issue=(
                                f"Method '{mname}' in '{name}' has different parameters than "
                                f"the parent '{base_name}' "
                                f"({', '.join(c_params)} vs {', '.join(p_params)})."
                            ),
                            suggestion="Keep the same signature as the parent method to respect the Liskov Substitution Principle (LSP).",
                            line_content=ctx.get_line(cm.lineno),
                        ))

        return findings
