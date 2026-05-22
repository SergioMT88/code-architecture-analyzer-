# Code Architecture Analyzer

[![npm version](https://badge.fury.io/js/code-architecture-analyzer.svg)](https://badge.fury.io/js/code-architecture-analyzer)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js Version](https://img.shields.io/badge/node-%3E%3D14.0.0-brightgreen)](https://nodejs.org/)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.8-blue)](https://www.python.org/)

**Read in:** [English](#english) | [Português](#português)

---

## English

Professional Python code architecture analyzer with automatic refactoring. Identifies **49 criteria**: SOLID violations, God Classes, anti-patterns, Django/Security-specific bugs (N+1 queries, mass assignment, hardcoded secrets, SQL injection), LLM error patterns, Feature Envy, Shotgun Surgery, and Liskov Substitution violations. Cross-file semantic duplication, data-flow analysis, purity classification, and equivalence test generation.

### Where to Start

There is a file in your project that everyone knows is problematic.
Nobody wants to touch it. When they have to, they change the minimum and leave quickly.
It works — but nobody really understands why.

This tool was made for that file.

Install and run on any Python file:

```bash
npm install -g code-architecture-analyzer
code-analyze setup          # install Python dependencies once
code-analyze check your_file.py
```

In seconds you see this:

```
  ██████░░░░  6.1/10  (C)  your_file.py
  ! 3 critical(s)  * 4 warning(s)

  1. [GodClass] line 12
     Problem: Class 'UserService' has 18 methods covering authentication,
     email, reports and payments. Every change here can break any of these.
     Suggestion: Split into smaller classes — one responsibility each.

  2. [HardcodedSecrets] line 47
     Problem: 'API_KEY = "sk-1234..."' — credential exposed in source code.
     Leaks through git history even if you remove it later.
     Suggestion: Use os.environ.get('API_KEY').

  3. [OrmInLoop] line 89
     Problem: .objects.get() inside a for loop — one query per iteration.
     With 100 records: 100 queries.
     Suggestion: Use select_related() or prefetch_related() before the loop.
```

This is not a generic warning list. It is your code, with the exact line, the real problem and what to do.

**What the score means — and what it does not**

The 0–10 score measures **structural quality**: well-defined responsibilities, low coupling, security patterns followed. It does not measure whether the code works correctly. A file can score 9/10 and have a business logic bug. Use the score as a compass, not a verdict.

**When you want more than analysis**

```bash
code-analyze analyze your_file.py --dry-run   # see what would change, touch nothing
code-analyze project src/                      # find duplicate functions across files
code-analyze init                              # set up pre-commit hook for the whole team
```

The tool always creates an automatic backup before any modification — you never lose the original.

> 📖 **Full documentation:** [SKILL.md](./SKILL.md) · [references/USAGE.md](./references/USAGE.md)

---

### 🚀 Quick Start

#### Via npx (Recommended)
```bash
npx code-architecture-analyzer your_file.py
```

#### Global Installation
```bash
npm install -g code-architecture-analyzer
code-analyze your_file.py
```

#### Local Installation
```bash
npm install code-architecture-analyzer --save-dev
npx code-analyze your_file.py
```

### 📋 Commands

```bash
# Complete analysis with refactoring
code-analyze your_file.py

# Analysis only (no refactoring)
code-analyze check your_file.py          # alias: c
code-analyze check your_file.py --json

# Preview changes without applying (safe mode)
code-analyze analyze your_file.py --dry-run

# Interactive mode: approve/reject each suggestion
code-analyze analyze your_file.py --interactive

# Force re-analysis (bypass lazy evaluation cache)
code-analyze check your_file.py --force

# Gate commits by minimum score (CI/pre-commit)
code-analyze check your_file.py --min-score 7.0

# Cross-file duplicate detection (two files)
code-analyze dup src/a.py src/b.py

# Project-wide analysis with fuzzy similarity
code-analyze project src/               # exact match
code-analyze project src/ --threshold 0.9  # 90%+ similar functions

# Score history between runs
code-analyze history your_file.py

# Save reports to a specific directory
code-analyze analyze your_file.py --output ./reports

# Generate visual HTML dashboard
code-analyze analyze your_file.py --html

# Generate patches only (no disk changes)
code-analyze analyze your_file.py --patch-only

# Machine-readable JSON output
code-analyze analyze your_file.py --json

# Smart project setup: detect type, create .analyzer.json + .pre-commit-config.yaml
code-analyze init

# System information
code-analyze info

# Install Python dependencies (pylint, ruff, black, isort, pytest)
code-analyze setup
```

Alias shortcuts: `a` (analyze), `c` (check), `r` (refactor), `v` (validate).

### 🔒 Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/SergioMT88/code-architecture-analyzer-
    rev: v4.3.1
    hooks:
      - id: code-analyze
        args: [--no-refactor, --quiet, --min-score=7.0]
```

Or generate automatically with `code-analyze init`.

### 🏗️ How It Works

#### Phase 1️⃣: Identification
1. **AST Scanning** — Parse Python code, detect classes, functions, imports, cyclomatic complexity
2. **Pylint + Ruff** — Run in parallel (ThreadPoolExecutor); graceful degradation if absent
3. **48 Detectors** — Registry pattern, one file per criterion, all run against AnalysisContext
4. **Lazy Evaluation** — MD5 hash cache; skips re-analysis if file unchanged (`--force` to bypass)
5. **Project Context** — Reads CLAUDE.md for known debt indicators; fan-in, git frequency, priority index

#### Phase 2️⃣: Proposition
1. **Problem Identification** — Score 0-10 per criterion with findings at exact line numbers
2. **Actionable Suggestions** — Before/after examples, prioritized by severity
3. **Pattern Advisor** — Maps findings → design patterns (Strategy, Facade, Chain of Responsibility)
4. **Equivalence Classification** — Classifies extraction candidates as `pure`/`side_effect`/`unknown`

#### Phase 3️⃣: Implementation
1. **Setup/Preparation** — Automatic backup in `.backups/`
2. **Structural Refactoring** — Remove duplicate/unused imports, fix f-strings, rename ambiguous vars
3. **Unit Tests** — Automatic pytest scaffold + equivalence test generation
4. **Formatting** — Black + isort (graceful degradation if absent)
5. **Final Validation** — Syntax verification via `compile()` + diff summary

### 📊 48 Evaluated Criteria

#### SOLID + Architecture (10)

| # | Criterion | Severity |
|---|-----------|----------|
| 1 | Single Responsibility (SRP) | HIGH |
| 2 | Open/Closed Principle (OCP) | MEDIUM |
| 3 | Dependency Inversion (DIP) | HIGH |
| 4 | Layer Separation | HIGH |
| 5 | Coupling | HIGH |
| 6 | Cohesion | MEDIUM |
| 7 | Design Patterns | INFO |
| 8 | God Class/Object | HIGH |
| 9 | Circular Dependencies | HIGH |
| 10 | Interface Segregation | MEDIUM |

#### LLM Error Patterns (24)

| # | Criterion | Severity |
|---|-----------|----------|
| 11 | BareExcept | HIGH |
| 12 | NoneComparison | LOW |
| 13 | MutableDefault | HIGH |
| 14 | ShadowingBuiltins | MEDIUM |
| 15 | SecurityRisk (eval/exec/pickle) | HIGH |
| 16 | AsyncSyncMismatch | HIGH |
| 17 | RedundantIfReturn | LOW |
| 18 | InconsistentReturns | MEDIUM |
| 19 | DotKeys | LOW |
| 20 | StringConcatInLoop | MEDIUM |
| 21 | AnyAllListComp | LOW |
| 22 | DeepNesting | MEDIUM |
| 23 | TypeIsinstance | LOW |
| 24 | UnusedIterationVar | LOW |
| 25 | DictGet | LOW |
| 26 | ManualAccumulate | LOW |
| 27 | RangeLenLoop | LOW |
| 28 | UnusedVariable | LOW |
| 29 | ManyParameters | MEDIUM |
| 30 | WildcardImport | MEDIUM |
| 31 | PrintLeak | LOW |
| 32 | MissingSuperInit | MEDIUM |
| 33 | OverrideSignatureMismatch | MEDIUM |
| 34 | AbstractMethodNotImplemented | HIGH |

#### Dependency Validation (2)

| # | Criterion | Severity |
|---|-----------|----------|
| 35 | ImportExists | HIGH |
| 36 | ApiExists | HIGH |

#### Structural Analysis (3)

| # | Criterion | Severity | What it detects |
|---|-----------|----------|-----------------|
| 37 | SemanticDuplication | MEDIUM | Structurally identical functions (AST fingerprint) |
| 38 | StringDispatch | MEDIUM | `if self.x == "literal"` repeated — Strategy Pattern candidate |
| 39 | DataFlowExtractor | MEDIUM | Cohesive def-use clusters in long functions — extraction boundaries |

#### Django-Aware (4) — v4.1.0

| # | Criterion | Severity | What it detects |
|---|-----------|----------|-----------------|
| 40 | IdentityComparison | HIGH | `if x is "literal"` — identity vs. equality |
| 41 | OrmInLoop | HIGH | `.objects.get()` inside `for`/`while` — N+1 query |
| 42 | MassAssignment | HIGH | `fields = '__all__'` in ModelForm/ModelSerializer |
| 43 | SaveSideEffects | HIGH | `send_mail`/`requests.*` inside `model.save()` |

#### Security (3) — v4.2.0

| # | Criterion | Severity | What it detects |
|---|-----------|----------|-----------------|
| 44 | HardcodedSecrets | HIGH | `API_KEY = "sk-..."` — credentials as string literals |
| 45 | InjectionRisk | HIGH | `.raw(f"...")`, `os.system(f"...")` — SQL/command injection |
| 46 | ContextManagerLeak | MEDIUM | `open()` without `with` statement |

#### Advanced Anti-Patterns (2) — v4.3.0

| # | Criterion | Severity | What it detects |
|---|-----------|----------|-----------------|
| 47 | FeatureEnvy | MEDIUM | Method accesses foreign object chains (`self.X.Y`) more than own attributes |
| 48 | ShotgunSurgery | MEDIUM | Constant referenced in 3+ distinct classes — single change ripples everywhere |

#### SOLID Extension — v4.3.0

| Criterion | Severity | What it detects |
|-----------|----------|-----------------|
| LSP | HIGH | `set_X` method assigns unexpected attributes beyond `self.X` — subclass breaks parent contract |

### ✨ Key Features

- **Lazy Evaluation** — MD5 hash cache, skips unchanged files. `--force` bypasses.
- **LLM-Aware Heuristic** — If 3+ classic LLM patterns violated, severity escalates MEDIUM→HIGH
- **Pre-commit gate** — `--min-score N` exits with code 1 if average score < N; integrates with pre-commit framework
- **Smart `init`** — Detects project type (Django/FastAPI/Flask/generic), writes `.analyzer.json` + `.pre-commit-config.yaml`
- **Cross-file duplication** — AST fingerprint across entire project (`project` command)
- **Fuzzy similarity** — `--threshold 0.9` groups 90%+ similar functions
- **Incremental fingerprint index** — `~/.code-analyzer/fingerprints/` with mtime-based updates
- **Data-flow clusters** — Identifies extractable blocks in long functions via def-use graphs
- **Purity classification** — Marks extraction candidates as `pure`/`side_effect`/`unknown`
- **Equivalence tests** — Auto-generates `test_equivalence_*.py` for each extraction candidate
- **Pattern Advisor** — Maps findings → Strategy, Facade, Chain of Responsibility suggestions
- **Priority Index** — fan-in (40%) + git commit frequency (35%) + coverage (25%)
- **Pylint unreliable detection** — Warns when E0401/E0611 errors dominate (Django projects)
- **Score disclaimer** — Explicit note that score measures structural conventions, not correctness

### 📄 Generated Outputs

```text
.skill_outputs/<file>/<timestamp>/
  analysis/<file>_analysis.json    — structured JSON with scores and findings
  reports/<file>_report.md         — human-readable Markdown report
  reports/<file>_report.html       — visual HTML dashboard with risk badge
  reports/<file>_refactor.patch    — git-apply-ready patch
  refactors/<file>_diff.txt        — refactor diff summary
  backups/<file>_backup.py         — automatic backup before any change
  tests/test_<file>.py             — pytest scaffold
  tests/test_equivalence_*.py      — equivalence tests for extraction candidates
  logs/execution_manifest.json     — manifest with all artifacts
```

### ⚙️ Configuration via `.analyzer.json`

```json
{
  "max_methods_per_class": 10,
  "max_lines_per_class": 200,
  "max_complexity": 10,
  "max_imports": 20,
  "min_comment_ratio": 10,
  "min_score": 7.0,
  "ignore_criteria": [],
  "output_dir": null,
  "dry_run": false,
  "interactive": false,
  "generate_tests": true,
  "compact": false
}
```

Create with: `code-analyze init`. Also supported via `pyproject.toml [tool.code-analyzer]`.

### 📋 Requirements

- Python 3.8+
- Node.js 14+
- Optional: pylint, ruff, black, isort, pytest (`code-analyze setup`)

### 📦 Package Info

- **Version:** 4.3.1
- **License:** MIT
- **Repository:** https://github.com/SergioMT88/code-architecture-analyzer-
- **Tests:** 193 passing

### 📚 Documentation

- [SKILL.md](./SKILL.md) — Detailed technical documentation
- [references/USAGE.md](./references/USAGE.md) — Usage guide

### 🔗 Links

- [npm Package](https://www.npmjs.com/package/code-architecture-analyzer)
- [GitHub Repository](https://github.com/SergioMT88/code-architecture-analyzer-)

---

## Português

Analisador profissional de arquitetura de código Python com refatoração automática **não-destrutiva** (dry-run + backup automático). Identifica **49 critérios**: violações SOLID, God Classes, anti-patterns, bugs específicos de Django/Segurança (N+1 queries, mass assignment, credenciais hardcoded, injeção SQL), padrões de erros gerados por LLMs, Feature Envy, Shotgun Surgery e violações de Liskov.

### Por onde começar

Existe um arquivo no seu projeto que todo mundo sabe que está problemático.
Ninguém quer mexer nele. Quando precisam, fazem o mínimo e saem rápido.
Ele funciona — mas ninguém entende direito por quê.

Essa ferramenta foi feita para esse arquivo.

Instale e rode em qualquer arquivo Python:

```bash
npm install -g code-architecture-analyzer
code-analyze setup          # instala dependências Python uma vez
code-analyze check seu_arquivo.py
```

Em alguns segundos você vê isso:

```
  ██████░░░░  6.1/10  (C)  seu_arquivo.py
  ! 3 crítico(s)  * 4 aviso(s)

  1. [GodClass] linha 12
     Problema: Classe 'UserService' tem 18 métodos cobrindo autenticação,
     email, relatórios e pagamentos. Cada mudança aqui pode quebrar qualquer
     uma dessas responsabilidades.
     Sugestão: Separe em classes menores — uma por responsabilidade.

  2. [HardcodedSecrets] linha 47
     Problema: 'API_KEY = "sk-1234..."' — credencial exposta no código-fonte.
     Vaza pelo histórico do git mesmo se você remover depois.
     Sugestão: Use os.environ.get('API_KEY').

  3. [OrmInLoop] linha 89
     Problema: .objects.get() dentro de um for — a cada iteração faz uma
     consulta ao banco. Com 100 registros: 100 queries.
     Sugestão: Use select_related() ou prefetch_related() antes do loop.
```

Isso não é uma lista genérica de avisos. É o seu código, com a linha exata, o problema real e o que fazer.

**O que o score significa — e o que não significa**

O score de 0 a 10 mede **qualidade estrutural**: responsabilidades bem definidas, acoplamento baixo, padrões de segurança seguidos. Ele não mede se o código funciona corretamente. Um arquivo pode ter score 9/10 e ter um bug de lógica de negócio. Use o score como bússola, não como veredito.

**Quando quiser ir além da análise**

```bash
code-analyze analyze seu_arquivo.py --dry-run   # veja o que mudaria, sem tocar em nada
code-analyze project src/                        # encontre funções duplicadas entre arquivos
code-analyze init                                # configure pre-commit hook para o time inteiro
```

A ferramenta sempre faz backup automático antes de qualquer modificação — você nunca perde o original.

> 📖 **Documentação completa:** [SKILL.md](./SKILL.md) · [references/USAGE.md](./references/USAGE.md)

---

### 🚀 Quick Start

#### Via npx (Recomendado)
```bash
npx code-architecture-analyzer seu_arquivo.py
```

#### Instalação Global
```bash
npm install -g code-architecture-analyzer
code-analyze seu_arquivo.py
```

### 📋 Comandos

```bash
# Análise completa com refatoração
code-analyze seu_arquivo.py

# Apenas análise (sem refatoração)
code-analyze check seu_arquivo.py       # alias: c

# Preview sem aplicar (modo seguro)
code-analyze analyze seu_arquivo.py --dry-run

# Modo interativo: aceite/rejeite cada sugestão
code-analyze analyze seu_arquivo.py --interactive

# Forçar reanálise (ignora cache lazy)
code-analyze check seu_arquivo.py --force

# Gate de score mínimo (CI/pre-commit)
code-analyze check seu_arquivo.py --min-score 7.0

# Duplicação cross-file entre dois arquivos
code-analyze dup src/a.py src/b.py

# Análise de projeto inteiro com similaridade fuzzy
code-analyze project src/
code-analyze project src/ --threshold 0.9

# Histórico de scores entre execuções
code-analyze history seu_arquivo.py

# Apenas patches sem modificar disco
code-analyze analyze seu_arquivo.py --patch-only

# Configuração inteligente do projeto
code-analyze init

# Instalar dependências Python
code-analyze setup
```

### 🔒 Pre-commit Hook

```yaml
# .pre-commit-config.yaml (gerado automaticamente por code-analyze init)
repos:
  - repo: https://github.com/SergioMT88/code-architecture-analyzer-
    rev: v4.3.1
    hooks:
      - id: code-analyze
        args: [--no-refactor, --quiet, --min-score=7.0]
```

### 📊 48 Critérios Avaliados

| Grupo | Critérios | Versão |
|-------|-----------|--------|
| SOLID + Arquitetura | SRP, OCP, DIP, LayerSeparation, Coupling, Cohesion, DesignPatterns (info), GodClass, CircularDeps, InterfaceSegregation | base |
| Padrões LLM (24) | BareExcept, MutableDefault, AsyncSyncMismatch, SecurityRisk, DeepNesting, PrintLeak... | base |
| Validação de Deps | ImportExists, ApiExists | v2.3 |
| Análise Estrutural | SemanticDuplication, StringDispatch, DataFlowExtractor | v3.x |
| Django-Aware | IdentityComparison, OrmInLoop (N+1), MassAssignment, SaveSideEffects | v4.1 |
| Segurança | HardcodedSecrets, InjectionRisk, ContextManagerLeak | v4.2 |
| Anti-Padrões Avançados | FeatureEnvy, ShotgunSurgery | v4.3 |
| SOLID Extensão | LSP (set_X side-effect) | v4.3 |

### ✨ Destaques

- **Lazy Evaluation** — cache MD5, reanalisa só se arquivo mudou
- **Pre-commit gate** — `--min-score N` bloqueia commit se score abaixo do mínimo
- **Smart init** — detecta Django/FastAPI/Flask, gera `.analyzer.json` + `.pre-commit-config.yaml`
- **Cross-file** — detecta funções duplicadas em projetos inteiros
- **Similaridade fuzzy** — `--threshold 0.9` agrupa funções 90%+ similares
- **Data-flow** — sugere boundaries de extração em funções longas
- **Equivalência** — gera `test_equivalence_*.py` como prova de refatoração segura
- **Django N+1** — detecta `.objects.get()` dentro de loops via AST
- **Credenciais hardcoded** — detecta `API_KEY = "sk-..."` em assignments
- **Injeção SQL/Command** — detecta `.raw(f"...")`, `os.system(f"...")` com f-strings
- **Feature Envy** — método que acessa mais a cadeia de outro objeto que os próprios atributos
- **Shotgun Surgery** — constante referenciada em 3+ classes distintas

### 📦 Informações

- **Versão:** 4.3.1 | **Licença:** MIT | **Testes:** 193 passando
- **Repositório:** https://github.com/SergioMT88/code-architecture-analyzer-

---

## License / Licença

MIT License — See [LICENSE](./LICENSE) file for details.
