# Code Architecture Analyzer

[![npm version](https://badge.fury.io/js/code-architecture-analyzer.svg)](https://badge.fury.io/js/code-architecture-analyzer)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js Version](https://img.shields.io/badge/node-%3E%3D14.0.0-brightgreen)](https://nodejs.org/)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.8-blue)](https://www.python.org/)

**Read in:** [English](#english) | [Português](#português)

---

## English

Professional Python code architecture analyzer with automatic refactoring. Identifies SOLID violations, God Classes, and design patterns. Three-phase analysis, two-phase proposition, and five-phase implementation.

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
code-analyze check your_file.py

# Preview changes without applying (safe mode)
code-analyze analyze your_file.py --dry-run

# Interactive mode: approve/reject each suggestion
code-analyze analyze your_file.py --interactive

# Save reports to a specific directory
code-analyze analyze your_file.py --output ./reports

# Refactoring only (with optional dry-run)
code-analyze refactor your_file.py
code-analyze refactor your_file.py --dry-run

# Validation only
code-analyze validate your_file.py

# Create .analyzer.json config file in current project
code-analyze init

# System information
code-analyze info

# Setup Python dependencies (pylint, ruff, black, isort, pytest)
code-analyze setup
```

### 📸 Example Output

```
Code Architecture Analyzer v2.0

Python 3.11.0 found

ANALYSIS PHASE
  Criterion: single_responsibility → Score: 4/10 ❌
  Criterion: god_class → Score: 3/10 ❌
  Criterion: coupling → Score: 7/10 ✅

IMPLEMENTATION (5 MICRO-PHASES) [APPLYING]
  Phase 1: Setup/Preparation...
  Phase 2: Structural Refactoring...
  Phase 3: Unit Tests...
  Phase 4: Formatting...
  Phase 5: Final Validation...

PIPELINE COMPLETED!
Files generated:
  * your_file_analysis.json
  * your_file_report.md
  * test_your_file.py
  * .backups/your_file_backup.py
```

### 🏗️ How It Works

#### Phase 1️⃣: Identification (3 micro-phases)
1. **AST Scanning** - Parse Python code with Abstract Syntax Tree
2. **Pylint Analysis** - Deep architectural verification
3. **Ruff Validation** - Ultra-fast anti-pattern scanning

#### Phase 2️⃣: Proposition (2 micro-phases)
1. **Problem Explanation** - Clear violation description
2. **Proposed Solution** - Refactored code example

#### Phase 3️⃣: Implementation (5 micro-phases)
1. **Setup/Preparation** - Dependency analysis and backup creation
2. **Structural Refactoring** - AST-based code rewriting
3. **Unit Tests** - Automatic pytest test generation
4. **Formatting** - Black formatting and isort organization
5. **Final Validation** - Syntax verification and metrics

### 📊 10 Evaluated Criteria

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

### 📄 Generated Outputs

- `your_file.py` - Refactored code
- `your_file_analysis.json` - Structured JSON report with scores
- `your_file_report.md` - Human-readable Markdown report
- `test_your_file.py` - Auto-generated pytest tests
- `.backups/your_file_backup.py` - Automatic backup

### 📋 Requirements

- Python 3.8+
- Node.js 14+

### 📦 Package Info

- **Version:** 2.0.0
- **License:** MIT
- **Repository:** https://github.com/SergioMT88/code-architecture-analyzer-

### 📚 Documentation

- [SKILL.md](./SKILL.md) - Detailed skill documentation
- [USAGE.md](./references/USAGE.md) - Usage guide

### 🔗 Links

- [npm Package](https://www.npmjs.com/package/code-architecture-analyzer)
- [GitHub Repository](https://github.com/SergioMT88/code-architecture-analyzer-)

---

## Português

Analisador profissional de arquitetura de código Python com refatoração automática. Identifica violações SOLID, God Classes e padrões de design. Análise em três fases, proposição em duas fases e implementação em cinco fases.

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
code-analyze check seu_arquivo.py

# Pré-visualizar mudanças sem aplicar (modo seguro)
code-analyze analyze seu_arquivo.py --dry-run

# Modo interativo: aceite/rejeite cada sugestão
code-analyze analyze seu_arquivo.py --interactive

# Salvar relatórios em um diretório específico
code-analyze analyze seu_arquivo.py --output ./relatorios

# Apenas refatoração (com dry-run opcional)
code-analyze refactor seu_arquivo.py
code-analyze refactor seu_arquivo.py --dry-run

# Apenas validação
code-analyze validate seu_arquivo.py

# Criar arquivo .analyzer.json de configuração no projeto
code-analyze init

# Informações do sistema
code-analyze info

# Instalar dependências Python (pylint, ruff, black, isort, pytest)
code-analyze setup
```

### 🏗️ Como Funciona

#### Fase 1️⃣: Identificação (3 micro-fases)
1. **Varredura AST** - Parse do código Python com Abstract Syntax Tree
2. **Análise Pylint** - Verificação arquitetural profunda
3. **Validação Ruff** - Varredura ultra-rápida de anti-padrões

#### Fase 2️⃣: Proposição (2 micro-fases)
1. **Explicar o Problema** - Descrição clara da violação
2. **Solução Proposta** - Exemplo de código refatorado

#### Fase 3️⃣: Implementação (5 micro-fases)
1. **Setup/Preparação** - Análise de dependências e criação de backup
2. **Refatoração Estrutural** - Reescrita de código baseada em AST
3. **Testes Unitários** - Geração automática de testes pytest
4. **Formatação** - Formatação com Black e organização com isort
5. **Validação Final** - Verificação de sintaxe e métricas

### 📊 10 Critérios Avaliados

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

### 📄 Saídas Geradas

- `seu_arquivo.py` - Código refatorado
- `seu_arquivo_analysis.json` - Relatório JSON estruturado com scores
- `seu_arquivo_report.md` - Relatório Markdown legível
- `test_seu_arquivo.py` - Testes pytest gerados automaticamente
- `.backups/seu_arquivo_backup.py` - Backup automático

### 📋 Requisitos

- Python 3.8+
- Node.js 14+

### 📦 Informações do Pacote

- **Versão:** 2.0.0
- **Licença:** MIT
- **Repositório:** https://github.com/SergioMT88/code-architecture-analyzer-

### 📚 Documentação

- [SKILL.md](./SKILL.md) - Documentação detalhada da skill
- [USAGE.md](./references/USAGE.md) - Guia de uso

### 🔗 Links

- [Pacote npm](https://www.npmjs.com/package/code-architecture-analyzer)
- [Repositório GitHub](https://github.com/SergioMT88/code-architecture-analyzer-)

---

## License / Licença

MIT License - See [LICENSE](./LICENSE) file for details.
