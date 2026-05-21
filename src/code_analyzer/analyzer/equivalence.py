"""Equivalence test generator — produces pytest scaffold to verify extraction safety."""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Dict, List


def _read_lines(filepath: str) -> List[str]:
    try:
        return Path(filepath).read_text(encoding="utf-8").splitlines()
    except Exception:
        return []


def generate_equivalence_test(
    filepath: str,
    func_name: str,
    candidate: Dict[str, Any],
) -> str:
    """Return a pytest file content that verifies extraction equivalence.

    For pure blocks: generates a concrete assertion scaffold.
    For side_effect/unknown: generates a TODO scaffold with instructions.
    """
    start = candidate["start_line"]
    end = candidate["end_line"]
    suggested_name = candidate.get("suggested_name", "_extract")
    purity = candidate.get("purity", "unknown")
    variables = candidate.get("variables", [])
    reasons = candidate.get("reasons", [])

    lines = _read_lines(filepath)
    block_lines = lines[start - 1:end] if lines else []
    # Dedent to remove original source indentation, then re-indent for function body
    dedented = textwrap.dedent("\n".join(block_lines)).strip()
    block_source = "\n".join(f"    {ln}" for ln in dedented.splitlines())

    vars_preview = ", ".join(variables[:4])
    reason_comment = f"  # {'; '.join(reasons)}" if reasons else ""

    module_name = Path(filepath).stem
    test_func = f"test_equivalence_{suggested_name.lstrip('_')}_{start}"

    if purity == "pure":
        body = f"""\
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Auto-generated equivalence test (Confianca: Alta — bloco puro)
# Funcao: {func_name}, linhas {start}-{end}
# Variaveis: {vars_preview}
# Extraia o bloco para '{suggested_name}()' e valide que o comportamento e identico.


def _inline_block({vars_preview}):
    \"\"\"Original block extracted inline for comparison.\"\"\"
{block_source}


def {test_func}():
    # TODO: substitua pelos valores reais dos argumentos
    # O bloco opera sobre: {vars_preview}
    # Exemplo (ajuste conforme o contexto real):
    sample_args = {{}}  # preencha com argumentos de teste reais
    result_inline = _inline_block(**sample_args)
    result_extracted = {suggested_name}(**sample_args)
    assert result_inline == result_extracted, (
        f"Equivalencia falhou: inline={{result_inline!r}} != extraido={{result_extracted!r}}"
    )
"""
    else:
        body = f"""\
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Auto-generated equivalence test (Confianca: {'Media' if purity == 'side_effect' else 'Baixa'})
# Funcao: {func_name}, linhas {start}-{end}
# Motivo: {', '.join(reasons) if reasons else 'chamadas nao resoluveis'}{reason_comment}
# Variaveis: {vars_preview}
# Instrucoes:
#   1. Extraia o bloco para '{suggested_name}()' no arquivo original
#   2. Ajuste os mocks/fixtures abaixo conforme os side effects reais
#   3. Rode 'pytest' — se passar, a extracao preserva o comportamento


def {test_func}():
    # TODO: configure mocks para os side effects identificados:
    # {reason_comment.strip() or 'nenhum reason detectado automaticamente'}
    #
    # Exemplo de estrutura:
    # from unittest.mock import MagicMock, patch
    # with patch('modulo.dependencia') as mock_dep:
    #     result_original = ... # chame a versao original
    #     result_extraido = {suggested_name}(...)
    #     assert result_original == result_extraido
    pytest.skip("TODO: configure args e mocks para validar equivalencia de '{func_name}' linhas {start}-{end}")
"""

    return body


def write_equivalence_tests(
    filepath: str,
    purity_map: Dict[str, List[Dict[str, Any]]],
    output_dir: str,
) -> List[str]:
    """Generate and write all equivalence test files. Returns list of written paths."""
    written: List[str] = []
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for func_name, candidates in purity_map.items():
        for candidate in candidates:
            content = generate_equivalence_test(filepath, func_name, candidate)
            suggested = candidate.get("suggested_name", "_extract").lstrip("_")
            start = candidate["start_line"]
            fname = f"test_equivalence_{suggested}_{start}.py"
            fpath = out / fname
            try:
                fpath.write_text(content, encoding="utf-8")
                written.append(str(fpath))
            except Exception:
                pass
    return written
