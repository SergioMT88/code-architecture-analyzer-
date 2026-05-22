"""Persistent cache for detector criteria, keyed by code + config + version.

Cache hit avoids running the 49 detectors when the same file/config combination
has been analyzed before. Stored at ``~/.code-analyzer/criteria_cache/``.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

_log = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / ".code-analyzer" / "criteria_cache"
_TOOLS_CACHE_DIR = Path.home() / ".code-analyzer" / "tools_cache"
_CACHE_FORMAT_VERSION = "1"


def _hash_key(code: str, config: Dict[str, Any], analyzer_version: str) -> str:
    h = hashlib.sha256()
    h.update(code.encode("utf-8"))
    h.update(json.dumps(config or {}, sort_keys=True, default=str).encode("utf-8"))
    h.update(analyzer_version.encode("utf-8"))
    h.update(_CACHE_FORMAT_VERSION.encode("utf-8"))
    return h.hexdigest()


def _read_cache(cache_dir: Path, key: str) -> Optional[Dict[str, Any]]:
    if os.environ.get("CODE_ANALYZER_NO_CACHE"):
        return None
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
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
    except Exception:
        _log.debug("Failed to write cache at %s", path, exc_info=True)


def get_cached_criteria(
    code: str, config: Dict[str, Any], analyzer_version: str
) -> Optional[Dict[str, Any]]:
    """Return cached criteria dict if present, else None."""
    return _read_cache(_CACHE_DIR, _hash_key(code, config, analyzer_version))


def save_criteria(
    code: str, config: Dict[str, Any], analyzer_version: str, criteria: Dict[str, Any]
) -> None:
    """Persist criteria dict for the given (code, config, version) tuple."""
    _write_cache(_CACHE_DIR, _hash_key(code, config, analyzer_version), criteria)


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
