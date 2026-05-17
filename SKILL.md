---
name: code-architecture-analyzer
description: Análise profunda de arquitetura Python com refatoração automática segura. Identifica 34 critérios: violações SOLID, God Classes, anti-patterns, padrões de erros gerados por LLMs e cobertura de testes. Suporta dry-run, modo interativo e config por projeto (.analyzer.json). Pipeline em 3 fases (Identificação → Proposição → Implementação) totalizando 10 micro-fases.
compatibility: Python 3.8+, Node.js 14+
version: 2.1.6
---

# Code Architecture Analyzer v2.1.6

Analisador profundo de arquitetura Python com refatoração automática **não-destrutiva** (dry-run + backup automático).

## Arquitetura da CLI

O pacote NPM (`code-architecture-analyzer`) expõe o comando `code-analyze` via `package.json` `"bin"`, que aponta para **`bin/cli.js`** (Node.js com commander). Existem dois entrypoints Python:

| Entrypoint | Uso | Flags extras |
|---|---|---|
| `bin/cli.py` | Thin shim: insere `src/` no `sys.path`, chama `code_analyzer.cli:main` | Subcomandos: `analyze`/`a`, `check`/`c`, `refactor`/`r`, `validate`/`v`, `init`, `info`, `setup` |
| `bin/cli.js` | CLI Node.js com `commander` (wrapper rico com spinners) | `--quiet`, `--json`, `--output <dir>`, `--html` |
| `index.js` | API programática (`require('code-architecture-analyzer')`) | `analyze()`, `refactor()`, `validate()` |

`bin/cli.js` chama `bin/cli.py` (que roteia para `src/code_analyzer/`) — não chama mais `scripts/` diretamente.

**Node → Python bridge:** `lib/python-utils.js:15-58` descobre o Python no sistema.

## Estrutura do Pacote Python

```
src/code_analyzer/
  __init__.py             # API pública: analyze(), refactor(), validate()
  cli.py                  # dispatch() — roteador de subcomandos
  config.py               # DEFAULT_CONFIG, load_config
  orchestrator.py         # pipeline argparse (build_parser + run_pipeline)
  artifact_manager.py     # ArtifactRegistry
  validator.py            # CodeValidator, validate_file
  refactorer.py           # RefactoringOrchestrator, refactor_file
  report_generator.py     # ReportGenerator, generate_reports
  analyzer/
    __init__.py           # run_analysis(), prune_criteria(), detect_all()
    core.py               # ArchitectureAnalyzer (NodeVisitor slim ~300 linhas)
    context.py            # AnalysisContext dataclass
    scoring.py            # score_to_status, mi_grade, wrap_criterion
    detectors/
      __init__.py         # Finding, Detector ABC, REGISTRY, @register
      srp.py … abstract_method.py  # 34 arquivos, um por critério
```

Instalável via `pip install -e .` (pyproject.toml com `[tool.setuptools.packages.find] where = ["src"]`).

## Principais Recursos

- ✅ Análise AST + integração com Pylint e Ruff
- ✅ **34 critérios** avaliados com score 0-10 cada
- ✅ Findings por **linha exata** com sugestões antes/depois
- ✅ Maintainability Index e complexidade ciclomática
- ✅ **Modo dry-run** — preview de mudanças sem aplicar
- ✅ **Modo interativo** — aceite/rejeite cada sugestão
- ✅ **Config por projeto** via `.analyzer.json` ou `pyproject.toml [tool.code-analyzer]`
- ✅ Análise de cobertura de testes (detecta métodos sem teste)
- ✅ Backup automático antes de qualquer modificação
- ✅ Geração de scaffold de testes pytest

## Como Funciona

### FASE 1️⃣: IDENTIFICAÇÃO (3 micro-fases)

#### Micro-fase 1a: Varredura AST
- Parse completo do código com `ast` (stdlib)
- Detecção de classes, métodos, funções, imports
- Cálculo de complexidade ciclomática por função
- Detecção de imports inline (anti-pattern)
- Mapeamento de dependências (stdlib vs third-party)

#### Micro-fase 1b: Análise Pylint
- Verificação arquitetural profunda
- Detecção de code smells e violações
- Análise de coesão e acoplamento
- Falha graciosamente se Pylint não instalado

#### Micro-fase 1c: Validação Ruff
- Varredura ultra-rápida de anti-padrões
- Validação de convenções PEP 8
- Identificação de dead code
- Falha graciosamente se Ruff não instalado

### FASE 2️⃣: PROPOSIÇÃO (2 micro-fases)

#### Micro-fase 2a: Identificação de Problemas
- Score 0-10 por critério (SRP, OCP, DIP, etc.)
- Findings com `location`, `issue`, `line_content`
- Severidade ALTA / MÉDIA / BAIXA por critério

#### Micro-fase 2b: Sugestões Acionáveis
- Sugestões concretas com exemplo `antes` → `depois`
- Recomendações priorizadas por severidade
- Geração de relatórios JSON e Markdown ricos

### FASE 3️⃣: IMPLEMENTAÇÃO (5 micro-fases)

#### Micro-fase 3a: Setup/Preparação
- Backup automático em `.backups/`
- Carregamento de `.analyzer.json` (se existir)
- Validação do arquivo de entrada

#### Micro-fase 3b: Refatoração Estrutural (Cleanup)
Transformações reais aplicadas:
- Adição de docstring de módulo (se ausente)
- Remoção de imports duplicados
- Remoção de imports não usados (via AST)
- Conversão de f-strings sem placeholders → strings normais
- Renomeação de variáveis ambíguas (`l`, `I`, `O` → `ln`, `idx`, etc.)
- Suporte a `--dry-run` em todas as operações

