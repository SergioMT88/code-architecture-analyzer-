"""Project-level analysis — the first cross-file pass [v7.2.0, Bloco B].

The per-file analyzer (`run_analysis`) is an `ast.NodeVisitor` over a single
file; it can never relate two points in *different* files. This module adds the
missing layer: it ingests a whole package/directory, parses every module once,
builds cross-file indices, and runs detectors that need to see more than one
file at a time.

Slice B8 + B9b (minimal vertical slice):
  - `discover_python_files` — walk a directory, skipping noise dirs.
  - `build_literal_index`  — map magic string literals -> the sites that use them.
  - `detect_cross_file_shotgun` — a magic literal repeated across >=3 files is
    Shotgun Surgery: changing it means editing every site. (Mirrors the per-file
    `ShotgunSurgery` detector, which only sees `Class.ATTR` within one file.)
  - `analyze_project` — orchestrates per-file analysis + the cross-file pass and
    returns an aggregated result dict.

Heavier cross-file work (symbol graph, interprocedural taint — B9c/B10) builds
on top of the index produced here.
"""
from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from code_analyzer.analyzer.detectors import Finding
from code_analyzer.analyzer.scoring import wrap_criterion

__all__ = [
    "discover_python_files",
    "build_literal_index",
    "detect_cross_file_shotgun",
    "analyze_project",
]

# Directories that never contain first-party source worth analysing.
_SKIP_DIRS = {
    "__pycache__", ".git", ".hg", ".svn", ".tox", ".nox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "node_modules", ".venv", "venv", "env",
    ".eggs", "build", "dist", ".idea", ".vscode", "site-packages",
}

# A "magic value" string literal: all-caps token, >=4 chars (PENDENTE, ACTIVE,
# STATUS_DONE). Lowercase config keys ("utf-8", "name") and free text (anything
# with a space or punctuation) are deliberately excluded to keep FP at zero on
# this first slice; the rule can broaden later with corpus evidence.
_MAGIC_RE = re.compile(r"[A-Z][A-Z0-9_]{3,}\Z")

# All-caps tokens that are conventional, not domain magic values.
_LITERAL_ALLOWLIST = {
    "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS",
    "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NOTSET",
    "TRUE", "FALSE", "NONE", "NULL", "UTF8", "ASCII", "JSON", "HTML",
    "TODO", "FIXME", "HTTP", "HTTPS",
}

_MIN_FILES = 3            # a literal must span this many distinct files to flag
_MAX_FINDINGS = 50


def _build_module_set(paths: List[Path], base: Path) -> set:
    """Return the set of top-level module names that exist inside *base*.

    Used by ImportExistsDetector (via config["known_project_modules"]) so it
    can skip modules that belong to the package being analysed without needing
    a filesystem probe on every import.
    """
    modules: set = set()
    for p in paths:
        try:
            rel = p.relative_to(base)
        except ValueError:
            continue
        parts = list(rel.parts)
        if not parts:
            continue
        # Strip __init__.py / .py suffix to get the dotted module name.
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]
        if not parts:
            continue
        modules.add(parts[0])  # top-level package / module name
    return modules


def discover_python_files(root: Path) -> List[Path]:
    """Return every ``*.py`` file under *root*, skipping noise directories.

    A single file path is returned as a one-element list (so callers can treat
    file and directory inputs uniformly)."""
    root = Path(root)
    if root.is_file():
        return [root] if root.suffix == ".py" else []
    found: List[Path] = []
    for path in root.rglob("*.py"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        found.append(path)
    return sorted(found)


def _is_magic_literal(value: str) -> bool:
    if not _MAGIC_RE.match(value):
        return False
    return value not in _LITERAL_ALLOWLIST


def build_literal_index(
    trees: Dict[Path, ast.AST],
) -> Dict[str, List[Tuple[Path, int]]]:
    """Map each magic string literal to the (file, line) sites that contain it.

    Only string constants passing :func:`_is_magic_literal` are indexed."""
    index: Dict[str, List[Tuple[Path, int]]] = defaultdict(list)
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant):
                continue
            value = node.value
            if not isinstance(value, str):
                continue
            if not _is_magic_literal(value):
                continue
            index[value].append((path, getattr(node, "lineno", 0)))
    return index


