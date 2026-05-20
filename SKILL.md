---
name: code-architecture-analyzer
description: Analise profunda de arquitetura Python com refatoracao automatica segura. 36 criterios: violacoes SOLID, God Classes, anti-patterns, deteccao semantica de duplicacao, score de risco de producao, patches git apply-aveis. Pipeline 3 fases, 10 micro-fases, lazy evaluation cache, deteccao cross-file, 112 testes.
compatibility: Python 3.8+, Node.js 14+
version: 3.2.0
---

# Code Architecture Analyzer v3.2.0

Analisador profundo de arquitetura Python com refatoracao automatica segura (dry-run + backup + patch).

**Score 10/10** — risco de producao, diffs PEP, deteccao semantica cross-file, cache lazy.

## Arquitetura da CLI

O pacote NPM (`code-architecture-analyzer`) expoe o comando `code-analyze` via `package.json` `"bin"`, que aponta para **`bin/cli.js`** (Node.js com commander). Existem dois entrypoints Python:

| Entrypoint | Uso | Flags extras |
|---|---|---|
| `bin/cli.py` | Thin shim: insere `src/` no `sys.path`, chama `code_analyzer.cli:main` | Subcomandos: `analyze`/`a`, `check`/`c`, `refactor`/`r`, `validate`/`v`, `dup`, `history`, `init`, `info`, `setup` |
| `bin/cli.js` | CLI Node.js com `commander` (wrapper rico com spinners) | `--quiet`, `--json`, `--output <dir>`, `--html`, `--force`, `--patch-only` |
| `index.js` | API programatica (`require('code-architecture-analyzer')`) | `analyze()`, `refactor()`, `validate()` |

`bin/cli.js` chama `bin/cli.py` (que roteia para `src/code_analyzer/`).

**Node → Python bridge:** `lib/python-utils.js` descobre o Python no sistema.

**Performance:** ruff + pylint executam em paralelo via `ThreadPoolExecutor`. Cache de AST evita re-parse. Historico usa indice `.index.json` (O(1) lookup).

## Estrutura do Pacote Python

```
src/code_analyzer/
  __init__.py             # API publica: analyze(), refactor(), validate()
  cli.py                  # dispatch() — roteador de subcomandos
  config.py               # DEFAULT_CONFIG, load_config
  orchestrator.py         # pipeline argparse (build_parser + run_pipeline)
  artifact_manager.py     # ArtifactRegistry
  validator.py            # CodeValidator, validate_file
  refactorer.py           # RefactoringOrchestrator, refactor_file, generate_patch
  report_generator.py     # ReportGenerator, generate_reports
  history.py              # save/load snapshots, index .index.json, lazy evaluation
  analyzer/
    __init__.py           # run_analysis(), prune_criteria(), detect_all()
    core.py               # ArchitectureAnalyzer (NodeVisitor slim)
    context.py            # AnalysisContext dataclass
    scoring.py            # score_to_status, mi_grade, production_risk_score
    semantic.py           # cross-file semantic duplication (subcomando dup)
    detectors/
      __init__.py         # Finding, Detector ABC, REGISTRY, @register
      srp.py … semantic_duplication.py  # 36 arquivos, um por criterio
```

Instalavel via `pip install -e .` (pyproject.toml com `[tool.setuptools.packages.find] where = ["src"]`).

## Principais Recursos

- ✅ Analise AST + integracao com Pylint e Ruff (paralelos)
- ✅ **36 criterios** avaliados com score 0-10 cada
- ✅ Findings por **linha exata** com sugestoes antes/depois
- ✅ **Maintainability Index**, complexidade ciclomatica, **score de risco de producao**
- ✅ **Modo dry-run** — preview de mudancas sem aplicar
- ✅ **Modo interativo** — [a]plicar/[p]ular/[v]er diff/[s]air por regra
- ✅ **Patches `git apply`-aveis** — diff limpo por sugestao
- ✅ **Flag `--patch-only`** — gera .patch sem modificar disco
- ✅ **Config por projeto** via `.analyzer.json` ou `pyproject.toml [tool.code-analyzer]`
- ✅ Analise de cobertura de testes (detecta metodos sem teste)
- ✅ Backup automatico antes de qualquer modificacao
- ✅ Geracao de scaffold de testes pytest
- ✅ **Lazy Evaluation** — cache por hash MD5, reanalise apenas se arquivo mudou
- ✅ **Duplicacao semantica** — fingerprint AST cross-file (`code-analyze dup a.py b.py`)
- ✅ **Heuristica LLM-Aware** — 3+ criterios LLM elevam severidade MEDIA → ALTA
- ✅ **Historico com indice** — `.index.json` (O(1) lookup), snapshots enxutos (~1KB)

