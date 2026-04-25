# Guia de Uso

## Instalação

```bash
npm install code-architecture-analyzer
```

## Uso Básico

```bash
code-analyze seu_arquivo.py
```

## Opções

```bash
# Sem refatoração
code-analyze seu_arquivo.py --no-refactor

# Especificar output
code-analyze seu_arquivo.py --output ./reports
```

## Interpretar Resultados

### Arquivo JSON
- `score`: 0-10 (quanto maior, melhor)
- `status`: ✅ OK, ⚠️ VIOLAÇÃO, ❌ CRÍTICO
- `findings`: problemas encontrados
- `recommendations`: sugestões

### Arquivo Markdown
- Análise legível em português
- Gráficos e tabelas
- Recomendações prioritizadas

## Exemplos

Ver exemplos em: TEST_GUIDE.md
