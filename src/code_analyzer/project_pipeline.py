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
    cross_criteria = result.get("cross_file", {}).get("criteria", {})
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

    from code_analyzer.project_pattern_advisor import get_project_pattern_advice

    advice = get_project_pattern_advice(cross_criteria)
    if advice:
        print("\nSUGESTOES DE PADRAO")
        for item in advice:
            print(f"  [{item['priority']}] {item['pattern']}: {item['symptom']}")
            print(f"      {item['suggestion']}")

    print("\n" + "-" * 70)
    print("Bloco B: B8+B9b ✅ B9c ✅ B9a ✅ B10 ✅ B11 ✅ B+ ✅")


def run_project_pipeline(args: argparse.Namespace) -> int:
    """Entry point for directory input. Returns a process exit code."""
    from code_analyzer.analyzer.criteria_cache import cleanup_stale_caches, cleanup_report_files
    cleanup_stale_caches()
    cleanup_report_files()

    stream_mode = getattr(args, "stream", False)

    if stream_mode:
        from code_analyzer.agent_protocol import StreamEvent
        StreamEvent.emit(StreamEvent.phase("scanning", "started"))

    result = analyze_project(args.file)
    if not result.get("success"):
        if stream_mode:
            StreamEvent.emit(StreamEvent.error(str(result.get("error")), "ERR_ANALYSIS"))
            StreamEvent.emit(StreamEvent.done())
        else:
            print(f"ERRO: {result.get('error')}")
        return 1

    if stream_mode:
        from code_analyzer.agent_protocol import StreamEvent
        files = result.get("files", {})
        StreamEvent.emit(StreamEvent.progress(len(files), len(files), f"{len(files)} files"))

        all_findings = 0
        all_high = 0
        all_medium = 0
        all_low = 0

        for rel, fr in files.items():
            if not fr.get("success"):
                continue
            for name, crit in fr.get("criteria", {}).items():
                for f in crit.get("findings", []):
                    sev = f.get("severity", "MEDIA")
                    if sev == "ALTA":
                        all_high += 1
                    elif sev == "MEDIA":
                        all_medium += 1
                    else:
                        all_low += 1
                    all_findings += 1
                    StreamEvent.emit(StreamEvent.finding(
                        file=rel,
                        criterion=name,
                        severity=sev,
                        confidence=f.get("confidence", 0.85),
                        line=f.get("line", 0),
                        issue=f.get("issue", ""),
                        suggestion=f.get("suggestion", ""),
                        location=f.get("location", ""),
                    ))
            StreamEvent.emit(StreamEvent.score(
                file=rel,
                score=_avg_file_score(fr),
                grade="A",
                total_findings=sum(
                    len(c.get("findings", []))
                    for c in fr.get("criteria", {}).values()
                ),
            ))

        cross = result.get("cross_file", {}).get("criteria", {})
        for name, crit in cross.items():
            for f in crit.get("findings", []):
                sev = f.get("severity", "MEDIA")
                if sev == "ALTA":
                    all_high += 1
                elif sev == "MEDIA":
                    all_medium += 1
                else:
                    all_low += 1
                all_findings += 1
                StreamEvent.emit(StreamEvent.finding(
                    file=f.get("file", ""),
                    criterion=name,
                    severity=sev,
                    confidence=f.get("confidence", 0.7),
                    line=f.get("line", 0),
                    issue=f.get("issue", ""),
                    suggestion=f.get("suggestion", ""),
                    location=f.get("location", ""),
                ))

        avg_score = 0.0
        scored = [_avg_file_score(fr) for fr in files.values() if fr.get("success")]
        if scored:
            avg_score = sum(scored) / len(scored)

        StreamEvent.emit(StreamEvent.summary(
            total_files=len(files),
            total_findings=all_findings,
            critical=0,
            high=all_high,
            medium=all_medium,
            low=all_low,
            score=avg_score,
            grade="A" if avg_score >= 9 else "B" if avg_score >= 8 else "C" if avg_score >= 7 else "D",
            gaps_emitted=6,
        ))

        for gap_info in [
            ("GodClass", "threshold=15; classes with 8-14 methods across 3+ concerns missed", "MEDIA",
             "Check classes with 8+ methods touching distinct attribute groups"),
            ("TaintFlow", "intra-file taint (incl. class methods) in envelope['semantic'] since v7.6; cross-module still single-hop", "ALTA",
             "Trace user input from request.GET/POST through services to subprocess/cursor.execute (multi-hop case)"),
            ("BusinessLogic", "semantic analysis limited to taint/dataflow/purity; ORM, race conditions still invisible", "ALTA",
             "Read function logic for TOCTOU, validation order, ORM best practices"),
        ]:
            StreamEvent.emit(StreamEvent.gap(*gap_info))

        StreamEvent.emit(StreamEvent.done())
        return 0

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
