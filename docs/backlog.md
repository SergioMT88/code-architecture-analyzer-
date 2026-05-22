# Backlog — Code Architecture Analyzer

## Visão

Evoluir o `code-architecture-analyzer` para uma skill portátil, prática e confiável que vai além de um linter — validando dependências reais, rastreando evolução do código ao longo do tempo e gerando sugestões que o dev consegue aplicar em segundos.

---

## Caminho para 10/10

| Versão | Foco | Nota esperada |
|--------|------|---------------|
| **v2.1.7** | P0: arquitetura interna, 34 critérios, pacote instalável | **6,8** |
| **v2.2.0** | Fix falsos positivos + pipeline + modo interativo (Concluída) | **7,6** |
| **v2.3.0** | Validação de dependências reais (imports + APIs) (Concluída) | **8,3** |
| **v2.4.0** | Otimização Controlada de Tokens (Concluída) | **8,5** |
| **v2.5.0** | Histórico entre execuções (Concluída) | **8,8** |
| **v3.0.0** | Refatoração Granular, Velocidade e Inteligência LLM (Concluída) | **8,8 → 9,5** |
| **v3.1.0** | Sugestões `git apply`-áveis + score de risco + diffs explicados (Concluída) | **10,0** |
| **v3.2.0** | Otimizacão de Performance — subprocess paralelo, cache AST, historico enxuto (Concluída) | **10,0 → 10,0** |
| **v3.2.2** | Honestidade — pylint unreliable detection, score disclaimer, CLAUDE.md context (Concluída) | **mantém 10,0** |
| **v3.3.0** | Diagnóstico Inteligente — string dispatch, ROI decrescente, sugestão de padrões (Concluída) | **+qualidade** |
| **v3.4.0** | Análise Estrutural — cross-file, data-flow graph, scoring contextual (Concluída) | **salto de valor** |
| **v4.0.0** | Cirurgia Robótica — prova de equivalência, duplicação cross-codebase em escala, pipelines como cidadãos de primeira classe (Concluída) | **disruptivo** |
| **v4.1.0** | Django-Aware — cobertura dos top erros de LLM: N+1, MassAssignment, SaveSideEffects, IdentityComparison (Concluída) | **+4 detectores críticos** |
| **v4.2.0** | Security Triad — HardcodedSecrets, InjectionRisk (SQL+command), ContextManagerLeak (Concluída) | **+3 detectores segurança** |
| **v5.0.0** | Test Pain como Sinal de Arquitetura — mock density, setup complexity, dependências implícitas reveladas pelos testes | **único sinal humano** |

---

## ☑️ v2.2.0 — Confiabilidade (+0,8) (Concluída)

> **Problema:** falsos positivos destroem a confiança no tool. Um score errado e o dev para de levar todos os outros a sério.

### Fix: falsos positivos nos critérios existentes

| # | Item | Critério afetado | Esforço |
|---|------|-----------------|---------|
| F1 | ~~`StringConcatInLoop` dispara em `complexity += 1` — diferenciar augmented assign numérico de concat de string~~ | StringConcatInLoop | P |
| F2 | ~~`DictGet` dispara em type hints como `Dict[str, int]` — ignorar contextos de anotação~~ | DictGet | P |
| F3 | ~~`Coupling` inconsistente — reescrever heurística baseando em imports externos únicos, não total de imports~~ | Coupling | G |
| F4 | ~~`Cohesion` gera score errático em classes pequenas — adicionar threshold mínimo de métodos antes de avaliar~~ | Cohesion | M |
| F5 | ~~`DeepNesting` dispara em `try/except` dentro de `if` — excluir blocos de tratamento de erro do contador~~ | DeepNesting | P |

### Fix: pipeline

| # | Item | Esforço |
|---|------|---------|
| P1 | ~~`check` pula scaffold de teste — alinhar comportamento real com documentação ou implementar corretamente~~ (Concluído) | P |
| P2 | ~~Ruff/pylint ausentes: o relatório deve avisar explicitamente que a análise foi parcial, não falhar silencioso~~ (Concluído) | P |
| P3 | ~~Scaffold de teste ainda gera só `@pytest.mark.skip` — gerar `assert result is not None` real baseado na assinatura~~ (Concluído) | M |

### Modo interativo melhorado

| # | Item | Esforço |
| I1 | ~~Mostrar diff before/after por finding antes de aceitar/rejeitar — hoje aceita cegamente~~ (Concluído) | M |
| I2 | ~~Opção `ver contexto` no interativo — exibir as 5 linhas ao redor do finding antes de decidir~~ (Concluído) | P |

### Documentação e exemplos

| # | Item | Esforço |
|---|------|---------|
| D1 | ~~Criar `docs/examples/` com arquivo de entrada real e output esperado (análise + relatório)~~ (Concluído) | M |
| D2 | ~~Atualizar `docs/uso.md` — desatualizado desde v2.0~~ (Concluído) | P |

---

## ☑️ v2.3.0 — Validação de dependências reais (+0,7) (Concluída)

