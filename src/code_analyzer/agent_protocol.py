"""Agent-Native Protocol — manifest, streaming events, and structured diffs.

This module defines the communication contract between the CLI tool and AI coding
agents. Instead of parsing terminal output, agents consume structured JSON/NDJSON.

A4P v1.0 — Agent-Augmented Architecture Analysis Protocol.
Supports hybrid detection: TOOL (deterministic AST) + AGENT (semantic reasoning).

CONTRACT VERSION: 1.0
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List


@dataclass
class Manifest:
    """Describes every capability the tool exposes to AI agents."""

    tool: str = "code-architecture-analyzer"
    protocol_version: str = "1.0"
    version: str = ""

    analysis: Dict[str, Any] = field(default_factory=dict)
    refactoring: Dict[str, Any] = field(default_factory=dict)
    agent_integration: Dict[str, Any] = field(default_factory=dict)

    streaming: bool = True
    confidence_scores: bool = True
    diffs_structured: bool = True

    known_gaps: List[Dict[str, Any]] = field(default_factory=list)

    requirements: Dict[str, Any] = field(default_factory=dict)

    commands: List[Dict[str, str]] = field(default_factory=list)
    criteria: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


class StreamEvent:
    """Base class for all streaming events emitted with --stream."""

    @staticmethod
    def phase(name: str, status: str, **extra) -> str:
        payload = {"event": "phase", "name": name, "status": status, **extra}
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def progress(current: int, total: int, file: str = "", **extra) -> str:
        payload = {"event": "progress", "current": current, "total": total, "file": file, **extra}
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def finding(file: str, criterion: str, severity: str, confidence: float,
                line: int = 0, issue: str = "", suggestion: str = "",
                location: str = "", source: str = "TOOL", **extra) -> str:
        payload = {
            "event": "finding",
            "file": file,
            "criterion": criterion,
            "severity": severity,
            "confidence": confidence,
            "line": line,
            "issue": issue,
            "suggestion": suggestion,
            "location": location,
            "source": source,
            **extra,
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def score(file: str, score: float, grade: str, mi: float = 0,
              risk: float = 0, **extra) -> str:
        payload = {
            "event": "score",
            "file": file,
            "score": score,
            "grade": grade,
            "mi": mi,
            "risk": risk,
            **extra,
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def summary(total_files: int = 1, total_findings: int = 0,
                critical: int = 0, high: int = 0, medium: int = 0, low: int = 0,
                **extra) -> str:
        payload = {
            "event": "summary",
            "total_files": total_files,
            "total_findings": total_findings,
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
            **extra,
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def action(record_id: str, criterion: str, severity: str, confidence: float,
               file: str, line: int, issue: str, suggestion: str = "",
               diff: str = "", verify: str = "", **extra) -> str:
        payload = {
            "event": "action",
            "id": record_id,
            "criterion": criterion,
            "severity": severity,
            "confidence": confidence,
            "file": file,
            "line": line,
            "issue": issue,
            "suggestion": suggestion,
            "diff": diff,
            "verify": verify,
            **extra,
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def error(message: str, code: str = "ERR_UNKNOWN", **extra) -> str:
        payload = {"event": "error", "message": message, "code": code, **extra}
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def done(**extra) -> str:
        payload = {"event": "done", **extra}
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def gap(criterion: str, file: str, reason: str, hint: str = "",
            severity: str = "MEDIA", **extra) -> str:
        payload = {
            "event": "gap",
            "criterion": criterion,
            "file": file,
            "reason": reason,
            "hint": hint,
            "severity": severity,
            "source": "TOOL",
            "agent_should_review": True,
            **extra,
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def augment(finding_criterion: str, file: str, field: str,
                old_value: Any, new_value: Any, rationale: str = "",
                source: str = "AGENT", **extra) -> str:
        payload = {
            "event": "augment",
            "criterion": finding_criterion,
            "file": file,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "rationale": rationale,
            "source": source,
            **extra,
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def emit(line: str) -> None:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def build_manifest(version: str) -> Manifest:
    from code_analyzer.analyzer.detectors import REGISTRY

    return Manifest(
        version=version,
        analysis={
            "modes": ["file", "project"],
            "phases": ["identification", "proposition", "implementation"],
            "tools": ["ruff"],
            "criteria_count": len(REGISTRY),
        },
        refactoring={
            "safe": True,
            "dry_run": True,
            "backup": True,
            "phases": [
                "cleanup", "structure", "test_scaffold",
                "formatting", "validation",
            ],
        },
        agent_integration={
            "streaming": True,
            "manifest": True,
            "structured_diffs": True,
            "token_efficient": True,
            "a4p_protocol": True,
            "gap_events": True,
            "augment_events": True,
            "source_tracing": True,
        },
        streaming=True,
        confidence_scores=True,
        diffs_structured=True,
        known_gaps=[
            {
                "criterion": "GodClass",
                "limit": "Threshold is max_methods+5=15; classes with 8-14 methods across 3+ concerns are missed",
                "agent_can_cover": True,
                "guidance": "Check classes with 8+ public methods touching 3+ distinct concerns (different attribute groups, different import categories)",
                "severity": "MEDIA",
            },
            {
                "criterion": "UselessListComp",
                "limit": "No detector exists for [x for x in xs] anti-pattern",
                "agent_can_cover": True,
                "guidance": "Look for list/dict comprehensions that are pure copies: [x for x in xs], {k: v for k, v in d.items()}",
                "severity": "BAIXA",
            },
            {
                "criterion": "TaintFlow",
                "limit": "Intra-file taint (incl. class methods) is built in since v7.6 and surfaced under envelope['semantic']; cross-module taint remains single-hop (multi-hop import chains not connected)",
                "agent_can_cover": True,
                "guidance": "Trace user-controlled values across module boundaries via import graph for the multi-hop case. Follow call chains from HTTP input sources (request.GET, request.POST) through service layers to sinks (cursor.execute, subprocess.run)",
                "severity": "ALTA",
            },
            {
                "criterion": "CloneDetection",
                "limit": "Only detects identical AST fingerprints; near-duplicates (renamed variables, different variable order) are missed",
                "agent_can_cover": True,
                "guidance": "Look for functions with similar structure but different variable names. Compare cyclomatic complexity and control flow patterns",
                "severity": "MEDIA",
            },
            {
                "criterion": "BusinessLogic",
                "limit": "Semantic analysis is limited to taint/dataflow/purity (envelope['semantic']); ORM behavior, race conditions, and incorrect business rules remain invisible to static analysis",
                "agent_can_cover": True,
                "guidance": "Read function logic and check: (1) does ORM usage match Django/SQLAlchemy best practices? (2) are there TOCTOU patterns? (3) do validation and mutation happen in correct order?",
                "severity": "ALTA",
            },
            {
                "criterion": "ScoreCalibration",
                "limit": "Score measures conventions (SOLID, complexity, coupling), not correctness. A 9.9/10 file can have 3 critical security bugs. The score does not reflect semantic quality.",
                "agent_can_cover": True,
                "guidance": "Recalibrate score based on security findings: each InjectionRisk -1.5, each HardcodedSecret -1.0, each MassAssignment -1.0. Combine tool score with security-weighted adjustment.",
                "severity": "ALTA",
            },
        ],
        requirements={
            "python": ">=3.8",
            "optional": ["ruff", "black", "isort", "pytest", "pytest-cov"],
            "node": ">=14.0.0",
        },
        commands=[
            {"name": "manifest", "description": "Return this manifest including known_gaps for agent augmentation", "agent_only": True},
            {"name": "check --stream <file>", "description": "Analyze with streaming events (findings + gaps)", "agent_only": False},
            {"name": "setup --agent", "description": "Install deps with machine-readable progress", "agent_only": True},
            {"name": "agent <file>", "description": "Generate metacognitive prompt", "agent_only": False},
        ],
        criteria=sorted(d.name for d in REGISTRY if hasattr(d, "name")),
        patterns=sorted([
            "Singleton", "FactoryMethod", "AbstractFactory", "Builder",
            "Prototype", "Adapter", "Bridge", "Composite", "Decorator",
            "Facade", "Proxy", "ChainOfResponsibility", "Command",
            "Iterator", "Mediator", "Memento", "Observer", "State",
            "Strategy", "TemplateMethod",
        ]),
    )
