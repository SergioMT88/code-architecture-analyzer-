#!/usr/bin/env python3
"""
Orchestrator - Coordena todas as fases
Orquestra: Análise (3 fases) → Proposição (2 fases) → Implementação (5 fases)
"""

import sys
from pathlib import Path
from analyzer import run_analysis
from refactorer import refactor_file
from report_generator import generate_reports


def main():
    if len(sys.argv) < 2:
        print("Uso: python orchestrator.py <arquivo.py>")
        sys.exit(1)

    filepath = sys.argv[1]
    no_refactor = "--no-refactor" in sys.argv

    print("\n" + "="*70)
    print("=  CODE ARCHITECTURE ANALYZER - PIPELINE COMPLETO")
    print("=  Analisando:", filepath)
    print("="*70 + "\n")

    # PHASE 1: IDENTIFICATION (3 micro-phases)
    print("="*70)
    print("PHASE 1 - IDENTIFICATION (3 micro-phases)")
    print("="*70)
    print("1a: AST Scanning")
    print("1b: Pylint Analysis")
    print("1c: Ruff Validation\n")

    analysis_result = run_analysis(filepath)

    if not analysis_result.get("success", False):
        error_msg = analysis_result.get('error')
        print(f"Error: {error_msg}")
        sys.exit(1)

    print("Phase 1 completed!\n")

    # Generate reports
    print("Generating reports...")
    report_files = generate_reports(filepath, analysis_result)
    json_report = report_files.get('json_report')
    md_report = report_files.get('markdown_report')
    print(f"   Reports: {json_report} and {md_report}\n")

    # PHASE 2: PROPOSITION (2 micro-phases)
    print("="*70)
    print("PHASE 2 - PROPOSITION (2 micro-phases)")
    print("="*70)
    print("2a: Explain the Problem")
    print("2b: Proposed Solution\n")

    criteria = analysis_result.get("criteria", {})
    problems = [c for c, v in criteria.items() if v.get("score", 10) < 8]

    if problems:
        problem_list = ', '.join(problems)
        print(f"Problems found in: {problem_list}\n")
    else:
        print("No critical problems found!\n")

    print("Phase 2 completed!\n")

    # PHASE 3: IMPLEMENTATION (5 micro-phases)
    if not no_refactor:
        print("="*70)
        print("PHASE 3 - IMPLEMENTATION (5 micro-phases)")
        print("="*70)

        refactoring_result = refactor_file(filepath)

        if refactoring_result.get("error"):
            error_msg = refactoring_result.get('error')
            print(f"Error: {error_msg}")
            sys.exit(1)

        print("Phase 3 completed!\n")

    print("="*70)
    print("=  ANALYSIS COMPLETED SUCCESSFULLY!")
    print("="*70)

    print(f"\nGenerated files:")
    print(f"   * {filepath} (analyzed/refactored)")
    print(f"   * {Path(filepath).stem}_analysis.json")
    print(f"   * {Path(filepath).stem}_report.md")
    if not no_refactor:
        backup_path = f".backups/{Path(filepath).stem}_backup.py"
        print(f"   * {backup_path}\n")
    else:
        print()


if __name__ == "__main__":
    main()