def detect_cross_file_shotgun(
    index: Dict[str, List[Tuple[Path, int]]],
    root: Path,
) -> List[Tuple[Path, dict]]:
    """A magic literal repeated across >=`_MIN_FILES` files is Shotgun Surgery.

    Emits one finding per occurrence (so every site is actionable), returned as
    ``(absolute_path, finding_dict)`` pairs. Findings carry criterion
    ``ShotgunSurgery`` — the same name as the per-file detector — because it is
    the same smell seen across module boundaries."""
    out: List[Tuple[Path, dict]] = []
    for value, sites in sorted(index.items()):
        distinct_files = {p for p, _ in sites}
        if len(distinct_files) < _MIN_FILES:
            continue
        try:
            rel_files = sorted(str(p.relative_to(root)) for p in distinct_files)
        except ValueError:
            rel_files = sorted(p.name for p in distinct_files)
        files_str = ", ".join(rel_files)
        for path, line in sites:
            finding = Finding(
                criterion="ShotgunSurgery",
                location=f"'{value}' em {len(distinct_files)} arquivos",
                line=line,
                severity="MEDIA",
                issue=(
                    f"O literal '{value}' aparece em {len(distinct_files)} arquivos "
                    f"diferentes ({files_str}). Mudar esse valor obriga a editar "
                    "todos esses arquivos — um caso classico de Shotgun Surgery."
                ),
                suggestion=(
                    f"Centralize '{value}' em uma unica constante (ex.: um modulo "
                    "de configuracao ou enum) e importe-a onde for necessaria."
                ),
                line_content="",
                confidence=0.8,
            )
            out.append((path, finding.to_dict(str(path))))
            if len(out) >= _MAX_FINDINGS:
                return out
    return out


def analyze_project(
    root: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Analyse every Python file under *root* and run the cross-file pass.

    Returns::

        {
          "success": True,
          "root": <abs path>,
          "files": { "<relpath>": <per-file run_analysis result>, ... },
          "parse_errors": { "<relpath>": "<msg>", ... },
          "cross_file": { "criteria": { "ShotgunSurgery": <criterion dict> } },
        }
    """
    from code_analyzer.analyzer import run_analysis

    root_path = Path(root)
    if not root_path.exists():
        return {"success": False, "error": f"Caminho nao encontrado: {root}"}

    paths = discover_python_files(root_path)
    if not paths:
        return {"success": False, "error": f"Nenhum arquivo .py em: {root}"}

    base = root_path if root_path.is_dir() else root_path.parent

    # Build the set of module names that belong to this package so that
    # ImportExistsDetector can skip them without false "module not found" flags.
    known_modules = _build_module_set(paths, base)
    file_config = dict(config or {})
    file_config["known_project_modules"] = known_modules

    files: Dict[str, Any] = {}
    parse_errors: Dict[str, str] = {}
    trees: Dict[Path, ast.AST] = {}

    for path in paths:
        rel = str(path.relative_to(base))
        files[rel] = run_analysis(str(path), config=file_config)
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError, UnicodeDecodeError) as exc:
            parse_errors[rel] = str(exc)

    literal_index = build_literal_index(trees)
    shotgun = detect_cross_file_shotgun(literal_index, base)

    cross_findings: List[dict] = []
    for path, fd in shotgun:
        try:
            fd["file"] = str(path.relative_to(base))
        except ValueError:
            fd["file"] = path.name
        cross_findings.append(fd)
    cross_criteria: Dict[str, Any] = {}
    if cross_findings:
        cross_criteria["ShotgunSurgery"] = wrap_criterion(
            name="ShotgunSurgery",
            severity="MEDIA",
            description="Shotgun Surgery cross-file — um literal magico repetido em varios modulos",
            findings=cross_findings,
            penalty_per_finding=2,
        )

    return {
        "success": True,
        "root": str(root_path),
        "files": files,
        "parse_errors": parse_errors,
        "cross_file": {"criteria": cross_criteria},
    }
