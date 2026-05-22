"""Circular dependency detector (project-level import graph analysis)."""
from __future__ import annotations

import ast
import hashlib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

_log = logging.getLogger(__name__)

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.limits import MAX_FINDINGS_PER_DETECTOR

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

# Cache em memória: chave = hash dos mtimes do projeto, valor = resultado do _build_graph
_GRAPH_CACHE: Dict[str, Any] = {}


def _project_root(filepath: str) -> Path:
    markers = ("pyproject.toml", "setup.py", "package.json", ".git")
    current = Path(filepath).resolve().parent
    for candidate in [current] + list(current.parents):
        if any((candidate / marker).exists() for marker in markers):
            return candidate
    return current




def _collect_py_files(root: Path):
    """Collect all .py files under root, skipping blocked dirs.
    Uses os.walk for better performance than rglob + skip."""
    py_files = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in {
            "__pycache__", ".git", "node_modules", ".skill_outputs",
            ".mypy_cache", ".pytest_cache", ".ruff_cache", "venv", ".venv",
            ".tox", "dist", "build", ".eggs"
        } and not d.startswith(".")]
        for f in filenames:
            if f.endswith(".py"):
                py_files.append(Path(dirpath) / f)
    return py_files


def _module_key(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    if relative.name == "__init__.py":
        parts = relative.parent.parts
    else:
        parts = relative.with_suffix("").parts
    return ".".join(parts) if parts else path.stem


def _module_aliases(path: Path, root: Path) -> List[str]:
    aliases = {path.stem}
    key = _module_key(path, root)
    aliases.add(key)
    if key.endswith(".__init__"):
        aliases.add(key.rsplit(".__init__", 1)[0])
    return [a for a in aliases if a]


def _resolve_relative(node: ast.ImportFrom, current_key: str) -> Optional[str]:
    if node.level <= 0:
        return node.module
    parts = current_key.split(".") if current_key else []
    if len(parts) < node.level:
        return None
    base = parts[: -node.level]
    if node.module:
        base.extend(node.module.split("."))
    elif len(node.names) == 1 and node.names[0].name != "*":
        base.append(node.names[0].name)
    return ".".join(base) if base else None


def _project_mtime_hash(root: Path) -> str:
    """Hash dos mtimes de todos os .py do projeto — muda só quando algum arquivo muda."""
    h = hashlib.md5()
    for path in _collect_py_files(root):
        try:
            h.update(f"{path}:{path.stat().st_mtime}".encode())
        except OSError:
            pass
    return h.hexdigest()


def _build_graph(filepath: str) -> Dict[str, Any]:
    root = _project_root(filepath)
    module_paths: Dict[str, Path] = {}
    alias_to_modules: Dict[str, Set[str]] = {}
    import_lines: Dict[str, Dict[str, List[int]]] = {}

    for path in _collect_py_files(root):
        if path == Path(filepath).resolve():
            continue
        try:
            key = _module_key(path, root)
        except Exception:
            _log.debug("Failed to compute module key for %s", path, exc_info=True)
            continue
        module_paths[key] = path
        for alias in _module_aliases(path, root):
            alias_to_modules.setdefault(alias, set()).add(key)

    current_path = Path(filepath).resolve()
    current_key = _module_key(current_path, root)
    module_paths[current_key] = current_path
    for alias in _module_aliases(current_path, root):
        alias_to_modules.setdefault(alias, set()).add(current_key)

    graph: Dict[str, Set[str]] = {m: set() for m in module_paths}
    for module_key, path in module_paths.items():
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except Exception:
            _log.debug("Failed to parse %s during circular dep scan", path, exc_info=True)
            continue
        for node in ast.walk(tree):
            targets: List[str] = []
            if isinstance(node, ast.Import):
                for imp in node.names:
                    targets.append(imp.name)
            elif isinstance(node, ast.ImportFrom):
                resolved = _resolve_relative(node, module_key)
                if resolved:
                    targets.append(resolved)
                if node.module:
                    targets.append(node.module)
            for target in targets:
                mods = alias_to_modules.get(target, set())
                if len(mods) == 1:
                    target_mod = next(iter(mods))
                    graph[module_key].add(target_mod)
                    import_lines.setdefault(module_key, {}).setdefault(target_mod, []).append(
                        getattr(node, "lineno", 1)
                    )

    return {
        "root": root,
        "current_key": current_key,
        "graph": graph,
        "import_lines": import_lines,
    }


def _find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    cycles: List[List[str]] = []
    seen_cycles: Set[Tuple[str, ...]] = set()
    state: Dict[str, int] = {}
    stack: List[str] = []
    stack_index: Dict[str, int] = {}

    def canonical(nodes: List[str]) -> Tuple[str, ...]:
        if not nodes:
            return tuple()
        rotations = [tuple(nodes[i:] + nodes[:i]) for i in range(len(nodes))]
        return min(rotations)

    def visit(node: str):
        state[node] = 1
        stack_index[node] = len(stack)
        stack.append(node)
        for neighbor in graph.get(node, set()):
            if neighbor not in graph:
                continue
            if state.get(neighbor, 0) == 0:
                visit(neighbor)
            elif state.get(neighbor) == 1 and neighbor in stack_index:
                cycle = stack[stack_index[neighbor]:]
                key = canonical(cycle)
                if key not in seen_cycles:
                    seen_cycles.add(key)
                    cycles.append(cycle)
        stack.pop()
        stack_index.pop(node, None)
        state[node] = 2

    for node in graph:
        if state.get(node, 0) == 0:
            visit(node)

    return cycles


@register
class CircularDepsDetector(Detector):
    name = "CircularDeps"
    severity = "ALTA"
    penalty_per_finding = 3
    description = "Circular Dependencies - A depends on B which depends on A"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        try:
            root = _project_root(ctx.filepath)
            cache_key = _project_mtime_hash(root)
            if cache_key not in _GRAPH_CACHE:
                _GRAPH_CACHE[cache_key] = _build_graph(ctx.filepath)
                if len(_GRAPH_CACHE) > 8:
                    del _GRAPH_CACHE[next(iter(_GRAPH_CACHE))]
            cached = _GRAPH_CACHE[cache_key]
            # current_key é por arquivo — não pode vir do cache
            current_key = _module_key(Path(ctx.filepath).resolve(), root)
            info = {**cached, "current_key": current_key}
            cycles = _find_cycles(info["graph"])
        except Exception:
            _log.warning("Circular dependency analysis failed for %s", ctx.filepath, exc_info=True)
            return []

        current_key = info["current_key"]
        import_lines = info["import_lines"]
        findings: List[Finding] = []

        for cycle_nodes in cycles:
            if current_key not in cycle_nodes:
                continue
            idx = cycle_nodes.index(current_key)
            next_module = cycle_nodes[(idx + 1) % len(cycle_nodes)]
            lineno = (import_lines.get(current_key, {}).get(next_module, [1]))[0]
            cycle_path = cycle_nodes[idx:] + cycle_nodes[:idx] + [current_key]
            findings.append(Finding(
                criterion=self.name,
                location=f"linha {lineno}" if lineno else "imports do modulo",
                line=lineno,
                severity="ALTA",
                issue="Dependencia circular detectada: " + " -> ".join(cycle_path),
                suggestion=(
                    "Extraia contratos/abstracoes comuns para um modulo neutro "
                    "ou inverta a dependencia com injecao de dependencia."
                ),
                line_content=ctx.get_line(lineno) if lineno else "",
            ))

        return findings[:MAX_FINDINGS_PER_DETECTOR]
