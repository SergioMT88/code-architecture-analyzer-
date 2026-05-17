#!/usr/bin/env python3
"""
Orchestrator v2.1.4 - Pipeline com config de projeto e modo interativo.

Orquestra: Identificacao (3 fases) -> Proposicao (2 fases) -> Implementacao (5 fases)
"""

import json
import sys
from pathlib import Path

from artifact_manager import ArtifactRegistry
from analyzer import run_analysis, prune_criteria
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
    "structured_outputs": True,
    "dry_run": False,
    "interactive": False,
}


def _parse_pyproject_toml(path: Path) -> dict:
    """Extrai [tool.code-analyzer] de um pyproject.toml."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            try:
                import toml as tomllib
            except ImportError:
                return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return data.get("tool", {}).get("code-analyzer", {})
    except Exception:
        return {}


def load_config(filepath: str, quiet: bool = False) -> dict:
    """Carrega config do projeto (.analyzer.json ou pyproject.toml).

    Ordem de precedencia: .analyzer.json > pyproject.toml > DEFAULT_CONFIG.
    """
    search_dirs = [
        Path(filepath).parent,
        Path(filepath).parent.parent,
        Path.cwd(),
    ]
    toml_data = {}
    json_data = {}
    for d in search_dirs:
        toml_path = d / "pyproject.toml"
        if toml_path.exists() and not toml_data:
            data = _parse_pyproject_toml(toml_path)
            if data:
                toml_data = data
                if not quiet:
                    print(f"Config carregada: {toml_path} ([tool.code-analyzer])")
        json_path = d / ".analyzer.json"
        if json_path.exists() and not json_data:
            try:
                json_data = json.loads(json_path.read_text(encoding="utf-8"))
                if not quiet:
                    print(f"Config carregada: {json_path}")
            except Exception as e:
                if not quiet:
                    print(f"Aviso: erro ao ler config {json_path}: {e}")
    merged = {**DEFAULT_CONFIG, **toml_data, **json_data}
    return merged


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


def print_phase(phase: str, subtitle: str = "", quiet: bool = False, json_mode: bool = False):
    if json_mode:
        return
    if quiet:
        print(f"\n[{phase}]")
        if subtitle:
            print(f"  {subtitle}")
        return
    print(f"\n{'='*70}")
    print(f"  {phase}")
    if subtitle:
        print(f"  {subtitle}")
    print('='*70)


def _score_bar(n: int, total: int = 10, size: int = 10) -> str:
    filled = round(n / max(total, 1) * size)
    fg = 92 if n >= 7 else 93 if n >= 5 else 91
    block = "#"
    dot = "-"
    bar = f"\033[{fg}m" + block * filled + "\033[90m" + dot * (size - filled) + "\033[0m"
    return bar

def _grade_color(grade: str) -> str:
    return {"A": "\033[92m", "B": "\033[94m", "C": "\033[93m", "D": "\033[91m"}.get(grade, "\033[0m")

def print_executive_summary(
    filepath: str,
    analysis: dict,
    artifact_registry: ArtifactRegistry,
    json_mode: bool = False,
):
    if json_mode:
        return
    criteria = analysis.get("criteria", {})
    metrics = analysis.get("metrics", {})
    scores = [v.get("score", 0) for v in criteria.values()]
    avg_score = round(sum(scores) / max(1, len(scores)), 1)
    grade = "A" if avg_score >= 9 else "B" if avg_score >= 7 else "C" if avg_score >= 5 else "D"
    critical = [(k, v) for k, v in criteria.items() if v.get("score", 10) < 5]
    warnings = [(k, v) for k, v in criteria.items() if 5 <= v.get("score", 10) < 7]
    total_findings = sum(len(v.get("findings", [])) for v in criteria.values())
    mi = metrics.get("maintainability_index", 0)
    mg = metrics.get("maintainability_grade", "N/A")

    bar = _score_bar(avg_score)
    gc = _grade_color(grade)
    print(f"\n  \033[1m{bar}  {avg_score}/10  ({gc}{grade}\033[0m\033[1m)\033[0m  \033[90m{Path(filepath).name}\033[0m")
    print(f"  \033[90m{'-'*50}\033[0m")
    print(f"  \033[90mMI:\033[0m {mi} ({mg})  "
          f"\033[91m! {len(critical)} critico(s)\033[0m  "
          f"\033[93m* {len(warnings)} aviso(s)\033[0m  "
          f"\033[94m. {total_findings} finding(s)\033[0m")
    print(f"  \033[90mSaida: {artifact_registry.run_root}\033[0m")


def print_findings_summary(analysis: dict, quiet: bool = False, json_mode: bool = False):
    """Imprime resumo dos problemas encontrados."""
    if json_mode:
        return
    criteria = analysis.get("criteria", {})
    metrics = analysis.get("metrics", {})

    print(f"\n  Maintainability Index: "
          f"{metrics.get('maintainability_index', 0)} "
          f"({metrics.get('maintainability_grade', 'N/A')})")
    print(f"  Complexidade media: {metrics.get('avg_cyclomatic_complexity', 0)}")
    print(f"  Ratio de comentarios: {metrics.get('comment_ratio', 0)}%\n")

    critical = [(k, v) for k, v in criteria.items() if v.get("score", 10) < 5]
    warnings = [(k, v) for k, v in criteria.items() if 5 <= v.get("score", 10) < 7]

    if quiet:
        print(f"  Criticos: {len(critical)} | Avisos: {len(warnings)}")
        return

    if critical:
        crit_mark = "!"
        crit_tag = f"\n  \033[1m\033[91m{crit_mark} CRITICO ({len(critical)} criterios):\033[0m"
        print(crit_tag)
        for key, val in critical:
            score = val.get("score", 0)
            n = len(val.get("findings", []))
            print(f"    {_score_bar(score)} \033[91m{key}\033[0m ({n} problemas)")
            for finding in val.get("findings", [])[:2]:
                loc = finding.get("location", "")
                iss = finding.get("issue", "")[:80]
                print(f"      \033[90m[{loc}]\033[0m {iss}")

    if warnings:
        warn_mark = "*"
        warn_tag = f"\n  \033[1m\033[93m{warn_mark} AVISO ({len(warnings)} criterios):\033[0m"
        print(warn_tag)
        for key, val in warnings:
            score = val.get("score", 0)
            n = len(val.get("findings", []))
            print(f"    {_score_bar(score)} \033[93m{key}\033[0m ({n} problemas)")

    ok_count = sum(1 for v in criteria.values() if v.get("score", 10) >= 7)
    if ok_count:
        ok_mark = "."
        print(f"  \033[92m{ok_mark} {ok_count} criterios OK\033[0m")

    tool_findings = analysis.get("tool_findings", {})
    total_tools = tool_findings.get("total", 0)
    if total_tools:
        print(f"\n  \033[94mFerramentas externas:\033[0m {total_tools} ocorrencias "
              f"(ruff: {len(tool_findings.get('ruff', []))}, "
              f"pylint: {len(tool_findings.get('pylint', []))})")
    tool_warnings = analysis.get("tool_warnings", [])
    for w in tool_warnings:
        warn_sym = "!"
        print(f"  \033[93m{warn_sym}\033[0m {w}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python orchestrator.py <arquivo.py> [opcoes]")
        print("Opcoes:")
        print("  --no-refactor   Apenas analisa, sem refatorar")
        print("  --dry-run       Mostra o que seria feito sem aplicar")
        print("  --interactive   Modo interativo (aceitar/rejeitar sugestoes)")
        print("  --output <dir>  Diretorio base para artefatos")
        print("  --quiet         Menos verbosidade no terminal")
        print("  --json          Saida JSON para integracoes com outros CLIs")
        print("  --html          Gera dashboard HTML visual (opcional)")
        sys.exit(1)

    filepath = sys.argv[1]
    no_refactor = "--no-refactor" in sys.argv
    dry_run = "--dry-run" in sys.argv
    interactive = "--interactive" in sys.argv
    quiet = "--quiet" in sys.argv
    json_mode = "--json" in sys.argv
    generate_html = "--html" in sys.argv
    output_dir = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_dir = sys.argv[idx + 1]

    config = load_config(filepath, quiet=quiet or json_mode)
    if dry_run:
        config["dry_run"] = True
    if interactive:
        config["interactive"] = True
    if quiet:
        config["quiet"] = True
    if json_mode:
        config["quiet"] = True
    if output_dir:
        config["output_dir"] = output_dir

    structured_outputs = config.get("structured_outputs", True)
    artifact_registry = ArtifactRegistry(
        filepath,
        output_dir=config.get("output_dir"),
        structured_outputs=structured_outputs,
    )

    if json_mode:
        pass
    elif quiet:
        print("\nCODE ARCHITECTURE ANALYZER v2.1.4")
        print(f"Arquivo: {filepath}")
        print(f"Saida: {artifact_registry.run_root}")
        if dry_run:
            print("Modo: DRY-RUN")
        if interactive:
            print("Modo: INTERATIVO")
    else:
        print("\n" + "="*70)
        print("  CODE ARCHITECTURE ANALYZER v2.1.4 - PIPELINE COMPLETO")
        print(f"  Arquivo: {filepath}")
        print(f"  Saida: {artifact_registry.run_root}")
        if dry_run:
            print("  MODO: DRY-RUN (nenhum arquivo sera modificado)")
        if interactive:
            print("  MODO: INTERATIVO")
        print("="*70)

    # FASE 1: IDENTIFICACAO
    print_phase("FASE 1 - IDENTIFICACAO (3 micro-fases)",
                "1a: AST Scanning | 1b: Pylint | 1c: Ruff",
                quiet=quiet, json_mode=json_mode)

    analysis = run_analysis(filepath, config)

    if not analysis.get("success", False):
        if json_mode:
            print(json.dumps({
                "success": False,
                "file": filepath,
                "error": analysis.get("error"),
            }, ensure_ascii=True, default=str))
            sys.exit(1)
        print(f"\nErro: {analysis.get('error')}")
        sys.exit(1)

    print_executive_summary(filepath, analysis, artifact_registry, json_mode=json_mode)
    print_findings_summary(analysis, quiet=config.get("quiet", False), json_mode=json_mode)
    if not json_mode:
        print("\n  Fase 1 concluida!")

    # Gerar relatorios
    report_files = generate_reports(
        filepath,
        analysis,
        output_dir=config.get("output_dir"),
        artifact_registry=artifact_registry,
        generate_html=generate_html,
    )
    if report_files.get("error"):
        if json_mode:
            print(json.dumps({
                "success": False,
                "file": filepath,
                "error": report_files.get("error"),
                "report_files": report_files,
                "analysis": analysis,
            }, ensure_ascii=True, default=str))
        else:
            print(f"\nErro ao gerar relatorios: {report_files.get('error')}")
            if report_files.get("log_file"):
                print(f"  Log: {report_files.get('log_file')}")
        sys.exit(1)

    if not json_mode:
        print("\n  Gerando relatorios...")
        print(f"  JSON:  {report_files.get('json_report')}")
        print(f"  MD:    {report_files.get('markdown_report')}")
        if report_files.get("html_report"):
            print(f"  HTML:  {report_files.get('html_report')}")
        if report_files.get("manifest"):
            print(f"  Manifest: {report_files.get('manifest')}")

    # FASE 2: PROPOSICAO
    print_phase("FASE 2 - PROPOSICAO (2 micro-fases)",
                "2a: Identificar problemas | 2b: Sugerir solucoes",
                quiet=quiet, json_mode=json_mode)

    criteria = analysis.get("criteria", {})
    all_findings = []
    refactoring_result = None
    for key, value in criteria.items():
        for f in value.get("findings", []):
            all_findings.append({"criterion": key, **f})

    if all_findings and not json_mode:
        print(f"\n  {len(all_findings)} problema(s) identificado(s):\n")
        max_findings = 3 if config.get("quiet") else 5
        for i, finding in enumerate(all_findings[:max_findings], 1):
            print(f"  {i}. [{finding['criterion']}] {finding['location']}")
            print(f"     Problema: {finding['issue'][:100]}")
            sug = finding.get('suggestion', '')
            if sug:
                print(f"     Sugestao: {sug[:100]}")
    elif not json_mode:
        print("\n  Nenhum problema critico encontrado automaticamente.")

    if not json_mode:
        print("\n  Fase 2 concluida!")

    # FASE 3: IMPLEMENTACAO
    if no_refactor:
        if not json_mode:
            print("\n  (--no-refactor: fase de implementacao ignorada)")
    else:
        should_refactor = True

        if interactive and all_findings:
            should_refactor = ask_user(
                "Deseja aplicar a refatoracao automatica?", default=False
            )

        if should_refactor:
            print_phase("FASE 3 - IMPLEMENTACAO (5 micro-fases)",
                        "3a: Setup | 3b: Refactor | 3c: Tests | 3d: Format | 3e: Validate",
                        quiet=quiet, json_mode=json_mode)

            if dry_run and not json_mode:
                print("\n  MODO DRY-RUN: mostrando o que seria feito...\n")

            refactoring_result = refactor_file(
                filepath,
                dry_run=dry_run,
                output_dir=config.get("output_dir"),
                structured_outputs=structured_outputs,
                artifact_registry=artifact_registry,
                quiet=quiet,
            )

            if refactoring_result.get("error"):
                if json_mode:
                    print(json.dumps({
                        "success": False,
                        "file": filepath,
                        "error": refactoring_result.get("error"),
                        "report_files": report_files,
                    }, ensure_ascii=True, default=str))
                    sys.exit(1)
                print(f"\n  Erro: {refactoring_result.get('error')}")
                sys.exit(1)

            if refactoring_result.get("diff") and not json_mode:
                diff = refactoring_result["diff"]
                if diff != "Sem alteracoes.":
                    print("\n  Diff das alteracoes:\n")
                    for line in diff.split('\n')[:20]:
                        print(f"  {line}")

            if not json_mode:
                print("\n  Fase 3 concluida!")
        elif not json_mode:
            print("\n  Refatoracao ignorada pelo usuario.")

    # SUMARIO FINAL
    if json_mode:
        payload = {
            "success": True,
            "file": filepath,
            "mode": {
                "no_refactor": no_refactor,
                "dry_run": dry_run,
                "interactive": interactive,
                "quiet": quiet,
            },
            "artifact_root": str(artifact_registry.run_root),
            "analysis": prune_criteria(analysis),
            "report_files": report_files,
        }
        if refactoring_result is not None:
            payload["refactoring"] = refactoring_result
        print(json.dumps(payload, ensure_ascii=True, default=str))
        return

    if quiet:
        print("\nPIPELINE CONCLUIDO")
    else:
        print("\n" + "="*70)
        print("  PIPELINE CONCLUIDO!")
        print("="*70)

    stem = Path(filepath).stem
    print("\n\033[1mResumo final\033[0m")
    print(f"  \033[94mJSON:\033[0m  {report_files.get('json_report', stem + '_analysis.json')}")
    print(f"  \033[94mMD:\033[0m    {report_files.get('markdown_report', stem + '_report.md')}")
    if report_files.get("html_report"):
        print(f"  \033[94mHTML:\033[0m  {report_files.get('html_report')}")
    if report_files.get("manifest"):
        print(f"  Manifest: {report_files.get('manifest')}")
    if not no_refactor and not dry_run:
        print(f"  Arquivo modificado: {filepath}")
        print(f"  Backup: {artifact_registry.backups_dir / f'{stem}_backup.py'}")
    print()


if __name__ == "__main__":
    main()
