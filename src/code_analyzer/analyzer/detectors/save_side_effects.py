"""SaveSideEffects detector — external I/O inside def save() on models.Model subclasses."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List, Set

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.analyzer.detectors._utils import class_bases

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_MODEL_BASES = frozenset({"Model", "models.Model", "TimeStampedModel", "MPTTModel", "PolymorphicModel"})

_IO_CALL_NAMES = frozenset({
    "send_mail", "send_mass_mail", "mail_admins", "mail_managers",
    "delay", "apply_async", "apply",
    "push", "notify", "send_notification",
    "get", "post", "put", "patch", "delete", "request",
    "urlopen", "urlretrieve",
    "publish", "send",
})

_IO_ATTR_CHAINS = frozenset({
    "requests", "urllib", "http", "smtplib", "socket",
    "boto3", "s3", "redis", "celery", "slack_sdk", "twilio",
    "firebase_admin", "sendgrid", "mailchimp", "stripe",
})


def _is_io_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name) and func.id in _IO_CALL_NAMES:
        return True
    if isinstance(func, ast.Attribute):
        if func.attr in _IO_CALL_NAMES:
            return True
        # Check root of chain: requests.get, celery.delay, boto3.client, etc.
        root = func.value
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id in _IO_ATTR_CHAINS:
            return True
    return False


@register
class SaveSideEffectsDetector(Detector):
    name = "SaveSideEffects"
    severity = "ALTA"
    penalty_per_finding = 4
    description = "Side effects in save() — external I/O inside model.save() breaks atomicity and testability"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ast.walk(ctx.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = class_bases(node)
            is_model = any(b in _MODEL_BASES for b in bases)
            if not is_model:
                continue

            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name != "save":
                    continue

                for child in ast.walk(item):
                    if not isinstance(child, ast.Call):
                        continue
                    if not _is_io_call(child):
                        continue
                    lineno = getattr(child, "lineno", item.lineno)
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"classe {node.name}.save(), linha {lineno}",
                        line=lineno,
                        severity="ALTA",
                        issue=(
                            f"Side effect externo (I/O, email, HTTP, fila) dentro de "
                            f"'{node.name}.save()'. Se a transacao for revertida (rollback), "
                            "o side effect ja foi disparado — impossivel desfazer."
                        ),
                        suggestion=(
                            "Mova o side effect para um signal com transaction.on_commit(), "
                            "ou para uma task Celery disparada apos o commit. "
                            "Exemplo: transaction.on_commit(lambda: send_mail(...))"
                        ),
                        line_content=ctx.get_line(lineno),
                    ))

        return findings
