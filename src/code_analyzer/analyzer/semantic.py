"""Cross-file semantic duplication — compare function fingerprints across files."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List

from code_analyzer.analyzer.detectors.semantic_duplication import _normalize_node


def compare_files(filepath_a: str, filepath_b: str) -> Dict[str, Any]:
    """Compare two Python files for structurally identical functions.

    Returns a dict with 'duplicates' — a list of fingerprint groups
    where each group contains functions with identical normalized AST bodies.
    """
    def extract(filepath: str) -> List[Dict[str, Any]]:
        path = Path(filepath)
        try:
            code = path.read_text(encoding="utf-8")
            tree = ast.parse(code)
        except (SyntaxError, FileNotFoundError, OSError):
            return []
        funcs: List[Dict[str, Any]] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.append({
                    "name": node.name,
                    "file": str(path),
                    "lineno": node.lineno,
                    "fingerprint": _normalize_node(node),
                })
        return funcs

    funcs_a = extract(filepath_a)
    funcs_b = extract(filepath_b)
    duplicates: List[Dict[str, Any]] = []

    fp_index: Dict[str, List[Dict[str, Any]]] = {}
    for f in funcs_a:
        fp_index.setdefault(f["fingerprint"], []).append(f)

    for f in funcs_b:
        if f["fingerprint"] in fp_index:
            group = fp_index[f["fingerprint"]] + [f]
            duplicates.append({
                "fingerprint": f["fingerprint"][:32] + "...",
                "functions": group,
            })

    return {"duplicates": duplicates}
