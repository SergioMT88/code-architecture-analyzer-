"""code_analyzer — Deep Python architecture analysis with automatic refactoring."""
from __future__ import annotations

import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)


def _read_version() -> str:
    package_json = Path(__file__).resolve().parents[2] / "package.json"
    try:
        return str(json.loads(package_json.read_text(encoding="utf-8")).get("version", "0.0.0"))
    except Exception:
        _log.debug("Failed to read version from package.json", exc_info=True)
        return "0.0.0"


__version__ = _read_version()

from code_analyzer.analyzer import run_analysis, prune_criteria  # noqa: E402
from code_analyzer.refactorer import refactor_file  # noqa: E402
from code_analyzer.report_generator import generate_reports  # noqa: E402
from code_analyzer.validator import validate_file  # noqa: E402
from code_analyzer.config import load_config  # noqa: E402
__all__ = [
    "run_analysis",
    "prune_criteria",
    "refactor_file",
    "generate_reports",
    "validate_file",
    "load_config",
    "__version__",
]
