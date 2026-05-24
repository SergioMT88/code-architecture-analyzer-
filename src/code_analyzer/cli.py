"""CLI entry point — dispatches subcommands to the pipeline modules."""
from __future__ import annotations

import io
import json
import logging
import platform
import subprocess
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

from code_analyzer import __version__
from code_analyzer.config import DEFAULT_CONFIG
from code_analyzer.orchestrator import main as orchestrator_main, build_parser


def _load_version() -> str:
    return __version__


def _emit(obj: dict, json_mode: bool) -> None:
    if not json_mode:
        return
    sys.stdout.write(json.dumps(obj, ensure_ascii=True, default=str) + "\n")


def _print_usage(json_mode: bool = False) -> None:
    commands = ["analyze", "check", "refactor", "validate", "init", "info", "setup", "history", "dup", "project"]
    if json_mode:
        _emit({
            "success": True,
            "usage": "code-analyze <arquivo.py> [opcoes]",
            "commands": commands,
        }, json_mode)
    else:
        print("Uso: code-analyze <arquivo.py> [opcoes]")
        print("Ou:  code-analyze <comando> [args] [opcoes]")
        print()
        print("Comandos:")
        print("  analyze  <arquivo.py>        Analisa e refatora")
        print("  check    <arquivo.py>        Analisa sem refatorar")
        print("  refactor <arquivo.py>        Refatora sem analisar")
        print("  validate <arquivo.py>        Valida sintaxe")
        print("  dup      <a.py> <b.py>       Duplicacao semantica entre 2 arquivos")
        print("  project  <diretorio/>        Duplicacao cross-file em todo o projeto")
        print("  history  <arquivo.py>        Historico de scores do arquivo")
        print("  init                         Cria .analyzer.json e pre-commit hook")
        print("  info                         Versao e ambiente")
        print("  setup                        Instala dependencias (ruff, pytest...)")


def _detect_project_type(cwd: Path) -> str:
    if (cwd / "manage.py").exists():
        return "django"
    candidates = list(cwd.glob("requirements*.txt"))
    req_dir = cwd / "requirements"
    if req_dir.is_dir():
        candidates.extend(req_dir.glob("*.txt"))
    for fname in ("pyproject.toml", "setup.py", "setup.cfg", "Pipfile"):
        p = cwd / fname
        if p.exists():
            candidates.append(p)
    for path in candidates:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            for proj_type, keywords in (("django", ["django"]), ("fastapi", ["fastapi"]), ("flask", ["flask"])):
                if any(kw in content for kw in keywords):
                    return proj_type
        except Exception:
            _log.debug("Failed to read %s for project type detection", path, exc_info=True)
            pass
    return "generic"


def _smart_config(project_type: str) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    cfg["architecture_style"] = project_type
    cfg["min_score"] = 7.0
    return cfg


def _write_precommit(cwd: Path, min_score: float, version: str) -> tuple:
    path = cwd / ".pre-commit-config.yaml"
    if path.exists():
        return path, False
    path.write_text(
        "repos:\n"
        f"  - repo: https://github.com/SergioMT88/code-architecture-analyzer-\n"
        f"    rev: v{version}\n"
        f"    hooks:\n"
        f"      - id: code-analyze\n"
        f"        args: [--no-refactor, --quiet, --min-score={min_score}]\n",
        encoding="utf-8",
    )
    return path, True


