#!/usr/bin/env python3
"""
Validator - Validação pós-refatoração
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any


class CodeValidator:
    """Valida código após refatoração"""

    def __init__(self, filepath: str, quiet: bool = False):
        self.filepath = Path(filepath)
        self.code = self.filepath.read_text(encoding='utf-8')
        self.results = {}
        self.quiet = quiet

    def validate_syntax(self) -> Dict[str, Any]:
        """Valida sintaxe Python"""
        try:
            compile(self.code, '<string>', 'exec')
            return {
                "valid": True,
                "message": "✅ Sintaxe válida"
            }
        except SyntaxError as e:
            return {
                "valid": False,
                "message": f"❌ Erro de sintaxe: {e}"
            }

    def check_code_metrics(self) -> Dict[str, Any]:
        """Coleta métricas do código"""
        lines = self.code.split('\n')
        code_lines = len([ln for ln in lines if ln.strip() and not ln.strip().startswith('#')])
        blank_lines = len([ln for ln in lines if not ln.strip()])

        return {
            "total_lines": len(lines),
            "code_lines": code_lines,
            "blank_lines": blank_lines
        }

    def validate(self) -> Dict[str, Any]:
        """Executa todas as validações"""
        if not self.quiet:
            print(f"🔍 Validando {self.filepath.name}...\n")

        results = {
            "file": str(self.filepath),
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "validations": {}
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
    """Função principal"""
    validator = CodeValidator(filepath, quiet=quiet)
    return validator.validate()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validator.py <arquivo.py>")
        sys.exit(1)

    is_json = "--json" in sys.argv
    result = validate_file(sys.argv[1], quiet="--quiet" in sys.argv or is_json)
    if is_json:
        print(json.dumps(result, ensure_ascii=True, default=str))
    else:
        print(json.dumps(result, indent=2, default=str))
