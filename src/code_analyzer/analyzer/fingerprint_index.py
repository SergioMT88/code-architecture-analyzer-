"""Persistent fingerprint index — incremental on-disk cache for cross-file dedup."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from code_analyzer.analyzer.semantic import _extract_functions, _SKIP_DIRS

_log = logging.getLogger(__name__)

_INDEX_DIR = Path.home() / ".code-analyzer" / "fingerprints"


def _project_key(dirpath: Path) -> str:
    return hashlib.md5(str(dirpath.resolve()).encode()).hexdigest()[:16]


def get_index_path(dirpath: Path) -> Path:
    return _INDEX_DIR / _project_key(dirpath) / "index.json"


def load_index(dirpath: Path) -> Dict[str, Any]:
    """Load existing index from disk. Returns {} if not found."""
    idx_path = get_index_path(dirpath)
    if not idx_path.exists():
        return {}
    try:
        return json.loads(idx_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _log.warning("Failed to load fingerprint index from %s", idx_path, exc_info=True)
        return {}


def _save_index(dirpath: Path, index: Dict[str, Any]) -> None:
    idx_path = get_index_path(dirpath)
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = idx_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(idx_path)


def update_index(dirpath: Path, max_files: int = 200) -> Dict[str, Any]:
    """Incrementally update the fingerprint index for *dirpath*.

    Skips files whose mtime hasn't changed since the last index update.
    Returns the updated index: {fingerprint_hash: [{file, func_name, lineno, mtime}]}.
    """
    dirpath = dirpath.resolve()
    existing = load_index(dirpath)

    # Build a fast lookup: file_path → {fp_hash: entry} from existing index
    file_mtimes: Dict[str, float] = {}
    for fp_hash, entries in existing.items():
        for entry in entries:
            fpath = entry.get("file", "")
            mtime = entry.get("mtime", 0.0)
            if fpath not in file_mtimes or file_mtimes[fpath] < mtime:
                file_mtimes[fpath] = mtime

    # Rebuild index: carry over unchanged files, re-scan changed ones
    new_index: Dict[str, List[Dict[str, Any]]] = {}
    files_scanned = 0

    for py_file in sorted(dirpath.rglob("*.py")):
        if any(p in _SKIP_DIRS for p in py_file.parts):
            continue
        if files_scanned >= max_files:
            break

        str_path = str(py_file)
        try:
            current_mtime = py_file.stat().st_mtime
        except OSError:
            _log.debug("Failed to stat %s during index update", py_file, exc_info=True)
            continue

        if file_mtimes.get(str_path, -1) == current_mtime:
            # Carry over unchanged entries for this file
            for fp_hash, entries in existing.items():
                kept = [e for e in entries if e.get("file") == str_path]
                if kept:
                    new_index.setdefault(fp_hash, []).extend(kept)
            files_scanned += 1
            continue

        # File changed or is new — re-extract
        try:
            funcs = _extract_functions(py_file)
        except (OSError, UnicodeDecodeError, SyntaxError):
            _log.debug("Failed to extract functions from %s", py_file, exc_info=True)
            files_scanned += 1
            continue

        for func in funcs:
            fp = func["fingerprint"]
            new_index.setdefault(fp, []).append({
                "file": str_path,
                "func_name": func["name"],
                "lineno": func["lineno"],
                "mtime": current_mtime,
            })
        files_scanned += 1

    _save_index(dirpath, new_index)
    return new_index
