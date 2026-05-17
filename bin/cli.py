#!/usr/bin/env python3

"""
Code Architecture Analyzer CLI entrypoint in Python.
"""

import json
import platform
import runpy
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from orchestrator import DEFAULT_CONFIG  # noqa: E402


def load_version() -> str:
    package_json = ROOT / "package.json"
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
        return str(data.get("version", "0.0.0"))
    except Exception:
        return "0.0.0"


def emit(obj: dict, json_mode: bool):
    if not json_mode:
        return
    sys.stdout.write(json.dumps(obj, ensure_ascii=True, default=str) + "\n")


def print_usage(json_mode: bool = False) -> None:
    if json_mode:
        emit({
            "success": True,
            "usage": "code-analyze <arquivo.py> [opcoes]",
            "commands": ["analyze", "check", "refactor", "validate", "init", "info", "setup"],
        }, json_mode)
    else:
        print("Uso: code-analyze <arquivo.py> [opcoes]")
        print("Ou:  code-analyze <comando> <arquivo.py> [opcoes]")
        print("Comandos: analyze, check, refactor, validate, init, info, setup")


def run_script(module_name: str, args: list[str]) -> None:
    old_argv = sys.argv[:]
    try:
        sys.argv = [f"{module_name}.py", *args]
        runpy.run_module(module_name, run_name="__main__")
    finally:
        sys.argv = old_argv


def handle_init(json_mode: bool = False) -> int:
    config_path = Path.cwd() / ".analyzer.json"
    if config_path.exists():
        emit({"success": False, "error": f"Arquivo ja existe: {config_path}"}, json_mode)
        return 0
    config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
    emit({"success": True, "file": str(config_path), "message": "Config criada"}, json_mode)
    return 0


def handle_info(json_mode: bool = False) -> int:
    version = load_version()
    emit({
        "success": True,
        "version": version,
        "python": sys.executable,
        "python_version": platform.python_version(),
        "platform": sys.platform,
        "working_dir": str(Path.cwd()),
    }, json_mode)
    return 0


def handle_setup(json_mode: bool = False) -> int:
    packages = ["pylint", "ruff", "black", "isort", "pytest"]
    cmd = [sys.executable, "-m", "pip", "install", *packages]
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=json_mode, text=json_mode)
    emit({
        "success": result.returncode == 0,
        "packages": packages,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }, json_mode)
    return result.returncode


def dispatch(argv: list[str]) -> int:
    json_mode = "--json" in argv

    if not argv or argv[0] in {"-h", "--help"}:
        print_usage(json_mode=json_mode)
        return 0

    if argv[0] in {"-v", "--version"}:
        emit({"success": True, "version": load_version()}, json_mode)
        return 0

    command = argv[0]
    args = argv[1:]

    if command in {"analyze", "a"}:
        if not args:
            emit({"success": False, "error": "Arquivo nao especificado"}, json_mode)
            return 1
        run_script("orchestrator", args)
        return 0

    if command in {"check", "c"}:
        if not args:
            emit({"success": False, "error": "Arquivo nao especificado"}, json_mode)
            return 1
        run_script("orchestrator", [args[0], "--no-refactor", *args[1:]])
        return 0

    if command in {"refactor", "r"}:
        if not args:
            emit({"success": False, "error": "Arquivo nao especificado"}, json_mode)
            return 1
        run_script("refactorer", args)
        return 0

    if command in {"validate", "v"}:
        if not args:
            emit({"success": False, "error": "Arquivo nao especificado"}, json_mode)
            return 1
        run_script("validator", args)
        return 0

    if command == "init":
        return handle_init(json_mode=json_mode)

    if command == "info":
        return handle_info(json_mode=json_mode)

    if command == "setup":
        return handle_setup(json_mode=json_mode)

    target = Path(command)
    if target.suffix == ".py" or target.exists():
        run_script("orchestrator", argv)
        return 0

    emit({"success": False, "error": f"Comando nao reconhecido: {command}"}, json_mode)
    return 1


def main() -> None:
    raise SystemExit(dispatch(sys.argv[1:]))


if __name__ == "__main__":
    main()
