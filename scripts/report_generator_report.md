# Relatorio de Analise de Arquitetura - report_generator.py

**Data:** 2026-04-25T20:51:24.472111
**Arquivo:** `scripts\report_generator.py`
**Ferramenta:** Code Architecture Analyzer v2.0

## Resumo Geral

| Item | Valor |
|------|-------|
| Score Geral | 7.4/10 (Grau B) |
| Manutenibilidade | A (Excellent) |
| Problemas Criticos | 0 |
| Avisos | 1 |
| Total de Findings | 5 |
**Avisos:** `SRP`

## Metricas de Codigo

| Metrica | Valor |
|---------|-------|
| Linhas totais | 396 |
| Linhas de codigo | 337 |
| Linhas de comentario | 3 |
| Ratio comentarios | 0.9% |
| Classes | 1 |
| Funcoes | 1 |
| Imports unicos | 5 |
| Complexidade media | 3.44 |
| Complexidade maxima | 9 |
| Maintainability Index | 95.9 (A (Excellent)) |

## Analise por Criterio

### SRP
**Score:** 6/10 [###--] | **Status:** VIOLACAO | **Severidade:** ALTA
*Single Responsibility Principle - cada classe deve ter apenas uma razao para mudar*

**2 problema(s) encontrado(s):**

**1. [linha 13]** Classe 'ReportGenerator' tem 17 metodos (limite: 10). Considere dividir em classes menores por responsabilidade.

```python
# Codigo atual (linha 13):
class ReportGenerator:
```

> **Sugestao:** Divida 'ReportGenerator' em: ReportGeneratorReader, ReportGeneratorWriter, ReportGeneratorValidator

**2. [linhas 13-361]** Classe 'ReportGenerator' tem 348 linhas (limite: 200). Muito grande para ter uma unica responsabilidade.

```python
# Codigo atual (linhas 13-361):
class ReportGenerator:
```

> **Sugestao:** Extraia grupos de metodos relacionados para novas classes

### GodClass
**Score:** 7/10 [####-] | **Status:** PARCIAL | **Severidade:** ALTA
*God Class - classe que centraliza responsabilidades demais*

**1 problema(s) encontrado(s):**

**1. [linhas 13-361]** God Class detectada: 'ReportGenerator' (348 linhas, 17 metodos). Classe sabe e faz demais.

```python
# Codigo atual (linhas 13-361):
class ReportGenerator:
```

> **Sugestao:** Aplique o padrao de decomposicao: extraia responsabilidades distintas de 'ReportGenerator'

### Coupling
**Score:** 8/10 [####-] | **Status:** PARCIAL | **Severidade:** ALTA
*Acoplamento - grau de interdependencia entre modulos*

**1 problema(s) encontrado(s):**

**1. [imports (topo do arquivo)]** Alto acoplamento: 5 modulos importados para 1 classe(s). Ratio ideal: <= 4 imports por classe.

> **Sugestao:** Use Dependency Injection ou Facade para reduzir dependencias diretas

### DIP
**Score:** 8/10 [####-] | **Status:** PARCIAL | **Severidade:** ALTA
*Dependency Inversion Principle - dependa de abstracoes, nao de implementacoes*

**1 problema(s) encontrado(s):**

**1. [linha 13]** Classe 'ReportGenerator' nao herda de interface/classe abstrata. Classes concretas devem depender de abstracoes.

```python
# Codigo atual (linha 13):
class ReportGenerator:
```

> **Sugestao:** Crie uma interface: 'class IReportGenerator(ABC): ...' e use 'class ReportGenerator(IReportGenerator):'

### Cohesion
**Score:** 10/10 [#####] | **Status:** OK | **Severidade:** MEDIA
*Coesao - metodos e atributos de uma classe devem estar relacionados*

Sem problemas detectados automaticamente.

### OCP
**Score:** 7/10 [####-] | **Status:** PARCIAL - analise manual recomendada | **Severidade:** MEDIA
*Open/Closed Principle - aberto para extensao, fechado para modificacao*

Sem problemas detectados automaticamente.

### LayerSeparation
**Score:** 7/10 [####-] | **Status:** PARCIAL - analise manual recomendada | **Severidade:** ALTA
*Separacao de Camadas - UI, logica de negocio e dados separados*

Sem problemas detectados automaticamente.

### DesignPatterns
**Score:** 7/10 [####-] | **Status:** PARCIAL - analise manual recomendada | **Severidade:** MEDIA
*Padroes de Design - uso de padroes reconhecidos*

Sem problemas detectados automaticamente.

### CircularDeps
**Score:** 7/10 [####-] | **Status:** PARCIAL - analise manual recomendada | **Severidade:** ALTA
*Dependencias Circulares - A depende de B que depende de A*

Sem problemas detectados automaticamente.

### InterfaceSegregation
**Score:** 7/10 [####-] | **Status:** PARCIAL - analise manual recomendada | **Severidade:** MEDIA
*Interface Segregation - interfaces especificas sao melhores que gerais*

Sem problemas detectados automaticamente.


## Analise de Dependencias

- **Total de imports:** 5
- **Modulos unicos:** 5

## Ferramentas Externas

### Ruff (8 ocorrencias)

- **Linha 64** [F541]: f-string without any placeholders
- **Linha 107** [F541]: f-string without any placeholders
- **Linha 108** [F541]: f-string without any placeholders
- **Linha 206** [F541]: f-string without any placeholders
- **Linha 214** [F541]: f-string without any placeholders
- **Linha 224** [F541]: f-string without any placeholders
- **Linha 256** [F541]: f-string without any placeholders
- **Linha 257** [F541]: f-string without any placeholders


## Analise de Testes

| Item | Valor |
|------|-------|
| Funcoes de teste | 0 |
| Classes de teste | 0 |
| Usa pytest | Nao |
| Cobertura estimada | 0.0% |

**Metodos sem testes (3):**

- `ReportGenerator.generate_json_report (linha 40)`
- `ReportGenerator.generate_markdown_report (linha 57)`
- `ReportGenerator.save_reports (linha 338)`

## Recomendacoes Priorizadas

### 1. [MEDIA] SRP
Score 6/10 - 2 problema(s). Oportunidade de melhoria importante.

**Acao:** Divida 'ReportGenerator' em: ReportGeneratorReader, ReportGeneratorWriter, ReportGeneratorValidator
