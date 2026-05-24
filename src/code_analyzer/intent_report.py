"""IL5 — Generate INTENT.md from stored intent answers.

Reads IntentStore.all_intents() and produces a human-readable Markdown file
grouped into three sections (Bugs Confirmados / Padrões Intencionais / Outro
Mecanismo).  The file is idempotent: every call regenerates it in full from
the current store state.

The file is intentionally terse — no boilerplate docstrings, no section for
zero-entry categories, no duplicate columns.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from code_analyzer.intent_store import IntentStore

_INTENT_MD = "INTENT.md"

_SECTION_ORDER = ["bug", "intentional", "other_mechanism"]

_SECTION_TITLE: Dict[str, str] = {
    "bug":             "Bugs Confirmados",
    "intentional":     "Padrões Intencionais",
    "other_mechanism": "Outro Mecanismo",
}

_ANSWER_LABEL: Dict[str, str] = {
    "bug":             "bug confirmado",
    "intentional":     "silenciado — intencional",
    "other_mechanism": "silenciado — outro mecanismo",
}


def _fmt_row(entry: Dict[str, Any]) -> str:
    location = entry.get("location", "—") or "—"
    criterion = entry.get("criterion", "—") or "—"
    note = entry.get("note", "") or "—"
    by = entry.get("answered_by", "?") or "?"
    date = (entry.get("asked_at", "") or "")[:10]  # YYYY-MM-DD
    return f"| `{location}` | {criterion} | {note} | {by} · {date} |"


def render_intent_md(intent_store: IntentStore) -> str:
    """Return full INTENT.md content as a string. Returns '' if store is empty."""
    intents = intent_store.all_intents()
    if not intents:
        return ""

    groups: Dict[str, List[Dict[str, Any]]] = {k: [] for k in _SECTION_ORDER}
    for entry in intents.values():
        answer = entry.get("answer", "")
        if answer in groups:
            groups[answer].append(entry)

    for lst in groups.values():
        lst.sort(key=lambda e: (e.get("criterion", ""), e.get("location", "")))

    lines: List[str] = [
        "# INTENT.md — Decisões do Projeto",
        "",
        "> Gerado por code-architecture-analyzer. Commite este arquivo — cada entrada é uma decisão do time.",
        f"> Última atualização: {_now_date()}",
        "",
    ]

    for answer in _SECTION_ORDER:
        entries = groups[answer]
        if not entries:
            continue
        title = _SECTION_TITLE[answer]
        lines.append("---")
        lines.append("")
        lines.append(f"## {title} ({len(entries)})")
        lines.append("")
        lines.append("| Local | Critério | Nota | Registrado por |")
        lines.append("|-------|----------|------|----------------|")
        for entry in entries:
            lines.append(_fmt_row(entry))
        lines.append("")

    return "\n".join(lines)


def write_intent_md(intent_store: IntentStore, project_root: Path) -> bool:
    """Write INTENT.md to *project_root*. Returns True if written, False if skipped."""
    content = render_intent_md(intent_store)
    if not content:
        return False
    (project_root / _INTENT_MD).write_text(content, encoding="utf-8")
    return True


def _now_date() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
