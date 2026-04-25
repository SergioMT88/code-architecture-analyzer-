#!/usr/bin/env python3
"""
Analyzer - Analise profunda de arquitetura Python v2.0
Fase 1: Identificacao (3 micro-fases)
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ArchitectureAnalyzer(ast.NodeVisitor):
    """Analisa codigo Python em busca de problemas arquiteturais com detalhes por linha."""

    def __init__(self, code: str, filepath: str = "<unknown>"):
        self.code = code
        self.filepath = filepath
        self.lines = code.split('\n')
        self.classes: Dict = {}
        self.functions: List = []
        self.imports: List = []
        self.import_nodes: List = []
        self.cyclomatic_complexity = 0
        self._current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef):
        methods = []
        for n in node.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append({
                    "name": n.name,
                    "lineno": n.lineno,
                    "complexity": self._calculate_complexity(n),
                    "lines": (n.end_lineno or n.lineno) - n.lineno,
                    "params": len(n.args.args)
                })

        lines = (node.end_lineno or 0) - (node.lineno or 0)
        complexity = self._calculate_complexity(node)
        bases = [ast.unparse(b) for b in node.bases] if node.bases else []

        self._current_class = node.name
        self.classes[node.name] = {
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno or node.lineno,
            "methods": methods,
            "num_methods": len(methods),
            "lines": lines,
            "complexity": complexity,
            "bases": bases,
            "attributes": self._get_class_attributes(node),
        }
        self.generic_visit(node)
        self._current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self._current_class is None:
            self.functions.append({
                "name": node.name,
                "lineno": node.lineno,
                "complexity": self._calculate_complexity(node),
                "lines": (node.end_lineno or node.lineno) - node.lineno
            })
            self.cyclomatic_complexity += self._calculate_complexity(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.name)
            self.import_nodes.append(
                {"module": alias.name, "lineno": node.lineno, "type": "import"})

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        self.imports.append(module)
        self.import_nodes.append({
            "module": module,
            "lineno": node.lineno,
            "type": "from",
            "names": [alias.name for alias in node.names]
        })

    def _get_class_attributes(self, node: ast.ClassDef) -> List[str]:
        attrs = []
        for item in ast.walk(node):
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                        if target.value.id == "self":
                            attrs.append(target.attr)
        return list(set(attrs))

    def _calculate_complexity(self, node) -> int:
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                                  ast.With, ast.Assert, ast.comprehension)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def _get_line(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def analyze(self) -> Dict[str, Any]:
        try:
            tree = ast.parse(self.code)
            self.visit(tree)
            criteria = self._evaluate_criteria()
            metrics = self._calculate_metrics()
            dependencies = self._analyze_dependencies()
            test_analysis = self._analyze_tests()

            return {
                "success": True,
                "metrics": metrics,
                "classes": self.classes,
                "functions": self.functions,
                "imports": self.import_nodes,
                "criteria": criteria,
                "dependencies": dependencies,
                "test_analysis": test_analysis,
            }
        except SyntaxError as e:
            return {"success": False, "error": f"Erro de sintaxe na linha {e.lineno}: {e.msg}"}

    def _calculate_metrics(self) -> Dict[str, Any]:
        code_lines = [l for l in self.lines if l.strip() and not l.strip().startswith('#')]
        comment_lines = [l for l in self.lines if l.strip().startswith('#')]
        blank_lines = [l for l in self.lines if not l.strip()]

        all_methods = []
        for cls in self.classes.values():
            all_methods.extend(cls["methods"])

        complexities = [m["complexity"] for m in all_methods] + \
                       [f["complexity"] for f in self.functions]

        mi = self._maintainability_index()

        return {
            "lines_of_code": len(self.lines),
            "code_lines": len(code_lines),
            "comment_lines": len(comment_lines),
            "blank_lines": len(blank_lines),
            "num_classes": len(self.classes),
            "num_functions": len(self.functions),
            "num_imports": len(set(self.imports)),
            "avg_cyclomatic_complexity": round(
                sum(complexities) / max(1, len(complexities)), 2
            ),
            "max_cyclomatic_complexity": max(complexities) if complexities else 0,
            "maintainability_index": mi,
            "maintainability_grade": self._mi_grade(mi),
            "comment_ratio": round(
                len(comment_lines) / max(1, len(code_lines)) * 100, 1
            ),
        }

    def _maintainability_index(self) -> float:
        """Calcula Maintainability Index (0-100)."""
        import math
        loc = max(1, len([l for l in self.lines if l.strip()]))
        avg_cc = self.cyclomatic_complexity / max(1, len(self.functions) + sum(
            c["num_methods"] for c in self.classes.values()
        ))
        comments = len([l for l in self.lines if l.strip().startswith('#')])
        cm = comments / max(1, loc) * 100

        mi = 171 - 5.2 * math.log(max(1, loc)) - 0.23 * avg_cc - 16.2 * \
                                  math.log(max(1, loc)) + 50 * math.sin(math.sqrt(2.4 * cm))
        return round(max(0, min(100, mi)), 1)

    def _mi_grade(self, mi: float) -> str:
        if mi >= 85:
            return "A (Excellent)"
        elif mi >= 65:
            return "B (Good)"
        elif mi >= 40:
            return "C (Moderate)"
        else:
            return "D (Poor - needs refactoring)"

    def _analyze_dependencies(self) -> Dict[str, Any]:
        """Analisa dependencias reais entre modulos."""
        import_names = [n["module"] for n in self.import_nodes]
        stdlib_modules = {
            "os", "sys", "json", "re", "math", "datetime", "pathlib",
            "typing", "collections", "itertools", "functools", "abc",
            "io", "time", "copy", "shutil", "subprocess", "threading",
            "asyncio", "logging", "unittest", "dataclasses", "enum"
        }

        third_party = [m for m in import_names if m.split('.')[0] not in stdlib_modules and m]
        internal = [m for m in import_names if m.startswith('.')]

        # Detectar possiveis imports circulares (mesmo arquivo importado de formas diferentes)
        seen = set()
        duplicate_imports = []
        for node in self.import_nodes:
            key = node["module"]
            if key in seen:
                duplicate_imports.append({
                    "module": key,
                    "lineno": node["lineno"],
                    "issue": f"Modulo '{key}' importado multiplas vezes",
                    "line_content": self._get_line(node["lineno"])
                })
            seen.add(key)

        # Detectar imports dentro de funcoes (anti-pattern)
        inline_imports = self._detect_inline_imports()

        return {
            "total_imports": len(self.import_nodes),
            "unique_modules": len(seen),
            "third_party": list(set(third_party)),
            "internal": internal,
            "duplicate_imports": duplicate_imports,
            "inline_imports": inline_imports,
            "coupling_score": self._calculate_coupling_score(len(seen), third_party),
        }

    def _detect_inline_imports(self) -> List[Dict]:
        """Detecta imports dentro de funcoes (anti-pattern)."""
        inline = []
        try:
            tree = ast.parse(self.code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for child in ast.walk(node):
                        if isinstance(child, (ast.Import, ast.ImportFrom)) and child != node:
                            module = ""
                            if isinstance(child, ast.Import):
                                module = child.names[0].name
                            elif isinstance(child, ast.ImportFrom):
                                module = child.module or ""
                            inline.append({
                                "lineno": child.lineno,
                                "module": module,
                                "inside_function": node.name,
                                "issue": f"Import '{module}' dentro da funcao '{node.name}' - mova para o topo",
                                "line_content": self._get_line(child.lineno)
                            })
        except Exception:
            pass
        return inline

    def _calculate_coupling_score(self, unique: int, third_party: List) -> Dict:
        score = 10
        issues = []
        if unique > 15:
            score -= 3
            issues.append(f"{unique} modulos importados (> 15) - alto acoplamento")
        if len(third_party) > 8:
            score -= 2
            issues.append(f"{len(third_party)} dependencias externas (> 8)")
        return {"score": max(0, score), "issues": issues}

    def _analyze_tests(self) -> Dict[str, Any]:
        """Analisa qualidade e cobertura de testes no proprio arquivo."""
        test_functions = [f for f in self.functions if f["name"].startswith("test_")]
        test_classes = {k: v for k, v in self.classes.items() if k.startswith("Test")}

        total_methods = sum(c["num_methods"] for c in self.classes.values())
        test_methods = sum(v["num_methods"] for v in test_classes.values())

        has_assert = "assert " in self.code
        has_pytest = "import pytest" in self.code or "from pytest" in self.code
        has_unittest = "import unittest" in self.code

        coverage_estimate = 0
        if total_methods > 0:
            coverage_estimate = round(min(100, test_methods / total_methods * 100), 1)

        return {
            "test_functions": len(test_functions),
            "test_classes": len(test_classes),
            "has_assertions": has_assert,
            "uses_pytest": has_pytest,
            "uses_unittest": has_unittest,
            "estimated_coverage": coverage_estimate,
            "missing_tests": self._find_missing_tests(test_classes),
        }

    def _find_missing_tests(self, test_classes: Dict) -> List[str]:
        tested_names = set()
        for cls in test_classes.values():
            for m in cls["methods"]:
                name = m["name"].replace("test_", "")
                tested_names.add(name)

        missing = []
        for cls_name, cls_info in self.classes.items():
            if not cls_name.startswith("Test"):
                for method in cls_info["methods"]:
                    if not method["name"].startswith("_") and method["name"] not in tested_names:
                        missing.append(f"{cls_name}.{method['name']} (linha {method['lineno']})")
        return missing[:10]

    def _evaluate_criteria(self) -> Dict:
        criteria = {}

        # SRP - Single Responsibility com detalhamento por linha
        srp_findings = []
        for cls_name, info in self.classes.items():
            if info["num_methods"] > 10:
                srp_findings.append({
                    "location": f"linha {info['lineno']}",
                    "issue": (
                        f"Classe '{cls_name}' tem {info['num_methods']} metodos (limite: 10). "
                        f"Considere dividir em classes menores por responsabilidade."
                    ),
                    "severity": "ALTA",
                    "line_content": self._get_line(info['lineno']),
                    "suggestion": f"Divida '{cls_name}' em: {cls_name}Reader, {cls_name}Writer, {cls_name}Validator"
                })
            if info["lines"] > 200:
                srp_findings.append({
                    "location": f"linhas {info['lineno']}-{info['end_lineno']}",
                    "issue": (
                        f"Classe '{cls_name}' tem {info['lines']} linhas (limite: 200). "
                        f"Muito grande para ter uma unica responsabilidade."
                    ),
                    "severity": "ALTA",
                    "line_content": self._get_line(info['lineno']),
                    "suggestion": "Extraia grupos de metodos relacionados para novas classes"
                })
            if info["num_methods"] > 0:
                high_cc = [m for m in info["methods"] if m["complexity"] > 10]
                for m in high_cc:
                    srp_findings.append({
                        "location": f"linha {m['lineno']}",
                        "issue": (
                            f"Metodo '{cls_name}.{m['name']}' tem complexidade ciclomatica {m['complexity']} (limite: 10). "
                            f"Metodos complexos violam SRP."
                        ),
                        "severity": "MEDIA",
                        "line_content": self._get_line(m['lineno']),
                        "suggestion": f"Extraia logica de '{m['name']}' em metodos menores e mais especificos"
                    })

        srp_score = max(0, 10 - len(srp_findings) * 2)
        criteria["SRP"] = {
            "score": srp_score,
            "status": self._score_to_status(srp_score),
            "findings": srp_findings,
            "severity": "ALTA",
            "description": "Single Responsibility Principle - cada classe deve ter apenas uma razao para mudar"
        }

        # God Class
        god_findings = []
        for cls_name, info in self.classes.items():
            attrs = info.get("attributes", [])
            god_score_class = 0
            reasons = []
            if info["lines"] > 300:
                god_score_class += 2
                reasons.append(f"{info['lines']} linhas")
            if info["num_methods"] > 15:
                god_score_class += 2
                reasons.append(f"{info['num_methods']} metodos")
            if len(attrs) > 10:
                god_score_class += 1
                reasons.append(f"{len(attrs)} atributos")
            if god_score_class >= 2:
                god_findings.append({
                    "location": f"linhas {info['lineno']}-{info['end_lineno']}",
                    "issue": f"God Class detectada: '{cls_name}' ({', '.join(reasons)}). Classe sabe e faz demais.",
                    "severity": "ALTA",
                    "line_content": self._get_line(info['lineno']),
                    "suggestion": f"Aplique o padrao de decomposicao: extraia responsabilidades distintas de '{cls_name}'"
                })

        god_score = max(0, 10 - len(god_findings) * 3)
        criteria["GodClass"] = {
            "score": god_score,
            "status": self._score_to_status(god_score),
            "findings": god_findings,
            "severity": "ALTA",
            "description": "God Class - classe que centraliza responsabilidades demais"
        }

        # Coupling - Acoplamento
        coupling_findings = []
        n_imports = len(set(self.imports))
        n_classes = max(1, len(self.classes))
        if n_imports > n_classes * 4:
            coupling_findings.append({
                "location": "imports (topo do arquivo)",
                "issue": (
                    f"Alto acoplamento: {n_imports} modulos importados para {n_classes} classe(s). "
                    f"Ratio ideal: <= 4 imports por classe."
                ),
                "severity": "ALTA",
                "line_content": "",
                "suggestion": "Use Dependency Injection ou Facade para reduzir dependencias diretas"
            })
        inline = self._detect_inline_imports()
        for imp in inline:
            coupling_findings.append({
                "location": f"linha {imp['lineno']}",
                "issue": imp["issue"],
                "severity": "MEDIA",
                "line_content": imp["line_content"],
                "suggestion": "Mova 'import {}' para o topo do arquivo".format(imp["module"])
            })

        coupling_score = max(0, 10 - len(coupling_findings) * 2)
        criteria["Coupling"] = {
            "score": coupling_score,
            "status": self._score_to_status(coupling_score),
            "findings": coupling_findings,
            "severity": "ALTA",
            "description": "Acoplamento - grau de interdependencia entre modulos"
        }

        # DIP - Dependency Inversion
        dip_findings = []
        for cls_name, info in self.classes.items():
            if not info["bases"] and info["num_methods"] > 5:
                dip_findings.append({
                    "location": f"linha {info['lineno']}",
                    "issue": (
                        f"Classe '{cls_name}' nao herda de interface/classe abstrata. "
                        f"Classes concretas devem depender de abstracoes."
                    ),
                    "severity": "MEDIA",
                    "line_content": self._get_line(info['lineno']),
                    "suggestion": f"Crie uma interface: 'class I{cls_name}(ABC): ...' e use 'class {cls_name}(I{cls_name}):'"
                })

        dip_score = max(0, 10 - len(dip_findings) * 2)
        criteria["DIP"] = {
            "score": dip_score,
            "status": self._score_to_status(dip_score),
            "findings": dip_findings,
            "severity": "ALTA",
            "description": "Dependency Inversion Principle - dependa de abstracoes, nao de implementacoes"
        }

        # Cohesion
        cohesion_findings = []
        for cls_name, info in self.classes.items():
            if info["num_methods"] > 0:
                attrs = info.get("attributes", [])
                if len(attrs) > 5 and info["num_methods"] > 5:
                    cohesion_findings.append({
                        "location": f"linha {info['lineno']}",
                        "issue": (
                            f"Classe '{cls_name}' pode ter baixa coesao: "
                            f"{len(attrs)} atributos e {info['num_methods']} metodos. "
                            f"Verifique se todos os metodos usam os mesmos atributos."
                        ),
                        "severity": "MEDIA",
                        "line_content": self._get_line(info['lineno']),
                        "suggestion": "Agrupe atributos e metodos relacionados em classes menores"
                    })

        cohesion_score = max(0, 10 - len(cohesion_findings) * 2)
        criteria["Cohesion"] = {
            "score": cohesion_score,
            "status": self._score_to_status(cohesion_score),
            "findings": cohesion_findings,
            "severity": "MEDIA",
            "description": "Coesao - metodos e atributos de uma classe devem estar relacionados"
        }

        # Preencher OCP, LayerSeparation, DesignPatterns, CircularDeps, InterfaceSegregation
        for key, desc, sev in [
            ("OCP", "Open/Closed Principle - aberto para extensao, fechado para modificacao", "MEDIA"),
            ("LayerSeparation", "Separacao de Camadas - UI, logica de negocio e dados separados", "ALTA"),
            ("DesignPatterns", "Padroes de Design - uso de padroes reconhecidos", "MEDIA"),
            ("CircularDeps", "Dependencias Circulares - A depende de B que depende de A", "ALTA"),
            ("InterfaceSegregation", "Interface Segregation - interfaces especificas sao melhores que gerais", "MEDIA"),
        ]:
            criteria[key] = {
                "score": 7,
                "status": "PARCIAL - analise manual recomendada",
                "findings": [],
                "severity": sev,
                "description": desc
            }

        return criteria

    def _score_to_status(self, score: int) -> str:
        if score >= 9:
            return "OK"
        elif score >= 7:
            return "PARCIAL"
        elif score >= 5:
            return "VIOLACAO"
        else:
            return "CRITICO"


def run_ruff(filepath: str) -> List[Dict]:
    """Executa ruff se disponivel e retorna findings."""
    findings = []
    try:
        result = subprocess.run(
            ["ruff", "check", filepath, "--output-format=json"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout:
            ruff_output = json.loads(result.stdout)
            for item in ruff_output[:20]:
                findings.append({
                    "tool": "ruff",
                    "lineno": item.get("location", {}).get("row", 0),
                    "code": item.get("code", ""),
                    "issue": item.get("message", ""),
                    "severity": "MEDIA" if item.get("code", "").startswith("E") else "BAIXA"
                })
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return findings


def run_pylint(filepath: str) -> List[Dict]:
    """Executa pylint se disponivel e retorna findings."""
    findings = []
    try:
        result = subprocess.run(
            ["pylint", filepath, "--output-format=json", "--score=no"],
            capture_output=True, text=True, timeout=15
        )
        if result.stdout:
            pylint_output = json.loads(result.stdout)
            for item in pylint_output[:20]:
                mtype = item.get("type", "")
                if mtype in ("error", "warning", "convention"):
                    findings.append({
                        "tool": "pylint",
                        "lineno": item.get("line", 0),
                        "code": item.get("message-id", ""),
                        "issue": item.get("message", ""),
                        "severity": "ALTA" if mtype == "error" else "MEDIA"
                    })
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return findings


def run_analysis(filepath: str, config: Optional[Dict] = None) -> Dict[str, Any]:
    """Executa analise completa com integracao de ferramentas externas."""
    file_path = Path(filepath)
    if not file_path.exists():
        return {"success": False, "error": f"Arquivo nao encontrado: {filepath}"}

    try:
        code = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {"success": False, "error": f"Erro ao ler arquivo: {e}"}

    analyzer = ArchitectureAnalyzer(code, filepath)
    result = analyzer.analyze()

    if result.get("success"):
        result["tool_findings"] = {
            "ruff": run_ruff(filepath),
            "pylint": run_pylint(filepath),
        }
        result["tool_findings"]["total"] = (
            len(result["tool_findings"]["ruff"]) +
            len(result["tool_findings"]["pylint"])
        )

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python analyzer.py <arquivo.py>")
        sys.exit(1)

    result = run_analysis(sys.argv[1])
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
