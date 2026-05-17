# Code Architecture Analyzer

[![npm version](https://badge.fury.io/js/code-architecture-analyzer.svg)](https://badge.fury.io/js/code-architecture-analyzer)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js Version](https://img.shields.io/badge/node-%3E%3D14.0.0-brightgreen)](https://nodejs.org/)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.8-blue)](https://www.python.org/)

**Read in:** [English](#english) | [Português](#português)

---

## English

Professional Python code architecture analyzer with automatic refactoring. Identifies **34 criteria**: SOLID violations, God Classes, anti-patterns, and LLM error patterns. Three-phase analysis pipeline with non-destructive refactoring (dry-run + automatic backup).

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

### 🏗️ CLI Architecture

The `code-analyze` command runs **`bin/cli.js`** (Node.js + commander with spinners), which delegates to **`bin/cli.py`** (thin shim → `src/code_analyzer/`). Both support all flags. The Python package is also pip-installable via `pyproject.toml`.

### Alias Shortcuts

All subcommands have one-letter aliases: `a` (analyze), `c` (check), `r` (refactor), `v` (validate).

### 📋 Commands

```bash
# Complete analysis with refactoring
code-analyze your_file.py

# Analysis only (no refactoring)
code-analyze check your_file.py       # alias: c
code-analyze check your_file.py --json

# Preview changes without applying (safe mode)
code-analyze analyze your_file.py --dry-run

# Interactive mode: approve/reject each suggestion
code-analyze analyze your_file.py --interactive

# Save reports to a specific directory
code-analyze analyze your_file.py --output ./reports

# Generate visual HTML dashboard
code-analyze analyze your_file.py --html

# Refactoring only
code-analyze refactor your_file.py     # alias: r
code-analyze refactor your_file.py --dry-run

# Validation only
code-analyze validate your_file.py     # alias: v

# Machine-readable JSON output
code-analyze analyze your_file.py --json
code-analyze refactor your_file.py --json
code-analyze validate your_file.py --json

# Create .analyzer.json config in current project
code-analyze init

# System information
code-analyze info

# Install Python dependencies (pylint, ruff, black, isort, pytest)
code-analyze setup
```

### Tests

```bash
python -m pytest tests/ -v     # recommended (pyproject.toml configures pythonpath)
python -m unittest discover tests
```

### 📸 Example Output

```
Code Architecture Analyzer v2.1.6

Python 3.11.0 found

ANALYSIS PHASE
  Criterion: SRP → Score: 4/10 ❌
  Criterion: GodClass → Score: 3/10 ❌
  Criterion: Coupling → Score: 7/10 ✅
  Criterion: BareExcept → Score: 10/10 ✅
  ... 34 criteria total

IMPLEMENTATION (5 MICRO-PHASES) [APPLYING]
  Phase 1: Setup/Preparation...
  Phase 2: Structural Refactoring...
  Phase 3: Unit Tests...
  Phase 4: Formatting...
  Phase 5: Final Validation...

PIPELINE COMPLETED
Files generated:
  * your_file_analysis.json
  * your_file_report.md
  * test_your_file.py
  * .backups/your_file_backup.py
```

### 🏗️ How It Works

#### Phase 1️⃣: Identification (3 micro-phases)
1. **AST Scanning** — Parse Python code with Abstract Syntax Tree
2. **Pylint Analysis** — Deep architectural verification (optional)
3. **Ruff Validation** — Ultra-fast anti-pattern scanning (optional)

#### Phase 2️⃣: Proposition (2 micro-phases)
1. **Problem Identification** — Score 0-10 per criterion with exact line findings
2. **Actionable Suggestions** — Before/after examples, prioritized by severity

#### Phase 3️⃣: Implementation (5 micro-phases)
1. **Setup/Preparation** — Automatic backup in `.backups/`
2. **Structural Refactoring** — Dedup imports, remove unused imports, fix f-strings, rename ambiguous vars
3. **Unit Tests** — Automatic pytest scaffold generation
4. **Formatting** — Black formatting and isort organization
5. **Final Validation** — Syntax verification and diff summary

### 📊 34 Evaluated Criteria

#### SOLID + Architecture (10)

| # | Criterion | Severity |
|---|-----------|----------|
| 1 | Single Responsibility (SRP) | HIGH |
| 2 | Open/Closed Principle (OCP) | MEDIUM |
| 3 | Dependency Inversion (DIP) | HIGH |
| 4 | Layer Separation | HIGH |
| 5 | Coupling | HIGH |
| 6 | Cohesion | MEDIUM |
| 7 | Design Patterns | MEDIUM |
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
| 15 | SecurityRisk | HIGH |
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

### 📄 Generated Outputs

```text
.skill_outputs/<file>/<timestamp>/
  analysis/<file>_analysis.json    — structured JSON report with scores
  reports/<file>_report.md         — human-readable Markdown report
  refactors/<file>_diff.txt        — refactor diff summary
  backups/<file>_backup.py         — automatic backup
  tests/test_<file>.py             — pytest scaffold
  logs/execution_manifest.json     — manifest with all artifacts
```

### ⚙️ Configuration via `.analyzer.json`

```json
{
  "max_methods_per_class": 10,
  "max_lines_per_class": 200,
  "max_complexity": 10,
  "max_imports": 20,
  "ignore_criteria": [],
  "output_dir": null,
  "dry_run": false,
  "interactive": false
}
```

Create with: `code-analyze init`. Also supported via `pyproject.toml [tool.code-analyzer]`.

### 🔌 CLI Contract

- `stdout`: human-readable by default, JSON when `--json` is used
- `stderr`: reserved for failures and runtime errors
- Exit code `0`: success / Exit code `1`: error

### 📋 Requirements

- Python 3.8+
- Node.js 14+
- Optional: pylint, ruff, black, isort, pytest (`code-analyze setup`)

### 📦 Package Info

- **Version:** 2.1.6
- **License:** MIT
- **Repository:** https://github.com/SergioMT88/code-architecture-analyzer-

### 📚 Documentation

- [SKILL.md](./SKILL.md) — Detailed skill documentation
- [AGENTS.md](./AGENTS.md) — Architecture and developer guide

### 🔗 Links

- [npm Package](https://www.npmjs.com/package/code-architecture-analyzer)
- [GitHub Repository](https://github.com/SergioMT88/code-architecture-analyzer-)

---

## Português

Analisador profissional de arquitetura de código Python com refatoração automática **não-destrutiva** (dry-run + backup automático). Identifica **34 critérios**: violações SOLID, God Classes, anti-patterns e padrões de erros gerados por LLMs.

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

#### Instalação Local
```bash
npm install code-architecture-analyzer --save-dev
npx code-analyze seu_arquivo.py
```

### 📋 Comandos

```bash
# Análise completa com refatoração
code-analyze seu_arquivo.py

# Apenas análise (sem refatoração)
code-analyze check seu_arquivo.py       # alias: c
code-analyze check seu_arquivo.py --json

# Pré-visualizar mudanças sem aplicar (modo seguro)
code-analyze analyze seu_arquivo.py --dry-run

# Modo interativo: aceite/rejeite cada sugestão
code-analyze analyze seu_arquivo.py --interactive

# Salvar relatórios em diretório específico
code-analyze analyze seu_arquivo.py --output ./relatorios

# Gerar dashboard HTML visual
code-analyze analyze seu_arquivo.py --html

# Apenas refatoração
code-analyze refactor seu_arquivo.py     # alias: r
code-analyze refactor seu_arquivo.py --dry-run

# Apenas validação de sintaxe
code-analyze validate seu_arquivo.py     # alias: v

# Saída JSON para integração com outras CLIs
code-analyze analyze seu_arquivo.py --json
code-analyze refactor seu_arquivo.py --json
code-analyze validate seu_arquivo.py --json

# Criar .analyzer.json no projeto atual
code-analyze init

# Informações do sistema
code-analyze info

# Instalar dependências Python (pylint, ruff, black, isort, pytest)
code-analyze setup
```

### 🏗️ Como Funciona

#### Fase 1️⃣: Identificação (3 micro-fases)
1. **Varredura AST** — Parse do código Python com Abstract Syntax Tree
2. **Análise Pylint** — Verificação arquitetural profunda (opcional)
3. **Validação Ruff** — Varredura ultra-rápida de anti-padrões (opcional)

#### Fase 2️⃣: Proposição (2 micro-fases)
1. **Identificação de Problemas** — Score 0-10 por critério com findings por linha exata
2. **Sugestões Acionáveis** — Exemplos antes/depois, priorizados por severidade

#### Fase 3️⃣: Implementação (5 micro-fases)
1. **Setup/Preparação** — Backup automático em `.backups/`
2. **Refatoração Estrutural** — Remove imports duplicados/não usados, corrige f-strings, renomeia vars ambíguas
3. **Testes Unitários** — Geração automática de scaffold pytest
4. **Formatação** — Formatação com Black e organização com isort
5. **Validação Final** — Verificação de sintaxe e diff resumido

### 📊 34 Critérios Avaliados

#### SOLID + Arquitetura (10)

| # | Critério | Severidade |
|---|----------|-----------|
| 1 | Responsabilidade Única (SRP) | ALTA |
| 2 | Princípio Aberto/Fechado (OCP) | MÉDIA |
| 3 | Inversão de Dependência (DIP) | ALTA |
| 4 | Separação de Camadas | ALTA |
| 5 | Acoplamento | ALTA |
| 6 | Coesão | MÉDIA |
| 7 | Padrões de Design | MÉDIA |
| 8 | God Class/Object | ALTA |
| 9 | Dependências Circulares | ALTA |
| 10 | Segregação de Interface | MÉDIA |

#### Padrões de Erros LLM (24)

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
| 30 | WildcardImport | MÉDIA |
| 31 | PrintLeak | BAIXA |
| 32 | MissingSuperInit | MÉDIA |
| 33 | OverrideSignatureMismatch | MÉDIA |
| 34 | AbstractMethodNotImplemented | ALTA |

### 📄 Saídas Geradas

```text
.skill_outputs/<arquivo>/<timestamp>/
  analysis/<arquivo>_analysis.json   — JSON estruturado com scores
  reports/<arquivo>_report.md        — Markdown legível
  refactors/<arquivo>_diff.txt       — Diff da refatoração
  backups/<arquivo>_backup.py        — Backup automático
  tests/test_<arquivo>.py            — Scaffold de testes pytest
  logs/execution_manifest.json       — Manifesto com todos os artefatos
```

### ⚙️ Configuração via `.analyzer.json`

```json
{
  "max_methods_per_class": 10,
  "max_lines_per_class": 200,
  "max_complexity": 10,
  "max_imports": 20,
  "ignore_criteria": [],
  "output_dir": null,
  "dry_run": false,
  "interactive": false
}
```

Crie com: `code-analyze init`. Também suportado via `pyproject.toml [tool.code-analyzer]`.

### 📋 Requisitos

- Python 3.8+
- Node.js 14+
- Opcional: pylint, ruff, black, isort, pytest (`code-analyze setup`)

### 📦 Informações do Pacote

- **Versão:** 2.1.6
- **Licença:** MIT
- **Repositório:** https://github.com/SergioMT88/code-architecture-analyzer-

### 📚 Documentação

- [SKILL.md](./SKILL.md) — Documentação técnica da skill
- [AGENTS.md](./AGENTS.md) — Guia de arquitetura para desenvolvedores

### 🔗 Links

- [Pacote npm](https://www.npmjs.com/package/code-architecture-analyzer)
- [Repositório GitHub](https://github.com/SergioMT88/code-architecture-analyzer-)

---

## License / Licença

MIT License — See [LICENSE](./LICENSE) file for details.
