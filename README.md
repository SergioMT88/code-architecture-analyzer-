# Code Architecture Analyzer

[![npm version](https://badge.fury.io/js/code-architecture-analyzer.svg)](https://badge.fury.io/js/code-architecture-analyzer)

Análise profunda de arquitetura Python com refatoração automática.

## Quick Start

### Via npx (Recomendado)
```bash
npx code-architecture-analyzer seu_arquivo.py
```

### Instalação Global
```bash
npm install -g code-architecture-analyzer
code-analyze seu_arquivo.py
```

### Instalação Local
```bash
npm install code-architecture-analyzer --save-dev
npx code-analyze seu_arquivo.py
```

## Comandos

```bash
# Análise completa com refatoração
code-analyze seu_arquivo.py

# Apenas análise
code-analyze check seu_arquivo.py

# Apenas refatoração
code-analyze refactor seu_arquivo.py

# Apenas validação
code-analyze validate seu_arquivo.py

# Informações do sistema
code-analyze info

# Setup
code-analyze setup
```

## Como Funciona

### 3 Fases de Identificação
1. Varredura AST
2. Análise com Pylint
3. Validação com Ruff

### 2 Fases de Proposição
1. Explicar problema
2. Solução proposta

### 5 Fases de Implementação
1. Setup/Preparação
2. Refatoração estrutural
3. Testes unitários
4. Formatação
5. Validação final

## 10 Critérios SOLID/Design

Avalia: SRP, OCP, DIP, Separação de Camadas, Acoplamento, Coesão, Design Patterns, God Class, Circular Dependencies, Interface Segregation

## Saídas

- Arquivo Python refatorado
- Relatório JSON com scores
- Relatório Markdown legível
- Testes gerados automaticamente

## Requisitos

- Python 3.8+
- Node.js 14+

## Licença

MIT