> **Problema:** LLMs alucinam pacotes e métodos. Nenhum linter valida isso. É o maior diferencial possível.

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| V1 | ~~**Validar imports contra dependências instaladas** — cruzar cada `import X` com `pip list` + `requirements.txt` / `Pipfile` / `pyproject.toml [project.dependencies]`. Reportar pacotes que não existem no ambiente.~~ | G | `detectors/import_exists.py` (novo) |
| V2 | ~~**Validar API chamada contra módulo real** — se o código faz `pandas.load_csv()`, inspecionar o módulo real com `importlib` e reportar que `load_csv` não existe. Apenas para módulos instalados, sem executar código.~~ | G | `detectors/api_exists.py` (novo) |
| V3 | **Aprender padrão do projeto e detectar desvios** (Adiado para v3.1.0) | G | `analyzer/pattern_learner.py` (novo) |

**Critério de pronto V1:** dado um arquivo que faz `import pandas` num projeto sem pandas no `requirements.txt`, o finding aparece com severidade ALTA e sugestão de adicionar ao requirements.

**Critério de pronto V2:** dado `requests.gets("url")` (método inexistente), o finding aparece com a lista de métodos corretos (`get`, `post`, etc.).

---

## ☑️ v2.4.0 — Otimização Controlada de Tokens (+0,3) (Concluída)

> **Problema:** relatórios e outputs muito longos gastam excesso de tokens de contexto da LLM e dificultam a leitura rápida pelo dev.

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| T1 | ~~**Agrupamento no PrintLeak** — múltiplos prints agrupados em um único finding consolidado por função~~ | P | `detectors/print_leak.py` |
| T2 | ~~**Modo compact no CLI e Markdown** — flag `--compact` para omitir descrições teóricas longas e snippets contextuais de 5 linhas~~ | M | `orchestrator.py`, `report_generator.py` |

---

## ☑️ v2.5.0 — Histórico entre execuções (+0,5) (Concluída)

> **Problema:** sem histórico, toda análise é um reset. O dev não sabe se o código melhorou.

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| H1 | ~~**Snapshot por execução** — salvar scores em `~/.code-analyzer/history/<projeto>/<arquivo>/<timestamp>.json`~~ | M | `artifact_manager.py` |
| H2 | ~~**Comando `history`** — `code-analyze history seu_arquivo.py` mostrando tabela de evolução dos scores no terminal~~ | M | `cli.py`, `orchestrator.py` |
| H3 | ~~**Seção de evolução no relatório** — "SRP: 4 → 6 → 8 (últimas 3 execuções)" no MD e no HTML dashboard~~ | M | `report_generator.py` |
| H4 | ~~**Alerta de regressão** — avisar quando um critério que estava OK piorou desde a última execução~~ | M | `orchestrator.py` |

**Critério de pronto:** rodar `code-analyze check arquivo.py` duas vezes com alteração entre elas. Na segunda, o terminal mostra "SRP: 6 → 8 (+2)" e o relatório inclui seção de histórico.

---

## ✅ v3.0.0 — Refatoração Granular, Velocidade e Inteligência LLM (+0,7) (Concluída)

> **Problema:** análise redundante de arquivos inalterados desperdiça CPU e tokens. Refatoração "tudo ou nada" tira controle do dev. Código gerado por LLM tem padrões repetitivos que passam despercebidos.

### Lazy Evaluation por Hash (Velocidade)

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| LZ1 | ~~**Pular reanálise de arquivos inalterados** — comparar hash MD5 com último snapshot do histórico; se bater, reutilizar `analysis_full` salva~~ | M | `orchestrator.py`, `history.py` |
| LZ2 | ~~**Flag `--force`** — permitir forçar reanálise completa ignorando o cache~~ | P | `cli.py` (já existe), `orchestrator.py` |

### Refatoração Granular In-Place (Usabilidade)

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| RG1 | ~~**Parâmetro `enabled_rules` no RefactoringOrchestrator** — filtrar `phase2_refactor_structure` para aplicar apenas regras selecionadas~~ | M | `refactorer.py` |
| RG2 | ~~**Modo interativo regra por regra** — `do_refactor()` pergunta ao dev cada regra individualmente antes de aplicar in-place~~ | M | `orchestrator.py` |

### Detecção de Duplicações e Modo LLM-Aware (Inteligência)

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| LL1 | ~~**Detector de duplicação semântica** — fingerprint AST normalizado (ignora nomes de variáveis locais e literais)~~ | G | `detectors/semantic_duplication.py` (novo) |
| LL2 | ~~**Heurística LLM-Aware** — se 3+ critérios clássicos de LLM (`BareExcept`, `MutableDefault`, `PrintLeak`, `UnusedVariable`) forem violados no mesmo run, elevar severidade de `MEDIA` para `ALTA`~~ | M | `analyzer/core.py` |

**Critério de pronto LZ1:** rodar `code-analyze check arquivo.py` duas vezes com o mesmo conteúdo — segunda execução mostra `[Lazy Evaluation] Arquivo não alterado. Reutilizando análise do histórico.`

**Critério de pronto RG2:** no modo interativo, opção 5 pergunta regra por regra ("Deseja remover imports não usados? (s/n)") e aplica apenas as aceitas.

**Critério de pronto LL1:** duas funções com corpos estruturalmente idênticos mas nomes/literais diferentes geram finding `MEDIA` sugerindo consolidação.

---

## ✅ v3.1.0 — Sugestões `git apply`-áveis + Score de Risco + Diffs Explicados (→ 10,0) (Concluída)

