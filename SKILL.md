---
name: code-architecture-analyzer
description: Análise profunda de arquitetura Python com refatoração automática segura. Identifica violações SOLID, God Classes, anti-patterns e cobertura de testes. Suporta dry-run, modo interativo e config por projeto (.analyzer.json). Pipeline em 3 fases (Identificação → Proposição → Implementação) totalizando 10 micro-fases.
compatibility: Python 3.8+, Node.js 14+
version: 2.1.3
---

# Code Architecture Analyzer v2.1.3

Analisador profundo de arquitetura Python com refatoração automática **não-destrutiva** (dry-run + backup automático).

## Principais Recursos

- ✅ Análise AST + integração com Pylint e Ruff
- ✅ 10 critérios SOLID/arquiteturais avaliados com score 0-10
- ✅ Findings por **linha exata** com sugestões antes/depois
- ✅ Maintainability Index e complexidade ciclomática
- ✅ **Modo dry-run** — preview de mudanças sem aplicar
- ✅ **Modo interativo** — aceite/rejeite cada sugestão
- ✅ **Config por projeto** via `.analyzer.json`
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

> **Nota de honestidade:** v2.1.3 não faz refatorações arquiteturais grandes (ex.: dividir God Class). Foco está em **cleanup seguro e não-destrutivo**. Refatorações estruturais profundas devem ser feitas manualmente com base nos findings.

> **Nota de robustez:** se a geração de relatórios falhar, o pipeline agora aborta de forma segura, grava `report_generation_error.log` e evita deixar `reports/*.md` vazio.

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

## 10 Critérios Avaliados

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

| Arquivo | Conteúdo |
|---------|----------|
| `seu_arquivo.py` | Código refatorado (com cleanup) |
| `seu_arquivo_analysis.json` | Relatório JSON estruturado |
| `seu_arquivo_report.md` | Relatório Markdown legível |
| `test_seu_arquivo.py` | Scaffold de testes pytest |
| `.backups/seu_arquivo_backup.py` | Backup do original |
