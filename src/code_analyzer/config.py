"""Project configuration loading — .analyzer.json and pyproject.toml support."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

_log = logging.getLogger(__name__)

__all__ = ["DEFAULT_CONFIG", "load_config"]

DEFAULT_CONFIG: Dict[str, Any] = {
    "max_methods_per_class": 10,
    "max_lines_per_class": 200,
    "max_lines_per_function": 50,
    "max_complexity": 10,
    "max_imports": 20,
    "min_comment_ratio": 10,
    "architecture_style": "generic",
    "ignore_criteria": [],
    "output_dir": None,
    "structured_outputs": True,
    "dry_run": False,
    "interactive": False,
    "min_score": None,
}


def _parse_pyproject_toml(path: Path) -> Dict[str, Any]:
    """Extract [tool.code-analyzer] from a pyproject.toml file."""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            try:
                import toml as tomllib  # type: ignore[no-redef]
            except ImportError:
                return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return data.get("tool", {}).get("code-analyzer", {})
    except (OSError, UnicodeDecodeError, ValueError):
        _log.debug("Failed to parse pyproject.toml at %s", path, exc_info=True)
        return {}


def load_config(filepath: str, quiet: bool = False) -> Dict[str, Any]:
    """Load project config from .analyzer.json or pyproject.toml.

    Precedence order: .analyzer.json > pyproject.toml > DEFAULT_CONFIG.
    """
    file_path = Path(filepath).resolve()
    cwd = Path.cwd().resolve()
    search_dirs = [file_path.parent, file_path.parent.parent]
    # Only add cwd if the file is actually under the project (prevents leaking
    # the host project's .analyzer.json into tests using temp directories)
    if cwd not in search_dirs and file_path.is_relative_to(cwd):
        search_dirs.append(cwd)
    toml_data: Dict[str, Any] = {}
    json_data: Dict[str, Any] = {}

    for d in search_dirs:
        toml_path = d / "pyproject.toml"
        if toml_path.exists() and not toml_data:
            data = _parse_pyproject_toml(toml_path)
            if data:
                toml_data = data
                if not quiet:
                    print(f"Config carregada: {toml_path} ([tool.code-analyzer])")

        json_path = d / ".analyzer.json"
        if json_path.exists() and not json_data:
            try:
                json_data = json.loads(json_path.read_text(encoding="utf-8"))
                if not quiet:
                    print(f"Config carregada: {json_path}")
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                if not quiet:
                    print(f"Aviso: erro ao ler config {json_path}: {exc}")

    return {**DEFAULT_CONFIG, **toml_data, **json_data}