> **Problema:** se o dev precisa copiar e colar linha por linha, ninguém usa. Toda sugestão deve virar um patch aplicável. O score atual não reflete risco real de produção.

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| G1 | ~~**Gerar `.patch` por finding** — diff limpo no formato `git apply` para cada sugestão de refatoração~~ | G | `refactorer.py` |
| G2 | ~~**Modo interativo com `git apply`** — mostrar patch formatado, perguntar `[a]pply / [s]kip / [v]er diff / [q]uit`~~ | G | `orchestrator.py` |
| G3 | ~~**Score de risco de produção** — probabilidade de quebrar em produção baseada em: cobertura de testes + complexidade ciclomática + acoplamento eferente + critérios ALTA sem cobertura~~ | G | `analyzer/scoring.py` |
| G4 | ~~**`--patch-only`** — gerar apenas os `.patch` sem aplicar, para o dev revisar no editor~~ | M | `orchestrator.py` |
| L3 | ~~**Diff contextual explicado** — não "import removido", mas "função `calculate()` extraída da classe `Order` porque não usava atributos de instância; linha 42 → `pricing.py:120`"~~ | G | `refactorer.py`, `report_generator.py` |
| DUP | ~~**Duplicação semântica entre arquivos** — expandir fingerprint AST para detectar funções idênticas em arquivos diferentes (LLM gera `process_user` e `handle_user_data` fazendo a mesma coisa)~~ | G | `analyzer/semantic.py` (novo) |

**Critério de pronto DUP:** `code-analyze dup src/a.py src/b.py` retorna JSON com pares de funções duplicadas cross-file.

---

## ✅ v3.2.0 — Otimização de Performance (+0,0 — mantém 10,0) (Concluída)

> **Problema:** a cada execução, 4 subprocessos sequenciais bloqueiam por até 25s, AST é re-parseado 3x por detectores diferentes, e o histórico cresce linearmente sem limite.

### Subprocesso paralelo

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| P1 | ~~**Paralelizar ruff + pylint** — `concurrent.futures.ThreadPoolExecutor` para rodar ambos em threads separadas em vez de 4 chamadas sequenciais~~ | M | `analyzer/core.py` |

### Cache de AST

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| P2 | ~~**Eliminar AST re-parse redundante** — `_detect_inline_imports` (coupling.py) e `SemanticDuplicationDetector` usam `ctx.tree` em vez de `ast.parse(ctx.code)`~~ | P | `detectors/coupling.py`, `detectors/semantic_duplication.py` |

### Histórico enxuto

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| P3 | ~~**Índice `.index.json` no histórico** — arquivo único com `{content_hash: timestamp}` para evitar ler todos os snapshots a cada `load_history()`~~ | M | `history.py` |
| P4 | ~~**`load_history()` paginada** — carregar apenas últimos N snapshots (padrão 10) em vez de todos; `get_last_matching_snapshot()` usa o índice~~ | M | `history.py` |
| P5 | ~~**Remover `analysis_full` do payload** — snapshot armazena apenas `content_hash` + `scores` + `maintainability_index`; análise completa fica em arquivo separado só quando necessário~~ | P | `history.py` |

**Critério de pronto P1:** `python -m pytest tests/ -v` passando + ruff e pylint executando em paralelo.

**Critério de pronto P2:** Nenhum detector chama `ast.parse()` diretamente; todos usam `ctx.tree`.

**Critério de pronto P3-P5:** `load_history()` com 50+ snapshots executa em <10ms; `get_last_matching_snapshot()` usa `.index.json` (1 leitura vs N leituras).

---

## ✅ v3.2.2 — Honestidade (Concluída — 2026-05-20)

> **Problema:** uso real por 7 rodadas revelou 3 formas de a ferramenta mentir por omissão: score Pylint zerado em Django, score alto com bugs sérios, e ausência de contexto de débitos conhecidos do projeto.

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| H1 | ~~**Pylint unreliable detection** — contar E0401/E0611; se ≥2, setar `unreliable=True` + warning explícito "configure DJANGO_SETTINGS_MODULE antes de confiar neste número"~~ | P | `analyzer/core.py` |
| H2 | ~~**Score disclaimer** — nota em Markdown, HTML e terminal explicando que o score mede convenções estruturais, não corretude semântica (bugs de ORM, race conditions, lógica de negócio são invisíveis)~~ | P | `report_generator.py`, `orchestrator.py` |
| H3 | ~~**Project context (CLAUDE.md)** — subir até 6 diretórios buscando CLAUDE.md, extrair linhas com indicadores de débito (bug, TODO, FIXME, hack...), exibir seção "Contexto do Projeto" nos relatórios e terminal~~ | M | `project_context.py` (novo), `analyzer/__init__.py`, `report_generator.py`, `orchestrator.py` |

---

## ✅ v3.3.0 — Diagnóstico Inteligente (Concluída — 2026-05-21)

> **Problema (feedback real — 7 rodadas):** a ferramenta para no sintoma ("God Class 900 linhas") mas não diz o diagnóstico ("11 callbacks via parâmetro → Strategy Pattern"). Detecção de string dispatch passa despercebida. Rodadas tardias sugerem trivialidades enquanto o problema real fica invisível.

