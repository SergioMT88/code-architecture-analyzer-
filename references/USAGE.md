# Guia de Uso

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

# Refatoração com dry-run
code-analyze refactor seu_arquivo.py --dry-run
```

## Configuração do Projeto

```bash
# Criar .analyzer.json com regras personalizadas
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
| `dry_run` | false | Sempre usar dry-run por padrão |
| `interactive` | false | Sempre usar modo interativo |

## Instalar Dependências Python

```bash
code-analyze setup
```

Instala automaticamente: `pylint`, `ruff`, `black`, `isort`, `pytest`.

## Interpretar Resultados

### Score por Critério
- **8-10** ✅ Bom
- **5-7** ⚠️ Atenção
- **0-4** ❌ Crítico — refatoração urgente

### Arquivos Gerados

| Arquivo | Descrição |
|---------|-----------|
| `seu_arquivo_analysis.json` | Relatório JSON com scores e findings por linha |
| `seu_arquivo_report.md` | Relatório Markdown legível |
| `test_seu_arquivo.py` | Testes pytest gerados automaticamente |
| `.backups/seu_arquivo_backup.py` | Backup automático antes da refatoração |