def _handle_init(json_mode: bool = False) -> int:
    from code_analyzer.agents_rules import generate_agents_md

    cwd = Path.cwd()
    project_type = _detect_project_type(cwd)
    cfg = _smart_config(project_type)
    min_score = cfg["min_score"]
    version = _load_version()

    config_path = cwd / ".analyzer.json"
    config_created = not config_path.exists()
    if config_created:
        config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    precommit_path, precommit_created = _write_precommit(cwd, min_score, version)

    agents_path = cwd / "AGENTS.md"
    agents_created = not agents_path.exists()
    if agents_created:
        agents_path.write_text(generate_agents_md(project_type, version), encoding="utf-8")

    if json_mode:
        _emit({
            "success": True,
            "project_type": project_type,
            "analyzer_config": str(config_path),
            "analyzer_config_created": config_created,
            "precommit_config": str(precommit_path),
            "precommit_config_created": precommit_created,
            "agents_md": str(agents_path),
            "agents_md_created": agents_created,
        }, json_mode)
        return 0

    type_label = {"django": "Django", "flask": "Flask", "fastapi": "FastAPI"}.get(project_type, "Python generico")
    print(f"\n  Code Architecture Analyzer — Configuracao Inteligente")
    print(f"\n  Projeto detectado: {type_label}\n")

    if config_created:
        print(f"  Criado:   .analyzer.json")
        print(f"            architecture_style: {project_type} | min_score: {min_score}")
    else:
        print(f"  Mantido:  .analyzer.json  (ja existia)")

    if agents_created:
        print(f"\n  Criado:   AGENTS.md")
        print(f"            Regras do projeto validaveis por code-analyze check")
        print(f"            Edite a secao ## [rules] com as regras do seu projeto")
    else:
        print(f"\n  Mantido:  AGENTS.md  (ja existia)")

    if precommit_created:
        print(f"\n  Criado:   .pre-commit-config.yaml")
        print(f"            Hook: code-analyze --min-score {min_score} --no-refactor --quiet")
    else:
        print(f"\n  Mantido:  .pre-commit-config.yaml  (ja existia)")

    print(f"\n  Proximos passos:")
    print(f"    1. Edite AGENTS.md — adicione as regras especificas do seu projeto")
    print(f"    2. pip install pre-commit && pre-commit install")
    print(f"    Pronto — cada commit valida codigo e regras automaticamente.\n")
    return 0


def _handle_info(json_mode: bool = False) -> int:
    _emit({
        "success": True,
        "version": _load_version(),
        "python": sys.executable,
        "python_version": platform.python_version(),
        "platform": sys.platform,
        "working_dir": str(Path.cwd()),
    }, json_mode)
    return 0


def _handle_setup(json_mode: bool = False) -> int:
    packages = ["ruff", "black", "isort", "pytest"]
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", *packages],
        cwd=str(root),
        capture_output=json_mode,
        text=json_mode,
    )
    _emit({
        "success": result.returncode == 0,
        "packages": packages,
        "returncode": result.returncode,
        "stdout": result.stdout if json_mode else "",
        "stderr": result.stderr if json_mode else "",
    }, json_mode)
    return result.returncode


def _run_orchestrator(argv: list) -> int:
    old = sys.argv[:]
    try:
        sys.argv = ["code-analyze", *argv]
        orchestrator_main()
        return 0
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0
    finally:
        sys.argv = old


def _run_refactorer(argv: list) -> int:
    from code_analyzer.refactorer import refactor_file
    import json as _json
    json_mode = "--json" in argv
    dry_run = "--dry-run" in argv
    quiet = "--quiet" in argv or json_mode
    filepath = next((a for a in argv if not a.startswith("--")), None)
    if not filepath:
        _emit({"success": False, "error": "Arquivo nao especificado"}, json_mode)
        return 1
    result = refactor_file(filepath, dry_run=dry_run, quiet=quiet)
    if json_mode:
        sys.stdout.write(_json.dumps(result, ensure_ascii=True, default=str) + "\n")
    return 1 if result.get("error") else 0


def _run_validator(argv: list) -> int:
    from code_analyzer.validator import validate_file
    import json as _json
    json_mode = "--json" in argv
    quiet = "--quiet" in argv or json_mode
    filepath = next((a for a in argv if not a.startswith("--")), None)
    if not filepath:
        _emit({"success": False, "error": "Arquivo nao especificado"}, json_mode)
        return 1
    result = validate_file(filepath, quiet=quiet)
    if json_mode:
        sys.stdout.write(_json.dumps(result, ensure_ascii=True, default=str) + "\n")
    return 0 if result.get("status") == "success" else 1


