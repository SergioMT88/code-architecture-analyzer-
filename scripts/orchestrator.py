#!/usr/bin/env python3
"""
Orchestrator v2.0 - Pipeline com config de projeto e modo interativo.

Orquestra: Identificacao (3 fases) -> Proposicao (2 fases) -> Implementacao (5 fases)
"""

import json
import sys
from pathlib import Path

from analyzer import run_analysis
from refactorer import refactor_file
from report_generator import generate_reports


DEFAULT_CONFIG = {
    "max_methods_per_class": 10,
    "max_lines_per_class": 200,
    "max_complexity": 10,
    "max_imports": 20,
    "min_comment_ratio": 10,
    "architecture_style": "generic",
    "ignore_criteria": [],
    "output_dir": None,
    "dry_run": False,
    "interactive": False,
}


def load_config(filepath: str) -> dict:
    """Carrega config do projeto (.analyzer.json) se existir."""
    search_paths = [
        Path(filepath).parent / ".analyzer.json",
        Path(filepath).parent.parent / ".analyzer.json",
        Path.cwd() / ".analyzer.json",
    ]
    for config_path in search_paths:
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding='utf-8'))
                merged = {**DEFAULT_CONFIG, **data}
                print(f"Config carregada: {config_path}")
                return merged
            except Exception as e:
                print(f"Aviso: erro ao ler config {config_path}: {e}")
    return DEFAULT_CONFIG.copy()


