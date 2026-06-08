"""Project-level Pattern Advisor — maps cross-file findings to design pattern advice [B11, v7.5.0].

Extends the per-file ``pattern_advisor.get_pattern_advice`` to the cross-file world:
ShotgunSurgery → Facade, HighFanIn → Dependency Inversion, CloneDetection →
Template Method, TaintFlow → Sanitization Layer.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _has_cross_finding(criteria: Dict[str, Any], name: str) -> bool:
    return bool(criteria.get(name, {}).get("findings"))


def _cross_count(criteria: Dict[str, Any], name: str) -> int:
    return len(criteria.get(name, {}).get("findings", []))


def get_project_pattern_advice(
    cross_criteria: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Return pattern suggestions based on cross-file findings.

    Each item: {pattern, symptom, suggestion, priority, criteria_involved}
    """
    advice: List[Dict[str, Any]] = []

    if _has_cross_finding(cross_criteria, "ShotgunSurgery"):
        n = _cross_count(cross_criteria, "ShotgunSurgery")
        advice.append({
            "pattern": "Facade",
            "symptom": f"{n} literais magicos repetidos em multiplos modulos",
            "suggestion": (
                "Centralize cada literal em uma constante/modulo unico. "
                "Crie uma Facade que exponha esses valores e seja importada "
                "por todos os consumidores."
            ),
            "priority": "ALTA",
            "criteria_involved": ["ShotgunSurgery"],
        })

    if _has_cross_finding(cross_criteria, "HighFanIn"):
        advice.append({
            "pattern": "Dependency Inversion",
            "symptom": "Simbolo importado por 5+ modulos — acoplamento concentrado",
            "suggestion": (
                "Defina uma interface/Protocol que abstraia o contrato do "
                "simbolo. Faca os consumidores dependerem da interface, nao "
                "da implementacao concreta."
            ),
            "priority": "ALTA",
            "criteria_involved": ["HighFanIn"],
        })

    if _has_cross_finding(cross_criteria, "CloneDetection"):
        n = _cross_count(cross_criteria, "CloneDetection")
        advice.append({
            "pattern": "Template Method",
            "symptom": f"{n} funcoes estruturalmente identicas em arquivos distintos",
            "suggestion": (
                "Extraia o corpo comum para uma classe base e use Template Method: "
                "a base implementa o esqueleto, subclasses sobrescrevem apenas "
                "os passos que variam."
            ),
            "priority": "MEDIA",
            "criteria_involved": ["CloneDetection"],
        })

    if _has_cross_finding(cross_criteria, "TaintFlow"):
        n = _cross_count(cross_criteria, "TaintFlow")
        advice.append({
            "pattern": "Sanitization Layer",
            "symptom": f"{n} fluxos contaminados entre modulos",
            "suggestion": (
                "Crie uma camada de sanitizacao (funcao/filtro/middleware) que "
                "valide e higienize dados na fronteira entre modulos antes que "
                "alcancem sinks sensiveis."
            ),
            "priority": "CRITICA",
            "criteria_involved": ["TaintFlow"],
        })

    if _has_cross_finding(cross_criteria, "GodClassCrossFile"):
        n = _cross_count(cross_criteria, "GodClassCrossFile")
        advice.append({
            "pattern": "Strategy",
            "symptom": f"Classe com {n} achados acumula muitos servicos externos",
            "suggestion": (
                "Extraia grupos de metodos que usam os mesmos servicos "
                "importados para classes Strategy separadas. Injete-as "
                "como dependencias no construtor da classe original."
            ),
            "priority": "ALTA",
            "criteria_involved": ["GodClassCrossFile"],
        })

    active = {c["pattern"] for c in advice}
    if len(advice) >= 2 and "Facade" in active and "Dependency Inversion" in active:
        advice.append({
            "pattern": "Strategy",
            "symptom": "Projeto com multiplos problemas estruturais cross-file",
            "suggestion": (
                "Considere uma estrategia coordenada de refactoring: aplique "
                "Dependency Inversion nos hotspots de acoplamento e Facade nos "
                "literais repetidos, revisando um modulo por vez."
            ),
            "priority": "MEDIA",
            "criteria_involved": ["ShotgunSurgery", "HighFanIn"],
        })

    return advice