def _run_history(argv: list) -> int:
    from datetime import datetime
    from code_analyzer.history import load_history
    json_mode = "--json" in argv
    raw_path = next((a for a in argv if not a.startswith("--")), None)
    if not raw_path:
        _emit({"success": False, "error": "Arquivo nao especificado"}, json_mode)
        return 1
        
    filepath = Path(raw_path).resolve()
    snapshots = load_history(str(filepath))
    
    if json_mode:
        _emit({"success": True, "history": snapshots}, json_mode)
        return 0
        
    if not snapshots:
        print(f"\n  Nenhum histórico encontrado para o arquivo: {raw_path}")
        return 0
        
    print(f"\n  Histórico de evolução para: {filepath.name}")
    print("  " + "-" * 95)
    print("  " + f"{'Execução (Data/Hora)':<20} | {'MI':<4} | {'Grade':<5} | {'Critérios com problemas (Score < 10)'}")
    print("  " + "-" * 95)
    
    for s in snapshots:
        ts_str = s.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts_str)
            dt_display = dt.strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            _log.debug("Failed to parse timestamp from snapshot", exc_info=True)
            dt_display = ts_str[:19].replace("T", " ")
            
        mi = s.get("maintainability_index", 100.0)
        grade = s.get("maintainability_grade", "A")
        
        problems = []
        for k, v in s.get("scores", {}).items():
            if v < 10.0:
                problems.append(f"{k} ({v:.1f})")
        problems_str = ", ".join(problems) if problems else "Nenhum"
        
        print("  " + f"{dt_display:<20} | {int(mi):<4} | {grade:<5} | {problems_str}")
        
    print("  " + "-" * 95 + "\n")
    return 0


def _run_duplication_check(argv: list) -> int:
    from code_analyzer.analyzer.semantic import compare_files

    json_mode = "--json" in argv
    files = [a for a in argv if not a.startswith("--")]
    if len(files) < 2:
        _emit({"success": False, "error": "Especifique 2 arquivos: code-analyze dup a.py b.py"}, json_mode)
        return 1

    result = compare_files(files[0], files[1])
    duplicates = result.get("duplicates", [])

    if json_mode:
        _emit({"success": True, "duplicates": duplicates}, json_mode)
        return 0

    if not duplicates:
        print("\n  Nenhuma duplicacao semantica encontrada entre os arquivos.")
        return 0

    print(f"\n  {len(duplicates)} grupo(s) de duplicacao encontrado(s):")
    for i, d in enumerate(duplicates, 1):
        funcs = d.get("functions", [])
        names = " | ".join(f"{f['name']} ({f['file']}:{f['lineno']})" for f in funcs)
        print(f"  {i}. {names}")
        print(f"     Sugestao: consolide em uma unica funcao parametrizavel.\n")
    return 0


def _run_project_check(argv: list) -> int:
    from code_analyzer.analyzer.semantic import compare_directory

    json_mode = "--json" in argv
    dirpath = next((a for a in argv if not a.startswith("--")), None)
    if not dirpath:
        _emit({"success": False, "error": "Diretorio nao especificado. Uso: code-analyze project <dir>"}, json_mode)
        return 1

    from pathlib import Path as _Path
    if not _Path(dirpath).is_dir():
        _emit({"success": False, "error": f"Diretorio nao encontrado: {dirpath}"}, json_mode)
        return 1

    # --threshold 0.9 (default 1.0 = exact match only)
    threshold = 1.0
    for i, a in enumerate(argv):
        if a == "--threshold" and i + 1 < len(argv):
            try:
                threshold = float(argv[i + 1])
                threshold = max(0.0, min(1.0, threshold))
            except ValueError:
                pass

    result = compare_directory(dirpath, threshold=threshold)
    duplicates = result.get("duplicates", [])

    if json_mode:
        _emit({"success": True, **result}, json_mode)
        return 0

    thr_str = f" (threshold: {threshold:.0%})" if threshold < 1.0 else ""
    print(f"\n  CODE ARCHITECTURE ANALYZER — Modo Projeto{thr_str}")
    print(f"  Diretorio: {result['dirpath']}")
    print(f"  Arquivos analisados: {result['files_scanned']} | Funcoes: {result['functions_analyzed']}")
    print(f"  Duplicacoes cross-file: {result['duplicate_count']}\n")

    if not duplicates:
        print("  Nenhuma duplicacao semantica encontrada entre arquivos.")
        return 0

    mode_label = "similares" if threshold < 1.0 else "identicas"
    print(f"  Top duplicacoes (estrutura de funcao {mode_label} em arquivos diferentes):\n")
    for i, dup in enumerate(duplicates[:10], 1):
        funcs = dup.get("functions", [])
        files = dup.get("files", [])
        func_names = " | ".join(
            f"\033[94m{f['name']}\033[0m ({_Path(f['file']).name}:{f['lineno']})"
            for f in funcs[:4]
        )
        sim = dup.get("similarity", 1.0)
        sim_str = f" \033[90m[{sim:.0%} similar]\033[0m" if sim < 1.0 else ""
        print(f"  {i}. {func_names}{sim_str}")
        if len(files) > 1:
            print(f"     \033[90mArquivos: {', '.join(_Path(fp).name for fp in files)}\033[0m")
        print(f"     \033[92mSugestao:\033[0m Consolide em uma unica funcao parametrizavel.\n")

    return 0


