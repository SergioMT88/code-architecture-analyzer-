"""Project pipeline — drives a directory/package analysis [v7.2.0, Bloco B8].

Thin counterpart to `pipeline.run_pipeline` (which is per-file): when the CLI is
given a directory, this runs `analyze_project` over every module, prints an
aggregated summary that foregrounds the *cross-file* findings, and supports
`--json`, `--agent`, and the `--min-score` gate. Per-file refactoring and the
interactive menu intentionally don't apply at the project level on this slice.
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

from code_analyzer import __version__
from code_analyzer.analyzer.project_index import analyze_project


def _avg_file_score(file_result: Dict[str, Any]) -> float:
    crit = file_result.get("criteria", {})
    scores = [c.get("score", 10) for c in crit.values() if isinstance(c, dict)]
    return sum(scores) / len(scores) if scores else 10.0


def _collect_cross_findings(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for name, crit in result.get("cross_file", {}).get("criteria", {}).items():
        for f in crit.get("findings", []):
            out.append({"criterion": name, **f})
    return out


def _print_human(result: Dict[str, Any]) -> None:
    files = result.get("files", {})
    cross = _collect_cross_findings(result)
    errors = result.get("parse_errors", {})

    print("\n" + "=" * 70)
    print(f"  CODE ARCHITECTURE ANALYZER v{__version__} - ANALISE DE PROJETO")
    print(f"  Raiz: {result.get('root')}")
    print(f"  Arquivos analisados: {len(files)}")
    print("=" * 70)

    print("\nPLACAR POR ARQUIVO")
    for rel in sorted(files):
        fr = files[rel]
        if not fr.get("success"):
            print(f"  {rel:<45} ERRO: {fr.get('error')}")
            continue
        n_find = sum(len(c.get("findings", [])) for c in fr.get("criteria", {}).values())
        print(f"  {rel:<45} score {_avg_file_score(fr):4.1f}/10   {n_find} achados")

    print(f"\nACHADOS CROSS-FILE ({len(cross)})")
    if not cross:
        print("  (nenhum) — nenhum achado cross-file detectado.")
    for f in cross:
        loc = f"{f.get('file','?')}:{f.get('line','?')}"
        print(f"  [{f['criterion']}] {f.get('location','')}  ({loc})")
        print(f"      {f.get('issue','')}")

    if errors:
        print(f"\nAVISOS DE PARSE ({len(errors)})")
        for rel, msg in errors.items():
            print(f"  {rel}: {msg}")

    print("\n" + "-" * 70)
    print("Bloco B: B8+B9b (dir+shotgun) ✅ B9c (symbol graph) ✅ B9a (clones) ✅ Proximo: B10 (taint).")


def run_project_pipeline(args: argparse.Namespace) -> int:
    """Entry point for directory input. Returns a process exit code."""
    result = analyze_project(args.file)
    if not result.get("success"):
        print(f"ERRO: {result.get('error')}")
        return 1

    if getattr(args, "agent", False):
        # Same unified agent JSON contract as single-file --agent (mode='project').
        from code_analyzer.analyzer.action_plan import generate_project_agent_json
        print(generate_project_agent_json(result))
    elif getattr(args, "json_mode", False):
        result.pop("symbol_index", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)

    min_score = getattr(args, "min_score", None)
    if min_score is not None:
        files = result.get("files", {})
        scored = [_avg_file_score(fr) for fr in files.values() if fr.get("success")]
        avg = sum(scored) / len(scored) if scored else 10.0
        if avg < min_score:
            print(f"\nGATE: media do projeto {avg:.2f} < {min_score} — FALHOU")
            return 1
    return 0
