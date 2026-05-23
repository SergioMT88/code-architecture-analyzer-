"""Project context loader — reads CLAUDE.md, computes fan-in and git frequency."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)

_DEBT_KEYWORDS = {
    "bug", "débito", "debito", "fixme", "todo", "hack", "workaround",
    "pendente", "conhecido", "broken", "fragile", "fragil", "regress",
    "issue", "problema conhecido",
}

_MAX_CONTENT_CHARS = 4000
_MAX_DEBT_LINES = 25
_MAX_SEARCH_DEPTH = 6


_MAX_FANIN_FILES = 300
_GIT_LOG_DAYS = 90
_HOT_FILE_COMMITS = 20


def _find_project_root(filepath: Path) -> Optional[Path]:
    """Walk up from filepath to find the project root (.git, pyproject.toml, .analyzer.json)."""
    cur = filepath.parent
    for _ in range(8):
        if (
            (cur / ".git").exists()
            or (cur / "pyproject.toml").exists()
            or (cur / ".analyzer.json").exists()
        ):
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def get_import_fan_in(filepath: Path, project_root: Path) -> int:
    """Count how many .py files in *project_root* import the module at *filepath*."""
    stem = filepath.stem
    checked = 0
    count = 0
    _SKIP_DIRS = {
        "venv", ".venv", "env", "virtualenv",
        "__pycache__", ".git", "node_modules", ".tox",
        "dist", "build", ".skill_outputs",
    }
    try:
        for py_file in project_root.rglob("*.py"):
            if any(p in _SKIP_DIRS for p in py_file.parts):
                continue
            if py_file.resolve() == filepath.resolve():
                continue
            checked += 1
            if checked > _MAX_FANIN_FILES:
                break
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                if (
                    f"import {stem}" in content
                    or f"from {stem} import" in content
                    or f"from .{stem} import" in content
                ):
                    count += 1
            except Exception:
                _log.debug("Failed to read %s for fan-in check", py_file, exc_info=True)
                continue
    except Exception:
        _log.debug("Fan-in scan failed for %s", filepath, exc_info=True)
    return count


def get_git_commit_count(filepath: Path) -> int:
    """Return number of git commits touching *filepath* in the last 90 days."""
    try:
        result = subprocess.run(
            [
                "git", "log", "--oneline",
                f"--since={_GIT_LOG_DAYS} days ago",
                "--follow", "--", str(filepath),
            ],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(filepath.parent),
        )
        if result.returncode != 0:
            return 0
        lines = [ln for ln in result.stdout.strip().split("\n") if ln.strip()]
        return len(lines)
    except Exception:
        _log.debug("git log failed for %s", filepath, exc_info=True)
        return 0


def compute_priority_index(fan_in: int, commit_count: int, coverage_pct: float) -> Dict[str, Any]:
    """Combine fan-in, commit frequency, and test coverage into a priority score (0-100).

    Higher score = higher priority to fix first.
    """
    s_fan_in = min(100.0, fan_in * 5.0)
    s_commits = min(100.0, commit_count * (100 / _HOT_FILE_COMMITS))
    s_no_coverage = max(0.0, 100.0 - coverage_pct)

    score = round(0.40 * s_fan_in + 0.35 * s_commits + 0.25 * s_no_coverage, 1)

    if score >= 75:
        label = "CRITICO"
        reason = "Alto impacto estrutural, arquivo quente e/ou baixa cobertura"
    elif score >= 50:
        label = "ALTA"
        reason = "Impacto moderado-alto — priorize antes de outros arquivos"
    elif score >= 25:
        label = "MEDIA"
        reason = "Impacto moderado — analise quando conveniente"
    else:
        label = "BAIXA"
        reason = "Baixo impacto estrutural no projeto"

    return {
        "score": score,
        "label": label,
        "reason": reason,
        "fan_in": fan_in,
        "commit_count": commit_count,
        "coverage_pct": round(coverage_pct, 1),
    }


def load_project_context(filepath: str) -> Dict[str, Any]:
    """Find CLAUDE.md walking up from *filepath* and extract relevant context.

    Returns a dict with:
      found            — bool, whether CLAUDE.md was located
      path             — str path to the file (when found)
      file_mentioned   — bool, whether the analyzed file's stem appears in CLAUDE.md
      known_debts      — list of lines containing debt indicators
      content_preview  — first 4000 chars of CLAUDE.md (for report embedding)
      truncated        — bool, whether content was cut
    """
    file_path = Path(filepath).resolve()

    # SC1 + SC2: structural context (fan-in, git frequency)
    project_root = _find_project_root(file_path)
    fan_in = get_import_fan_in(file_path, project_root) if project_root else 0
    commit_count = get_git_commit_count(file_path)

    claude_md = _find_claude_md(file_path.parent)

    if claude_md is None:
        return {
            "found": False,
            "fan_in": fan_in,
            "commit_count": commit_count,
            "project_root": str(project_root) if project_root else None,
        }

    try:
        content = claude_md.read_text(encoding="utf-8")
    except Exception:
        _log.debug("Failed to read CLAUDE.md at %s", claude_md, exc_info=True)
        return {
            "found": False,
            "fan_in": fan_in,
            "commit_count": commit_count,
            "project_root": str(project_root) if project_root else None,
        }

    stem = file_path.stem.lower()
    file_mentioned = stem in content.lower()

    known_debts = _extract_debt_lines(content)
    truncated = len(content) > _MAX_CONTENT_CHARS

    return {
        "found": True,
        "path": str(claude_md),
        "file_mentioned": file_mentioned,
        "known_debts": known_debts,
        "content_preview": content[:_MAX_CONTENT_CHARS] + (" [...]" if truncated else ""),
        "truncated": truncated,
        "fan_in": fan_in,
        "commit_count": commit_count,
        "project_root": str(project_root) if project_root else None,
    }


def _find_claude_md(start: Path) -> Path | None:
    cur = start
    for _ in range(_MAX_SEARCH_DEPTH):
        candidate = cur / "CLAUDE.md"
        if candidate.exists():
            return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _extract_debt_lines(content: str) -> List[str]:
    results: List[str] = []
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if any(kw in lower for kw in _DEBT_KEYWORDS):
            results.append(stripped)
            if len(results) >= _MAX_DEBT_LINES:
                break
    return results