def dispatch(argv: list) -> int:
    json_mode = "--json" in argv

    if not argv or argv[0] in {"-h", "--help"}:
        _print_usage(json_mode)
        return 0

    if argv[0] in {"-v", "--version"}:
        _emit({"success": True, "version": _load_version()}, json_mode)
        return 0

    command = argv[0]
    args = argv[1:]

    if command in {"analyze", "a"}:
        if not args:
            _emit({"success": False, "error": "Arquivo nao especificado"}, json_mode)
            return 1
        return _run_orchestrator(args)

    if command in {"check", "c"}:
        if not args:
            _emit({"success": False, "error": "Arquivo nao especificado"}, json_mode)
            return 1
        return _run_orchestrator([args[0], "--no-refactor", *args[1:]])

    if command in {"refactor", "r"}:
        if not args:
            _emit({"success": False, "error": "Arquivo nao especificado"}, json_mode)
            return 1
        return _run_refactorer(args)

    if command in {"validate", "v"}:
        if not args:
            _emit({"success": False, "error": "Arquivo nao especificado"}, json_mode)
            return 1
        return _run_validator(args)

    if command == "init":
        return _handle_init(json_mode)

    if command == "info":
        return _handle_info(json_mode)

    if command == "setup":
        return _handle_setup(json_mode)

    if command == "history":
        if not args:
            _emit({"success": False, "error": "Arquivo nao especificado"}, json_mode)
            return 1
        return _run_history(args)

    if command == "dup":
        if not args:
            _emit({"success": False, "error": "Uso: code-analyze dup <a.py> <b.py>"}, json_mode)
            if not json_mode:
                print("Uso: code-analyze dup <a.py> <b.py>")
            return 1
        return _run_duplication_check(args)

    if command == "project":
        if not args:
            _emit({"success": False, "error": "Uso: code-analyze project <diretorio/>"}, json_mode)
            if not json_mode:
                print("Uso: code-analyze project <diretorio/>")
            return 1
        return _run_project_check(args)

    target = Path(command)
    if target.suffix == ".py" or target.exists():
        return _run_orchestrator(argv)

    _emit({"success": False, "error": f"Comando nao reconhecido: {command}"}, json_mode)
    return 1


def _fix_windows_encoding() -> None:
    """Força UTF-8 no stdout/stderr para evitar UnicodeEncodeError em terminais cp1252."""
    def _needs_fix(stream: object) -> bool:
        if not hasattr(stream, "buffer"):
            return False
        enc = getattr(stream, "encoding", "") or ""
        return enc.lower().replace("-", "") != "utf8"

    if _needs_fix(sys.stdout):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True  # type: ignore[union-attr]
        )
    if _needs_fix(sys.stderr):
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True  # type: ignore[union-attr]
        )


def main() -> None:
    _fix_windows_encoding()
    raise SystemExit(dispatch(sys.argv[1:]))


if __name__ == "__main__":
    main()