### Detecção de String Dispatch (esforço baixo, valor alto)

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| SD1 | ~~**Novo detector `StringDispatch`** — varrer métodos de uma classe buscando `if self.X == "literal":` (ou `elif`) repetido em ≥2 métodos com o mesmo atributo. Finding: "atributo `provider` usado como dispatcher em 3 métodos — candidato a Strategy Pattern".~~ (Concluído) | M | `detectors/string_dispatch.py` |
| SD2 | ~~**Sugestão concreta no finding** — o finding deve nomear o padrão e sugerir a interface mínima: `class ProviderStrategy(ABC): def process(self, ...): ...`~~ (Concluído) | P | `detectors/string_dispatch.py` |

### Aviso de ROI Decrescente (esforço muito baixo, valor médio)

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| ROI1 | ~~**Detecção de plateau** — ao carregar histórico, se `abs(score_atual - score_anterior) < 0.3` em 2+ rodadas consecutivas, emitir aviso: "Score estável há N rodadas. Considere: (a) análise cross-file, (b) refatoração manual do monólito, (c) parar esta linha de análise."~~ (Concluído) | P | `orchestrator.py`, `history.py` |
| ROI2 | ~~**Estratégia alternativa sugerida** — o aviso deve apontar o critério mais estagnado e sugerir ação concreta fora do escopo do linter (ex: "God Class não melhora mais — divida manualmente antes de reanalizar")~~ (Concluído) | P | `orchestrator.py` |

### Sugestão de Padrões a Partir de Sintomas (esforço médio, valor alto)

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| PA1 | ~~**`pattern_advisor.py`** — módulo que lê o dict de `criteria` e aplica regras de mapeamento: God Class + muitos params → Strategy; SRP violado + DIP violado → Facade; muitos callbacks injetados → Pipeline/Chain of Responsibility~~ (Concluído) | M | `pattern_advisor.py` |
| PA2 | ~~**Seção "Padrões sugeridos" no relatório** — após os critérios, listar padrões identificados com: nome do padrão, por que se aplica aqui, interface mínima de exemplo em Python~~ (Concluído) | M | `report_generator.py` |
| PA3 | ~~**Integração no terminal** — ao final da Fase 2, mostrar padrões detectados se houver (compacto: "→ Candidatos: Strategy (LLMService), Facade (ViewsHelper)")~~ (Concluído) | P | `orchestrator.py` |

**Testes:** 117 testes passando (80 base + 37 sprints anteriores + 12 novos: 3 StringDispatch, 1 Pattern Advisor, 1 ROI, 7 SC, 2 CF, 3 DF — via implementação antecipada junto com v3.4.0).

---

## ✅ v3.4.0 — Análise Estrutural (Cross-file + Data-flow + Scoring Contextual) (Concluída — 2026-05-21)

> **Problema (feedback real — 7 rodadas):** o maior gap é que a ferramenta olha cada arquivo isoladamente. 25 funções idênticas entre `views_module.py` e `views/helpers.py` são invisíveis. Um `handle_chat_message` de 886 linhas com 7 fases internas não tem seus boundaries de extração sugeridos. `llm_service.py` importado por 47 arquivos recebe a mesma nota que um arquivo utilitário isolado.

### Cross-file Analysis (esforço alto, valor muito alto)

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| CF1 | ~~**Modo projeto** — `code-analyze project src/` que varre todos os `.py` do diretório e roda análise multi-arquivo~~ (Concluído) | G | `cli.py` |
| CF2 | ~~**Hash de corpo de função normalizado** — fingerprint AST que ignora nomes de variáveis locais e literais; detecta funções estruturalmente idênticas entre arquivos diferentes~~ (Concluído) | G | `analyzer/semantic.py` |
| CF3 | ~~**Relatório de duplicação cross-file** — saída formatada no terminal com nomes, arquivos e sugestão de consolidação~~ (Concluído) | M | `cli.py` |
| CF4 | ~~**`code-analyze dup src/a.py src/b.py`** — modo rápido para comparar dois arquivos específicos~~ (Concluído) | M | `cli.py` |

**Bug fix (auto-teste 2026-05-21):** `compare_directory()` e `get_import_fan_in()` não ignoravam `.skill_outputs/` — incluíam os próprios backups gerados pela ferramenta como arquivos do projeto. Adicionado `.skill_outputs` ao `_SKIP_DIRS` em `semantic.py` e `project_context.py`.

### Data-flow Graph (esforço alto, valor alto)

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| DF1 | ~~**Análise def-use dentro de funções longas** — para funções com >50 linhas, construir grafo produtor/consumidor via BFS em índice de variáveis~~ (Concluído) | G | `analyzer/dataflow.py` |
| DF2 | ~~**Detecção de clusters coesos** — grupos de variáveis que produzem e consomem entre si sem cruzar com outras variáveis; parâmetros excluídos do union-find para evitar conexões artificiais~~ (Concluído) | G | `analyzer/dataflow.py` |
| DF3 | ~~**Sugestão de boundaries de extração** — finding `DataFlowExtractor` com nome sugerido, range de linhas e variáveis envolvidas~~ (Concluído) | M | `detectors/dataflow_extractor.py` |

