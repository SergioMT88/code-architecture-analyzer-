# CLAUDE.md — Code Architecture Analyzer

Guia de contexto para o Claude Code trabalhar neste repositório.

## O que é este projeto

Ferramenta CLI de análise de arquitetura Python com refatoração automática não-destrutiva.
Publicada no npm como `code-architecture-analyzer`. Usa Node.js como wrapper e Python como motor de análise.

## Como instalar e testar

```bash
pip install -e .              # instala em modo editável
python -m pytest tests/ -v    # roda os 166 testes
```

Não há Makefile nem CI. Testes ficam em `tests/test_skill_core.py`.

## Arquivos-chave

| Arquivo | Papel |
|---------|-------|
| `src/code_analyzer/orchestrator.py` | Entry point (`build_parser` + `main`) |
| `src/code_analyzer/pipeline.py` | Pipeline core (`run_pipeline`, `_setup`, `_phase1-3`, `_finalize`) [v4.4] |
| `src/code_analyzer/terminal_ui.py` | Terminal UI (`ScoreBundle`, `print_*` functions) [v4.4] |
| `src/code_analyzer/interactive.py` | Interactive menu (`interactive_menu`) [v4.4] |
| `src/code_analyzer/gate.py` | Min-score gate (`check_min_score`) [v4.4] |
| `src/code_analyzer/analyzer/__init__.py` | `run_analysis()` — coordena AST + ruff + project_context |
| `src/code_analyzer/analyzer/core.py` | `ArchitectureAnalyzer` (AST visitor) + `run_ruff()` (ruleset expandido — substitui pylint) |
| `src/code_analyzer/analyzer/criteria_cache.py` | Cache persistente de criteria por hash de conteudo [v6.0.0] |
| `src/code_analyzer/report_generator.py` | Geração de Markdown, HTML e JSON |
| `src/code_analyzer/project_context.py` | Leitura de CLAUDE.md para surfacing de débitos conhecidos |
| `src/code_analyzer/history.py` | Persistência de histórico de scores entre execuções |
| `src/code_analyzer/analyzer/detectors/` | 46 detectores @register (inclui HardcodedSecrets, InjectionRisk, ContextManagerLeak — v4.2.0) |
| `src/code_analyzer/analyzer/purity.py` | Classifica blocos candidatos como pure/side_effect/unknown [v4.0.0] |
| `src/code_analyzer/analyzer/equivalence.py` | Gera test_equivalence_*.py para candidatos de extração [v4.0.0] |
| `src/code_analyzer/analyzer/fingerprint_index.py` | Índice incremental de fingerprints em ~/.code-analyzer/fingerprints/ [v4.0.0] |
| `src/code_analyzer/analyzer/test_pain.py` | TP1-TP4: mock density, cobertura, complexidade, isolamento — revela acoplamento real via testes [v5.0.0] |
| `src/code_analyzer/pattern_advisor.py` | `get_pattern_advice()` — mapeia findings → padrão de design (Strategy, Facade, etc.) [v3.3.0] |
| `src/code_analyzer/analyzer/dataflow.py` | `analyze_file()` — clusters def-use em funções longas [v3.4.0] |
| `src/code_analyzer/analyzer/semantic.py` | `compare_files()` + `compare_directory()` — duplicação cross-file [v3.4.0] |

## Limites conhecidos da ferramenta (feedback de uso real — 2026-05-20)

1. **~~Pylint não confiável em Django~~** — *Removido em v6.0.0*. Pylint foi substituído por `ruff --select=E,F,W,B,SIM,UP,PL,RUF` (ruleset que porta PLR/PLW/PLC do pylint em Rust, ~25x mais rápido). Sem mais subprocess de 2s/arquivo, sem warning `unreliable` por configuração de ambiente.

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

Versão atual: **6.0.0** (definida em `package.json`).
v6.0.0 — Performance overhaul: (1) 43 detectores migrados para `ctx._walk_cache` compartilhado (sem mais `ast.parse(ctx.code)` ou `ast.walk(tree)` redundantes); (2) Pylint removido — substituido por `ruff --select=E,F,W,B,SIM,UP,PL,RUF` (cobertura equivalente, ~25x mais rapido); (3) Cache de criteria por hash em `~/.code-analyzer/criteria_cache/`; (4) Timing por detector no resultado (`performance.detector_timings`).
v4.0.0 — Cirurgia Robótica: purity.py, equivalence.py, fingerprint_index.py, fuzzy similarity (--threshold), seção [Equivalência] no terminal e Markdown.
v4.1.0 — Django-Aware: IdentityComparison, OrmInLoop (N+1), MassAssignment (fields='__all__'), SaveSideEffects (I/O em save()). 43 critérios, 153 testes.
v4.2.0 — Security Triad: HardcodedSecrets (credenciais literais), InjectionRisk (SQL/command via f-string), ContextManagerLeak (open() sem with). 46 critérios, 166 testes.
v4.3.0 — FeatureEnvy, ShotgunSurgery, LSP (set_X side-effect), pre-commit hook (--min-score), code-analyze init. 49 critérios, 193 testes.
v5.0.0 — Test Pain metrics (TP1-TP4): mock density, coverage, complexity, isolation. 203 testes.
v4.3.1 — P0 fixes: LSP remove NotImplementedError false-positive (padrão ABC legítimo); DesignPatterns penalty_per_finding=0 (findings informacionais não reduzem score).
v4.3.2 — Packaging fix: remove __pycache__ e .skill_outputs do pacote npm (1.1 MB → 423 kB); remove links para docs locais do README que quebravam renderização no npmjs.com.

## Workflow de desenvolvimento

```
docs/backlog.md  →  docs/sprint_atual.md  →  código + testes  →  docs/sprint_concluida/
```

- Items arquivados em `docs/sprint_concluida/YYYY-MM-DD-itemN-desc.md`
- `.skill_outputs/` é gitignored
- Não há CI — rodar pytest manualmente

## Dependências Python opcionais

`ruff`, `black`, `isort`, `pytest` — instalar via `code-analyze setup` ou `pip install`.
A ferramenta degrada graciosamente se qualquer uma estiver ausente. **A partir da v6.0.0 pylint foi removido** — ruff cobre todos os checks PL nativamente, ~25x mais rápido.
