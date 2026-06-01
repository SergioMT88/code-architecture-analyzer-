"""Pattern Advisor — maps architecture findings to design pattern suggestions."""
from __future__ import annotations

from typing import Any, Dict, List


def _avg_score(criteria: Dict[str, Any]) -> float:
    scores = [v.get("score", 10.0) for v in criteria.values()]
    return round(sum(scores) / max(1, len(scores)), 1)


def _has_finding(criteria: Dict[str, Any], name: str) -> bool:
    return bool(criteria.get(name, {}).get("findings"))


def _score(criteria: Dict[str, Any], name: str) -> float:
    return criteria.get(name, {}).get("score", 10.0)


def _finding_texts(criteria: Dict[str, Any], name: str) -> List[str]:
    """Return lowercase issue texts for all findings of a criterion."""
    return [
        f.get("issue", "").lower()
        for f in criteria.get(name, {}).get("findings", [])
    ]


def get_pattern_advice(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a list of design-pattern suggestions based on architecture findings.

    Each item: {pattern, symptom, suggestion, priority, criteria_involved}
    """
    criteria = analysis.get("criteria", {})
    metrics = analysis.get("metrics", {})
    advice: List[Dict[str, Any]] = []

    srp_bad = _score(criteria, "SRP") < 6
    dip_bad = _score(criteria, "DIP") < 6
    cohesion_bad = _score(criteria, "Cohesion") < 6
    coupling_bad = _score(criteria, "Coupling") < 6
    string_dispatch = _has_finding(criteria, "StringDispatch")
    long_methods = _score(criteria, "SRP") < 7 and metrics.get("max_cyclomatic_complexity", 0) > 10
    param_smell = _has_finding(criteria, "LongParameterList")
    god_class = srp_bad and cohesion_bad

    # Observer pattern — notify/subscribe methods + coupling
    observer_detected = _detect_observer(criteria, metrics)
    if observer_detected:
        advice.append(observer_detected)

    # Facade pattern — coordination of multiple subsystems
    facade_detected = _detect_facade(criteria, metrics)
    if facade_detected:
        advice.append(facade_detected)

    # Strategy Pattern
    if string_dispatch:
        advice.append({
            "pattern": "Strategy",
            "symptom": "Dispatch manual com 'self.X == string' em varios metodos",
            "suggestion": (
                "Defina uma interface Strategy e crie uma subclasse por variante. "
                "Substitua os ifs por um dict { chave: SubStrategy() } e delegue."
            ),
            "priority": "ALTA",
            "criteria_involved": ["StringDispatch"],
        })
    elif god_class and param_smell:
        advice.append({
            "pattern": "Strategy",
            "symptom": "God Class com muitos parametros em varios metodos",
            "suggestion": (
                "Identifique grupos de metodos que variam juntos. "
                "Extraia cada grupo para uma classe Strategy injetada no construtor."
            ),
            "priority": "ALTA",
            "criteria_involved": ["SRP", "Cohesion", "LongParameterList"],
        })

    # Facade Pattern (fallback — if not detected structurally)
    if coupling_bad and srp_bad and not string_dispatch and not facade_detected:
        advice.append({
            "pattern": "Facade",
            "symptom": "Alto acoplamento com multiplas responsabilidades",
            "suggestion": (
                "Crie uma classe Facade que encapsula a interacao com os modulos externos. "
                "Clientes so falam com a Facade, reduzindo acoplamento direto."
            ),
            "priority": "ALTA" if _score(criteria, "Coupling") < 4 else "MEDIA",
            "criteria_involved": ["Coupling", "SRP"],
        })

    # Template Method Pattern
    if long_methods and not string_dispatch:
        advice.append({
            "pattern": "Template Method",
            "symptom": "Metodos longos com estrutura similar (alta complexidade ciclomatica)",
            "suggestion": (
                "Extraia o esqueleto do algoritmo para um metodo template na classe base. "
                "Subclasses sobrescrevem apenas os passos que variam."
            ),
            "priority": "MEDIA",
            "criteria_involved": ["SRP"],
        })

    # Dependency Injection / DIP
    if dip_bad:
        advice.append({
            "pattern": "Dependency Injection",
            "symptom": "Dependencias concretas instanciadas internamente (violacao de DIP)",
            "suggestion": (
                "Receba dependencias pelo construtor em vez de instancia-las internamente. "
                "Use uma interface/ABC para cada dependencia injetada."
            ),
            "priority": "ALTA" if _score(criteria, "DIP") < 4 else "MEDIA",
            "criteria_involved": ["DIP"],
        })

    return advice


def _detect_observer(criteria: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any] | None:
    """Detect Observer pattern from DesignPatterns findings and coupling signals."""
    dp_findings = _finding_texts(criteria, "DesignPatterns")
    has_observer_finding = any("observer" in t for t in dp_findings)
    if has_observer_finding:
        return {
            "pattern": "Observer",
            "symptom": "Classe com subscribe + notify indica publicador de eventos",
            "suggestion": (
                "Defina uma interface EventObserver/Listener e registre observers dinamicamente. "
                "Isso desacopla o emissor dos consumidores."
            ),
            "priority": "MEDIA",
            "criteria_involved": ["DesignPatterns", "Coupling"],
        }
    # Heuristic: coupling + notify-like methods
    if _score(criteria, "Coupling") < 5:
        return {
            "pattern": "Observer",
            "symptom": "Acoplamento alto pode indicar notificacao direta entre classes",
            "suggestion": (
                "Se classes notificam umas as outras diretamente, extraia para um padrao Observer. "
                "Defina uma interface EventObserver e registre observers dinamicamente."
            ),
            "priority": "BAIXA",
            "criteria_involved": ["Coupling"],
        }
    return None


def _detect_facade(criteria: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any] | None:
    """Detect Facade pattern from DesignPatterns findings and coordination signals."""
    dp_findings = _finding_texts(criteria, "DesignPatterns")
    has_facade_finding = any("facade" in t for t in dp_findings)
    if has_facade_finding:
        return {
            "pattern": "Facade",
            "symptom": "Classe coordena multiplos subsistemas",
            "suggestion": (
                "Documente a Facade e garanta que ela nao acumula logica — "
                "apenas delega para subsistemas especializados."
            ),
            "priority": "MEDIA",
            "criteria_involved": ["DesignPatterns"],
        }
    return None