### Scoring Contextual (esforço médio, valor alto)

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| SC1 | ~~**Import fan-in** — contar quantos outros arquivos `.py` do projeto importam este módulo; scan ignora venv, `__pycache__`, `.skill_outputs` e similares~~ (Concluído) | M | `project_context.py` |
| SC2 | ~~**Git commit frequency** — `git log --oneline --follow <filepath>` nos últimos 90 dias; arquivos com >20 commits são "hot files"~~ (Concluído) | M | `project_context.py` |
| SC3 | ~~**Score de prioridade contextual** — combina fan-in (40%) + commit frequency (35%) + falta de cobertura (25%) → Índice 0-100 com label CRÍTICO/ALTA/MÉDIA/BAIXA~~ (Concluído) | M | `project_context.py`, `orchestrator.py`, `report_generator.py` |

**Testes:** 129 testes passando (129 total — 12 novos cobrindo SC1-SC3, CF1-CF2, DF1-DF3).

---

## ✅ v4.1.0 — Django-Aware (Concluída — 2026-05-21)

> **Problema:** pesquisa ampla identificou os 11 erros mais comuns de LLMs em Python/Django. A ferramenta cobria 3/11 completamente. Esta sprint fecha os 4 gaps mais impactantes via análise estática pura.

### Cobertura dos Top 11 erros de LLM

| # | Erro | Detector | Status |
|---|------|----------|--------|
| 1 | Mass Assignment `fields = '__all__'` | **MassAssignment** (novo) | ✅ Detecta |
| 2 | Bare Except `except Exception: pass` | BareExcept (ALTA) | ✅ Detecta |
| 3 | N+1 Queries — acesso ORM dentro de loop | **OrmInLoop** (novo) | ✅ Detecta |
| 4 | Race Condition sem `select_for_update` | Nenhum | ❌ Não detecta |
| 5 | Side effects no `save()` | **SaveSideEffects** (novo) | ✅ Detecta |
| 6 | God View — função com muitas responsabilidades | SRP + DeepNesting + GodClass | 🟡 Parcial |
| 7 | Signals sem `transaction.on_commit` | Nenhum | ❌ Não detecta |
| 8 | Mutable Default Argument `def f(x=[])` | MutableDefault (MEDIA) | ✅ Detecta |
| 9 | `is` vs `==` com strings/ints dinâmicos | **IdentityComparison** (novo) | ✅ Detecta |
| 10 | Async/Await com ORM síncrono | AsyncSyncMismatch | ✅ Detecta |
| 11 | MRO errado em Django CBVs | Nenhum | ❌ Não detecta |

**Resultado: 7/11 ✅ completos / 1 🟡 parcial / 3 ❌ ausentes**

### Novos detectores implementados

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| DG1 | ~~**IdentityComparison** — detectar `if x is "literal"` ou `if x is 42`; `ast.Compare` com op `Is`/`IsNot` e comparador `ast.Constant` não-None~~ | P | `detectors/identity_comparison.py` |
| DG2 | ~~**OrmInLoop** — detectar acesso a `.objects.` ou chamadas ORM dentro de `for`/`while` sem `select_related`/`prefetch_related`; parent map via `ast.walk` para identificar nó dentro de loop~~ | M | `detectors/orm_in_loop.py` |
| DG3 | ~~**MassAssignment** — detectar `fields = '__all__'` em classes herdando de `ModelForm`, `ModelSerializer`, `ModelViewSet`; verifica body direto e inner class `Meta`~~ | P | `detectors/mass_assignment.py` |
| DG4 | ~~**SaveSideEffects** — detectar chamadas de I/O externo (`send_mail`, `requests.*`, `celery.*`, `boto3.*`) dentro de `def save()` em classes herdando de `models.Model`~~ | M | `detectors/save_side_effects.py` |

### Gaps restantes (deferidos)

| # | Item | Dificuldade | Por que difícil |
|---|------|-------------|-----------------|
| DG5 | Race Condition sem `select_for_update` | Alta | Exige rastrear padrão read-then-write sobre o mesmo queryset; falsos positivos altos |
| DG6 | God View (Django) | Média | SRP já captura tamanho; faltaria classificar "é uma view" via herança `View`/`APIView` |
| DG7 | Signals sem `transaction.on_commit` | Alta | Exige rastrear uso de `@receiver` + verificar se corpo dispara I/O fora de `on_commit` |
| DG8 | MRO errado em Django CBVs | Alta | Exige inferir MRO real a partir de herança múltipla e detectar shadow de métodos |

**Testes:** 153 (138 base + 15 novos: 4×IdentityComparison, 3×OrmInLoop, 4×MassAssignment, 4×SaveSideEffects).

---

## ✅ v4.2.0 — Security Triad (Concluída — 2026-05-21)

> **Problema:** pesquisa aprofundada (Endor Labs 2025, arXiv 2024, OWASP LLM Top 10) revelou que 43-59% do código Python gerado por IA contém vulnerabilidades de injeção, 23-33% expõe credenciais hardcoded e gerenciamento de recursos (open sem with) é sistematicamente ignorado. Três gaps estruturais fechados via AST puro.

### Cobertura atualizada dos erros críticos de IA (após v4.2.0)

