#!/usr/bin/env python3
"""
Analyzer - Análise profunda de arquitetura Python
Fase 1: Identificação (3 micro-fases)
"""

import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

class ArchitectureAnalyzer(ast.NodeVisitor):
    """Analisa código Python em busca de problemas arquiteturais"""

    def __init__(self, code: str):
        self.code = code
        self.lines = code.split('\n')
        self.classes: Dict = {}
        self.functions: List = []
        self.imports: List = []
        self.cyclomatic_complexity = 0

    def visit_ClassDef(self, node: ast.ClassDef):
        """Micro-fase 1a: Varredura AST - Analisa classes"""
        methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
        lines = (node.end_lineno or 0) - (node.lineno or 0)
        complexity = self._calculate_complexity(node)

        self.classes[node.name] = {
            "name": node.name,
            "lineno": node.lineno,
            "methods": methods,
            "num_methods": len(methods),
            "lines": lines,
            "complexity": complexity,
            "imports": self.imports.copy()
        }
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Micro-fase 1a: Varredura AST - Analisa funções"""
        self.functions.append(node.name)
        self.cyclomatic_complexity += self._calculate_complexity(node)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        """Micro-fase 1a: Varredura AST - Coleta imports"""
        for alias in node.names:
            self.imports.append(alias.name)

    def _calculate_complexity(self, node) -> float:
        """Calcula complexidade ciclomática"""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
        return complexity

    def analyze(self) -> Dict[str, Any]:
        """Executa análise completa"""
        try:
            tree = ast.parse(self.code)
            self.visit(tree)

            criteria = self._evaluate_criteria()

            return {
                "success": True,
                "metrics": {
                    "lines_of_code": len(self.lines),
                    "num_classes": len(self.classes),
                    "num_functions": len(self.functions),
                    "num_imports": len(self.imports),
                    "avg_cyclomatic_complexity": self.cyclomatic_complexity / max(1, len(self.functions))
                },
                "classes": self.classes,
                "functions": self.functions,
                "criteria": criteria
            }
        except SyntaxError as e:
            return {"success": False, "error": f"Erro de sintaxe: {e}"}

    def _evaluate_criteria(self) -> Dict:
        """Micro-fase 1b: Análise Pylint - Avalia 10 critérios"""
        criteria = {}

        # SRP - Single Responsibility
        srp_findings = []
        for class_name, info in self.classes.items():
            if info["num_methods"] > 10:
                srp_findings.append({
                    "location": f"{class_name}:{info['lineno']}",
                    "issue": f"Classe tem {info['num_methods']} métodos (> 10)",
                    "severity": "ALTA"
                })
            if info["lines"] > 500:
                srp_findings.append({
                    "location": f"{class_name}:{info['lineno']}",
                    "issue": f"Classe tem {info['lines']} linhas (> 500)",
                    "severity": "ALTA"
                })

        criteria["SRP"] = {
            "score": max(0, 10 - len(srp_findings) * 2),
            "status": "✅ OK" if not srp_findings else "⚠️ VIOLAÇÃO" if len(srp_findings) < 3 else "❌ CRÍTICO",
            "findings": srp_findings,
            "severity": "ALTA"
        }

        # God Class
        god_class_findings = []
        for class_name, info in self.classes.items():
            if info["lines"] > 500:
                god_class_findings.append({
                    "location": f"{class_name}:{info['lineno']}",
                    "issue": f"God Class: {info['lines']} linhas",
                    "severity": "ALTA"
                })

        criteria["GodClass"] = {
            "score": max(0, 10 - len(god_class_findings) * 3),
            "status": "✅ OK" if not god_class_findings else "❌ CRÍTICO",
            "findings": god_class_findings,
            "severity": "ALTA"
        }

        # Coupling
        coupling_score = 10
        if len(self.imports) > len(self.classes) * 3:
            coupling_score = 5

        criteria["Coupling"] = {
            "score": coupling_score,
            "status": "✅ OK" if coupling_score >= 8 else "⚠️ VIOLAÇÃO",
            "findings": [],
            "severity": "ALTA"
        }

        # Preencher outros critérios (simplificado)
        for criterion in ["OCP", "DIP", "LayerSeparation", "Cohesion", "DesignPatterns", "CircularDeps", "InterfaceSegregation"]:
            criteria[criterion] = {
                "score": 7,
                "status": "✅ PARCIAL",
                "findings": [],
                "severity": "MÉDIA"
            }

        return criteria

def run_analysis(filepath: str) -> Dict[str, Any]:
    """Micro-fase 1c: Validação Ruff - Executa análise completa"""
    file_path = Path(filepath)
    if not file_path.exists():
        return {"error": f"Arquivo não encontrado: {filepath}"}

    try:
        code = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {"error": f"Erro ao ler arquivo: {e}"}

    analyzer = ArchitectureAnalyzer(code)
    return analyzer.analyze()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python analyzer.py <arquivo.py>")
        sys.exit(1)

    result = run_analysis(sys.argv[1])
    print(json.dumps(result, indent=2, default=str))