## Como Funciona

### FASE 1: IDENTIFICACAO (3 micro-fases)

#### Micro-fase 1a: Varredura AST
- Parse completo do codigo com `ast` (stdlib)
- Deteccao de classes, metodos, funcoes, imports
- Calculo de complexidade ciclomatica por funcao
- Deteccao de imports inline (anti-pattern)
- Mapeamento de dependencias (stdlib vs third-party)

#### Micro-fase 1b: Analise Pylint (paralelo com Ruff)
- Verificacao arquitetural profunda
- Deteccao de code smells e violacoes
- Analise de coesao e acoplamento
- Falha graciosamente se Pylint nao instalado

#### Micro-fase 1c: Validacao Ruff (paralelo com Pylint)
- Varredura ultra-rapida de anti-padroes
- Validacao de convencoes PEP 8
- Identificacao de dead code
- Falha graciosamente se Ruff nao instalado

### FASE 2: PROPOSICAO (2 micro-fases)

#### Micro-fase 2a: Identificacao de Problemas
- Score 0-10 por criterio (SRP, OCP, DIP, etc.)
- Findings com `location`, `issue`, `line_content`
- Severidade ALTA / MEDIA / BAIXA por criterio
- Score de risco de producao (0.0 a 1.0)
- Heuristica LLM-Aware (elevacao de severidade)

#### Micro-fase 2b: Sugestoes Acionaveis
- Sugestoes concretas com exemplo `antes` → `depois`
- Recomendacoes priorizadas por severidade
- Geracao de relatorios JSON, Markdown e HTML
- Patches no formato `git apply`

### FASE 3: IMPLEMENTACAO (5 micro-fases)

#### Micro-fase 3a: Setup/Preparacao
- Backup automatico
- Carregamento de `.analyzer.json` (se existir)
- Validacao do arquivo de entrada

#### Micro-fase 3b: Refatoracao Estrutural (Cleanup)
Transformacoes reais aplicadas (com descricao enriquecida: PEP, linha de origem):
- Adicao de docstring de modulo (se ausente)
- Remocao de imports duplicados (mapeia linha da primeira ocorrencia)
- Remocao de imports nao usados (via AST)
- Conversao de f-strings sem placeholders → strings normais
- Renomeacao de variaveis ambiguas (`l`, `I`, `O` → `ln`, `idx`, `result`)
- Suporte a `--dry-run` e `--patch-only` em todas as operacoes
- Parametro `enabled_rules` para refatoracao granular

> **Nota de honestidade:** A skill faz cleanup seguro e nao-destrutivo. Refatoracoes arquiteturais grandes (ex.: dividir God Class) devem ser feitas manualmente com base nos findings.

#### Micro-fase 3c: Testes Unitarios (Scaffold)
- Geracao automatica de scaffold pytest se nao existir
- Esqueleto com testes placeholder marcados como `@pytest.mark.skip`

#### Micro-fase 3d: Formatacao e Padronizacao
- Black para formatacao consistente (se instalado)
- isort para organizacao de imports (se instalado)
- Fallback: formatador basico (rstrip + linhas vazias consecutivas)

#### Micro-fase 3e: Validacao Final
- Verificacao de sintaxe via `compile()`
- Geracao de patch e diff resumido
- Confirmacao de integridade

## 36 Criterios Avaliados

### SOLID + Arquitetura (10 criterios)

