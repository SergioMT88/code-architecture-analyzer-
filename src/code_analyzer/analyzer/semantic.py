"""Cross-file semantic duplication — compare function fingerprints across files."""
from __future__ import annotations

import ast
import difflib
from pathlib import Path
from typing import Any, Dict, List

from code_analyzer.analyzer.detectors.semantic_duplication import _normalize_node

_SKIP_DIRS = frozenset({
    "venv", ".venv", "env", "virtualenv",
    "__pycache__", ".git", "node_modules", ".tox",
    "dist", "build", ".skill_outputs",
})


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


def _fingerprint_similarity(fp_a: str, fp_b: str) -> float:
    """Return token-level similarity ratio between two fingerprint strings."""
    return difflib.SequenceMatcher(None, fp_a, fp_b).ratio()


def compare_directory(dirpath: str, max_files: int = 100, threshold: float = 1.0) -> Dict[str, Any]:
    """Find structurally similar functions across all .py files in *dirpath*.

    threshold=1.0 (default): exact fingerprint match only.
    threshold<1.0 (e.g. 0.9): also groups functions with >=threshold similarity
    using difflib token comparison. Only includes groups from >=2 different files.
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

    duplicates: List[Dict[str, Any]] = []

    if threshold >= 1.0:
        # Fast exact-match path (original behaviour)
        fp_index: Dict[str, List[Dict[str, Any]]] = {}
        for f in all_funcs:
            fp_index.setdefault(f["fingerprint"], []).append(f)

        for fp, group in fp_index.items():
            unique_files = {f["file"] for f in group}
            if len(unique_files) >= 2:
                duplicates.append({
                    "fingerprint": fp[:32] + "...",
                    "similarity": 1.0,
                    "count": len(group),
                    "files": sorted(unique_files),
                    "functions": group,
                })
    else:
        # Fuzzy path: O(n^2) comparison with early pruning via exact-match first
        visited: set = set()
        for i, fa in enumerate(all_funcs):
            for j, fb in enumerate(all_funcs):
                if j <= i or fa["file"] == fb["file"]:
                    continue
                key = (min(i, j), max(i, j))
                if key in visited:
                    continue
                visited.add(key)
                if fa["fingerprint"] == fb["fingerprint"]:
                    sim = 1.0
                else:
                    sim = _fingerprint_similarity(fa["fingerprint"], fb["fingerprint"])
                if sim >= threshold:
                    duplicates.append({
                        "fingerprint": fa["fingerprint"][:32] + "...",
                        "similarity": round(sim, 3),
                        "count": 2,
                        "files": sorted({fa["file"], fb["file"]}),
                        "functions": [fa, fb],
                    })

    duplicates.sort(key=lambda d: (d["similarity"], d["count"]), reverse=True)

    return {
        "dirpath": str(root),
        "files_scanned": files_scanned,
        "functions_analyzed": len(all_funcs),
        "duplicates": duplicates,
        "duplicate_count": len(duplicates),
        "threshold": threshold,
    }
