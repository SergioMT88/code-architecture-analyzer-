---
name: code-architecture-analyzer
description: Análise profunda de arquitetura Python com refatoração automática. Identifica violações SOLID, God Classes, padrões de design. Executa análise em 3 micro-fases, proposição em 2 micro-fases, refatoração em 5 micro-fases.
compatibility: Python 3.8+, Node.js 14+
---

# Code Architecture Analyzer

Analisador profundo de arquitetura Python com refatoração automática.

## Como Funciona

### FASE 1️⃣: IDENTIFICAÇÃO (3 micro-fases)

#### Micro-fase 1a: Varredura AST
- Parse do código Python com Abstract Syntax Tree
- Detecção de classes, métodos, funções
- Mapeamento de dependências
- Cálculo de métricas: complexidade, tamanho

#### Micro-fase 1b: Análise Pylint
- Verificação arquitetural profunda
- Detecção de code smells
- Análise de responsabilidades
- Verificação de coesão e acoplamento

#### Micro-fase 1c: Validação Ruff
- Varredura ultra-rápida de anti-padrões
- Validação de convenções Python
- Verificação de imports circulares
- Identificação de dead code

### FASE 2️⃣: PROPOSIÇÃO (2 micro-fases)

#### Micro-fase 2a: Explicar Problema
- Descrição clara da violação
- Impacto na manutenção
- Exemplos do código problemático

#### Micro-fase 2b: Solução Proposta
- Código refatorado como exemplo
- Estratégia de refatoração
- Mudanças estruturais necessárias

### FASE 3️⃣: IMPLEMENTAÇÃO (5 micro-fases)

#### Micro-fase 3a: Setup/Preparação
- Análise de dependências
- Criação de ambiente de teste
- Backup automático do código original

#### Micro-fase 3b: Refatoração Estrutural
- Uso de libcst para transformações AST
- Reescrita de classes/métodos
- Reorganização de módulos

#### Micro-fase 3c: Testes Unitários
- Geração automática de testes pytest
- Validação de funcionalidade
- Coverage analysis

#### Micro-fase 3d: Formatação e Padronização
- Black para formatação consistente
- isort para organização de imports
- Validação final com Pylint

#### Micro-fase 3e: Validação Final
- Verificação de sintaxe
- Relatório JSON com scores atualizados
- Documento de mudanças

## 10 Critérios Avaliados

| # | Critério | Severidade |
|---|----------|-----------|
| 1 | Single Responsibility (SRP) | ALTA |
| 2 | Open/Closed Principle (OCP) | MÉDIA |
| 3 | Dependency Inversion (DIP) | ALTA |
| 4 | Separação de Camadas | ALTA |
| 5 | Acoplamento | ALTA |
| 6 | Coesão | MÉDIA |
| 7 | Padrões de Design | MÉDIA |
| 8 | God Class/Object | ALTA |
| 9 | Circular Dependencies | ALTA |
| 10 | Interface Segregation | MÉDIA |

## Saídas Geradas

- `seu_arquivo.py` - Código refatorado
- `seu_arquivo_analysis.json` - Relatório JSON estruturado
- `seu_arquivo_report.md` - Relatório Markdown
- `test_seu_arquivo.py` - Testes gerados
- `.backups/seu_arquivo_backup.py` - Backup original