| Erro | Detector | Status |
|------|----------|--------|
| Mass Assignment `fields='__all__'` | MassAssignment | ✅ |
| Bare Except | BareExcept | ✅ |
| N+1 Queries | OrmInLoop | ✅ |
| Side effects em `save()` | SaveSideEffects | ✅ |
| `is` vs `==` com literais | IdentityComparison | ✅ |
| Async/Await com ORM síncrono | AsyncSyncMismatch | ✅ |
| Mutable Default Argument | MutableDefault | ✅ |
| Hard-coded secrets | **HardcodedSecrets** (novo) | ✅ |
| SQL/Command injection via f-string | **InjectionRisk** (novo) | ✅ |
| `open()` sem `with` | **ContextManagerLeak** (novo) | ✅ |
| God View | SRP + GodClass | 🟡 Parcial |
| Race Condition sem `select_for_update` | Nenhum | ❌ Runtime |
| Signals sem `transaction.on_commit` | Nenhum | ❌ Runtime |
| MRO errado em Django CBVs | Nenhum | ❌ Runtime |

**10/13 ✅ via análise estática pura. Os 3 restantes são semânticos (requerem runtime).**

### Novos detectores

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| SEC1 | ~~**HardcodedSecrets** — varrer `ast.Assign`/`ast.AnnAssign`; se nome contém `secret/password/api_key/token/credential` e valor é string literal não-placeholder, reportar ALTA com sugestão de `os.environ.get()`~~ | P | `detectors/hardcoded_secrets.py` |
| SEC2 | ~~**InjectionRisk** — detectar `.raw()`, `.extra()`, `cursor.execute()`, `os.system()`, `subprocess.run()` com argumento `ast.JoinedStr` (f-string) ou `ast.BinOp(Add/Mod)` (concatenação/%-format) — SQL e command injection numa passagem~~ | M | `detectors/injection_risk.py` |
| SEC3 | ~~**ContextManagerLeak** — parent map para verificar se `open()` tem ancestral `ast.With`; se não, reportar MEDIA com sugestão de `with open() as f:`~~ | P | `detectors/context_manager_leak.py` |

**Testes:** 166 (153 base + 13 novos: 5×HardcodedSecrets, 5×InjectionRisk, 3×ContextManagerLeak).

---

## ✅ v4.0.0 — Cirurgia Robótica (Concluída — 2026-05-21)

> **Visão:** a ferramenta não aponta o problema — ela opera e fecha o paciente. Não é auditoria, é copiloto de refatoração. As três features abaixo juntas transformam o diagnóstico em ação verificável.

---

### 4.1 — Refactoring com Prova de Equivalência

| # | Item | Esforço | Status |
|---|------|---------|--------|
| EQ1 | ~~**Classificador de pureza funcional** (`purity.py`) — `pure`/`side_effect`/`unknown` via `ast.walk`~~ | G | ✅ Concluído |
| EQ2 | **Prova formal AST para funções puras** — substituição e isomorfismo estrutural | G | ⏳ Deferido (funções puras são raras em Django) |
| EQ3 | ~~**Geração de `test_equivalence_*.py`** — scaffold pytest para blocos com side effects~~ | G | ✅ Concluído |
| EQ4 | **PR pronto** — patch + teste + commit message em uma operação | G | ⏳ Deferido para v4.5 |
| EQ5 | ~~**Relatório de confiança** — badges Alta/Média/Baixa no terminal e Markdown~~ | M | ✅ Concluído |

---

### 4.2 — Duplicação Cross-Codebase em Escala

| # | Item | Esforço | Status |
|---|------|---------|--------|
| XD1 | ~~**Índice de fingerprints em disco** — `~/.code-analyzer/fingerprints/` com mtime incremental~~ | G | ✅ Concluído |
| XD2 | ~~**`code-analyze project <dir> --threshold 0.9`** — similaridade fuzzy configurável~~ | G | ✅ Concluído |
| XD3 | **Diff lado a lado no relatório** — HTML com grid mostrando diferenças de variáveis | G | ⏳ Deferido para v4.5 |
| XD4 | **Consolidação automática** — PR pronto para duplicatas 100% idênticas | G | ⏳ Deferido para v4.5 |
| XD5 | ~~**Modo incremental** — re-indexa apenas arquivos com mtime alterado~~ | G | ✅ Concluído (via fingerprint_index.py) |

---

### 4.3 — Pipelines como Cidadãos de Primeira Classe

| # | Item | Esforço | Status |
|---|------|---------|--------|
| PL1 | **Detector de pipeline implícito** — sequências lineares de blocos sem cruzamento de variáveis | G | ⏳ Deferido para v4.5 |
| PL2 | **Grafo de dependência de dados entre fases** — inputs/outputs/side effects por fase | G | ⏳ Deferido para v4.5 |
| PL3 | **Inferência de nomes de fase** — a partir de comentários, variável de output, padrão de chamada | G | ⏳ Deferido para v4.5 |
| PL4 | **Geração do código refatorado** — orquestrador + N métodos de fase com assinatura inferida | G | ⏳ Deferido para v4.5 |
| PL5 | **Prova de equivalência do pipeline** — EQ2/EQ3 aplicado ao conjunto de métodos gerados | G | ⏳ Deferido para v4.5 |
| PL6 | **PR pronto para pipeline** — patch + testes + diff fase a fase | G | ⏳ Deferido para v4.5 |

**Testes v4.0.0:** 138 (129 base + 9 novos: purity, equivalence, fingerprint_index, fuzzy).

---

## v5.0.0 — Test Pain como Sinal de Arquitetura

