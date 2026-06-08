"""print() inside non-main functions (debug leak) detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_ALLOWED_FUNCTIONS = {"main", "run", "setup"}
_UI_MODULE_MARKERS = {"terminal_ui", "interactive", "cli", "console", "tui", "prompt"}


@register
class PrintLeakDetector(Detector):
    default_confidence = 0.8
    name = "PrintLeak"
    severity = "MEDIA"
    description = "PrintLeak - print() inside library functions may be forgotten debug output"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        # Skip UI/terminal modules where prints are intentional
        file_lower = ctx.filepath.lower()
        if any(marker in file_lower for marker in _UI_MODULE_MARKERS):
            return []
        findings: List[Finding] = []

        parents = ctx.parents
        func_prints = {}
        for node in ctx.get_nodes_by_type(ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id != "print":
                continue
            func_name = None
            cur = parents.get(node)
            while cur is not None:
                if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_name = cur.name
                    break
                cur = parents.get(cur)
            if func_name is None or func_name in _ALLOWED_FUNCTIONS:
                continue
            if func_name not in func_prints:
                func_prints[func_name] = []
            func_prints[func_name].append(node)

        for func_name, nodes in func_prints.items():
            if not nodes:
                continue
            # Ordena por linha
            nodes.sort(key=lambda n: n.lineno)
            if len(nodes) == 1:
                node = nodes[0]
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="MEDIA",
                    issue=f"print() inside '{func_name}()' may be forgotten debug output left in production.",
                    suggestion=f"Replace print() with logging or remove if it was temporary debug output in '{func_name}'.",
                    line_content=ctx.get_line(node.lineno),
                ))
            else:
                lines_list = [n.lineno for n in nodes]
                lines_str = ", ".join(str(ln) for ln in lines_list)
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linhas {lines_str}",
                    line=lines_list[0],
                    severity="MEDIA",
                    issue=f"print() was found {len(nodes)} times inside '{func_name}()' (lines {lines_str}).",
                    suggestion=f"Replace these prints with logging or remove them if they were temporary debug outputs in '{func_name}'.",
                    line_content="\n".join(ctx.get_line(ln) for ln in lines_list if ctx.get_line(ln)),
                ))

        # Ordenar findings por linha para estabilidade
        findings.sort(key=lambda f: f.line)
        return findings
