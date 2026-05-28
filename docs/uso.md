# Uso — Guia de Referência

Este documento explica como utilizar o **Code Architecture Analyzer** de forma prática, previsível e eficiente, integrando as novas opções de controle do desenvolvedor.

---

## Fluxo Recomendado de Trabalho

1. **Diagnóstico Simples (`check`):**
   Execute o analisador no modo "somente leitura" para identificar problemas de design sem alterar arquivos de código.
2. **Refatoração Segura (`refactor`):**
   Aplique o cleanup estrutural seguro (docstrings, imports desnecessários, f-strings inúteis, etc.) gerando backups automáticos.
3. **Modo Interativo (`--interactive`):**
   Utilize o assistente interativo passo-a-passo no console para revisar findings críticos e selecionar quais correções aplicar.
4. **Validação de Sintaxe (`validate`):**
   Sempre execute uma validação rápida de integridade para confirmar a ausência de erros de sintaxe Python pós-refatoração.

---

## Comandos Principais e Opções de CLI

```bash
# Diagnóstico estático e relatório Markdown/HTML
code-analyze check arquivo.py
code-analyze check arquivo.py --output ./reports

# Diagnóstico ignorando geração de scaffolds de testes unitários
code-analyze check arquivo.py --output ./reports --no-tests

# Modo Interativo (Questionário Assistido)
code-analyze check arquivo.py --interactive

# Aplicação de refatorações (cleanup automático)
code-analyze refactor arquivo.py

# Simulação de refatoração (visualiza diff sem gravar alterações)
code-analyze refactor arquivo.py --dry-run

# Validação rápida de sintaxe do arquivo
code-analyze validate arquivo.py

# Instalação de dependências externas (ruff, black, isort, pytest)
code-analyze setup

# Inicialização do arquivo de configurações local (.analyzer.json)
code-analyze init
```

*Nota: Todos os comandos principais suportam a flag `--json` para produzir saídas limpas no stdout em formato estruturado (ideal para integrações ou scripts de terceiros).*

---

## Modo Interativo Aprimorado (Revisão Segura)

Ao executar com a flag `--interactive`, você tem controle total sobre o que é exibido e gravado:

1. **Opção de Ver Código Ampliado (`[c]ontexto`):**
   Ao navegar em problemas críticos (`1) Ver problemas criticos em detalhe`), você pode escolher `[c]` para exibir 5 linhas antes e depois do ponto da violação no arquivo (totalizando 11 linhas), permitindo analisar o entorno do problema diretamente no terminal.
2. **Visualização Prévia de Diff de Refatoração:**
   Ao selecionar `5) Aplicar correcoes automaticas`, o analisador primeiro simula a refatoração (`dry-run`) e exibe as primeiras 30 linhas de alterações. Se houver mais linhas de diferença, o sistema pergunta se deseja visualizar o diff completo.
3. **Consentimento Explícito para Gravação:**
   O console solicitará explicitamente a confirmação: `Deseja aplicar estas correcoes ao arquivo original? [y/N]`. O arquivo físico no disco só é modificado se você consentir.
4. **Consentimento para Testes:**
   Antes de refatorar, a CLI pergunta se você deseja gerar o scaffold de testes pytest.

---

## Geração Controlada de Testes Unitários

A ferramenta gera automaticamente um scaffold de testes unitários com asserções reais (como `assert result is not None` ou `assert True` e suporte a chamadas assíncronas com `@pytest.mark.asyncio`) para os métodos públicos e classes detectadas.

Você pode desativar ou restringir esse comportamento:
* **Na CLI:** Use a flag `--no-tests`.
* **Nas Configurações:** Defina `"generate_tests": false` no arquivo de configuração do projeto.

---

## Configurações Personalizáveis

A ferramenta lê regras locais de estilo e limites a partir do arquivo `.analyzer.json` ou da seção `[tool.code-analyzer]` no `pyproject.toml`.

### Exemplo de `.analyzer.json`:
```json
{
  "max_methods_per_class": 10,
  "max_lines_per_class": 200,
  "max_complexity": 10,
  "max_imports": 20,
  "min_comment_ratio": 10,
  "min_cohesion_methods": 5,
  "generate_tests": true,
  "ignore_criteria": ["SRP"]
}
```

* **`min_cohesion_methods` (Padrão: 5):** Classes com menos métodos que este limite são ignoradas pelo detector de coesão (`Cohesion` LCOM), evitando falsos positivos em pequenas classes de dados ou utilitárias.
* **`generate_tests`:** Se definido como `false`, suprime a geração de arquivos de testes unitários por padrão em todas as execuções de refatoração ou check.
* **`ignore_criteria`:** Lista de critérios de design que devem ser pulados durante a análise.

---

## Alertas de Ferramentas Ausentes

O analisador usa `ruff` (com o ruleset `E,F,W,B,SIM,UP,PL,RUF`) para enriquecer o diagnóstico. *Desde a v6.0.0 o pylint foi removido — o ruleset `PL` do ruff cobre os mesmos checks ~25x mais rápido.*
Se alguma dessas ferramentas não estiver instalada no ambiente (PATH):
* A análise **não falhará**. O analisador executará normalmente com suas heurísticas nativas do AST.
* O relatório Markdown exibirá um aviso destacado de **Análise Parcial** (`> [!WARNING]`).
* O painel visual HTML mostrará um card informativo sugerindo executar o comando `code-analyze setup` ou `pip install`.
