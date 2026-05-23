"""Analysis context passed to every detector."""

import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class AnalysisContext:
    """Immutable snapshot of a parsed file passed to all detectors."""

    code: str
    lines: List[str]
    filepath: str
    classes: Dict[str, Any]
    functions: List[Dict[str, Any]]
    imports: List[str]
    import_nodes: List[Dict[str, Any]]
    config: Dict[str, Any] = field(default_factory=dict)
    tree: Any = field(default=None)  # ast.Module, populated by core.py
    _walk_cache: Any = field(default=None, repr=False)
    _by_type_cache: Dict[Tuple[type, ...], List[ast.AST]] = field(
        default_factory=dict, repr=False
    )
    _parents_cache: Any = field(default=None, repr=False)

    def __post_init__(self):
        """Pre-compute commonly-used AST node lists to avoid repeated ast.walk()."""
        if self.tree is not None and self._walk_cache is None:
            self._walk_cache = list(ast.walk(self.tree))

    def get_nodes_by_type(self, *types):
        """Return all AST nodes matching any of the given types from cached walk.

        Result is memoized per type-tuple — repeated calls cost a dict lookup.
        """
        if self._walk_cache is None:
            return []
        key = types
        cached = self._by_type_cache.get(key)
        if cached is None:
            cached = [n for n in self._walk_cache if isinstance(n, types)]
            self._by_type_cache[key] = cached
        return cached

    @property
    def parents(self) -> Dict[ast.AST, ast.AST]:
        """Lazy parent map: child node -> parent node.

        Used by detectors that need to walk up from a node (e.g. DeepNesting,
        PrintLeak). Built once per analysis on first access. Keyed by node
        identity (default hash) so `node in parents` and `parents[node]` work.
        """
        if self._parents_cache is None:
            pmap: Dict[ast.AST, ast.AST] = {}
            if self._walk_cache is not None:
                for node in self._walk_cache:
                    for child in ast.iter_child_nodes(node):
                        pmap[child] = node
            self._parents_cache = pmap
        return self._parents_cache

    def get_line(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def threshold(self, key: str, default: int) -> int:
        try:
            return int(self.config.get(key, default))
        except (TypeError, ValueError):
            return default

    def is_ignored(self, criterion: str) -> bool:
        ignored = {
            str(item).strip().lower() for item in self.config.get("ignore_criteria", [])
        }
        return criterion.lower() in ignored
