"""Post-refactoring code validator."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _read_with_fallback(path: Path) -> str:
    """Read text file with encoding fallback.

    Tries UTF-8 first, then latin-1 (which accepts every byte) to avoid
    UnicodeDecodeError on non-UTF-8 files (e.g. Windows cp1252, ISO-8859-1).
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


class CodeValidator:
    """Validates Python code after refactoring."""

    def __init__(self, filepath: str, quiet: bool = False) -> None:
        self.filepath = Path(filepath)
        self.code = _read_with_fallback(self.filepath)
        self.quiet = quiet

    def validate_syntax(self) -> Dict[str, Any]:
        try:
            compile(self.code, "<string>", "exec")
            return {"valid": True, "message": "✅ Sintaxe válida"}
        except SyntaxError as exc:
            return {"valid": False, "message": f"❌ Erro de sintaxe: {exc}"}

    def check_code_metrics(self) -> Dict[str, Any]:
        lines = self.code.split("\n")
        return {
            "total_lines": len(lines),
            "code_lines": len([ln for ln in lines if ln.strip() and not ln.strip().startswith("#")]),
            "blank_lines": len([ln for ln in lines if not ln.strip()]),
        }

    def validate(self) -> Dict[str, Any]:
        if not self.quiet:
            print(f"🔍 Validando {self.filepath.name}...\n")

        results: Dict[str, Any] = {
            "file": str(self.filepath),
            "timestamp": datetime.now().isoformat(),
            "validations": {},
        }

        if not self.quiet:
            print("  1. Verificando sintaxe...")
        results["validations"]["syntax"] = self.validate_syntax()

        if results["validations"]["syntax"]["valid"]:
            if not self.quiet:
                print("  2. Coletando métricas...")
            results["validations"]["metrics"] = self.check_code_metrics()
            results["success"] = True
        else:
            results["success"] = False

        return results


def validate_file(filepath: str, quiet: bool = False) -> Dict[str, Any]:
    return CodeValidator(filepath, quiet=quiet).validate()
