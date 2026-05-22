---
name: code-architecture-analyzer
description: Analise profunda de arquitetura Python com refatoracao automatica segura. 46 criterios: SOLID, anti-patterns LLM, Django-Aware (N+1, MassAssignment, SaveSideEffects), Security (HardcodedSecrets, InjectionRisk, ContextManagerLeak), cross-file semantico, data-flow, purity classification, equivalence tests. 166 testes.
compatibility: Python 3.8+, Node.js 14+
version: 4.2.0
---

# Code Architecture Analyzer v4.2.0

Analisador profundo de arquitetura Python com refatoracao automatica segura (dry-run + backup + patch).

**46 criterios** — SOLID, LLM patterns, Django-Aware, Security, cross-file, data-flow, purity classification.

## Arquitetura da CLI

O pacote NPM (`code-architecture-analyzer`) expoe o comando `code-analyze` via `package.json` `"bin"`, que aponta para **`bin/cli.js`** (Node.js com commander). Existem dois entrypoints Python:

| Entrypoint | Uso |
|---|---|
| `bin/cli.py` | Thin shim: insere `src/` no `sys.path`, chama `code_analyzer.cli:main` |
| `bin/cli.js` | CLI Node.js com `commander` (wrapper com spinners) |
| `index.js` | API programatica (`require('code-architecture-analyzer')`) |

Subcomandos: `analyze`/`a`, `check`/`c`, `refactor`/`r`, `validate`/`v`, `dup`, `project`, `history`, `init`, `info`, `setup`.

**Performance:** ruff + pylint em paralelo via `ThreadPoolExecutor`. Cache AST (ctx.tree). Historico com indice `.index.json` (O(1) lookup). Lazy evaluation por MD5.

## Estrutura do Pacote Python

```
src/code_analyzer/
  __init__.py              # API publica: run_analysis(), prune_criteria()
  cli.py                   # dispatch() — roteador de subcomandos
  orchestrator.py          # pipeline argparse (build_parser + run_pipeline)
  report_generator.py      # ReportGenerator — Markdown, HTML, JSON
  history.py               # save/load snapshots, .index.json, lazy evaluation
  pattern_advisor.py       # mapeia findings -> Strategy, Facade, etc. [v3.3]
  project_context.py       # fan-in, git frequency, priority index, CLAUDE.md [v3.4]
  analyzer/
    __init__.py            # run_analysis(), detect_all()
    core.py                # ArchitectureAnalyzer (NodeVisitor slim)
    context.py             # AnalysisContext dataclass
    scoring.py             # score_to_status, mi_grade, production_risk_score
    semantic.py            # compare_files(), compare_directory() [v3.4]
    dataflow.py            # analyze_file() — def-use clusters [v3.4]
    purity.py              # classify_block/file() — pure/side_effect/unknown [v4.0]
    equivalence.py         # generate_equivalence_test() — test_equivalence_*.py [v4.0]
    fingerprint_index.py   # update_index(), load_index() — mtime incremental [v4.0]
    detectors/
      __init__.py          # Finding, Detector ABC, REGISTRY, @register
      _utils.py            # build_parent_map(), class_bases() compartilhados
      srp.py … (46 arquivos, um por criterio)
```

## 46 Criterios Avaliados

### SOLID + Arquitetura (10)

| # | Criterio | Severidade |
|---|----------|-----------|
| 1 | Single Responsibility (SRP) | ALTA |
| 2 | Open/Closed Principle (OCP) | MEDIA |
| 3 | Dependency Inversion (DIP) | ALTA |
| 4 | Layer Separation | ALTA |
| 5 | Coupling | ALTA |
| 6 | Cohesion | MEDIA |
| 7 | Design Patterns | MEDIA |
| 8 | God Class/Object | ALTA |
| 9 | Circular Dependencies | ALTA |
| 10 | Interface Segregation | MEDIA |

### Padroes de Erros LLM (24)

| # | Criterio | Severidade |
|---|----------|-----------|
| 11 | BareExcept | ALTA |
| 12 | NoneComparison | BAIXA |
| 13 | MutableDefault | ALTA |
| 14 | ShadowingBuiltins | MEDIA |
| 15 | SecurityRisk (eval/exec/pickle) | ALTA |
| 16 | AsyncSyncMismatch | ALTA |
| 17 | RedundantIfReturn | BAIXA |
| 18 | InconsistentReturns | MEDIA |
| 19 | DotKeys | BAIXA |
| 20 | StringConcatInLoop | MEDIA |
| 21 | AnyAllListComp | BAIXA |
| 22 | DeepNesting | MEDIA |
| 23 | TypeIsinstance | BAIXA |
| 24 | UnusedIterationVar | BAIXA |
| 25 | DictGet | BAIXA |
| 26 | ManualAccumulate | BAIXA |
| 27 | RangeLenLoop | BAIXA |
| 28 | UnusedVariable | BAIXA |
| 29 | ManyParameters | MEDIA |
| 30 | WildcardImport | MEDIA |
| 31 | PrintLeak | BAIXA |
| 32 | MissingSuperInit | MEDIA |
| 33 | OverrideSignatureMismatch | MEDIA |
| 34 | AbstractMethodNotImplemented | ALTA |

### Validacao de Dependencias (2)

| # | Criterio | Severidade | Como detecta |
|---|----------|-----------|--------------|
| 35 | ImportExists | ALTA | Cruza imports com pip list + requirements.txt |
| 36 | ApiExists | ALTA | Inspeciona modulo real com importlib, valida metodo existe |

### Analise Estrutural (3)

