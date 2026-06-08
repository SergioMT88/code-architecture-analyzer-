"""Single source of truth for the package version."""
from __future__ import annotations

import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)


def _read_version() -> str:
    package_json = Path(__file__).resolve().parents[2] / "package.json"
    try:
        return str(json.loads(package_json.read_text(encoding="utf-8")).get("version", "0.0.0"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _log.debug("Failed to read version from package.json", exc_info=True)
        return "0.0.0"


__version__ = _read_version()
