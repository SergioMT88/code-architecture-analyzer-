"""Semantic duplication detector — compares normalized AST fingerprints of functions."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Dict, List, Tuple

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _normalize_node(node: ast.AST) -> str:
    """Walk an AST node and return a normalized fingerprint string.

    Local variable names (id fields) and literal constants (str, int, float)
    are replaced with placeholders so that structurally identical functions
    with different variable names or hard-coded strings still produce the
    same fingerprint.
    """
    parts: List[str] = []

    def walk(n: ast.AST) -> None:
        tname = type(n).__name__
        parts.append(tname)
        for field, value in ast.iter_fields(n):
            parts.append(field)
            if isinstance(value, ast.AST):
                walk(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        walk(item)
                    elif isinstance(item, str):
                        # Replace string literals/labels with placeholder
                        parts.append("__STR__")
                    elif isinstance(item, (int, float)):
                        parts.append("__NUM__")
                    else:
                        parts.append(repr(type(item).__name__))
            elif isinstance(value, str):
                if field == "id":
                    # Local variable names are normalized
                    parts.append("__ID__")
                else:
                    parts.append("__STR__")
            elif isinstance(value, (int, float)):
                parts.append("__NUM__")
            else:
                parts.append(repr(type(value).__name__))

    walk(node)
    return "".join(parts)


@register
class SemanticDuplicationDetector(Detector):
    name = "SemanticDuplication"
    severity = "MEDIA"
    description = "Detects functions with structurally identical bodies (semantic duplication)"
    penalty_per_finding = 2
    default_confidence = 0.7

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ctx.tree
        except SyntaxError:
            return findings

        funcs: List[Tuple[ast.FunctionDef, str]] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fingerprint = _normalize_node(node)
                funcs.append((node, fingerprint))

        if len(funcs) < 2:
            return findings

        dupes: Dict[str, List[ast.FunctionDef]] = {}
        seen_fingerprints: Dict[str, ast.FunctionDef] = {}
        for fn, fp in funcs:
            if fp in seen_fingerprints:
                base = seen_fingerprints[fp].name
                dupes.setdefault(base, [seen_fingerprints[fp]])
                dupes[base].append(fn)
            else:
                seen_fingerprints[fp] = fn

        for base_name, duplicates in dupes.items():
            names = sorted(f.name for f in duplicates)
            lines = [f.lineno for f in duplicates]
            findings.append(Finding(
                criterion=self.name,
                location=f"linhas {', '.join(str(l) for l in lines)}",
                line=lines[0],
                severity="MEDIA",
                issue=f"Funcoes com corpo estruturalmente identico detectadas: {', '.join(names)}.",
                suggestion="Consolide as funcoes duplicadas em uma unica implementacao parametrizavel.",
                line_content=ctx.get_line(lines[0]),
            ))

        return findings
