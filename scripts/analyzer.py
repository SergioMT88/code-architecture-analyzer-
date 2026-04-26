#!/usr/bin/env python3
"""
Analyzer - Analise profunda de arquitetura Python v2.1.3
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

    analyzer = ArchitectureAnalyzer(code, filepath, config=config)
    result = analyzer.analyze()

    if result.get("success"):
        result["config"] = config or {}
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
