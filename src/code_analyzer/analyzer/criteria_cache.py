"""Persistent cache for detector criteria, keyed by code + config + version.

Cache hit avoids running the 49 detectors when the same file/config combination
has been analyzed before. Stored at ``~/.code-analyzer/criteria_cache/``.

Cache entries are auto-cleaned after 7 days of inactivity and after successful
refactoring of the source file.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

_log = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".code-analyzer" / "criteria_cache"
_TOOLS_CACHE_DIR = Path.home() / ".code-analyzer" / "tools_cache"
_CACHE_FORMAT_VERSION = "1"
_CACHE_MAX_AGE_SECONDS = 7 * 24 * 3600


def _hash_key(code: str, config: Dict[str, Any], analyzer_version: str, agents_md_hash: str = "") -> str:
    h = hashlib.sha256()
    h.update(code.encode("utf-8"))
    h.update(json.dumps(config or {}, sort_keys=True, default=str).encode("utf-8"))
    h.update(analyzer_version.encode("utf-8"))
    h.update(_CACHE_FORMAT_VERSION.encode("utf-8"))
    if agents_md_hash:
        h.update(agents_md_hash.encode("utf-8"))
    return h.hexdigest()


def _read_cache(cache_dir: Path, key: str) -> Optional[Dict[str, Any]]:
    if os.environ.get("CODE_ANALYZER_NO_CACHE"):
        return None
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _log.debug("Failed to read cache at %s", path, exc_info=True)
        return None


def _write_cache(cache_dir: Path, key: str, payload: Dict[str, Any]) -> None:
    if os.environ.get("CODE_ANALYZER_NO_CACHE"):
        return
    path = cache_dir / f"{key}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        _log.debug("Failed to write cache at %s", path, exc_info=True)


def get_cached_criteria(
    code: str, config: Dict[str, Any], analyzer_version: str, agents_md_hash: str = ""
) -> Optional[Dict[str, Any]]:
    """Return cached criteria dict if present, else None."""
    return _read_cache(_CACHE_DIR, _hash_key(code, config, analyzer_version, agents_md_hash))


def save_criteria(
    code: str, config: Dict[str, Any], analyzer_version: str, criteria: Dict[str, Any],
    agents_md_hash: str = ""
) -> None:
    """Persist criteria dict for the given (code, config, version, agents_md) tuple."""
    _write_cache(_CACHE_DIR, _hash_key(code, config, analyzer_version, agents_md_hash), criteria)


def get_cached_tool_findings(
    code: str, analyzer_version: str
) -> Optional[Dict[str, Any]]:
    """Return cached ruff findings if present, else None.

    Tool findings depend only on file content (not config), so the key omits config.
    """
    return _read_cache(_TOOLS_CACHE_DIR, _hash_key(code, {}, analyzer_version))


def save_tool_findings(
    code: str, analyzer_version: str, findings: Dict[str, Any]
) -> None:
    """Persist ruff findings for the given (code, version) tuple."""
    _write_cache(_TOOLS_CACHE_DIR, _hash_key(code, {}, analyzer_version), findings)


def cleanup_stale_caches() -> int:
    """Remove cache entries older than _CACHE_MAX_AGE_SECONDS. Returns count removed."""
    removed = 0
    now = time.time()
    for cache_dir in (_CACHE_DIR, _TOOLS_CACHE_DIR):
        if not cache_dir.exists():
            continue
        for entry in cache_dir.glob("*.json"):
            try:
                age = now - entry.stat().st_mtime
                if age > _CACHE_MAX_AGE_SECONDS:
                    entry.unlink()
                    removed += 1
            except OSError:
                pass
    if removed:
        _log.debug("Cleaned up %d stale cache entries", removed)
    return removed


def cleanup_report_files() -> int:
    """Remove HTML reports older than 1 day from ~/.code-analyzer/reports/. Returns count removed."""
    reports_dir = Path.home() / ".code-analyzer" / "reports"
    if not reports_dir.exists():
        return 0
    removed = 0
    now = time.time()
    for entry in reports_dir.glob("*.html"):
        try:
            age = now - entry.stat().st_mtime
            if age > 86400:
                entry.unlink()
                removed += 1
        except OSError:
            pass
    return removed