| # | Criterio | Severidade | Como e Detectado |
|---|----------|-----------|------------------|
| 1 | Single Responsibility (SRP) | ALTA | Metodos por classe + linhas por classe |
| 2 | Open/Closed Principle (OCP) | MEDIA | Heuristica estatica |
| 3 | Dependency Inversion (DIP) | ALTA | Analise de imports concretos vs abstratos |
| 4 | Separacao de Camadas | ALTA | Mistura de I/O, logica e apresentacao |
| 5 | Acoplamento | ALTA | Numero de imports + acoplamento eferente |
| 6 | Coesao | MEDIA | Atributos compartilhados entre metodos |
| 7 | Padroes de Design | MEDIA | Deteccao de patterns conhecidos |
| 8 | God Class/Object | ALTA | Linhas + metodos + atributos |
| 9 | Circular Dependencies | ALTA | Analise de grafo de imports |
| 10 | Interface Segregation | MEDIA | Tamanho de classes abstratas |

### Padroes de Erros LLM (24 criterios)

| # | Criterio | Severidade |
|---|----------|-----------|
| 11 | BareExcept | ALTA |
| 12 | NoneComparison | BAIXA |
| 13 | MutableDefault | ALTA |
| 14 | ShadowingBuiltins | MEDIA |
| 15 | SecurityRisk | ALTA |
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

### Validacao de Dependencias Reais (2 criterios)

| # | Criterio | Severidade |
|---|----------|-----------|
| 35 | ImportExists | ALTA |
| 36 | ApiExists | ALTA |

### Heuristica LLM-Aware

Se 3+ criterios classicos de LLM (`BareExcept`, `MutableDefault`, `PrintLeak`, `UnusedVariable`) forem violados no mesmo run, a severidade e elevada de MEDIA para ALTA.

## Novos Subcomandos (v3.0+)

| Comando | Descricao |
|---------|-----------|
| `code-analyze dup a.py b.py` | Deteccao de duplicacao semantica cross-file |
| `code-analyze history arq.py` | Historico de scores e metricas entre execucoes |
| `code-analyze analyze arq.py --patch-only` | Gerar apenas .patch sem modificar disco |
| `code-analyze analyze arq.py --force` | Forcar reanalise ignorando cache lazy |

## Aliases de Comandos

| Comando | Alias |
|---------|-------|
| `code-analyze analyze` | `code-analyze a` |
| `code-analyze check` | `code-analyze c` |
| `code-analyze refactor` | `code-analyze r` |
| `code-analyze validate` | `code-analyze v` |

## Testes

```bash
python -m pytest tests/ -v          # pytest (recomendado) — 112 testes
python -m unittest discover tests   # unittest runner
python tests/test_skill_core.py     # direto
```

Usa `pyproject.toml` com `[tool.pytest.ini_options] testpaths = ["tests"] pythonpath = ["src"]`.

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

Crie com: `code-analyze init`

Tambem suportado via `pyproject.toml [tool.code-analyzer]`.

## Modos de Execucao

| Modo | Comando | Comportamento |
|------|---------|---------------|
| **Padrao** | `code-analyze arq.py` | Analisa + refatora + gera relatorios + patch |
| **Analise pura** | `code-analyze check arq.py` | So analise, nao modifica |
| **Dry-run** | `code-analyze analyze arq.py --dry-run` | Mostra diff sem aplicar |
| **Patch-only** | `code-analyze analyze arq.py --patch-only` | Gera .patch sem modificar disco |
| **Interativo** | `code-analyze analyze arq.py --interactive` | [a]plicar/[p]ular/[v]er diff/[s]air |
| **Refactor isolado** | `code-analyze refactor arq.py` | So fase 3 |
| **Validacao isolada** | `code-analyze validate arq.py` | So checagem de sintaxe |
| **Duplicacao cross-file** | `code-analyze dup a.py b.py` | Fingerprint AST entre arquivos |

## Saidas Geradas

Tudo dentro de `.skill_outputs/<arquivo>/<timestamp>/`:

| Arquivo | Conteudo |
|---------|----------|
| `analysis/<arquivo>_analysis.json` | Relatorio JSON estruturado |
| `reports/<arquivo>_report.md` | Relatorio Markdown legivel |
| `reports/<arquivo>_report.html` | Dashboard HTML com risk badge |
| `reports/<arquivo>_refactor.patch` | Patch formato `git apply` |
| `refactors/<arquivo>_diff.txt` | Diff resumido da refatoracao |
| `backups/<arquivo>_backup.py` | Backup do original |
| `tests/test_<arquivo>.py` | Scaffold de testes pytest |
| `logs/execution_manifest.json` | Manifesto com todos os artefatos gerados |
