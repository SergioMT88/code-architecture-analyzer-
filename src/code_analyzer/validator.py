"""Post-refactoring code validator."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class CodeValidator:
    """Validates Python code after refactoring."""

    def __init__(self, filepath: str, quiet: bool = False) -> None:
        self.filepath = Path(filepath)
        self.code = self.filepath.read_text(encoding="utf-8")
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
            results["status"] = "success"
        else:
            results["status"] = "failed"

        return results


def validate_file(filepath: str, quiet: bool = False) -> Dict[str, Any]:
    return CodeValidator(filepath, quiet=quiet).validate()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validator.py <arquivo.py>")
        sys.exit(1)
    is_json = "--json" in sys.argv
    result = validate_file(sys.argv[1], quiet="--quiet" in sys.argv or is_json)
    print(json.dumps(result, indent=2 if not is_json else None, default=str))
