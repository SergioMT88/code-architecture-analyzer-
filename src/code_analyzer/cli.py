"""CLI entry point — dispatches subcommands to the pipeline modules."""
from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

from code_analyzer.config import DEFAULT_CONFIG
from code_analyzer.orchestrator import main as orchestrator_main, build_parser


def _load_version() -> str:
    package_json = Path(__file__).resolve().parents[3] / "package.json"
    try:
        return str(json.loads(package_json.read_text(encoding="utf-8")).get("version", "0.0.0"))
    except Exception:
        return "0.0.0"


def _emit(obj: dict, json_mode: bool) -> None:
    if not json_mode:
        return
    sys.stdout.write(json.dumps(obj, ensure_ascii=True, default=str) + "\n")


def _print_usage(json_mode: bool = False) -> None:
    if json_mode:
        _emit({
            "success": True,
            "usage": "code-analyze <arquivo.py> [opcoes]",
            "commands": ["analyze", "check", "refactor", "validate", "init", "info", "setup"],
        }, json_mode)
    else:
        print("Uso: code-analyze <arquivo.py> [opcoes]")
        print("Ou:  code-analyze <comando> <arquivo.py> [opcoes]")
        print("Comandos: analyze, check, refactor, validate, init, info, setup")


def _handle_init(json_mode: bool = False) -> int:
    config_path = Path.cwd() / ".analyzer.json"
    if config_path.exists():
        _emit({"success": False, "error": f"Arquivo ja existe: {config_path}"}, json_mode)
        return 0
    config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
    _emit({"success": True, "file": str(config_path), "message": "Config criada"}, json_mode)
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
    packages = ["pylint", "ruff", "black", "isort", "pytest"]
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

    target = Path(command)
    if target.suffix == ".py" or target.exists():
        return _run_orchestrator(argv)

    _emit({"success": False, "error": f"Comando nao reconhecido: {command}"}, json_mode)
    return 1


def main() -> None:
    raise SystemExit(dispatch(sys.argv[1:]))


if __name__ == "__main__":
    main()
