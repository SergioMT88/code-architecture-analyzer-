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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from code_analyzer.analyzer.detectors import Finding
from code_analyzer.analyzer.scoring import wrap_criterion

__all__ = [
    "discover_python_files",
    "build_literal_index",
    "detect_cross_file_shotgun",
    "analyze_project",
    "build_symbol_index",
    "detect_high_fan_in",
    "SymbolIndex",
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
_HIGH_FAN_IN_THRESHOLD = 5  # symbol imported in this many files → hotspot


@dataclass
class SymbolIndex:
    """Cross-module symbol graph built from AST trees already parsed by analyze_project."""
    exports: Dict[str, Set[str]] = field(default_factory=dict)
    imports: Dict[str, Dict[str, str]] = field(default_factory=dict)
    usages: Dict[str, List[str]] = field(default_factory=dict)


def _relpath_str(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return path.name


def _module_key_to_relpath(trees: Dict[Path, ast.AST], base: Path) -> Dict[str, str]:
    """Map dotted module key -> relpath string for every parsed file."""
    result: Dict[str, str] = {}
    for path in trees:
        try:
            rel_path = path.relative_to(base)
        except ValueError:
            continue
        parts = list(rel_path.parts)
        if not parts:
            continue
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]
        if not parts:
            continue
        rel_str = str(path.relative_to(base))
        full_key = ".".join(parts)
        result[full_key] = rel_str
        # Also register all suffix sub-keys so that "shopapp.models" resolves
        # even when the package is nested and the full key is
        # "complex_challenge.shopapp.models". setdefault gives priority to
        # shallower files (root-level "models.py" beats nested "pkg/models.py").
        for i in range(1, len(parts)):
            result.setdefault(".".join(parts[i:]), rel_str)
    return result


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


def build_symbol_index(
    trees: Dict[Path, ast.AST],
    base: Path,
) -> SymbolIndex:
    """Build a cross-module symbol graph from already-parsed AST trees.

    Pass 1: collect module-level exports (ClassDef, FunctionDef, top-level Assign,
    excluding names starting with '_').
    Pass 2: resolve ImportFrom statements to project-internal modules and populate usages.
    External (stdlib/third-party) imports are ignored (source_rel == '').
    """
    idx = SymbolIndex()
    key_to_rel = _module_key_to_relpath(trees, base)

    # Pass 1: exports
    for path, tree in trees.items():
        rel = _relpath_str(path, base)
        exported: Set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                exported.add(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    exported.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        exported.add(target.id)
        idx.exports[rel] = exported

    # Pass 2: imports → usages
    for path, tree in trees.items():
        rel = _relpath_str(path, base)
        idx.imports[rel] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.level != 0 or not node.module:
                continue
            source_rel = key_to_rel.get(node.module, "")
            for alias in node.names:
                sym_name = alias.name
                if sym_name == "*":
                    continue
                local_name = alias.asname or alias.name
                idx.imports[rel][local_name] = source_rel
                if source_rel:
                    usage_key = f"{source_rel}::{sym_name}"
                    idx.usages.setdefault(usage_key, [])
                    if rel not in idx.usages[usage_key]:
                        idx.usages[usage_key].append(rel)

    return idx


def detect_high_fan_in(
    symbol_index: SymbolIndex,
    base: Path,
) -> List[Tuple[Path, dict]]:
    """Detect symbols imported by 5+ project files — structural coupling hotspots."""
    out: List[Tuple[Path, dict]] = []
    for usage_key, importers in sorted(symbol_index.usages.items()):
        if len(importers) < _HIGH_FAN_IN_THRESHOLD:
            continue
        source_rel, sym_name = usage_key.split("::", 1)
        source_path = base / source_rel
        importer_list = ", ".join(sorted(importers))
        finding = Finding(
            criterion="HighFanIn",
            location=f"{sym_name} em {source_rel}",
            line=1,
            severity="MEDIA",
            issue=(
                f"'{sym_name}' e importado por {len(importers)} modulos "
                f"({importer_list}). Mudar sua interface quebra todos os "
                "chamadores simultaneamente — trate-o como API publica."
            ),
            suggestion=(
                f"Estabilize a interface de '{sym_name}' ou reduza o acoplamento "
                "extraindo um contrato (Protocol/ABC) que os chamadores dependam."
            ),
            line_content="",
            confidence=0.85,
        )
        fd = finding.to_dict(str(source_path))
        fd["blast_radius"] = sorted(importers)
        out.append((source_path, fd))
        if len(out) >= _MAX_FINDINGS:
            break
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
    symbol_index = build_symbol_index(trees, base)
    fan_in = detect_high_fan_in(symbol_index, base)
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

    fan_in_findings: List[dict] = []
    for path, fd in fan_in:
        try:
            fd["file"] = str(path.relative_to(base))
        except ValueError:
            fd["file"] = path.name
        fan_in_findings.append(fd)
    if fan_in_findings:
        cross_criteria["HighFanIn"] = wrap_criterion(
            name="HighFanIn",
            severity="MEDIA",
            description="High Fan-In — simbolo importado por 5+ modulos e hotspot de acoplamento",
            findings=fan_in_findings,
            penalty_per_finding=2,
        )

    return {
        "success": True,
        "root": str(root_path),
        "files": files,
        "parse_errors": parse_errors,
        "cross_file": {"criteria": cross_criteria},
        "symbol_index": symbol_index,
    }
