"""HardcodedSecrets detector — credentials/tokens/keys as string literals in code."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_SENSITIVE_KEYWORDS = frozenset({
    "secret", "password", "passwd", "api_key", "apikey", "token",
    "credential", "credentials", "private_key", "privatekey",
    "access_key", "accesskey", "client_secret", "auth_key",
    "auth_token", "secret_key", "secretkey", "jwt_secret",
    "encryption_key", "signing_key", "webhook_secret",
    "stripe", "stripe_key", "stripe_secret",
    "sk_live", "pk_live", "sk_test", "pk_test",
})

_PLACEHOLDER_HINTS = frozenset({
    "your-", "your_", "<your", "example", "placeholder",
    "changeme", "changethis", "xxxxxx", "replace-me", "replace_me",
    "todo", "insert", "here", "dummy", "fake", "test-key",
})

_MIN_LENGTH = 6


def _looks_like_placeholder(value: str) -> bool:
    lower = value.lower()
    return any(hint in lower for hint in _PLACEHOLDER_HINTS)


def _name_is_sensitive(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in _SENSITIVE_KEYWORDS)


def _check_assignment(target_name: str, value_node: ast.AST, lineno: int, ctx: "AnalysisContext") -> "Finding | None":
    if not _name_is_sensitive(target_name):
        return None
    if not isinstance(value_node, ast.Constant):
        return None
    value = value_node.value
    if not isinstance(value, str) or len(value) < _MIN_LENGTH:
        return None
    if _looks_like_placeholder(value):
        return None
    masked = value[:4] + "..." if len(value) > 4 else "***"
    return Finding(
        criterion="HardcodedSecrets",
        location=f"linha {lineno}",
        line=lineno,
        severity="ALTA",
        issue=(
            f"Credencial hardcoded detectada: '{target_name}' = '{masked}'. "
            "Segredos em codigo-fonte vazam via git history, logs e repositorios publicos."
        ),
        suggestion=(
            f"Mova '{target_name}' para variavel de ambiente: "
            f"os.environ.get('{target_name.upper()}') ou use python-decouple/django-environ."
        ),
        line_content=ctx.get_line(lineno),
    )


@register
class HardcodedSecretsDetector(Detector):
    name = "HardcodedSecrets"
    severity = "ALTA"
    penalty_per_finding = 4
    default_confidence = 0.95
    description = "Hardcoded secret — credential/token/key stored as string literal instead of environment variable"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        for node in ctx.get_nodes_by_type(ast.Assign, ast.AnnAssign):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        finding = _check_assignment(target.id, node.value, node.lineno, ctx)
                        if finding:
                            findings.append(finding)
                    elif isinstance(target, ast.Attribute):
                        finding = _check_assignment(target.attr, node.value, node.lineno, ctx)
                        if finding:
                            findings.append(finding)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.value is not None:
                    finding = _check_assignment(node.target.id, node.value, node.lineno, ctx)
                    if finding:
                        findings.append(finding)
        return findings
