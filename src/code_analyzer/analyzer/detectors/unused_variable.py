"""Assigned-but-never-used variable detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List, Set

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.limits import MAX_FINDINGS_PER_DETECTOR

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _store_linenos(ctx: "AnalysisContext") -> dict:
    """Map var name -> first lineno where it appears in Store context."""
    mapping: dict = {}
    for node in ctx.get_nodes_by_type(ast.Name):
        if isinstance(node.ctx, ast.Store) and node.id not in mapping:
            mapping[node.id] = node.lineno
    return mapping


def _class_attr_names(ctx: "AnalysisContext") -> Set[str]:
    """Return names assigned directly in any class body (not inside methods)."""
    names: Set[str] = set()
    for node in ctx.get_nodes_by_type(ast.ClassDef):
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                names.add(item.target.id)
    return names


def _attr_accesses(ctx: "AnalysisContext") -> Set[str]:
    """Return all attribute names accessed anywhere as ClassName.attr."""
    names: Set[str] = set()
    for node in ctx.get_nodes_by_type(ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id and node.value.id[0].isupper():
            names.add(node.attr)
    return names


@register
class UnusedVariableDetector(Detector):
    name = "UnusedVariable"
    severity = "MEDIA"
    description = "UnusedVariable - variable assigned but never read in the same scope"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        if ctx.tree is None:
            return findings

        # Names to skip: class attributes + names used via ClassName.attr
        excluded = _class_attr_names(ctx) | _attr_accesses(ctx)
        store_linenos = _store_linenos(ctx)

        scopes: List[tuple] = [(None, list(ast.iter_child_nodes(ctx.tree)))]
        for node in ctx.get_nodes_by_type(ast.FunctionDef, ast.AsyncFunctionDef):
            scopes.append((node, list(ast.iter_child_nodes(node))))

        for func_node, body_nodes in scopes:
            assigned: Set[str] = set()
            loaded: Set[str] = set()
            params: Set[str] = set()
            if func_node and isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in (
                    func_node.args.args
                    + func_node.args.kwonlyargs
                    + func_node.args.posonlyargs
                ):
                    params.add(arg.arg)
                if func_node.args.vararg:
                    params.add(func_node.args.vararg.arg)
                if func_node.args.kwarg:
                    params.add(func_node.args.kwarg.arg)
            for n in body_nodes:
                for child in ast.walk(n):
                    if isinstance(child, ast.Name):
                        if isinstance(child.ctx, ast.Store):
                            assigned.add(child.id)
                        elif isinstance(child.ctx, ast.Load):
                            loaded.add(child.id)
            for var in assigned:
                if var.startswith("_") or var in ("self", "cls"):
                    continue
                if var in params:
                    continue
                if var.isupper():  # conventional constant — may be used externally
                    continue
                if var in excluded:  # class attribute or ClassName.attr usage found
                    continue
                if var not in loaded:
                    lineno = store_linenos.get(var, 0)
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {lineno}",
                        line=lineno,
                        severity="MEDIA",
                        issue=f"Variable '{var}' assigned but never used.",
                        suggestion=f"Remove the assignment to '{var}' if it is not needed.",
                        line_content=ctx.get_line(lineno),
                    ))

        return findings[:MAX_FINDINGS_PER_DETECTOR]
