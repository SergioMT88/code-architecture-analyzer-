"""Utilitários de baixo nível: filtros e execução de comandos.

Aqui moram os SUMIDOUROS de taint. A vulnerabilidade só se realiza quando
um valor controlado pelo usuário (vindo de outro módulo) chega até cá.
"""

import subprocess

# segredo hardcoded (ocorrência 1/2) — formato de chave de provedor
STRIPE_KEY = "sk_test__REPLACED_BY_HISTORY_REWRITE"


def build_filter(user_value):
    """Monta um fragmento WHERE a partir de um valor cru. Sem escaping."""
    return f"name = '{user_value}'"


def run_command(parts):
    """Executa uma lista de tokens como shell. shell=True + join = injeção."""
    linha = " ".join(parts)
    return subprocess.run(linha, shell=True, capture_output=True)
