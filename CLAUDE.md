# CLAUDE.md — Code Architecture Analyzer

Guia de contexto para o Claude Code trabalhar neste repositório.

## O que é este projeto

Ferramenta CLI de análise de arquitetura Python com refatoração automática não-destrutiva.
Publicada no npm como `code-architecture-analyzer`. Usa Node.js como wrapper e Python como motor de análise.

## Como instalar e testar

```bash
pip install -e .              # instala em modo editável
python -m pytest tests/ -v    # roda os 129 testes
```

Não há Makefile nem CI. Testes ficam em `tests/test_skill_core.py`.

## Arquivos-chave

| Arquivo | Papel |
|---------|-------|
| `src/code_analyzer/orchestrator.py` | Pipeline principal (`run_pipeline`) e saída no terminal |
| `src/code_analyzer/analyzer/__init__.py` | `run_analysis()` — coordena AST + pylint + ruff + project_context |
| `src/code_analyzer/analyzer/core.py` | `ArchitectureAnalyzer` (AST visitor) + `run_pylint()` + `run_ruff()` |
| `src/code_analyzer/report_generator.py` | Geração de Markdown, HTML e JSON |
| `src/code_analyzer/project_context.py` | Leitura de CLAUDE.md para surfacing de débitos conhecidos |
| `src/code_analyzer/history.py` | Persistência de histórico de scores entre execuções |
| `src/code_analyzer/analyzer/detectors/` | 36 detectores @register, um por critério |
| `src/code_analyzer/pattern_advisor.py` | `get_pattern_advice()` — mapeia findings → padrão de design (Strategy, Facade, etc.) [v3.3.0] |
| `src/code_analyzer/analyzer/dataflow.py` | `analyze_file()` — clusters def-use em funções longas [v3.4.0] |
| `src/code_analyzer/analyzer/semantic.py` | `compare_files()` + `compare_directory()` — duplicação cross-file [v3.4.0] |

## Limites conhecidos da ferramenta (feedback de uso real — 2026-05-20)

1. **Pylint não confiável em Django sem ambiente configurado** — erros E0401/E0611 derrubam o score para 0.00/10 sem refletir qualidade real. A partir de v3.2.2, `run_pylint()` detecta isso e emite warning `unreliable=True`.

2. **Cobertura de testes é inferencial** — a ferramenta NÃO executa `pytest --cov`. Ela lê o código e infere cobertura por correspondência de nomes (`test_X` cobre `X`). Pode errar em cobertura indireta.

3. **Não detecta bugs semânticos** — filtro-após-slice em QuerySet Django, `usuario=None` passado onde não esperado, race conditions — são invisíveis para análise estática. Score alto ≠ ausência de bugs funcionais.

4. **Scores são de convenção, não de corretude** — um arquivo com 9.28/10 pode ter 3 bugs críticos. O score mede SOLID, complexidade ciclomática, acoplamento. Desde v3.2.2, relatórios exibem esse disclaimer explicitamente.

5. **Sem memória entre análises** — cada run parte do zero. Desde v3.2.2, a ferramenta lê o CLAUDE.md do projeto analisado e exibe débitos conhecidos no relatório (seção "Contexto do Projeto").

## Convenções de código

- Python source em inglês. Saída terminal (user-visible) em português.
- `max-line-length = 100` (ruff).
- Cada novo detector em `detectors/` precisa: `@register`, suporte a `ignore_criteria`, teste em `test_skill_core.py`.
- Nunca modificar arquivo sem backup automático.
- Rodar `python -m pytest tests/` antes de marcar qualquer item como concluído.

## Versionamento

Versão atual: **3.4.0** (definida em `src/code_analyzer/__init__.py` e `package.json`).
v3.4.0 — Análise Estrutural: SC (fan-in, git frequency, priority index), CF (cross-file dup, project mode), DF (data-flow clusters).

## Workflow de desenvolvimento

```
docs/backlog.md  →  docs/sprint_atual.md  →  código + testes  →  docs/sprint_concluida/
```

- Items arquivados em `docs/sprint_concluida/YYYY-MM-DD-itemN-desc.md`
- `.skill_outputs/` é gitignored
- Não há CI — rodar pytest manualmente

## Dependências Python opcionais

`pylint`, `ruff`, `black`, `isort`, `pytest` — instalar via `code-analyze setup` ou `pip install`.
A ferramenta degrada graciosamente se qualquer uma estiver ausente.