> **Visão:** todo sinal de análise do backlog anterior foi gerado por máquina — AST, métricas, heurísticas. Este é o único sinal gerado por humano que a ferramenta pode ler: o custo que o dev pagou para testar o código. Arquitetura ruim torna testes difíceis de escrever. Medir essa dificuldade é medir acoplamento e coesão com uma precisão que análise estática nunca alcança sozinha.

---

### 5.1 — Métricas de Dor de Teste

> **Premissa:** se `test_payment.py` precisa de 8 mocks para testar uma função de 30 linhas, aquela função tem 8 dependências reais — não as 2 que o acoplamento estrutural mostra. O teste é o oráculo.

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| TP1 | **Detector de mock density** — em arquivos de teste, contar instâncias de `MagicMock`, `patch`, `monkeypatch`, `Mock`, `AsyncMock` por função de teste. Razão `mocks / linhas_testadas` > 0.3 = sinal de acoplamento real não visível no AST. | M | `analyzer/test_pain.py` (novo) |
| TP2 | **Detector de setup complexity** — medir linhas de fixture/setup (`setUp`, `@pytest.fixture`, blocos `with patch(...)`) versus linhas de assertion. Razão setup/assert > 3:1 = abstração errada na camada testada. | M | `analyzer/test_pain.py` |
| TP3 | **Razão teste/produção por módulo** — cruzar `test_X.py` com `X.py`: razão `linhas_de_teste / linhas_de_produção`. Módulo crítico (fan-in alto) com razão < 0.3 = sub-testado ou tão acoplado que ninguém consegue testar. | M | `analyzer/test_pain.py`, `project_context.py` |
| TP4 | **Test pain score** — score 0–10 por módulo composto de: mock density (40%) + setup complexity (30%) + razão teste/produção (30%). Integrar ao score de risco de produção existente (`scoring.py`). | M | `analyzer/scoring.py` |

---

### 5.2 — Cruzamento com Análise Estrutural

> **Premissa:** o test pain score sozinho é um número. Cruzado com os findings estruturais, vira diagnóstico.

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| TP5 | **Correlação mock ↔ acoplamento real** — se `test_llm_service.py` tem mock density alta mas o AST de `llm_service.py` mostra coupling score 7/10, reportar divergência: "acoplamento estrutural subestimado — teste revela 6 dependências reais não capturadas pelo AST". | G | `report_generator.py` |
| TP6 | **Identificação de módulos impossíveis de testar** — módulo com fan-in alto (importado por muitos) + test pain score baixo + sem testes = "módulo crítico sem safety net". Severidade ALTA automática, independente dos outros scores. | M | `analyzer/test_pain.py`, `analyzer/scoring.py` |
| TP7 | **Mapa de dependências reveladas pelos testes** — reconstruir o grafo de dependências reais a partir dos `patch("modulo.Classe")` nos testes (o dev patcheou o que ele sabia que seria chamado). Comparar com o grafo de imports do AST. Divergências = dependências implícitas não declaradas. | G | `analyzer/test_pain.py`, `analyzer/dataflow.py` |

---

### 5.3 — Sugestões Orientadas por Dor

> **Premissa:** se a ferramenta sabe onde dói testar, ela sabe onde refatorar primeiro — não pelo score estrutural, mas pela evidência de que o dev já sinalizou o problema ao escrever testes difíceis.

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| TP8 | **"Refatore para tornar testável"** — para módulos com test pain alto, sugerir refatoração orientada a testabilidade: injeção de dependência onde há `patch`, extração de interface onde há `MagicMock` de classe concreta, separação de I/O onde há mock de `requests`/`django.db`. | G | `pattern_advisor.py` (v3.3), `report_generator.py` |
| TP9 | **Priorização por dor humana** — reordenar as recomendações combinando: score estrutural (AST) + test pain score + fan-in (v3.4). O módulo que lidera nas três dimensões vai para o topo da lista, não o que tem pior score estrutural isolado. | M | `report_generator.py`, `analyzer/scoring.py` |
| TP10 | **Evolução do test pain no histórico** — rastrear test pain score entre execuções (já existe `history.py`). Se o pain está subindo enquanto o score estrutural está estável, detectar e alertar: "o código não piorou no AST, mas está ficando mais difícil de testar — sinal de degradação encoberta". | M | `history.py`, `orchestrator.py` |

**Critério de pronto TP1:** arquivo de teste com 5+ `patch()` por função gera finding com mock density e sugere injeção de dependência.

**Critério de pronto TP6:** módulo com fan-in > 10, test pain score < 3 e sem arquivo de teste correspondente recebe severidade ALTA automática no relatório.

**Critério de pronto TP7:** grafo de dependências reconstruído a partir dos patches do teste difere do grafo de imports AST em ≥1 módulo — divergência reportada como "dependência implícita não declarada".

**Critério de pronto TP10:** duas rodadas consecutivas com test pain crescendo enquanto score AST estável geram alerta "degradação encoberta detectada".

---

## Norte do produto

> Checklist do que separa uma skill boa de uma indispensável.

