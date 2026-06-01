"""HardcodedSecrets detector — credentials/tokens/keys as string literals in code.

Two complementary passes:
  1. name-based  — assignment to a sensitively-named variable with a literal value
  2. value-based — any string literal matching a known provider key format
                   (AWS/GitHub/Stripe/Google/Slack/private-key block), regardless
                   of the variable name. Catches `cfg = "AKIA..."`.
"""
from __future__ import annotations

import ast
import re
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

# Provider key formats — high-specificity prefixes, low false-positive risk.
# (label, compiled regex). Each pattern is anchored to a provider-specific shape.
_PROVIDER_PATTERNS = [
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Stripe key", re.compile(r"\b[sprk]k_(?:live|test)_[A-Za-z0-9]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
]


def _match_provider(value: str) -> "str | None":
    """Return the provider label if *value* matches a known key format, else None."""
    for label, pattern in _PROVIDER_PATTERNS:
        if pattern.search(value):
            return label
    return None


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
        flagged_lines: set = set()

        # Pass 1 — name-based: sensitively-named target with a literal value.
        for node in ctx.get_nodes_by_type(ast.Assign, ast.AnnAssign):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        finding = _check_assignment(target.id, node.value, node.lineno, ctx)
                        if finding:
                            findings.append(finding)
                            flagged_lines.add(node.lineno)
                    elif isinstance(target, ast.Attribute):
                        finding = _check_assignment(target.attr, node.value, node.lineno, ctx)
                        if finding:
                            findings.append(finding)
                            flagged_lines.add(node.lineno)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.value is not None:
                    finding = _check_assignment(node.target.id, node.value, node.lineno, ctx)
                    if finding:
                        findings.append(finding)
                        flagged_lines.add(node.lineno)

        # Pass 2 — value-based: any string literal matching a provider key format,
        # regardless of variable name. Skips lines already flagged by pass 1.
        for node in ctx.get_nodes_by_type(ast.Constant):
            if not isinstance(node.value, str) or len(node.value) < _MIN_LENGTH:
                continue
            if node.lineno in flagged_lines:
                continue
            if _looks_like_placeholder(node.value):
                continue
            label = _match_provider(node.value)
            if label is None:
                continue
            masked = node.value[:4] + "..."
            findings.append(Finding(
                criterion="HardcodedSecrets",
                location=f"linha {node.lineno}",
                line=node.lineno,
                severity="ALTA",
                issue=(
                    f"Credencial hardcoded detectada por formato ({label}): '{masked}'. "
                    "Segredos em codigo-fonte vazam via git history, logs e repositorios publicos."
                ),
                suggestion=(
                    "Mova o segredo para variavel de ambiente (os.environ) ou um cofre "
                    "de segredos e rotacione a chave exposta imediatamente."
                ),
                line_content=ctx.get_line(node.lineno),
            ))
            flagged_lines.add(node.lineno)

        return findings
