"""Cross-file semantic duplication — compare function fingerprints across files."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List

from code_analyzer.analyzer.detectors.semantic_duplication import _normalize_node

_SKIP_DIRS = frozenset({"venv", "__pycache__", ".git", "node_modules", ".tox", "dist", "build", ".skill_outputs"})


def _extract_functions(filepath: Path) -> List[Dict[str, Any]]:
    """Parse a .py file and return a list of function fingerprint dicts."""
    try:
        code = filepath.read_text(encoding="utf-8")
        tree = ast.parse(code)
    except (SyntaxError, FileNotFoundError, OSError):
        return []
    funcs: List[Dict[str, Any]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append({
                "name": node.name,
                "file": str(filepath),
                "lineno": node.lineno,
                "fingerprint": _normalize_node(node),
            })
    return funcs


def compare_files(filepath_a: str, filepath_b: str) -> Dict[str, Any]:
    """Compare two Python files for structurally identical functions."""
    funcs_a = _extract_functions(Path(filepath_a))
    funcs_b = _extract_functions(Path(filepath_b))
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


def compare_directory(dirpath: str, max_files: int = 100) -> Dict[str, Any]:
    """Find structurally identical functions across all .py files in *dirpath*.

    Returns a dict with 'duplicates' grouped by identical AST fingerprint,
    only including groups where functions come from at least 2 different files.
    """
    root = Path(dirpath)
    all_funcs: List[Dict[str, Any]] = []
    files_scanned = 0

    for py_file in sorted(root.rglob("*.py")):
        if any(p in _SKIP_DIRS for p in py_file.parts):
            continue
        if files_scanned >= max_files:
            break
        funcs = _extract_functions(py_file)
        if funcs:
            all_funcs.extend(funcs)
            files_scanned += 1

    fp_index: Dict[str, List[Dict[str, Any]]] = {}
    for f in all_funcs:
        fp_index.setdefault(f["fingerprint"], []).append(f)

    duplicates: List[Dict[str, Any]] = []
    for fp, group in fp_index.items():
        unique_files = {f["file"] for f in group}
        if len(unique_files) >= 2:
            duplicates.append({
                "fingerprint": fp[:32] + "...",
                "count": len(group),
                "files": sorted(unique_files),
                "functions": group,
            })

    duplicates.sort(key=lambda d: d["count"], reverse=True)

    return {
        "dirpath": str(root),
        "files_scanned": files_scanned,
        "functions_analyzed": len(all_funcs),
        "duplicates": duplicates,
        "duplicate_count": len(duplicates),
    }