| # | O que o dev sênior quer | Versão alvo |
|---|------------------------|-------------|
| N1 | Score de risco de produção em vez de lista de findings | v3.0 — G3 |
| N2 | "Isso aqui não existe" — validar imports e APIs reais | v2.3 — V1/V2 |
| N3 | Diff contextual que explica a decisão, não só o que mudou | v3.1 — L3 |
| N4 | Memória entre execuções — "SRP melhorou 2pts em 30 dias" | v2.5 — H1/H2 |
| N5 | Modo LLM-aware — `except:` de LLM tem severidade maior | v3.0 — LL2 |
| N6 | Sugestão `git apply`-ável — revisada em 2s e aplicada | v3.1 — G1/G2 |
| N7 | Refatoração granular — "aplica só isso, ignora aquilo" | v3.0 — RG2 |
| N8 | Motor de Inferência de Tipos estático local para eliminar falsos positivos semânticos | Futura / v3.5 |
| N9 | Tabela de Símbolos real (Symbol Table) para mapear escopos e imports com precisão absoluta | Futura / v3.5 |
| N10 | Cross-file analysis — detectar 25 funções idênticas entre arquivos em segundos | v3.4 — CF1/CF2 |
| N11 | "God Class 900 linhas → Strategy Pattern" — diagnóstico, não só sintoma | v3.3 — PA1/SD1 |
| N12 | "Mexa aqui primeiro" — priorização por fan-in + frequência de commit + cobertura | v3.4 — SC1/SC3 |
| N13 | Aviso de ROI decrescente — "Score estável há 2 rodadas, mude de estratégia" | v3.3 — ROI1 |
| N14 | Data-flow graph — sugerir boundaries de extração em funções longas automaticamente | v3.4 — DF1/DF3 |
| N15 | Refactoring com prova de equivalência — scaffold de teste gerado automaticamente | v4.0 ✅ — EQ1/EQ3/EQ5 |
| N16 | Duplicação cross-codebase em escala — índice incremental + similaridade fuzzy | v4.0 ✅ — XD1/XD2/XD5 |
| N17 | Django N+1 detectado via AST — acesso `.objects.` dentro de loop | v4.1 ✅ — OrmInLoop |
| N18 | Mass Assignment detectado — `fields='__all__'` em ModelForm/Serializer | v4.1 ✅ — MassAssignment |
| N19 | Side effects em `save()` detectados — I/O externo em model.save() | v4.1 ✅ — SaveSideEffects |
| N20 | Hard-coded secrets detectados — credenciais literais no código-fonte | v4.2 ✅ — HardcodedSecrets |
| N21 | SQL/Command injection detectados — f-strings em raw()/os.system() | v4.2 ✅ — InjectionRisk |
| N22 | Resource leak detectado — open() sem with statement | v4.2 ✅ — ContextManagerLeak |
| N23 | Test pain como sinal de arquitetura — o único sinal gerado por humano que a ferramenta pode ler | v5.0 — TP1/TP7 |
| N24 | Dependências implícitas reveladas pelos testes — grafo real vs. grafo AST | v5.0 — TP7 |
| N25 | Priorização por dor humana — score estrutural + test pain + fan-in | v5.0 — TP9 |
| N26 | PR pronto completo — patch + teste de equivalência + commit message em uma operação | v4.5 — EQ4/PL6 |

---

## Concluído — v2.1.7 e anteriores

<details>
<summary>Ver todos os itens concluídos</summary>

### Infraestrutura e contrato CLI
- Contrato universal de CLI (cmd + flags + exit codes + stdout/stderr)
- Saída estruturada por execução (`.skill_outputs/`)
- Validação final via `compile()` antes de escrever mudanças
- Manifesto com todos os artefatos gerados
- Config por projeto (`.analyzer.json` + `pyproject.toml [tool.code-analyzer]`)
- `--output`, `--dry-run`, `--json`, `--html` funcionando em todos os comandos
- Avisar quando ruff/pylint não estão instalados
- `--json` consistente em todos os comandos do `bin/cli.py`
- Dashboard HTML auto-contido com cards e score bars
- Resumo executivo no terminal com grade A/B/C/D

### Arquitetura interna (P0)
- Migração `scripts/` → `src/code_analyzer/` (pacote pip instalável via pyproject.toml)
- Detector Registry: 34 detectores independentes substituindo God Class de 2263 linhas
- `detect_all()` substituindo `_evaluate_criteria()` de 547 linhas
- argparse (`build_parser` + `run_pipeline`) substituindo `main()` de 246 linhas
- `bin/cli.js` roteando para `bin/cli.py` sem hardcode de paths
- 80/80 testes passando

### Critérios SOLID + Arquitetura (10)
- Single Responsibility (SRP)
- Open/Closed Principle (OCP)
- Dependency Inversion (DIP)
- Layer Separation
- Coupling
- Cohesion
- Design Patterns (com sinais estruturais)
- God Class/Object
- Circular Dependencies (com grafo real)
- Interface Segregation

### Critérios LLM — padrões comuns (24)
- BareExcept, NoneComparison, MutableDefault, ShadowingBuiltins
- SecurityRisk (eval/exec/pickle), AsyncSyncMismatch
- RedundantIfReturn, InconsistentReturns, DotKeys
- StringConcatInLoop, AnyAllListComp, DeepNesting
- TypeIsinstance, UnusedIterationVar, DictGet, ManualAccumulate
- RangeLenLoop, UnusedVariable, ManyParameters, WildcardImport
- PrintLeak, MissingSuperInit, OverrideSignatureMismatch, AbstractMethodNotImplemented

### Testes
- 80 testes cobrindo comportamento de todos os detectores
- `pyproject.toml` com `testpaths` e `pythonpath` configurados

</details>