> **Nota de honestidade:** v2.1.5 não faz refatorações arquiteturais grandes (ex.: dividir God Class). Foco está em **cleanup seguro e não-destrutivo**. Refatorações estruturais profundas devem ser feitas manualmente com base nos findings.

> **Nota de robustez:** se a geração de relatórios falhar, o pipeline aborta de forma segura, grava `report_generation_error.log` e evita deixar `reports/*.md` vazio.

#### Micro-fase 3c: Testes Unitários (Scaffold)
- Geração automática de scaffold pytest se não existir
- Esqueleto com testes placeholder marcados como `@pytest.mark.skip`
- O usuário deve implementar os testes reais — a skill não infere casos de teste

#### Micro-fase 3d: Formatação e Padronização
- Black para formatação consistente (se instalado)
- isort para organização de imports (se instalado)
- Fallback: formatador básico (rstrip + linhas vazias consecutivas)

#### Micro-fase 3e: Validação Final
- Verificação de sintaxe via `compile()`
- Geração de diff resumido
- Confirmação de integridade

## 34 Critérios Avaliados

### SOLID + Arquitetura (10 critérios)

| # | Critério | Severidade | Como é Detectado |
|---|----------|-----------|------------------|
| 1 | Single Responsibility (SRP) | ALTA | Métodos por classe + linhas por classe |
| 2 | Open/Closed Principle (OCP) | MÉDIA | Heurística estática |
| 3 | Dependency Inversion (DIP) | ALTA | Análise de imports concretos vs abstratos |
| 4 | Separação de Camadas | ALTA | Mistura de I/O, lógica e apresentação |
| 5 | Acoplamento | ALTA | Número de imports + acoplamento eferente |
| 6 | Coesão | MÉDIA | Atributos compartilhados entre métodos |
| 7 | Padrões de Design | MÉDIA | Detecção de patterns conhecidos |
| 8 | God Class/Object | ALTA | Linhas + métodos + atributos |
| 9 | Circular Dependencies | ALTA | Análise de grafo de imports |
| 10 | Interface Segregation | MÉDIA | Tamanho de classes abstratas |

### Padrões de Erros LLM (24 critérios)

| # | Critério | Severidade |
|---|----------|-----------|
| 11 | BareExcept | ALTA |
| 12 | NoneComparison | BAIXA |
| 13 | MutableDefault | ALTA |
| 14 | ShadowingBuiltins | MÉDIA |
| 15 | SecurityRisk | ALTA |
| 16 | AsyncSyncMismatch | ALTA |
| 17 | RedundantIfReturn | BAIXA |
| 18 | InconsistentReturns | MÉDIA |
| 19 | DotKeys | BAIXA |
| 20 | StringConcatInLoop | MÉDIA |
| 21 | AnyAllListComp | BAIXA |
| 22 | DeepNesting | MÉDIA |
| 23 | TypeIsinstance | BAIXA |
| 24 | UnusedIterationVar | BAIXA |
| 25 | DictGet | BAIXA |
| 26 | ManualAccumulate | BAIXA |
| 27 | RangeLenLoop | BAIXA |
| 28 | UnusedVariable | BAIXA |
| 29 | ManyParameters | MÉDIA |
| 30 | WildcardImport | MEDIA |
| 31 | PrintLeak | BAIXA |
| 32 | MissingSuperInit | MÉDIA |
| 33 | OverrideSignatureMismatch | MEDIA |
| 34 | AbstractMethodNotImplemented | ALTA |

## Aliases de Comandos

| Comando | Alias |
|---------|-------|
| `code-analyze analyze` | `code-analyze a` |
| `code-analyze check` | `code-analyze c` |
| `code-analyze refactor` | `code-analyze r` |
| `code-analyze validate` | `code-analyze v` |

## Testes

```bash
python -m pytest tests/ -v          # pytest (recomendado)
python -m unittest discover tests   # unittest runner
python tests/test_skill_core.py     # direto
```

Usa `pyproject.toml` com `[tool.pytest.ini_options] testpaths = ["tests"] pythonpath = ["src"]`.

## Configuração via `.analyzer.json`

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
  "interactive": false
}
```

Crie com: `code-analyze init`

Também suportado via `pyproject.toml [tool.code-analyzer]`.

## Modos de Execução

| Modo | Comando | Comportamento |
|------|---------|---------------|
| **Padrão** | `code-analyze arq.py` | Analisa + refatora + gera relatórios |
| **Análise pura** | `code-analyze check arq.py` | Só análise, não modifica |
| **Dry-run** | `code-analyze analyze arq.py --dry-run` | Mostra diff sem aplicar |
| **Interativo** | `code-analyze analyze arq.py --interactive` | Pergunta antes de aplicar |
| **Refactor isolado** | `code-analyze refactor arq.py` | Só fase 3 |
| **Validação isolada** | `code-analyze validate arq.py` | Só checagem de sintaxe |

## Saídas Geradas

Tudo dentro de `.skill_outputs/<arquivo>/<timestamp>/`:

| Arquivo | Conteúdo |
|---------|----------|
| `analysis/<arquivo>_analysis.json` | Relatório JSON estruturado |
| `reports/<arquivo>_report.md` | Relatório Markdown legível |
| `refactors/<arquivo>_diff.txt` | Diff resumido da refatoração |
| `backups/<arquivo>_backup.py` | Backup do original |
| `tests/test_<arquivo>.py` | Scaffold de testes pytest |
| `logs/execution_manifest.json` | Manifesto com todos os artefatos gerados |
