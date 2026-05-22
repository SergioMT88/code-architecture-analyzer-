# Guia de Uso — v4.3.1

## Instalação

```bash
# Via npx (sem instalar)
npx code-architecture-analyzer seu_arquivo.py

# Instalação global
npm install -g code-architecture-analyzer
```

## Uso Básico

```bash
# Análise completa (analisa + refatora)
code-analyze seu_arquivo.py

# Apenas análise (sem modificar o arquivo)
code-analyze check seu_arquivo.py
```

## Flags Disponíveis

```bash
# Pré-visualizar sem aplicar (recomendado na primeira vez)
code-analyze analyze seu_arquivo.py --dry-run

# Modo interativo: aceite/rejeite cada sugestão
code-analyze analyze seu_arquivo.py --interactive

# Salvar relatórios em outro diretório
code-analyze analyze seu_arquivo.py --output ./relatorios

# Forçar reanálise (ignora cache lazy evaluation)
code-analyze check seu_arquivo.py --force

# Gate de score mínimo — exit code 1 se score abaixo do limite
code-analyze check seu_arquivo.py --min-score 7.0

# JSON estruturado (para CI/integrações)
code-analyze check seu_arquivo.py --json

# Apenas patches sem modificar disco
code-analyze analyze seu_arquivo.py --patch-only
```

## Configuração do Projeto

```bash
# Criar .analyzer.json com detecção inteligente de tipo de projeto
# (detecta Django / FastAPI / Flask / genérico automaticamente)
code-analyze init
```

O arquivo `.analyzer.json` gerado permite configurar:

| Campo | Padrão | Descrição |
|-------|--------|-----------|
| `max_methods_per_class` | 10 | Máximo de métodos por classe |
| `max_lines_per_class` | 200 | Máximo de linhas por classe |
| `max_complexity` | 10 | Complexidade ciclomática máxima |
| `max_imports` | 20 | Máximo de imports |
| `min_comment_ratio` | 10 | Mínimo de comentários (%) |
| `min_score` | 7.0 | Score mínimo para pre-commit gate |
| `dry_run` | false | Sempre usar dry-run por padrão |
| `interactive` | false | Sempre usar modo interativo |
| `ignore_criteria` | [] | Lista de critérios a ignorar |

## Pre-commit Hook

```yaml
# .pre-commit-config.yaml (gerado automaticamente por code-analyze init)
repos:
  - repo: https://github.com/SergioMT88/code-architecture-analyzer-
    rev: v4.3.1
    hooks:
      - id: code-analyze
        args: [--no-refactor, --quiet, --min-score=7.0]
```

Instalar e ativar:
```bash
pip install pre-commit
pre-commit install
```

## Análise Cross-file

```bash
# Comparar dois arquivos específicos
code-analyze dup src/a.py src/b.py

# Varrer projeto inteiro (match exato)
code-analyze project src/

# Varrer com similaridade fuzzy (90%+ similar)
code-analyze project src/ --threshold 0.9
```

## Histórico de Scores

```bash
# Ver evolução de scores entre execuções
code-analyze history seu_arquivo.py
```

## Instalar Dependências Python

```bash
code-analyze setup
```

Instala automaticamente: `ruff`, `black`, `isort`, `pytest`. (Pylint removido em v6.0.0 — ruff cobre os checks PL nativamente, ~25x mais rapido.)

## Interpretar Resultados

### Score por Critério
- **8-10** ✅ Bom
- **5-7** ⚠️ Atenção
- **0-4** ❌ Crítico — refatoração urgente

### Nota de Risco de Produção
- **70-100** Moderado — código estruturalmente sólido
- **40-69** Risco — melhorias recomendadas
- **0-39** Alto Risco — atenção imediata

### Arquivos Gerados

| Arquivo | Descrição |
|---------|-----------|
| `_analysis.json` | Relatório JSON com scores e findings por linha |
| `_report.md` | Relatório Markdown legível |
| `_report.html` | Dashboard HTML visual com risk badge |
| `_refactor.patch` | Patch git apply-ready |
| `test_*.py` | Testes pytest gerados automaticamente |
| `test_equivalence_*.py` | Testes de equivalência para candidatos de extração |
| `_backup.py` | Backup automático antes da refatoração |

## 48 Critérios em Resumo

| Grupo | Critérios |
|-------|-----------|
| SOLID | SRP, OCP, DIP, LayerSeparation, Coupling, Cohesion, DesignPatterns (info), GodClass, CircularDeps, ISP |
| LLM Patterns | BareExcept, MutableDefault, AsyncSyncMismatch, DeepNesting, UnusedVariable, InconsistentReturns… (24 total) |
| Dependências | ImportExists, ApiExists |
| Estrutural | SemanticDuplication, StringDispatch, DataFlowExtractor |
| Django-Aware | IdentityComparison, OrmInLoop (N+1), MassAssignment, SaveSideEffects |
| Segurança | HardcodedSecrets, InjectionRisk, ContextManagerLeak |
| Anti-Padrões | FeatureEnvy, ShotgunSurgery, LSP |
