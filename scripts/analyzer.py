#!/usr/bin/env python3
"""
Analyzer - Analise profunda de arquitetura Python v2.1.5
Fase 1: Identificacao (3 micro-fases)
"""

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class ArchitectureAnalyzer(ast.NodeVisitor):
    """Analisa codigo Python em busca de problemas arquiteturais com detalhes por linha."""

    def __init__(self, code: str, filepath: str = "<unknown>", config: Optional[Dict[str, Any]] = None):
        self.code = code
        self.filepath = filepath
        self.lines = code.split('\n')
        self.config = {
            "max_methods_per_class": 10,
            "max_lines_per_class": 200,
            "max_complexity": 10,
            "max_imports": 20,
            "min_comment_ratio": 10,
            "ignore_criteria": [],
        }
        if config:
            self.config.update(config)
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
        code_lines = [ln for ln in self.lines if ln.strip() and not ln.strip().startswith('#')]
        comment_lines = [ln for ln in self.lines if ln.strip().startswith('#')]
        blank_lines = [ln for ln in self.lines if not ln.strip()]

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
            "comment_ratio_target": self._threshold("min_comment_ratio", 10),
            "comment_ratio_ok": round(
                len(comment_lines) / max(1, len(code_lines)) * 100, 1
            ) >= self._threshold("min_comment_ratio", 10),
            "comment_ratio_gap": round(
                max(0, self._threshold("min_comment_ratio", 10) - (
                    len(comment_lines) / max(1, len(code_lines)) * 100
                )),
                1,
            ),
        }

    def _maintainability_index(self) -> float:
        """Calcula Maintainability Index (0-100)."""
        import math
        loc = max(1, len([ln for ln in self.lines if ln.strip()]))
        avg_cc = self.cyclomatic_complexity / max(1, len(self.functions) + sum(
            c["num_methods"] for c in self.classes.values()
        ))
        comments = len([ln for ln in self.lines if ln.strip().startswith('#')])
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
        circular = self._detect_project_circular_dependencies()

        return {
            "total_imports": len(self.import_nodes),
            "unique_modules": len(seen),
            "third_party": list(set(third_party)),
            "internal": internal,
            "duplicate_imports": duplicate_imports,
            "inline_imports": inline_imports,
            "circular_dependencies": circular.get("cycles", []),
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
                                "issue": (
                                    f"Import '{module}' dentro da funcao"
                                    f" '{node.name}' - mova para o topo"
                                ),
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
        max_methods = self._threshold("max_methods_per_class", 10)
        max_lines = self._threshold("max_lines_per_class", 200)
        max_complexity = self._threshold("max_complexity", 10)
        max_imports = self._threshold("max_imports", 20)

        # SRP - Single Responsibility
        if not self._is_ignored("SRP"):
            srp_findings = []
            for cls_name, info in self.classes.items():
                if info["num_methods"] > max_methods:
                    srp_findings.append({
                        "location": f"linha {info['lineno']}",
                        "issue": (
                            f"Classe '{cls_name}' tem {info['num_methods']} metodos "
                            f"(limite configurado: {max_methods})."
                        ),
                        "severity": "ALTA",
                        "line_content": self._get_line(info["lineno"]),
                        "suggestion": (
                            f"Divida '{cls_name}' em classes menores por responsabilidade."
                        ),
                    })
                if info["lines"] > max_lines:
                    srp_findings.append({
                        "location": f"linhas {info['lineno']}-{info['end_lineno']}",
                        "issue": (
                            f"Classe '{cls_name}' tem {info['lines']} linhas "
                            f"(limite configurado: {max_lines})."
                        ),
                        "severity": "ALTA",
                        "line_content": self._get_line(info["lineno"]),
                        "suggestion": "Extraia grupos de metodos relacionados para novas classes.",
                    })
                for method in info["methods"]:
                    if method["complexity"] > max_complexity:
                        srp_findings.append({
                            "location": f"linha {method['lineno']}",
                            "issue": (
                                f"Metodo '{cls_name}.{method['name']}' tem complexidade "
                                f"{method['complexity']} (limite configurado: {max_complexity})."
                            ),
                            "severity": "MEDIA",
                            "line_content": self._get_line(method["lineno"]),
                            "suggestion": (
                                f"Extraia logica de '{method['name']}' em metodos menores."
                            ),
                        })

            srp_score = max(0, 10 - len(srp_findings) * 2)
            criteria["SRP"] = {
                "score": srp_score,
                "status": self._score_to_status(srp_score),
                "findings": srp_findings,
                "severity": "ALTA",
                "description": (
                    "Single Responsibility Principle - cada classe deve ter apenas uma razao para mudar"
                ),
            }

        # God Class
        if not self._is_ignored("GodClass"):
            god_findings = []
            for cls_name, info in self.classes.items():
                attrs = info.get("attributes", [])
                reasons = []
                if info["lines"] > max_lines * 1.5:
                    reasons.append(f"{info['lines']} linhas")
                if info["num_methods"] > max_methods + 5:
                    reasons.append(f"{info['num_methods']} metodos")
                if len(attrs) > max_methods:
                    reasons.append(f"{len(attrs)} atributos")
                if reasons:
                    god_findings.append({
                        "location": f"linhas {info['lineno']}-{info['end_lineno']}",
                        "issue": (
                            f"Classe '{cls_name}' concentra muitas responsabilidades "
                            f"({', '.join(reasons)})."
                        ),
                        "severity": "ALTA",
                        "line_content": self._get_line(info["lineno"]),
                        "suggestion": (
                            f"Aplique decomposicao e extraia responsabilidades de '{cls_name}'."
                        ),
                    })

            god_score = max(0, 10 - len(god_findings) * 3)
            criteria["GodClass"] = {
                "score": god_score,
                "status": self._score_to_status(god_score),
                "findings": god_findings,
                "severity": "ALTA",
                "description": "God Class - classe que centraliza responsabilidades demais",
            }

        # Coupling
        if not self._is_ignored("Coupling"):
            coupling_findings = []
            n_imports = len(set(self.imports))
            n_classes = max(1, len(self.classes))
            if n_imports > max_imports:
                coupling_findings.append({
                    "location": "imports (topo do arquivo)",
                    "issue": (
                        f"O arquivo possui {n_imports} imports unicos, acima do limite configurado {max_imports}."
                    ),
                    "severity": "ALTA",
                    "line_content": "",
                    "suggestion": "Revise dependencias, remova imports nao usados e considere separar responsabilidades.",
                })
            if n_imports > n_classes * 4:
                coupling_findings.append({
                    "location": "imports (topo do arquivo)",
                    "issue": (
                        f"Alto acoplamento: {n_imports} modulos importados para {n_classes} classe(s)."
                    ),
                    "severity": "ALTA",
                    "line_content": "",
                    "suggestion": "Use Dependency Injection ou Facade para reduzir dependencias diretas.",
                })
            inline = self._detect_inline_imports()
            for imp in inline:
                coupling_findings.append({
                    "location": f"linha {imp['lineno']}",
                    "issue": imp["issue"],
                    "severity": "MEDIA",
                    "line_content": imp["line_content"],
                    "suggestion": f"Mova 'import {imp['module']}' para o topo do arquivo.",
                })

            coupling_score = max(0, 10 - len(coupling_findings) * 2)
            criteria["Coupling"] = {
                "score": coupling_score,
                "status": self._score_to_status(coupling_score),
                "findings": coupling_findings,
                "severity": "ALTA",
                "description": "Acoplamento - grau de interdependencia entre modulos",
            }

        # DIP
        if not self._is_ignored("DIP"):
            dip_findings = []
            for cls_name, info in self.classes.items():
                if not info["bases"] and info["num_methods"] > max(5, max_methods // 2):
                    dip_findings.append({
                        "location": f"linha {info['lineno']}",
                        "issue": (
                            f"Classe '{cls_name}' depende apenas de implementacao concreta. "
                            "Considere depender de abstracoes."
                        ),
                        "severity": "MEDIA",
                        "line_content": self._get_line(info["lineno"]),
                        "suggestion": (
                            f"Crie uma interface/ABC para '{cls_name}' e injete a dependencia."
                        ),
                    })

            dip_score = max(0, 10 - len(dip_findings) * 2)
            criteria["DIP"] = {
                "score": dip_score,
                "status": self._score_to_status(dip_score),
                "findings": dip_findings,
                "severity": "ALTA",
                "description": (
                    "Dependency Inversion Principle - dependa de abstracoes, nao de implementacoes"
                ),
            }

        # Cohesion
        if not self._is_ignored("Cohesion"):
            cohesion_findings = []
            for cls_name, info in self.classes.items():
                attrs = info.get("attributes", [])
                public_methods = [m for m in info["methods"] if not m["name"].startswith("_")]
                if len(attrs) > max(5, max_methods // 2) and len(public_methods) > max(5, max_methods // 2):
                    cohesion_findings.append({
                        "location": f"linha {info['lineno']}",
                        "issue": (
                            f"Classe '{cls_name}' pode ter baixa coesao: {len(attrs)} atributos "
                            f"e {len(public_methods)} metodos publicos."
                        ),
                        "severity": "MEDIA",
                        "line_content": self._get_line(info["lineno"]),
                        "suggestion": "Agrupe atributos e metodos relacionados em classes menores.",
                    })

            cohesion_score = max(0, 10 - len(cohesion_findings) * 2)
            criteria["Cohesion"] = {
                "score": cohesion_score,
                "status": self._score_to_status(cohesion_score),
                "findings": cohesion_findings,
                "severity": "MEDIA",
                "description": "Coesao - metodos e atributos de uma classe devem estar relacionados",
            }

        # OCP
        if not self._is_ignored("OCP"):
            ocp_findings = self._detect_ocp_findings()
            ocp_score = max(0, 10 - len(ocp_findings) * 2)
            criteria["OCP"] = {
                "score": ocp_score,
                "status": self._score_to_status(ocp_score),
                "findings": ocp_findings,
                "severity": "MEDIA",
                "description": "Open/Closed Principle - aberto para extensao, fechado para modificacao",
            }

        # Layer separation
        if not self._is_ignored("LayerSeparation"):
            layer_findings = self._detect_layer_separation_findings()
            layer_score = max(0, 10 - len(layer_findings) * 2)
            criteria["LayerSeparation"] = {
                "score": layer_score,
                "status": self._score_to_status(layer_score),
                "findings": layer_findings,
                "severity": "ALTA",
                "description": "Separacao de Camadas - UI, logica de negocio e dados separados",
            }

        # Design patterns
        if not self._is_ignored("DesignPatterns"):
            pattern_findings = self._detect_design_pattern_findings()
            pattern_score = min(10, 7 + len(pattern_findings))
            criteria["DesignPatterns"] = {
                "score": pattern_score,
                "status": self._score_to_status(pattern_score),
                "findings": pattern_findings,
                "severity": "MEDIA",
                "description": (
                    "Padroes de Design - reconhecimento de Singleton, Factory, Strategy, "
                    "Adapter e Repository quando explicitamente evidentes"
                ),
            }

        # Circular dependencies
        if not self._is_ignored("CircularDeps"):
            circular_findings = self._detect_circular_dependency_findings()
            circular_score = max(0, 10 - len(circular_findings) * 3)
            criteria["CircularDeps"] = {
                "score": circular_score,
                "status": self._score_to_status(circular_score),
                "findings": circular_findings,
                "severity": "ALTA",
                "description": "Dependencias Circulares - A depende de B que depende de A",
            }

        # Wildcard imports
        if not self._is_ignored("WildcardImport"):
            wildcard_findings = self._detect_wildcard_import_findings()
            wildcard_score = max(0, 10 - len(wildcard_findings) * 3)
            criteria["WildcardImport"] = {
                "score": wildcard_score,
                "status": self._score_to_status(wildcard_score),
                "findings": wildcard_findings,
                "severity": "ALTA",
                "description": "Wildcard import - from X import * polui o namespace e dificulta rastrear origem",
            }

        # Print debug leak
        if not self._is_ignored("PrintLeak"):
            print_findings = self._detect_print_leak_findings()
            print_score = max(0, 10 - len(print_findings) * 2)
            criteria["PrintLeak"] = {
                "score": print_score,
                "status": self._score_to_status(print_score),
                "findings": print_findings,
                "severity": "MEDIA",
                "description": "Print leak - chamadas de print fora de funcoes main/CLI podem ser debug esquecido",
            }

        # Many parameters (>6)
        if not self._is_ignored("ManyParameters"):
            many_params_findings = self._detect_many_parameters_findings()
            many_params_score = max(0, 10 - len(many_params_findings) * 2)
            criteria["ManyParameters"] = {
                "score": many_params_score,
                "status": self._score_to_status(many_params_score),
                "findings": many_params_findings,
                "severity": "MEDIA",
                "description": "Many parameters - funcoes com mais de 6 parametros indicam baixa coesao",
            }

        # Security (eval/exec/pickle/input)
        if not self._is_ignored("Security"):
            security_findings = self._detect_security_findings()
            security_score = max(0, 10 - len(security_findings) * 3)
            criteria["Security"] = {
                "score": security_score,
                "status": self._score_to_status(security_score),
                "findings": security_findings,
                "severity": "ALTA",
                "description": "Security - eval()/exec()/pickle/input() sem validacao representam risco",
            }

        # Async/sync mismatch
        if not self._is_ignored("AsyncSyncMismatch"):
            async_findings = self._detect_async_sync_mismatch_findings()
            async_score = max(0, 10 - len(async_findings) * 3)
            criteria["AsyncSyncMismatch"] = {
                "score": async_score,
                "status": self._score_to_status(async_score),
                "findings": async_findings,
                "severity": "MEDIA",
                "description": "Async/sync mismatch - async sem await ou await fora de async",
            }

        # Redundant if/return
        if not self._is_ignored("RedundantIfReturn"):
            redundant_findings = self._detect_redundant_if_return_findings()
            redundant_score = max(0, 10 - len(redundant_findings) * 2)
            criteria["RedundantIfReturn"] = {
                "score": redundant_score,
                "status": self._score_to_status(redundant_score),
                "findings": redundant_findings,
                "severity": "BAIXA",
                "description": "Redundant if/return - if x: return True else: return False pode ser return x",
            }

        # Unused variables
        if not self._is_ignored("UnusedVariable"):
            unused_findings = self._detect_unused_variable_findings()
            unused_score = max(0, 10 - len(unused_findings) * 2)
            criteria["UnusedVariable"] = {
                "score": unused_score,
                "status": self._score_to_status(unused_score),
                "findings": unused_findings,
                "severity": "MEDIA",
                "description": "Unused variable - variavel declarada mas nunca lida no escopo",
            }

        # Inconsistent returns
        if not self._is_ignored("InconsistentReturns"):
            ret_findings = self._detect_inconsistent_returns_findings()
            ret_score = max(0, 10 - len(ret_findings) * 3)
            criteria["InconsistentReturns"] = {
                "score": ret_score,
                "status": self._score_to_status(ret_score),
                "findings": ret_findings,
                "severity": "MEDIA",
                "description": "Inconsistent returns - tipos de retorno diferentes entre branches da funcao",
            }

        # Performance: for i in range(len(x))
        if not self._is_ignored("RangeLenLoop"):
            range_len_findings = self._detect_range_len_loop_findings()
            range_len_score = max(0, 10 - len(range_len_findings) * 2)
            criteria["RangeLenLoop"] = {
                "score": range_len_score,
                "status": self._score_to_status(range_len_score),
                "findings": range_len_findings,
                "severity": "MEDIA",
                "description": "RangeLen loop - for i in range(len(x)): itere diretamente sobre a colecao",
            }

        # Performance: .keys() desnecessario
        if not self._is_ignored("DotKeys"):
            dotkeys_findings = self._detect_dot_keys_findings()
            dotkeys_score = max(0, 10 - len(dotkeys_findings) * 2)
            criteria["DotKeys"] = {
                "score": dotkeys_score,
                "status": self._score_to_status(dotkeys_score),
                "findings": dotkeys_findings,
                "severity": "BAIXA",
                "description": "DotKeys - .keys() desnecessario em 'in' ou 'for', dict ja itera sobre chaves",
            }

        # Performance: string concat em loop
        if not self._is_ignored("StringConcatInLoop"):
            str_concat_findings = self._detect_string_concat_in_loop_findings()
            str_concat_score = max(0, 10 - len(str_concat_findings) * 3)
            criteria["StringConcatInLoop"] = {
                "score": str_concat_score,
                "status": self._score_to_status(str_concat_score),
                "findings": str_concat_findings,
                "severity": "ALTA",
                "description": "StringConcatInLoop - s += x dentro de loop e O(n^2), prefira list + ''.join()",
            }

        # Performance: any([...]) com list comprehension
        if not self._is_ignored("AnyAllListComp"):
            any_all_findings = self._detect_any_all_list_comp_findings()
            any_all_score = max(0, 10 - len(any_all_findings) * 2)
            criteria["AnyAllListComp"] = {
                "score": any_all_score,
                "status": self._score_to_status(any_all_score),
                "findings": any_all_findings,
                "severity": "MEDIA",
                "description": "AnyAllListComp - any([...])/all([...]) cria lista intermediaria, use generator",
            }

        # Performance: nested loops deep
        if not self._is_ignored("DeepNesting"):
            deep_findings = self._detect_deep_nesting_findings()
            deep_score = max(0, 10 - len(deep_findings) * 3)
            criteria["DeepNesting"] = {
                "score": deep_score,
                "status": self._score_to_status(deep_score),
                "findings": deep_findings,
                "severity": "MEDIA",
                "description": "DeepNesting - mais de 3 niveis de aninhamento (for/if/while) prejudica legibilidade",
            }

        # Performance: type(x) == T em vez de isinstance
        if not self._is_ignored("TypeIsInstance"):
            type_isinstance_findings = self._detect_type_isinstance_findings()
            type_isinstance_score = max(0, 10 - len(type_isinstance_findings) * 2)
            criteria["TypeIsInstance"] = {
                "score": type_isinstance_score,
                "status": self._score_to_status(type_isinstance_score),
                "findings": type_isinstance_findings,
                "severity": "BAIXA",
                "description": "TypeIsInstance - type(x) == T nao suporta heranca, use isinstance(x, T)",
            }

        # Performance: list comprehension sem usar a variavel
        if not self._is_ignored("UnusedIterationVar"):
            unused_iter_findings = self._detect_unused_iteration_var_findings()
            unused_iter_score = max(0, 10 - len(unused_iter_findings) * 2)
            criteria["UnusedIterationVar"] = {
                "score": unused_iter_score,
                "status": self._score_to_status(unused_iter_score),
                "findings": unused_iter_findings,
                "severity": "MEDIA",
                "description": "UnusedIterationVar - comprehension nao usa a variavel de iteracao",
            }

        # Performance: dict subscript sem .get()
        if not self._is_ignored("DictGet"):
            dict_get_findings = self._detect_dict_get_findings()
            dict_get_score = max(0, 10 - len(dict_get_findings) * 2)
            criteria["DictGet"] = {
                "score": dict_get_score,
                "status": self._score_to_status(dict_get_score),
                "findings": dict_get_findings,
                "severity": "BAIXA",
                "description": "DictGet - subscript dict sem fallback pode ser .get()",
            }

        # Performance: list/set manual accumulation in loop
        if not self._is_ignored("ManualAccumulate"):
            manual_findings = self._detect_manual_accumulate_findings()
            manual_score = max(0, 10 - len(manual_findings) * 2)
            criteria["ManualAccumulate"] = {
                "score": manual_score,
                "status": self._score_to_status(manual_score),
                "findings": manual_findings,
                "severity": "MEDIA",
                "description": "ManualAccumulate - list.append()/set.add() em loop prefira comprehension",
            }

        # Shadowing builtins
        if not self._is_ignored("ShadowingBuiltins"):
            shadow_findings = self._detect_shadowing_builtins_findings()
            shadow_score = max(0, 10 - len(shadow_findings) * 2)
            criteria["ShadowingBuiltins"] = {
                "score": shadow_score,
                "status": self._score_to_status(shadow_score),
                "findings": shadow_findings,
                "severity": "MEDIA",
                "description": "Shadowing de builtins - nomes como list, dict, id, type sendo usados como variavel ou parametro",
            }

        # Mutable default arguments
        if not self._is_ignored("MutableDefault"):
            mutable_findings = self._detect_mutable_default_findings()
            mutable_score = max(0, 10 - len(mutable_findings) * 3)
            criteria["MutableDefault"] = {
                "score": mutable_score,
                "status": self._score_to_status(mutable_score),
                "findings": mutable_findings,
                "severity": "ALTA",
                "description": "Argumento mutavel como default - lista/dict/set como parametro padrao e compartilhado entre chamadas",
            }

        # Comparison to None (== None / != None)
        if not self._is_ignored("NoneComparison"):
            none_findings = self._detect_none_comparison_findings()
            none_score = max(0, 10 - len(none_findings) * 3)
            criteria["NoneComparison"] = {
                "score": none_score,
                "status": self._score_to_status(none_score),
                "findings": none_findings,
                "severity": "MEDIA",
                "description": "Comparacao com None usando ==/!= - use 'is None' / 'is not None'",
            }

        # Bare Except
        if not self._is_ignored("BareExcept"):
            except_findings = self._detect_bare_except_findings()
            except_score = max(0, 10 - len(except_findings) * 3)
            criteria["BareExcept"] = {
                "score": except_score,
                "status": self._score_to_status(except_score),
                "findings": except_findings,
                "severity": "ALTA",
                "description": "Bare except - except sem tipo pega SystemExit, KeyboardInterrupt e esconde erros reais",
            }

        # Interface Segregation
        if not self._is_ignored("InterfaceSegregation"):
            interface_findings = self._detect_interface_segregation_findings()
            interface_score = max(0, 10 - len(interface_findings) * 2)
            criteria["InterfaceSegregation"] = {
                "score": interface_score,
                "status": self._score_to_status(interface_score),
                "findings": interface_findings,
                "severity": "MEDIA",
                "description": "Interface Segregation - interfaces especificas sao melhores que gerais",
            }

        # Missing super().__init__()
        if not self._is_ignored("MissingSuperInit"):
            ms_findings = self._detect_missing_super_init_findings()
            ms_score = max(0, 10 - len(ms_findings) * 3)
            criteria["MissingSuperInit"] = {
                "score": ms_score,
                "status": self._score_to_status(ms_score),
                "findings": ms_findings,
                "severity": "ALTA",
                "description": "Missing super().__init__() - classe filha com __init__ proprio nao chama o construtor da classe pai",
            }

        # Override signature mismatch
        if not self._is_ignored("OverrideSignatureMismatch"):
            osm_findings = self._detect_override_signature_findings()
            osm_score = max(0, 10 - len(osm_findings) * 3)
            criteria["OverrideSignatureMismatch"] = {
                "score": osm_score,
                "status": self._score_to_status(osm_score),
                "findings": osm_findings,
                "severity": "MEDIA",
                "description": "Override com assinatura diferente - metodo filho tem parametros diferentes do pai (quebra LSP)",
            }

        # Abstract method not implemented
        if not self._is_ignored("AbstractMethodNotImplemented"):
            am_findings = self._detect_abstract_method_findings()
            am_score = max(0, 10 - len(am_findings) * 3)
            criteria["AbstractMethodNotImplemented"] = {
                "score": am_score,
                "status": self._score_to_status(am_score),
                "findings": am_findings,
                "severity": "ALTA",
                "description": "Metodo abstrato nao implementado - classe herda de ABC mas nao implementa todos os metodos abstratos",
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

    def _threshold(self, key: str, fallback: int) -> int:
        try:
            return int(self.config.get(key, fallback))
        except (TypeError, ValueError):
            return fallback

    def _is_ignored(self, criterion: str) -> bool:
        ignored = {str(item).strip().lower() for item in self.config.get("ignore_criteria", [])}
        return criterion.lower() in ignored

    def _count_if_chain(self, if_node: ast.If) -> int:
        count = 1
        current = if_node
        while (
            len(current.orelse) == 1
            and isinstance(current.orelse[0], ast.If)
        ):
            count += 1
            current = current.orelse[0]
        return count

    def _project_root(self) -> Path:
        markers = ("pyproject.toml", "setup.py", "package.json", ".git")
        current = Path(self.filepath).resolve().parent
        for candidate in [current] + list(current.parents):
            if any((candidate / marker).exists() for marker in markers):
                return candidate
        return current

    def _should_skip_project_path(self, path: Path) -> bool:
        blocked_parts = {
            "__pycache__",
            ".git",
            "node_modules",
            ".skill_outputs",
        }
        blocked_prefixes = ("temp_skill_outputs",)
        return any(
            part in blocked_parts or any(part.startswith(prefix) for prefix in blocked_prefixes)
            for part in path.parts
        )

    def _module_key_for_path(self, path: Path, root: Path) -> str:
        relative = path.relative_to(root)
        if relative.name == "__init__.py":
            parts = relative.parent.parts
        else:
            parts = relative.with_suffix("").parts
        if not parts:
            return path.stem
        return ".".join(parts)

    def _module_aliases_for_path(self, path: Path, root: Path) -> List[str]:
        aliases = {path.stem}
        module_key = self._module_key_for_path(path, root)
        aliases.add(module_key)
        if module_key.endswith(".__init__"):
            aliases.add(module_key.rsplit(".__init__", 1)[0])
        return [alias for alias in aliases if alias]

    def _resolve_relative_import(self, node: ast.ImportFrom, current_key: str) -> Optional[str]:
        if node.level <= 0:
            return node.module

        current_parts = current_key.split(".") if current_key else []
        if len(current_parts) < node.level:
            return None

        base_parts = current_parts[:-node.level]
        if node.module:
            base_parts.extend(node.module.split("."))
        elif len(node.names) == 1 and node.names[0].name != "*":
            base_parts.append(node.names[0].name)
        if not base_parts:
            return None
        return ".".join(base_parts)

    def _extract_local_import_names(self, source: str) -> List[str]:
        names: List[str] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return names

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names.append(node.module)
        return names

    def _build_project_import_graph(self) -> Dict[str, Any]:
        root = self._project_root()
        module_paths: Dict[str, Path] = {}
        alias_to_modules: Dict[str, Set[str]] = {}
        import_lines: Dict[str, Dict[str, List[int]]] = {}

        for path in root.rglob("*.py"):
            if path == Path(self.filepath).resolve() or self._should_skip_project_path(path):
                continue
            try:
                module_key = self._module_key_for_path(path, root)
            except Exception:
                continue

            module_paths[module_key] = path
            for alias in self._module_aliases_for_path(path, root):
                alias_to_modules.setdefault(alias, set()).add(module_key)

        current_path = Path(self.filepath).resolve()
        current_key = self._module_key_for_path(current_path, root)
        module_paths[current_key] = current_path
        for alias in self._module_aliases_for_path(current_path, root):
            alias_to_modules.setdefault(alias, set()).add(current_key)

        graph: Dict[str, Set[str]] = {module: set() for module in module_paths}

        for module_key, path in module_paths.items():
            try:
                source = path.read_text(encoding="utf-8")
            except Exception:
                continue

            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        target_name = alias.name
                        target_modules = alias_to_modules.get(target_name, set())
                        if len(target_modules) == 1:
                            target_module = next(iter(target_modules))
                            graph[module_key].add(target_module)
                            import_lines.setdefault(module_key, {}).setdefault(target_module, []).append(node.lineno)
                elif isinstance(node, ast.ImportFrom):
                    resolved = self._resolve_relative_import(node, module_key)
                    target_names: List[str] = []
                    if resolved:
                        target_names.append(resolved)
                    if node.module:
                        target_names.append(node.module)

                    for target_name in target_names:
                        target_modules = alias_to_modules.get(target_name, set())
                        if len(target_modules) != 1:
                            continue
                        target_module = next(iter(target_modules))
                        graph[module_key].add(target_module)
                        import_lines.setdefault(module_key, {}).setdefault(target_module, []).append(node.lineno)

        return {
            "root": root,
            "current_key": current_key,
            "module_paths": module_paths,
            "alias_to_module": {k: sorted(v) for k, v in alias_to_modules.items()},
            "graph": graph,
            "import_lines": import_lines,
        }

    def _find_graph_cycles(self, graph: Dict[str, Set[str]]) -> List[List[str]]:
        cycles: List[List[str]] = []
        seen_cycles: Set[Tuple[str, ...]] = set()
        state: Dict[str, int] = {}
        stack: List[str] = []
        stack_index: Dict[str, int] = {}

        def canonical(nodes: List[str]) -> Tuple[str, ...]:
            if not nodes:
                return tuple()
            rotations = [tuple(nodes[i:] + nodes[:i]) for i in range(len(nodes))]
            return min(rotations)

        def visit(node: str):
            state[node] = 1
            stack_index[node] = len(stack)
            stack.append(node)

            for neighbor in graph.get(node, set()):
                if neighbor not in graph:
                    continue
                neighbor_state = state.get(neighbor, 0)
                if neighbor_state == 0:
                    visit(neighbor)
                elif neighbor_state == 1 and neighbor in stack_index:
                    cycle_nodes = stack[stack_index[neighbor]:]
                    key = canonical(cycle_nodes)
                    if key not in seen_cycles:
                        seen_cycles.add(key)
                        cycles.append(cycle_nodes)

            stack.pop()
            stack_index.pop(node, None)
            state[node] = 2

        for node in graph:
            if state.get(node, 0) == 0:
                visit(node)

        return cycles

    def _detect_ocp_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings

        for func in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            for child in func.body:
                if isinstance(child, ast.If):
                    chain = self._count_if_chain(child)
                    if chain >= 3:
                        findings.append({
                            "location": f"linha {child.lineno}",
                            "issue": (
                                f"Cadeia if/elif com {chain} ramificacoes em '{func.name}'. "
                                "Isso costuma dificultar extensao sem modificar o codigo existente."
                            ),
                            "severity": "MEDIA",
                            "line_content": self._get_line(child.lineno),
                            "suggestion": (
                                "Considere Strategy, tabela de dispatch ou polimorfismo "
                                "para reduzir a necessidade de alterar a funcao."
                            ),
                        })
        return findings[:10]

    def _detect_layer_separation_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings

        io_calls = []
        infrastructure_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"print", "input", "open"}:
                    io_calls.append(node.lineno)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    base = alias.name.split(".")[0]
                    if base in {"flask", "fastapi", "django", "requests", "sqlite3", "sqlalchemy"}:
                        infrastructure_modules.add(base)
            elif isinstance(node, ast.ImportFrom):
                base = (node.module or "").split(".")[0]
                if base in {"flask", "fastapi", "django", "requests", "sqlite3", "sqlalchemy"}:
                    infrastructure_modules.add(base)

        if io_calls and (self.classes or self.functions):
            findings.append({
                "location": f"linha {min(io_calls)}",
                "issue": (
                    "O arquivo mistura chamadas de I/O com logica de dominio. "
                    "Isso dificulta teste, manutencao e reuso."
                ),
                "severity": "ALTA",
                "line_content": self._get_line(min(io_calls)),
                "suggestion": (
                    "Separe camada de apresentacao/CLI, servico de negocio e acesso a dados "
                    "em modulos distintos."
                ),
            })

        if infrastructure_modules and (self.classes or self.functions):
            findings.append({
                "location": "imports do topo",
                "issue": (
                    f"O arquivo depende de modulos de infraestrutura ({', '.join(sorted(infrastructure_modules))}) "
                    "e ainda concentra logica de negocio. A separacao de camadas pode estar fraca."
                ),
                "severity": "MEDIA",
                "line_content": "",
                "suggestion": "Isolar infraestrutura em adaptadores ou repositórios e manter a regra de negocio independente.",
            })

        return findings[:10]

    def _detect_design_pattern_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        for cls_name, info in self.classes.items():
            method_names = {m["name"] for m in info.get("methods", [])}
            base_names = {base.split(".")[-1] for base in info.get("bases", [])}
            lower = cls_name.lower()
            detected: List[Dict[str, str]] = []

            if "__new__" in method_names or "singleton" in lower:
                detected.append({
                    "pattern": "Singleton",
                    "evidence": "__new__ presente ou nome da classe sugere instancia unica",
                })

            if any(keyword in lower for keyword in ("factory", "builder")) or (
                method_names.intersection({"create", "build", "make"})
            ):
                detected.append({
                    "pattern": "Factory",
                    "evidence": "Nome da classe ou metodos sugerem criacao centralizada de objetos",
                })

            if "strategy" in lower or base_names.intersection({"ABC", "Protocol"}):
                if method_names.intersection({"execute", "run", "apply"}) or len(info.get("bases", [])) > 0:
                    detected.append({
                        "pattern": "Strategy",
                        "evidence": "Base abstrata ou contrato claro com metodo de execucao",
                    })

            if any(keyword in lower for keyword in ("adapter", "wrapper")) or (
                {"adaptee", "wrapped", "delegate"}.intersection({a.lower() for a in info.get("attributes", [])})
            ):
                detected.append({
                    "pattern": "Adapter",
                    "evidence": "Nome da classe ou atributos indicam adaptacao/encapsulamento de outra API",
                })

            if any(keyword in lower for keyword in ("repository", "repo")) or (
                method_names.intersection({"save", "get", "find", "list", "delete"})
            ):
                detected.append({
                    "pattern": "Repository",
                    "evidence": "Nome da classe ou metodos indicam isolamento de acesso a dados",
                })

            if detected:
                findings.append({
                    "location": f"linha {info['lineno']}",
                    "issue": (
                        f"Padrões de design identificados em '{cls_name}': "
                        + ", ".join(item["pattern"] for item in detected)
                    ),
                    "severity": "BAIXA",
                    "line_content": self._get_line(info["lineno"]),
                    "suggestion": (
                        "Documente a intencao do padrao e mantenha a interface pequena e consistente."
                    ),
                    "patterns": detected,
                })
        return findings[:10]

    def _detect_circular_dependency_findings(self) -> List[Dict[str, Any]]:
        return self._detect_project_circular_dependencies().get("findings", [])[:10]

    def _detect_project_circular_dependencies(self) -> Dict[str, Any]:
        graph_info = self._build_project_import_graph()
        cycles = self._find_graph_cycles(graph_info["graph"])
        current_key = graph_info["current_key"]
        import_lines = graph_info["import_lines"]

        cycle_entries: List[Dict[str, Any]] = []
        findings: List[Dict[str, Any]] = []

        for cycle_nodes in cycles:
            if current_key not in cycle_nodes:
                continue

            idx = cycle_nodes.index(current_key)
            next_module = cycle_nodes[(idx + 1) % len(cycle_nodes)]
            line_numbers = import_lines.get(current_key, {}).get(next_module, [])
            lineno = line_numbers[0] if line_numbers else 1
            cycle_path = cycle_nodes[idx:] + cycle_nodes[:idx] + [current_key]

            cycle_entries.append({
                "path": cycle_path,
                "modules": cycle_nodes,
                "current_module": current_key,
                "next_module": next_module,
                "import_line": lineno,
            })

            findings.append({
                "location": f"linha {lineno}" if lineno else "imports do modulo",
                "issue": (
                    "Dependencia circular detectada: "
                    + " -> ".join(cycle_path)
                ),
                "severity": "ALTA",
                "line_content": self._get_line(lineno) if lineno else "",
                "suggestion": (
                    "Extraia contratos/abstracoes comuns para um modulo neutro "
                    "ou inverta a dependencia com injecao de dependencia."
                ),
            })

        return {
            "graph": {key: sorted(values) for key, values in graph_info["graph"].items()},
            "cycles": cycle_entries,
            "findings": findings,
            "root": str(graph_info["root"]),
            "current_module": current_key,
        }

    def _detect_bare_except_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                func_name = self._find_enclosing_function(node)
                findings.append({
                    "location": f"linha {node.lineno}",
                    "issue": (
                        "Except sem tipo detectado. "
                        "Isso captura SystemExit, KeyboardInterrupt e erro interno do Python, "
                        "alem de esconder excecoes reais."
                    ),
                    "severity": "ALTA",
                    "line_content": self._get_line(node.lineno),
                    "suggestion": (
                        "Substitua 'except:' por 'except Exception:' ou o tipo de excecao esperado"
                        + (f" na funcao '{func_name}'" if func_name else "")
                        + "."
                    ),
                })
        return findings

    def _detect_none_comparison_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            has_none = any(
                isinstance(c, ast.Constant) and c.value is None
                for c in [node.left] + node.comparators
            )
            if not has_none:
                continue
            for op in node.ops:
                if isinstance(op, (ast.Eq, ast.NotEq)):
                    op_name = "==" if isinstance(op, ast.Eq) else "!="
                    findings.append({
                        "location": f"linha {node.lineno}",
                        "issue": (
                            f"Comparacao com None usando '{op_name}'. "
                            "Isso pode dar falsos positivos com objetos que implementam __eq__."
                        ),
                        "severity": "MEDIA",
                        "line_content": self._get_line(node.lineno),
                        "suggestion": (
                            f"Substitua '{op_name} None' por "
                            f"{'is not None' if isinstance(op, ast.NotEq) else 'is None'}'."
                        ),
                    })
        return findings

    def _detect_mutable_default_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for default in node.args.defaults + node.args.kw_defaults:
                if default is None:
                    continue
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    findings.append({
                        "location": f"linha {default.lineno}",
                        "issue": (
                            f"Argumento mutavel como default em '{node.name}()'. "
                            "O mesmo objeto e compartilhado entre todas as chamadas."
                        ),
                        "severity": "ALTA",
                        "line_content": self._get_line(default.lineno),
                        "suggestion": (
                            f"Substitua por '= None' e use 'if arg is None: arg = []' "
                            f"dentro de '{node.name}'."
                        ),
                    })
        return findings

    def _detect_shadowing_builtins_findings(self) -> List[Dict[str, Any]]:
        builtins = {"list", "dict", "set", "tuple", "int", "str", "float", "bool",
                     "id", "type", "len", "max", "min", "sum", "any", "all",
                     "map", "filter", "zip", "sorted", "reversed", "iter", "next",
                     "input", "print", "open", "file", "dir", "vars", "object"}
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.args + node.args.kwonlyargs:
                    if arg.arg in builtins:
                        findings.append({
                            "location": f"linha {arg.lineno}",
                            "issue": (
                                f"Parametro '{arg.arg}' em '{node.name}()' "
                                f"sombra o builtin '{arg.arg}'."
                            ),
                            "severity": "MEDIA",
                            "line_content": self._get_line(arg.lineno),
                            "suggestion": f"Renomeie o parametro '{arg.arg}' para evitar confusao com o builtin.",
                        })
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                if node.id in builtins:
                    findings.append({
                        "location": f"linha {node.lineno}",
                        "issue": (
                            f"Variavel '{node.id}' sombra o builtin '{node.id}'."
                        ),
                        "severity": "MEDIA",
                        "line_content": self._get_line(node.lineno),
                        "suggestion": f"Renomeie a variavel '{node.id}' para evitar confusao com o builtin.",
                    })
        return findings

    def _detect_security_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        dangerous_names = {"eval", "exec"}
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in dangerous_names:
                findings.append({
                    "location": f"linha {node.lineno}",
                    "issue": (
                        f"{node.func.id}() detectado - risco de injecao de codigo."
                    ),
                    "severity": "ALTA",
                    "line_content": self._get_line(node.lineno),
                    "suggestion": (
                        f"Substitua {node.func.id}() por alternativas seguras "
                        f"(ast.literal_eval, subprocess, etc)."
                    ),
                })
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "load":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "pickle":
                    findings.append({
                        "location": f"linha {node.lineno}",
                        "issue": "pickle.load() detectado - risco de execucao arbitraria.",
                        "severity": "ALTA",
                        "line_content": self._get_line(node.lineno),
                        "suggestion": (
                            "Substitua pickle por JSON, YAML ou schema "
                            "validado se possivel."
                        ),
                    })
            elif isinstance(node.func, ast.Name) and node.func.id == "input" and not self._is_input_safe(node):
                findings.append({
                    "location": f"linha {node.lineno}",
                    "issue": "input() sem validacao - risco de injecao se combinado com exec/eval.",
                    "severity": "MEDIA",
                    "line_content": self._get_line(node.lineno),
                    "suggestion": (
                        "Valide a entrada do usuario ou use raw_input() "
                        "se disponivel."
                    ),
                })
        return findings

    def _is_input_safe(self, call_node: ast.Call) -> bool:
        """Heuristica: input() com argumento string literal é só prompt, menos perigoso."""
        if call_node.args:
            return True
        return False

    def _detect_async_sync_mismatch_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                has_await = any(
                    isinstance(child, ast.Await) for child in ast.walk(node)
                )
                if not has_await:
                    findings.append({
                        "location": f"linha {node.lineno}",
                        "issue": (
                            f"Funcao async '{node.name}' nao usa await - "
                            f"pode ser sync."
                        ),
                        "severity": "MEDIA",
                        "line_content": self._get_line(node.lineno),
                        "suggestion": (
                            f"Remova 'async' de '{node.name}' se nao ha "
                            f"operacao assincrona."
                        ),
                    })
        parents = {child: n for n in ast.walk(tree) for child in ast.iter_child_nodes(n)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Await):
                continue
            cur = node
            while cur in parents:
                cur = parents[cur]
                if isinstance(cur, ast.FunctionDef):
                    findings.append({
                        "location": f"linha {node.lineno}",
                        "issue": (
                            "await usado fora de funcao async "
                            f"em '{cur.name}'."
                        ),
                        "severity": "ALTA",
                        "line_content": self._get_line(node.lineno),
                        "suggestion": (
                            "Adicione 'async' antes de 'def' "
                            f"em '{cur.name}'."
                        ),
                    })
                    break
                if isinstance(cur, ast.AsyncFunctionDef):
                    break
        return findings

    def _detect_redundant_if_return_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            if len(node.body) == 1 and len(node.orelse) == 1:
                body = node.body[0]
                orelse = node.orelse[0]
                if (isinstance(body, ast.Return) and isinstance(body.value, ast.Constant)
                        and isinstance(orelse, ast.Return) and isinstance(orelse.value, ast.Constant)):
                    b_val = body.value.value
                    o_val = orelse.value.value
                    if b_val is True and o_val is False:
                        findings.append({
                            "location": f"linha {node.lineno}",
                            "issue": (
                                "if/return True/False redundante - "
                                "pode ser substituido por 'return cond'."
                            ),
                            "severity": "BAIXA",
                            "line_content": self._get_line(node.lineno),
                            "suggestion": "Substitua por 'return <condicao>'.",
                        })
                    elif b_val is False and o_val is True:
                        findings.append({
                            "location": f"linha {node.lineno}",
                            "issue": (
                                "if/return False/True redundante - "
                                "pode ser substituido por 'return not cond'."
                            ),
                            "severity": "BAIXA",
                            "line_content": self._get_line(node.lineno),
                            "suggestion": "Substitua por 'return not <condicao>'.",
                        })
        return findings

    def _infer_return_type(self, node: Optional[ast.AST]) -> Optional[str]:
        if node is None:
            return "None"
        if isinstance(node, ast.Constant):
            if node.value is None:
                return "None"
            return type(node.value).__name__
        if isinstance(node, (ast.List, ast.ListComp)):
            return "list"
        if isinstance(node, (ast.Dict, ast.DictComp)):
            return "dict"
        if isinstance(node, (ast.Set, ast.SetComp)):
            return "set"
        if isinstance(node, (ast.Tuple, ast.GeneratorExp)):
            return "tuple"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return f"{node.func.id}()"
        return "unknown"

    def _detect_inconsistent_returns_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            types: set = set()
            for child in ast.walk(node):
                if isinstance(child, ast.Return):
                    types.add(self._infer_return_type(child.value))
            if len(types) >= 2:
                types_str = ", ".join(sorted(types))
                findings.append({
                    "location": f"linha {node.lineno}",
                    "issue": (
                        f"Funcao '{node.name}' retorna tipos diferentes: "
                        f"{types_str}."
                    ),
                    "severity": "MEDIA",
                    "line_content": self._get_line(node.lineno),
                    "suggestion": (
                        f"Padronize o retorno de '{node.name}' para um unico tipo."
                    ),
                })
        return findings

    def _detect_dot_keys_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for op, comp in zip(node.ops, node.comparators):
                    if not isinstance(op, ast.In):
                        continue
                    if not (isinstance(comp, ast.Call) and isinstance(comp.func, ast.Attribute)
                            and comp.func.attr == "keys"):
                        continue
                    var = ""
                    if isinstance(comp.func.value, ast.Name):
                        var = comp.func.value.id
                    findings.append({
                        "location": f"linha {node.lineno}",
                        "issue": (
                            ".keys() desnecessario em comparacao 'in'."
                        ),
                        "severity": "BAIXA",
                        "line_content": self._get_line(node.lineno),
                        "suggestion": (
                            f"Use 'if x in {var}' em vez de 'if x in {var}.keys()'."
                        ),
                    })
            if isinstance(node, ast.For):
                if not (isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Attribute)
                        and node.iter.func.attr == "keys"):
                    continue
                var = ""
                if isinstance(node.iter.func.value, ast.Name):
                    var = node.iter.func.value.id
                findings.append({
                    "location": f"linha {node.lineno}",
                    "issue": (
                        ".keys() desnecessario em loop 'for'."
                    ),
                    "severity": "BAIXA",
                    "line_content": self._get_line(node.lineno),
                    "suggestion": (
                        f"Use 'for k in {var}' em vez de 'for k in {var}.keys()'."
                    ),
                })
        return findings

    def _detect_string_concat_in_loop_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, ast.For):
                continue
            loop_var = None
            if isinstance(node.target, ast.Name):
                loop_var = node.target.id
            for child in ast.walk(node):
                if isinstance(child, ast.AugAssign):
                    if not isinstance(child.op, ast.Add):
                        continue
                    if not isinstance(child.target, ast.Name):
                        continue
                    var = child.target.id
                    if var == loop_var:
                        continue
                    findings.append({
                        "location": f"linha {child.lineno}",
                        "issue": (
                            f"'{var} += ...' dentro de loop pode ser "
                            f"lento com strings (O(n^2))."
                        ),
                        "severity": "ALTA",
                        "line_content": self._get_line(child.lineno),
                        "suggestion": (
                            "Acumule partes em uma lista e use "
                            "'\"\".join(partes)' no final."
                        ),
                    })
                elif isinstance(child, ast.Assign) and len(child.targets) == 1:
                    target = child.targets[0]
                    if not isinstance(target, ast.Name):
                        continue
                    if not isinstance(child.value, ast.BinOp):
                        continue
                    if not isinstance(child.value.op, ast.Add):
                        continue
                    if not isinstance(child.value.left, ast.Name):
                        continue
                    if child.value.left.id != target.id:
                        continue
                    if target.id == loop_var:
                        continue
                    findings.append({
                        "location": f"linha {child.lineno}",
                        "issue": (
                            f"'{target.id} = {target.id} + ...' dentro de "
                            f"loop pode ser lento com strings (O(n^2))."
                        ),
                        "severity": "ALTA",
                        "line_content": self._get_line(child.lineno),
                        "suggestion": (
                            "Acumule partes em uma lista e use "
                            "'\"\".join(partes)' no final."
                        ),
                    }                )
        return findings

    def _detect_any_all_list_comp_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Name) and node.func.id in ("any", "all")):
                continue
            if not node.args:
                continue
            if not isinstance(node.args[0], ast.ListComp):
                continue
            findings.append({
                "location": f"linha {node.lineno}",
                "issue": (
                    f"{node.func.id}([comprehension]) cria lista "
                    f"intermediaria desnecessaria."
                ),
                "severity": "MEDIA",
                "line_content": self._get_line(node.lineno),
                "suggestion": (
                    f"Remova os colchetes: "
                    f"'{node.func.id}(x for x in ...)'."
                ),
            })
        return findings

    def _detect_deep_nesting_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        parents = {child: n for n in ast.walk(tree) for child in ast.iter_child_nodes(n)}
        nested_types = (ast.For, ast.AsyncFor, ast.If, ast.While)
        for node in ast.walk(tree):
            if not isinstance(node, nested_types):
                continue
            depth = 0
            cur = node
            while cur in parents:
                cur = parents[cur]
                if isinstance(cur, nested_types):
                    depth += 1
            if depth >= 3:
                findings.append({
                    "location": f"linha {node.lineno}",
                    "issue": (
                        f"Aninhamento de {depth} niveis de controle "
                        f"(for/if/while). Prejudica legibilidade."
                    ),
                    "severity": "MEDIA",
                    "line_content": self._get_line(node.lineno),
                    "suggestion": (
                        "Extraia blocos internos para funcoes separadas "
                        "ou use early returns/continues."
                    ),
                })
        return findings

    def _detect_type_isinstance_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for op, comp in zip(node.ops, node.comparators):
                if not isinstance(op, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)):
                    continue
                if not (isinstance(node.left, ast.Call)
                        and isinstance(node.left.func, ast.Name)
                        and node.left.func.id == "type"
                        and node.left.args):
                    continue
                type_name = ""
                if isinstance(comp, ast.Name):
                    type_name = comp.id
                elif isinstance(comp, ast.Tuple):
                    type_name = ", ".join(
                        elt.id for elt in comp.elts if isinstance(elt, ast.Name)
                    )
                findings.append({
                    "location": f"linha {node.lineno}",
                    "issue": (
                        f"type(...) == {type_name} nao suporta heranca."
                    ),
                    "severity": "BAIXA",
                    "line_content": self._get_line(node.lineno),
                    "suggestion": (
                        f"Use isinstance(x, {type_name}) para suportar "
                        f"subclasses."
                    ),
                })
        return findings

    def _detect_unused_iteration_var_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
                continue
            if not node.generators:
                continue
            gen = node.generators[0]
            iter_vars: set = set()
            for n in ast.walk(gen.target):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    iter_vars.add(n.id)
            if "_" in iter_vars:
                continue
            used_vars: set = set()
            for n in ast.walk(node.elt):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    used_vars.add(n.id)
            if iter_vars and not (iter_vars & used_vars):
                vars_str = ", ".join(sorted(iter_vars))
                findings.append({
                    "location": f"linha {node.lineno}",
                    "issue": (
                        f"Comprehension nao usa a variavel '{vars_str}' "
                        f"na expressao de saída."
                    ),
                    "severity": "MEDIA",
                    "line_content": self._get_line(node.lineno),
                    "suggestion": (
                        "Se o objetivo e executar efeito colateral, "
                        "use um loop 'for' normal em vez de comprehension."
                    ),
                })
        return findings

    def _detect_dict_get_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        names_with_dot_get: set = set()
        names_with_subscript: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "get" and isinstance(node.func.value, ast.Name):
                    names_with_dot_get.add(node.func.value.id)
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name) and isinstance(node.ctx, ast.Load):
                    names_with_subscript.add(node.value.id)
        for name in sorted(names_with_subscript):
            if name in names_with_dot_get:
                continue
            findings.append({
                "location": f"referencias a '{name}'",
                "issue": (
                    f"Acesso a '{name}[chave]' sem fallback. "
                    f"Se a chave pode nao existir, use .get()."
                ),
                "severity": "BAIXA",
                "line_content": "",
                "suggestion": (
                    f"Use '{name}.get(chave)' ou "
                    f"'{name}.get(chave, default)' em vez de "
                    f"'{name}[chave]'."
                ),
            })
        return findings

    def _detect_manual_accumulate_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, ast.For):
                continue
            if isinstance(node.target, ast.Name) and node.target.id == "_":
                continue
            if len(node.body) != 1:
                continue
            if not isinstance(node.body[0], ast.Expr):
                continue
            call = node.body[0].value
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr not in ("append", "add"):
                continue
            if not isinstance(call.func.value, ast.Name):
                continue
            findings.append({
                "location": f"linha {node.lineno}",
                "issue": (
                    f"'{call.func.value.id}.{call.func.attr}()' em loop "
                    f"pode ser substituido por comprehension."
                ),
                "severity": "MEDIA",
                "line_content": self._get_line(node.lineno),
                "suggestion": (
                    "Use list comprehension ou set comprehension "
                    "em vez de acumular manualmente no loop."
                ),
            })
        return findings

    def _detect_range_len_loop_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, ast.For):
                continue
            if not isinstance(node.iter, ast.Call):
                continue
            if not (isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range"):
                continue
            if not node.iter.args or not isinstance(node.iter.args[0], ast.Call):
                continue
            call = node.iter.args[0]
            if not (isinstance(call.func, ast.Name) and call.func.id == "len"):
                continue
            target_id = None
            if isinstance(node.target, ast.Name):
                target_id = node.target.id
            if target_id is None:
                continue
            findings.append({
                "location": f"linha {node.lineno}",
                "issue": (
                    f"Loop 'for {target_id} in range(len(...))' deve usar "
                    f"iteracao direta sobre a colecao."
                ),
                "severity": "MEDIA",
                "line_content": self._get_line(node.lineno),
                "suggestion": (
                    "Itere diretamente sobre a colecao: "
                    "'for item in colecao:' em vez de acessar por indice."
                ),
            })
        return findings

    def _detect_unused_variable_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        scopes: List[tuple[Optional[ast.AST], List[ast.AST]]] = [(None, list(ast.iter_child_nodes(tree)))]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append((node, list(ast.iter_child_nodes(node))))
        for func_node, body_nodes in scopes:
            assigned: set = set()
            loaded: set = set()
            params: set = set()
            if func_node and isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in func_node.args.args + func_node.args.kwonlyargs + func_node.args.posonlyargs:
                    params.add(arg.arg)
                if func_node.args.vararg:
                    params.add(func_node.args.vararg.arg)
                if func_node.args.kwarg:
                    params.add(func_node.args.kwarg.arg)
            for n in body_nodes:
                for child in ast.walk(n):
                    if isinstance(child, ast.Name):
                        if isinstance(child.ctx, ast.Store):
                            assigned.add(child.id)
                        elif isinstance(child.ctx, ast.Load):
                            loaded.add(child.id)
            for var in assigned:
                if var.startswith("_") or var.startswith("__"):
                    continue
                if var in ("self", "cls"):
                    continue
                if var in params:
                    continue
                if var not in loaded:
                    findings.append({
                        "location": f"linha {self._find_lineno(tree, var)}",
                        "issue": (
                            f"Variavel '{var}' declarada mas nunca usada."
                        ),
                        "severity": "MEDIA",
                        "line_content": self._get_line(self._find_lineno(tree, var)),
                        "suggestion": (
                            f"Remova a atribuicao a '{var}' se nao e necessaria."
                        ),
                    })
        return findings[:10]

    def _find_lineno(self, tree: ast.AST, name: str) -> int:
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Store):
                return node.lineno
        return 0

    def _detect_many_parameters_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = node.args.args + node.args.kwonlyargs
            if node.args.vararg:
                params.append(node.args.vararg)
            if node.args.kwarg:
                params.append(node.args.kwarg)
            if node.args.posonlyargs:
                params = node.args.posonlyargs + params
            if len(params) > 6:
                findings.append({
                    "location": f"linha {node.lineno}",
                    "issue": (
                        f"Funcao '{node.name}' tem {len(params)} parametros "
                        f"(maximo recomendado: 6)."
                    ),
                    "severity": "MEDIA",
                    "line_content": self._get_line(node.lineno),
                    "suggestion": (
                        f"Agrupe parametros relacionados em um objeto de configuracao "
                        f"ou divida '{node.name}' em funcoes menores."
                    ),
                })
        return findings

    def _detect_wildcard_import_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.names[0].name == "*":
                module = node.module or ""
                findings.append({
                    "location": f"linha {node.lineno}",
                    "issue": f"from {module} import * - import coringa polui o namespace.",
                    "severity": "ALTA",
                    "line_content": self._get_line(node.lineno),
                    "suggestion": (
                        f"Substitua por import {module} ou imports explicitos "
                        f"(from {module} import X, Y, Z)."
                    ),
                })
        return findings

    def _detect_print_leak_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        parents = {child: n for n in ast.walk(tree) for child in ast.iter_child_nodes(n)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "print":
                continue
            func_name = None
            cur = node
            while cur in parents:
                cur = parents[cur]
                if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_name = cur.name
                    break
            if func_name is None or func_name in ("main", "run", "setup"):
                continue
            findings.append({
                "location": f"linha {node.lineno}",
                "issue": (
                    f"Print dentro de '{func_name}()' pode ser debug esquecido em producao."
                ),
                "severity": "MEDIA",
                "line_content": self._get_line(node.lineno),
                "suggestion": (
                    f"Substitua print() por logging ou remova se era debug temporario "
                    f"em '{func_name}'."
                ),
            })
        return findings

    def _find_enclosing_function(self, node: ast.AST) -> str:
        try:
            tree = ast.parse(self.code)
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for child in ast.walk(n):
                        if child is node:
                            return n.name
        except SyntaxError:
            pass
        return ""

    def _detect_interface_segregation_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        threshold = max(5, self._threshold("max_methods_per_class", 10) // 2)
        for cls_name, info in self.classes.items():
            public_methods = [m for m in info.get("methods", []) if not m["name"].startswith("_")]
            if len(public_methods) >= threshold and len(info.get("bases", [])) == 0:
                findings.append({
                    "location": f"linha {info['lineno']}",
                    "issue": (
                        f"Classe '{cls_name}' expõe {len(public_methods)} metodos publicos. "
                        "Pode haver responsabilidade de interface ampla demais."
                    ),
                    "severity": "MEDIA",
                    "line_content": self._get_line(info["lineno"]),
                    "suggestion": (
                        "Divida a API em interfaces menores e exponha apenas os metodos "
                        "que cada consumidor realmente precisa."
                    ),
                })
        return findings[:10]

    def _detect_missing_super_init_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
        for name, node in classes.items():
            if not node.bases:
                continue
            has_init = any(
                isinstance(n, ast.FunctionDef) and n.name == "__init__"
                for n in node.body
            )
            if not has_init:
                continue
            init_node = next(
                n for n in node.body
                if isinstance(n, ast.FunctionDef) and n.name == "__init__"
            )
            calls_super_init = any(
                isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Attribute)
                and isinstance(n.value.func.value, ast.Call)
                and isinstance(n.value.func.value.func, ast.Name)
                and n.value.func.value.func.id == "super"
                and n.value.func.attr == "__init__"
                for n in ast.walk(init_node)
            )
            if not calls_super_init:
                findings.append({
                    "location": f"linha {node.lineno}",
                    "issue": f"Classe '{name}' herda de {ast.unparse(node.bases[0])} mas nao chama super().__init__() no seu __init__",
                    "severity": "ALTA",
                    "line_content": self._get_line(node.lineno),
                    "suggestion": "Adicione super().__init__() no inicio do __init__ para garantir inicializacao da classe pai",
                })
        return findings

    def _detect_override_signature_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
        for name, node in classes.items():
            if not node.bases:
                continue
            for base in node.bases:
                base_name = ast.unparse(base)
                parent = classes.get(base_name)
                if parent is None:
                    continue
                child_methods = {
                    n.name: n for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                parent_methods = {
                    n.name: n for n in parent.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                for mname, cm in child_methods.items():
                    if mname not in parent_methods:
                        continue
                    pm = parent_methods[mname]
                    c_params = [a.arg for a in cm.args.args if a.arg not in ("self", "cls")]
                    p_params = [a.arg for a in pm.args.args if a.arg not in ("self", "cls")]
                    if c_params != p_params:
                        findings.append({
                            "location": f"linha {cm.lineno}",
                            "issue": f"Metodo '{mname}' em '{name}' tem parametros diferentes do metodo na classe pai '{base_name}' ({', '.join(c_params)} vs {', '.join(p_params)})",
                            "severity": "MEDIA",
                            "line_content": self._get_line(cm.lineno),
                            "suggestion": "Mantenha a mesma assinatura do metodo pai para respeitar Liskov Substitution Principle (LSP)",
                        })
        return findings

    def _detect_abstract_method_findings(self) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return findings
        abstract_methods: Dict[str, List[str]] = {}
        abstract_classes: Set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            is_abstract = any(
                ast.unparse(b) in ("ABC", "Protocol")
                for b in node.bases
            )
            abstr_methods = []
            for n in node.body:
                if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for d in n.decorator_list:
                    is_abstractmethod = (
                        (isinstance(d, ast.Attribute) and d.attr == "abstractmethod")
                        or (isinstance(d, ast.Name) and d.id == "abstractmethod")
                    )
                    if is_abstractmethod:
                        abstr_methods.append(n.name)
                        is_abstract = True
            if not is_abstract:
                continue
            abstract_classes.add(node.name)
            if abstr_methods:
                abstract_methods[node.name] = abstr_methods

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name in abstract_classes:
                continue
            for base in node.bases:
                base_name = ast.unparse(base)
                if base_name not in abstract_methods:
                    continue
                implemented = {
                    n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                missing = [m for m in abstract_methods[base_name] if m not in implemented]
                if missing:
                    findings.append({
                        "location": f"linha {node.lineno}",
                        "issue": f"Classe '{node.name}' herda de '{base_name}' mas nao implementa metodos abstratos: {', '.join(missing)}",
                        "severity": "ALTA",
                        "line_content": self._get_line(node.lineno),
                        "suggestion": f"Implemente os metodos {', '.join(missing)} na classe '{node.name}'",
                    })
        return findings[:10]


def run_ruff(filepath: str) -> Dict:
    """Executa ruff se disponivel e retorna findings + disponibilidade."""
    result = {"findings": [], "available": True}
    try:
        subprocess.run(["ruff", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        result["available"] = False
        return result
    try:
        proc = subprocess.run(
            ["ruff", "check", filepath, "--output-format=json"],
            capture_output=True, text=True, timeout=10
        )
        if proc.stdout:
            ruff_output = json.loads(proc.stdout)
            for item in ruff_output[:20]:
                result["findings"].append({
                    "tool": "ruff",
                    "lineno": item.get("location", {}).get("row", 0),
                    "code": item.get("code", ""),
                    "issue": item.get("message", ""),
                    "severity": "MEDIA" if item.get("code", "").startswith("E") else "BAIXA"
                })
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return result


def run_pylint(filepath: str) -> Dict:
    """Executa pylint se disponivel e retorna findings + disponibilidade."""
    result = {"findings": [], "available": True}
    try:
        subprocess.run(["pylint", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        result["available"] = False
        return result
    try:
        proc = subprocess.run(
            ["pylint", filepath, "--output-format=json", "--score=no"],
            capture_output=True, text=True, timeout=15
        )
        if proc.stdout:
            pylint_output = json.loads(proc.stdout)
            for item in pylint_output[:20]:
                mtype = item.get("type", "")
                if mtype in ("error", "warning", "convention"):
                    result["findings"].append({
                        "tool": "pylint",
                        "lineno": item.get("line", 0),
                        "code": item.get("message-id", ""),
                        "issue": item.get("message", ""),
                        "severity": "ALTA" if mtype == "error" else "MEDIA"
                    })
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return result


def run_analysis(filepath: str, config: Optional[Dict] = None) -> Dict[str, Any]:
    """Executa analise completa com integracao de ferramentas externas."""
    file_path = Path(filepath)
    if not file_path.exists():
        return {"success": False, "error": f"Arquivo nao encontrado: {filepath}"}

    try:
        code = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {"success": False, "error": f"Erro ao ler arquivo: {e}"}

    analyzer = ArchitectureAnalyzer(code, filepath, config=config)
    result = analyzer.analyze()

    if result.get("success"):
        result["config"] = config or {}
        ruff_result = run_ruff(filepath)
        pylint_result = run_pylint(filepath)
        result["tool_findings"] = {
            "ruff": ruff_result["findings"],
            "pylint": pylint_result["findings"],
        }
        result["tool_findings"]["total"] = (
            len(result["tool_findings"]["ruff"]) +
            len(result["tool_findings"]["pylint"])
        )
        tool_warnings = []
        if not ruff_result["available"]:
            tool_warnings.append("ruff nao instalado — analise parcial")
        if not pylint_result["available"]:
            tool_warnings.append("pylint nao instalado — analise parcial")
        if tool_warnings:
            result["tool_warnings"] = tool_warnings

    return result


def prune_criteria(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Remove criterios sem findings do dict de analise para reduzir payload."""
    if not isinstance(analysis, dict):
        return analysis
    if "criteria" not in analysis:
        return analysis
    criteria = analysis["criteria"]
    if not isinstance(criteria, dict):
        return analysis
    pruned = {
        k: v for k, v in criteria.items()
        if v.get("findings")
    }
    result = dict(analysis)
    result["criteria"] = pruned
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python analyzer.py <arquivo.py>")
        sys.exit(1)

    result = run_analysis(sys.argv[1])
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