| # | Criterio | Severidade | Como detecta |
|---|----------|-----------|--------------|
| 37 | SemanticDuplication | MEDIA | Fingerprint AST normalizado (ignora nomes de vars e literais) |
| 38 | StringDispatch | MEDIA | `if self.x == "literal"` em 2+ metodos → candidato a Strategy |
| 39 | DataFlowExtractor | MEDIA | Clusters def-use coesos em funcoes >50 linhas |

### Django-Aware (4) — v4.1.0

| # | Criterio | Severidade | Como detecta |
|---|----------|-----------|--------------|
| 40 | IdentityComparison | ALTA | `ast.Compare` com `Is`/`IsNot` e `ast.Constant` nao-None |
| 41 | OrmInLoop | ALTA | `.objects.*` dentro de `for`/`while` via parent map |
| 42 | MassAssignment | ALTA | `fields = '__all__'` em classes herdando de ModelForm/Serializer |
| 43 | SaveSideEffects | ALTA | `send_mail`/`requests.*`/`celery.*` em `def save()` de models.Model |

### Seguranca (3) — v4.2.0

| # | Criterio | Severidade | Como detecta |
|---|----------|-----------|--------------|
| 44 | HardcodedSecrets | ALTA | Assignment com nome sensivel (api_key, token, password) + valor literal nao-placeholder |
| 45 | InjectionRisk | ALTA | `.raw()`/`cursor.execute()`/`os.system()`/`subprocess.*` com f-string ou concatenacao |
| 46 | ContextManagerLeak | MEDIA | `open()` sem ancestral `ast.With` via parent map |

## Heuristica LLM-Aware

Se 3+ criterios classicos de LLM (`BareExcept`, `MutableDefault`, `PrintLeak`, `UnusedVariable`) violados no mesmo run → severidade MEDIA elevada para ALTA automaticamente.

## Novos Recursos v4.x

| Recurso | Comando/Flag | Descricao |
|---------|-------------|-----------|
| Projeto inteiro | `code-analyze project src/` | Varre todos os .py, detecta duplicacoes cross-file |
| Similaridade fuzzy | `--threshold 0.9` | Agrupa funcoes 90%+ similares (nao so identicas) |
| Indice incremental | automatico | `~/.code-analyzer/fingerprints/` com mtime; re-indexa so arquivos alterados |
| Purity classifier | automatico | Classifica candidatos de extracao como pure/side_effect/unknown |
| Equivalence tests | `.skill_outputs/tests/` | Gera `test_equivalence_*.py` para cada candidato |
| [Equivalencia] terminal | automatico | Exibe badges Alta/Media/Baixa por candidato de extracao |
| Secao Equivalencia MD | automatico | Tabela no relatorio Markdown com confidence por funcao |
| Django N+1 | automatico | OrmInLoop detecta `.objects.*` dentro de loops |
| Mass Assignment | automatico | MassAssignment detecta fields='__all__' em forms/serializers |
| Credenciais hardcoded | automatico | HardcodedSecrets detecta API_KEY/TOKEN/PASSWORD como literais |
| Injection Risk | automatico | InjectionRisk detecta f-strings em raw()/os.system() |

## Subcomandos

| Comando | Descricao |
|---------|-----------|
| `code-analyze check arq.py` | So analise, sem refatorar |
| `code-analyze analyze arq.py --dry-run` | Preview sem aplicar |
| `code-analyze analyze arq.py --patch-only` | Gera .patch sem modificar disco |
| `code-analyze analyze arq.py --interactive` | [a]plicar/[p]ular/[v]er diff/[s]air |
| `code-analyze analyze arq.py --force` | Ignora cache lazy, forcca reanalise |
| `code-analyze dup a.py b.py` | Duplicacao semantica entre dois arquivos |
| `code-analyze project src/` | Analise cross-file de diretorio |
| `code-analyze project src/ --threshold 0.9` | Com similaridade fuzzy |
| `code-analyze history arq.py` | Evolucao de scores entre execucoes |

## Testes

```bash
python -m pytest tests/ -v    # 166 testes
```

## Configuracao via `.analyzer.json`

```json
{
  "max_methods_per_class": 10,
  "max_lines_per_class": 200,
  "max_complexity": 10,
  "max_imports": 20,
  "min_comment_ratio": 10,
  "ignore_criteria": [],
  "output_dir": null,
  "dry_run": false,
  "interactive": false,
  "generate_tests": true,
  "compact": false
}
```

Crie com: `code-analyze init`. Tambem suportado via `pyproject.toml [tool.code-analyzer]`.

## Saidas Geradas

```text
.skill_outputs/<arquivo>/<timestamp>/
  analysis/<arquivo>_analysis.json      — JSON estruturado com scores
  reports/<arquivo>_report.md           — Markdown legivel
  reports/<arquivo>_report.html         — Dashboard HTML com risk badge
  reports/<arquivo>_refactor.patch      — Patch formato git apply
  refactors/<arquivo>_diff.txt          — Diff resumido
  backups/<arquivo>_backup.py           — Backup do original
  tests/test_<arquivo>.py               — Scaffold pytest
  tests/test_equivalence_*.py           — Testes de equivalencia gerados
  logs/execution_manifest.json          — Manifesto com todos os artefatos
```

## Limites Conhecidos

1. **Pylint nao confiavel em Django** — E0401/E0611 derrubam score sem refletir qualidade. Detectado automaticamente; warning `unreliable=True` emitido.
2. **Cobertura inferencial** — Nao executa `pytest --cov`; infere por correspondencia de nomes.
3. **Nao detecta bugs semanticos** — Race conditions, logica de negocio errada, ORM QuerySet mal usado sao invisiveis para analise estatica.
4. **Score de convencao, nao de corretude** — 9.5/10 pode ter bugs criticos. Disclaimer exibido em todos os relatorios.
5. **Erros de runtime** — Signals sem on_commit, CBV MRO, race conditions requerem analise de runtime; nao cobertos por analise estatica pura.