def ask_user(question: str, default: bool = True) -> bool:
    """Pergunta ao usuario em modo interativo."""
    default_str = "S/n" if default else "s/N"
    try:
        answer = input(f"\n{question} [{default_str}]: ").strip().lower()
        if not answer:
            return default
        return answer in ("s", "sim", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return default


def print_phase(phase: str, subtitle: str = ""):
    print(f"\n{'='*70}")
    print(f"  {phase}")
    if subtitle:
        print(f"  {subtitle}")
    print('='*70)


def print_findings_summary(analysis: dict):
    """Imprime resumo dos problemas encontrados."""
    criteria = analysis.get("criteria", {})
    metrics = analysis.get("metrics", {})

    print(f"\n  Maintainability Index: "
          f"{metrics.get('maintainability_index', 0)} "
          f"({metrics.get('maintainability_grade', 'N/A')})")
    print(f"  Complexidade media: {metrics.get('avg_cyclomatic_complexity', 0)}")
    print(f"  Ratio de comentarios: {metrics.get('comment_ratio', 0)}%\n")

    critical = [(k, v) for k, v in criteria.items() if v.get("score", 10) < 5]
    warnings = [(k, v) for k, v in criteria.items() if 5 <= v.get("score", 10) < 7]

    if critical:
        print(f"  CRITICO ({len(critical)} criterios):")
        for key, val in critical:
            score = val.get("score", 0)
            n = len(val.get("findings", []))
            print(f"    - {key}: {score}/10 ({n} problemas)")
            for finding in val.get("findings", [])[:2]:
                print(f"      * [{finding['location']}] {finding['issue'][:80]}")

    if warnings:
        print(f"\n  AVISO ({len(warnings)} criterios):")
        for key, val in warnings:
            score = val.get("score", 0)
            n = len(val.get("findings", []))
            print(f"    - {key}: {score}/10 ({n} problemas)")

    tool_findings = analysis.get("tool_findings", {})
    total_tools = tool_findings.get("total", 0)
    if total_tools:
        print(f"\n  Ferramentas externas: {total_tools} ocorrencias "
              f"(ruff: {len(tool_findings.get('ruff', []))}, "
              f"pylint: {len(tool_findings.get('pylint', []))})")


def main():
    if len(sys.argv) < 2:
        print("Uso: python orchestrator.py <arquivo.py> [opcoes]")
        print("Opcoes:")
        print("  --no-refactor   Apenas analisa, sem refatorar")
        print("  --dry-run       Mostra o que seria feito sem aplicar")
        print("  --interactive   Modo interativo (aceitar/rejeitar sugestoes)")
        sys.exit(1)

    filepath = sys.argv[1]
    no_refactor = "--no-refactor" in sys.argv
    dry_run = "--dry-run" in sys.argv
    interactive = "--interactive" in sys.argv

    config = load_config(filepath)
    if dry_run:
        config["dry_run"] = True
    if interactive:
        config["interactive"] = True

    print("\n" + "="*70)
    print("  CODE ARCHITECTURE ANALYZER v2.0 - PIPELINE COMPLETO")
    print(f"  Arquivo: {filepath}")
    if dry_run:
        print("  MODO: DRY-RUN (nenhum arquivo sera modificado)")
    if interactive:
        print("  MODO: INTERATIVO")
    print("="*70)

    # FASE 1: IDENTIFICACAO
    print_phase("FASE 1 - IDENTIFICACAO (3 micro-fases)",
                "1a: AST Scanning | 1b: Pylint | 1c: Ruff")

    analysis = run_analysis(filepath, config)

    if not analysis.get("success", False):
        print(f"\nErro: {analysis.get('error')}")
        sys.exit(1)

    print_findings_summary(analysis)
    print("\n  Fase 1 concluida!")

    # Gerar relatorios
    print("\n  Gerando relatorios...")
    output_dir = config.get("output_dir")
    report_files = generate_reports(filepath, analysis, output_dir)
    if not report_files.get("error"):
        print(f"  JSON: {report_files.get('json_report')}")
        print(f"  MD:   {report_files.get('markdown_report')}")
    else:
        print(f"  Aviso: {report_files.get('error')}")

    # FASE 2: PROPOSICAO
    print_phase("FASE 2 - PROPOSICAO (2 micro-fases)",
                "2a: Identificar problemas | 2b: Sugerir solucoes")

    criteria = analysis.get("criteria", {})
    all_findings = []
    for key, value in criteria.items():
        for f in value.get("findings", []):
            all_findings.append({"criterion": key, **f})

    if all_findings:
        print(f"\n  {len(all_findings)} problema(s) identificado(s):\n")
        for i, finding in enumerate(all_findings[:5], 1):
            print(f"  {i}. [{finding['criterion']}] {finding['location']}")
            print(f"     Problema: {finding['issue'][:100]}")
            sug = finding.get('suggestion', '')
            if sug:
                print(f"     Sugestao: {sug[:100]}")
    else:
        print("\n  Nenhum problema critico encontrado automaticamente.")

    print("\n  Fase 2 concluida!")

    # FASE 3: IMPLEMENTACAO
    if no_refactor:
        print("\n  (--no-refactor: fase de implementacao ignorada)")
    else:
        should_refactor = True

        if interactive and all_findings:
            should_refactor = ask_user(
                "Deseja aplicar a refatoracao automatica?", default=False
            )

        if should_refactor:
            print_phase("FASE 3 - IMPLEMENTACAO (5 micro-fases)",
                        "3a: Setup | 3b: Refactor | 3c: Tests | 3d: Format | 3e: Validate")

            if dry_run:
                print("\n  MODO DRY-RUN: mostrando o que seria feito...\n")

            refactoring_result = refactor_file(filepath, dry_run=dry_run)

            if refactoring_result.get("error"):
                print(f"\n  Erro: {refactoring_result.get('error')}")
                sys.exit(1)

            if refactoring_result.get("diff"):
                diff = refactoring_result["diff"]
                if diff != "Sem alteracoes.":
                    print(f"\n  Diff das alteracoes:\n")
                    for line in diff.split('\n')[:20]:
                        print(f"  {line}")

            print("\n  Fase 3 concluida!")
        else:
            print("\n  Refatoracao ignorada pelo usuario.")

    # SUMARIO FINAL
    print("\n" + "="*70)
    print("  PIPELINE CONCLUIDO!")
    print("="*70)

    stem = Path(filepath).stem
    print(f"\n  Arquivos gerados:")
    print(f"    * {report_files.get('json_report', stem + '_analysis.json')}")
    print(f"    * {report_files.get('markdown_report', stem + '_report.md')}")
    if not no_refactor and not dry_run:
        print(f"    * {filepath} (modificado)")
        print(f"    * .backups/{stem}_backup.py")
    print()


if __name__ == "__main__":
    main()
