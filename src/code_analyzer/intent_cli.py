"""IL7 — `code-analyze intent` CLI subcommands.

Subcommands:
  list               List all stored intents
  show <N>           Show details of intent #N (from list)
  reset <N>          Remove intent #N (finding re-appears next run)
  export             Print INTENT.md content to stdout
  import <file>      Merge intents from another project's .analyzer_intent.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_ANSWER_LABEL: Dict[str, str] = {
    "bug":             "bug confirmado",
    "intentional":     "intencional",
    "other_mechanism": "outro mecanismo",
}

_HELP = """\
Uso: code-analyze intent <subcomando> [args]

Subcomandos:
  list                  Lista todas as decisoes registradas
  show <N>              Mostra detalhes da decisao #N
  reset <N>             Remove a decisao #N (finding volta a aparecer)
  export                Imprime o conteudo do INTENT.md no stdout
  import <arquivo>      Mescla decisoes de outro .analyzer_intent.json
"""


def _resolve_store() -> Tuple[Any, Path]:
    from code_analyzer.intent_store import IntentStore
    from code_analyzer.project_context import _find_project_root
    root = _find_project_root(Path.cwd())
    if root is None:
        print("Erro: nao encontrei a raiz do projeto (git root ou pyproject.toml).")
        sys.exit(1)
    return IntentStore(str(root)), root


def _sorted_entries(intents: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Return (finding_id, entry) pairs sorted by (criterion, location) for stable numbering."""
    return sorted(
        intents.items(),
        key=lambda kv: (kv[1].get("criterion", ""), kv[1].get("location", "")),
    )


def _cmd_list() -> int:
    store, _ = _resolve_store()
    intents = store.all_intents()
    if not intents:
        print("Nenhuma decisao registrada em .analyzer_intent.json.")
        print('Execute "code-analyze <arquivo>" para iniciar uma sessao de perguntas.')
        return 0

    entries = _sorted_entries(intents)
    print(f"\n  {len(entries)} decisao(oes) registrada(s) em .analyzer_intent.json\n")
    print(f"  {'#':<4}  {'Local':<30}  {'Criterio':<22}  Decisao")
    print(f"  {'─'*4}  {'─'*30}  {'─'*22}  {'─'*18}")
    for idx, (fid, entry) in enumerate(entries, 1):
        loc = (entry.get("location") or "—")[:30]
        crit = (entry.get("criterion") or "—")[:22]
        label = _ANSWER_LABEL.get(entry.get("answer", ""), entry.get("answer", "—"))
        print(f"  {idx:<4}  {loc:<30}  {crit:<22}  {label}")
    print()
    print('  Use "code-analyze intent show <N>" para detalhes.')
    print('  Use "code-analyze intent reset <N>" para remover uma decisao.')
    return 0


def _cmd_show(args: List[str]) -> int:
    if not args:
        print("Uso: code-analyze intent show <N>")
        return 1
    store, _ = _resolve_store()
    intents = store.all_intents()
    entries = _sorted_entries(intents)
    try:
        idx = int(args[0])
    except ValueError:
        print(f"Erro: '{args[0]}' nao e um numero valido.")
        return 1
    if idx < 1 or idx > len(entries):
        print(f"Erro: decisao #{idx} nao existe (total: {len(entries)}).")
        return 1
    fid, entry = entries[idx - 1]
    label = _ANSWER_LABEL.get(entry.get("answer", ""), entry.get("answer", "—"))
    note = entry.get("note") or "—"
    by = entry.get("answered_by") or "?"
    at = entry.get("asked_at") or "?"
    print(f"\n  Decisao #{idx}\n")
    print(f"  Criterio:   {entry.get('criterion') or '—'}")
    print(f"  Local:      {entry.get('location') or '—'}")
    print(f"  Decisao:    {label}")
    print(f"  Nota:       {note}")
    print(f"  Registrado: {by} · {at}")
    return 0


def _cmd_reset(args: List[str]) -> int:
    if not args:
        print("Uso: code-analyze intent reset <N>")
        return 1
    store, _ = _resolve_store()
    intents = store.all_intents()
    entries = _sorted_entries(intents)
    try:
        idx = int(args[0])
    except ValueError:
        print(f"Erro: '{args[0]}' nao e um numero valido.")
        return 1
    if idx < 1 or idx > len(entries):
        print(f"Erro: decisao #{idx} nao existe (total: {len(entries)}).")
        return 1
    fid, entry = entries[idx - 1]
    crit = entry.get("criterion") or "?"
    loc = entry.get("location") or "?"
    store._data.setdefault("intents", {}).pop(fid, None)
    store._write()
    print(f"  Removida decisao #{idx}: {crit} em {loc}.")
    print("  O finding voltara a aparecer na proxima analise.")
    return 0


def _cmd_export() -> int:
    from code_analyzer.intent_report import render_intent_md
    store, _ = _resolve_store()
    content = render_intent_md(store)
    if not content:
        print("Nenhuma decisao registrada — INTENT.md estaria vazio.")
        return 0
    print(content)
    return 0


def _cmd_import(args: List[str]) -> int:
    from code_analyzer.intent_store import IntentStore
    if not args:
        print("Uso: code-analyze intent import <arquivo>")
        return 1
    src_path = Path(args[0])
    if not src_path.exists():
        print(f"Erro: arquivo nao encontrado: {src_path}")
        return 1
    try:
        raw = json.loads(src_path.read_text(encoding="utf-8"))
        src_intents: Dict[str, Any] = raw.get("intents", {})
    except Exception as exc:
        print(f"Erro ao ler {src_path}: {exc}")
        return 1

    store, _ = _resolve_store()
    existing = store.all_intents()
    new_count = 0
    skip_count = 0
    for fid, entry in src_intents.items():
        if fid in existing:
            skip_count += 1
            continue
        store._data.setdefault("intents", {})[fid] = entry
        new_count += 1
    if new_count:
        store._write()
    print(f"  {new_count} nova(s) decisao(oes) importada(s).")
    if skip_count:
        print(f"  {skip_count} ja existia(m) (mantida(s)).")
    return 0


def run_intent_cli(argv: List[str]) -> int:
    """Dispatch `code-analyze intent <subcommand>` calls."""
    if not argv or argv[0] in ("-h", "--help"):
        print(_HELP)
        return 0
    cmd = argv[0]
    rest = argv[1:]
    dispatch = {
        "list":   lambda: _cmd_list(),
        "show":   lambda: _cmd_show(rest),
        "reset":  lambda: _cmd_reset(rest),
        "export": lambda: _cmd_export(),
        "import": lambda: _cmd_import(rest),
    }
    if cmd not in dispatch:
        print(f"Subcomando desconhecido: '{cmd}'. Use --help para ver as opcoes.")
        return 1
    return dispatch[cmd]()
