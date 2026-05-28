# Backlog — Code Architecture Analyzer

## Visão

Evoluir o `code-architecture-analyzer` para uma skill portátil, prática e confiável que vai além de um linter — validando dependências reais, rastreando evolução do código ao longo do tempo e gerando sugestões que o dev consegue aplicar em segundos.

---

## Por que comunicação é o diferencial real

> "Skill de sobra na internet. Que sabe comunicar bem e é confiável são poucas."

A internet está cheia de analisadores com profundidade técnica — AST, 49 critérios, cache, Django-aware. Isso virou commodity. O que separa uma ferramenta que o dev usa todo dia de uma que ele desinstala na segunda semana não é o número de detectores: é se ele **acredita** no que ela diz e se ela **fala no momento certo**.

Duas frases que definem o que falta hoje:

> "A ferramenta tem profundidade técnica de sobra, mas comunicação pobre com o usuário. O HTML é a prova que ela sabe fazer — ela só não entrega."

> "A ferramenta te dá o diagnóstico e a sugestão, mas não o plano de ação priorizado. É um raio-X com 45 manchas marcadas, mas sem o médico dizendo 'opere essa primeiro'."

### Os três pilares

| Pilar | O que significa | Versão |
|-------|----------------|--------|
| **Confiança** | FP baixo, disclaimers honestos, confidence calibrada. O tool não adivinha — pergunta quando incerto e usa a resposta como verdade. O dev não ignora o que ele diz porque ele raramente mente. | v6.0.1 ✅ + v6.1 (Intent Learning) |
| **Comunicação** | O sinal certo, no canal certo, no momento certo. Não 45 findings no terminal — os 3 que importam, no PR, quando o dev ainda pode agir. | v6.2 (PR bot, badge, triage) |
| **Ação** | Não só diagnóstico — o plano ordenado. "Corrija esse primeiro: impacto +1.2pts, risco baixo, 10 linhas." O médico que lê o raio-X e opera, não só aponta as manchas. | v7.0 (ActionRecord, agora ancorado nas respostas do v6.1) |

### O caminho

```
Confiança → Comunicação → Ação
(v6.1)       (v6.2)       (v7.0)
```

Sem confiança, melhorar a comunicação só amplifica o ruído.
Sem comunicação, a ação nunca chega ao dev no momento certo.
Com os três, a ferramenta vira o único analisador que o time consulta antes de fazer merge.

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
| **v4.3.0** | AAB-2026 — FeatureEnvy, ShotgunSurgery, LSP (set_X side-effect), pre-commit hook (--min-score), code-analyze init inteligente (Concluída) | **48 critérios, 193 testes, 96/100** |
| **v4.3.1** | P0 fixes — LSP remove NotImplementedError falso positivo; DesignPatterns penalty=0 (Concluída) | **100/100 AAB-2026** |
| **v4.4.0** | Refatoração de Arquitetura — orquestrador.py 907 → 45 linhas; God Function quebrada em 5 sub-funções com PipelineContext; extração de terminal_ui, interactive, gate, pipeline (Concluída) | **nota interna 9.3** |
| **v4.4.1** | Falsos Positivos — PrintLeak ignora módulos de UI; InconsistentReturns não pune None implícito (Concluída) | **confiabilidade** |
| **v5.0.0** | Test Pain como Sinal de Arquitetura — mock density, cobertura real, complexidade de teste, isolamento; 5º componente no production_risk_score (Concluída — core) | **203 testes, risco +7pts** |
| **v6.0.0** | Performance Overhaul + Pylint Removal — walk cache compartilhado, criteria cache por hash, ruff substitui pylint (Concluída — 2026-05-22) | **5-8x mais rápido** |
| **v6.0.1** | FP fixes — DictGet/InconsistentReturns/UnusedVariable/NoneComparison + _SKIP_DIRS expandido (Concluída — 2026-05-23) | **-53% findings ruidosos** |
| **v6.1.0** | Intent Learning — perguntas direcionadas, `INTENT.md` auto-gerado, confidence calibrada, respostas como ground truth (Concluída — 2026-05-24) | **diferencial defensável: ferramenta que aprende o projeto** |
| **v6.2.0** | UX overhaul — welcome, bloco "O que fazer agora", HTML automático, i18n pt/en, `--force` zera criteria_cache (Concluída — 2026-05-23) | **297 testes** |
| **v6.3.0** | Agent mode — `--agent` produz Markdown estruturado limpo para agentes de IA (Concluída — 2026-05-24) | **agentes como usuário primário** |
| **v6.4.0** | Distribuição — GitHub Action no marketplace + PR comment bot + Score decomposto + badge dinâmico (Planejada) | **alcance viral** |
| **v7.0.0** | Caminho das Pedras — output Agent-Ready: confidence, provenance, blast radius, suggested diff, verification spec (Em andamento — ver `sprint_atual.md`) | **diferencial defensável: LSP para arquitetura** |

---

## 🚧 v7.0.0 — Caminho das Pedras (Agent-Ready Output) (Em andamento — ver `sprint_atual.md`)

> **Problema central:** "A ferramenta te dá o diagnóstico e a sugestão, mas não o plano de ação priorizado. É um raio-X com 45 manchas marcadas, mas sem o médico dizendo 'opere essa primeiro'."
>
> **Problema de profundidade (validado em campo — 2026-05-24):** A ferramenta opera no nível **sintático/estrutural** mas os bugs que importam estão no nível **semântico/domínio**. Exemplo real: `views.py` de um projeto Django com `planner_create_course` sem `@login_required` (qualquer anônimo pode criar cursos) e `AgentOrchestrator(user=..., lesson=...)` instanciado e descartado (possível bug). A ferramenta não viu nenhum dos dois — viu `print()` e imports inline, mas não o que importava para segurança e corretude.
>
> O gap tem nome: a ferramenta sabe **o que está estruturalmente errado** mas não **o que é semanticamente perigoso**. Ir fundo sem confidence calibrada vira ruído. Por isso profundidade vem aqui, no v7.0, junto com o sistema de confidence.
>
> **O insight que define o teto do problema (2026-05-24):** Um desenvolvedor humano nunca analisa código sem contexto — ele leu o PRD antes de escrever, sabe *por que* aquela função existe, *para que* aquele endpoint foi criado, *quem* vai consumir aquela API. Quando ele revisa código alheio, reconstrói mentalmente esse PRD a partir de nomes, comentários, testes e docs. A ferramenta hoje não faz isso — ela lê a estrutura mas não entende a intenção. Resultado: ela vê `planner_create_course` sem `@login_required` mas não sabe que o nome implica criação de recurso que exige autenticação. Ela vê `AgentOrchestrator(user=..., lesson=...)` sem atribuição mas não sabe se aquela instanciação foi intencional (fire-and-forget) ou acidental (bug de refatoração).
>
> **Atingir top 3 do mundo requer que a ferramenta entenda o PRD do código** — o *por que* foi feito e *para que* foi feito — não apenas o *como* foi implementado. **A decisão arquitetural do v6.1 muda como isso é feito:** em vez de inferir intenção via LLM (caro, alucina), o tool pergunta ao usuário nos pontos incertos e persiste a resposta em `.analyzer_intent.json`. A v7.0 herda esse `.analyzer_intent.json` como ground truth — ActionRecords só são gerados quando o tool tem confidence ≥ 0.85 *após* aplicar as respostas do usuário. LLM entra apenas onde o usuário não pode/não vai responder (resumos, geração de diffs mecânicos, classificação de impacto).
>
> A ferramenta hoje para no nível 2 — "achei X, considere Y". Pra ser top 3 do mundo (e diferencial sobre Sonar/DeepSource/Codacy) precisa virar nível 3 — gerar `ActionRecord` estruturado que um agente de codificação aplica sem revisão humana nos casos triviais. A pergunta-chave que essa versão responde: *"posso confiar nesse finding o suficiente pra deixar um agente aplicar o fix sem revisão?"*. Hoje a resposta é "não, sempre revisa". Meta: virar "sim, nos triviais com confidence > 0.85".

### Mudança arquitetural

Hoje:
```
findings → criteria → score → report
```

Depois:
```
findings → enrichment → action_records → agent_output
```

### As 6 dimensões de cada `ActionRecord`

| Dimensão | Pergunta que responde | Reuso |
|---|---|---|
| **Provenance** | "De onde veio esse valor?" | `analyzer/dataflow.py` (v3.4.0, já existe — falta expor por finding) |
| **Usage graph** | "Quem mais usa isso?" | `analyzer/detectors/circular_deps.py` (grafo já montado — expor fan-in/blast radius) |
| **Test coverage** | "Que teste cobre isso?" | `analyzer/test_pain.py` (mapping test_X → X já existe) |
| **Confidence** | "Tenho certeza?" | Novo — cada detector emite 0.0-1.0 baseado em regras de contexto |
| **Suggested diff** | "Como muda o código?" | Estender `--patch-only` (hoje só cleanup) pra padrões mecânicos |
| **Verification** | "Como sei que funcionou?" | Novo — `VerifyStep(kind="test"|"lint"|"missing_test", cmd=...)` |

### Tarefas

| # | Item | Arquivo | Esforço |
|---|------|---------|---------|
| AR1 | ~~**`ActionRecord` dataclass** — `Finding + provenance + callers + tests_covering + confidence + suggested_diff + verification + risk_level`~~ (Concluído — 2026-05-24) | `analyzer/action_plan.py` (novo) | 1 sprint |
| AR2 | **Confidence por detector** — adicionar campo `confidence: float` em `Finding`, cada detector preenche baseado em regras de contexto (ex: DictGet em dict externo = 0.9, em dict literal local = 0.2) | `analyzer/detectors/*.py` | 1 sprint |
| AR3 | ~~**Flag `--agent-mode`** — output JSON otimizado pra LLM com ActionRecords completos. Sem ANSI, com `summary`, `why_here`, `blast_radius`~~ (Concluído — 2026-05-24) | `agent_output.py` + `pipeline.py` | 0.5 sprint |
| AR4 | **Enrichment pipeline** — conecta findings a dataflow + circular_deps + test_pain. Output: `result["action_records"]` | `analyzer/action_plan.py` | 1-2 sprints |
| AR5 | **Diff generation pros 4 padrões mecânicos** — `dict[k] → dict.get(k)`, `== None → is None`, `range(len()) → enumerate`, `except: → except Exception:` usando libcst ou ast.unparse | `refactorer.py` (estender) | 1-2 sprints |
| AR6 | **Verification spec** — pra cada `ActionRecord`, gerar `verify: List[VerifyStep]` com `pytest` + `ruff` rodáveis | `analyzer/action_plan.py` | 1 sprint |
| AR7 | **`code-analyze apply <action_id>`** — aplica um ActionRecord específico, roda verify, reverte se falha | `cli.py` + `refactorer.py` | 1 sprint |

### Análise semântica / domínio (validada em campo — 2026-05-24)

> Itens abaixo dependem do **Intent Learning (v6.1)**. Cada um emite findings com `confidence` baixa por padrão — sem a infraestrutura de perguntas+respostas+`INTENT.md`, viram ruído. Um detector que dispara em toda view sem `@login_required` gera FPs para endpoints públicos por design; com Intent Learning, o usuário responde uma vez ("este módulo é privado, todas as views devem ter auth") e os FPs evaporam para sempre.

| # | Item | O que detecta | Exemplo real |
|---|------|--------------|--------------|
| SD1 | **`DjangoViewSecurity`** — verifica presença de `@login_required`, `@permission_required` e `@csrf_exempt` em views Django. Flags quando endpoint aceita mutação (POST/PUT/DELETE) sem autenticação | Views sem `@login_required` expostas | `planner_create_course` aceitava criação de curso por anônimo |
| SD2 | **`UnusedCallResult`** — detecta chamada de método/construtor cujo retorno é descartado e não é padrão "fire-and-forget" conhecido (`thread.start()`, `logger.*`, `print()`) | Objeto instanciado e ignorado | `AgentOrchestrator(user=..., lesson=...)` sem atribuição — bug ou efeito colateral oculto |
| SD3 | **`DeadAssignment`** — detecta expressão cujo resultado nunca é usado na função (não é underscore, não é atribuição a `_`) | Valor calculado e jogado fora | `data.get("context", "practice")` sem atribuição — sobra de refatoração |
| SD4 | **Inline import map completo** — varrer TODO o corpo de funções recursivamente, não só o nível 1. Hoje o Coupling só acha alguns inline imports | Todos os imports dentro de funções | 7 inline imports em `views.py` não detectados |

### Exemplo de output `--agent-mode`

```json
{
  "action_records": [
    {
      "id": "core.py:45:DictGet:7f3a",
      "summary": "Replace dict[key] with dict.get(key) in parse_response",
      "location": "src/api.py:45",
      "why_here": "payload comes from requests.json() at line 30 (external source)",
      "blast_radius": ["src/api/views.py:88", "src/services/auth.py:42"],
      "tests_covering": ["tests/test_api.py::test_parse_success"],
      "confidence": 0.92,
      "risk_level": "safe",
      "diff": "@@ -45,1 +45,3 @@\n-    user_id = payload[\"user_id\"]\n+    user_id = payload.get(\"user_id\")\n+    if user_id is None:\n+        raise ValueError(\"user_id missing in payload\")\n",
      "verify": [
        {"kind": "test", "cmd": "pytest tests/test_api.py::test_parse_success"},
        {"kind": "missing_test", "spec": "parse_response with payload={} should raise ValueError"},
        {"kind": "lint", "cmd": "ruff check src/api.py"}
      ]
    }
  ]
}
```

### Por que isso é diferencial real

Sonar, DeepSource, Codacy fazem **nível 2** (detector + sugestão textual). Nenhum faz **nível 3** (output executável). GitHub Copilot/Cursor/Aider tentam gerar fixes mas não têm:
- Grafo de dependências do projeto
- Mapping de testes
- Confidence calibrada por contexto
- Detectores arquiteturais

Mas o diferencial mais profundo não é técnico — é epistemológico: **nenhuma ferramenta hoje entende o PRD do código**. Elas leem o que está escrito, não o porquê foi escrito. Um analisador que reconstrua a intenção por trás de cada decisão estrutural — mesmo que parcialmente, mesmo que com confidence 0.6 — já diz mais do que qualquer ferramenta puramente sintática.

> "Seria como eu tivesse que entender o PRD do código — o por que foi feito e para que foi feito."

Esse é o gap que separa o top 3 do resto: não mais detectores, não mais regras, mas a capacidade de responder *"faz sentido existir aqui?"* com fundamentação. Um desenvolvedor sênior faz isso intuitivamente. Uma ferramenta que faz isso com rastreabilidade e confidence vira o par-programador que o time consulta antes de toda PR.

Se essa versão sair, a ferramenta vira **"LSP para arquitetura"** — camada que sustenta agentes (Claude Code, Cursor, Aider, Copilot Agent) com sinais estruturados que eles sozinhos não geram. Ninguém faz isso pra Python hoje.

### Critério de pronto

- [ ] Flag `--agent-mode` produz JSON com ActionRecords completos
- [ ] Confidence calibrada em todos os 49 detectores
- [ ] 4 padrões mecânicos com diff gerado automaticamente
- [ ] `code-analyze apply <id>` aplica + verifica + reverte se falha
- [ ] Testes E2E: rodar a ferramenta no próprio código, aplicar 5 action records, todos os 203 testes continuam passando
- [ ] Doc explicando contrato `--agent-mode` pra integradores (Cursor, Claude Code, Aider)

---

## 🔮 v6.4.0 — Distribuição (Planejada)

> **Nota de versionamento (2026-05-28):** esta seção foi originalmente numerada v6.2.0, mas o número v6.2.0 foi consumido pelo UX overhaul de fato lançado em 2026-05-23. A "Distribuição" foi renumerada para v6.4.0 e permanece não iniciada.

> **Problema:** Performance e detectores não importam se a ferramenta não está no fluxo diário do dev. Hoje você precisa rodar manualmente. Pra adoção viral, precisa estar no PR, no editor, no badge do README.

### Tarefas

| # | Item | Esforço |
|---|------|---------|
| D1 | **GitHub Action no marketplace** — `uses: SergioMT88/code-architecture-analyzer@v6` com inputs `min-score`, `fail-on-regression`, `comment-pr` | 1 sprint |
| D2 | **PR comment bot** — Action posta comment no PR: "Score caiu de 8.2 para 7.4 — `analyzer/core.py` ganhou 3 críticos" com link para detalhes | 0.5 sprint |
| D3 | **Score com decomposição** — relatório mostra "Risco 34.5/100 = 35% complexidade + 25% acoplamento + 21% cobertura + 13% tamanho + 6% findings". Já tem os números, falta apresentar | 0.5 sprint |
| D4 | **Badge dinâmico** — `archscore.io/<user>/<repo>/badge.svg` (GitHub Pages estático, atualizado por Action) | 1 sprint |
| D5 | **VS Code extension MVP** — wrapper sobre `code-analyze --json`. Highlights inline ao salvar. Quick-fix: "Silence this finding" | 1-2 sprints |

### Critério de pronto

- [ ] Action publicada em github.com/marketplace
- [ ] Repo de exemplo usando a Action com badge no README
- [ ] Extension publicada no VS Code Marketplace (pode ser preview)
- [ ] Decomposição do score aparece em terminal, JSON e HTML

---

## ✅ v6.3.0 — Agent Mode (Concluída — 2026-05-24)

> **Decisão de produto:** agentes de IA são o usuário primário da ferramenta. A flag `--agent` produz Markdown estruturado limpo (sem ANSI, sem HTML, sem perguntas interativas) com ACTION PLAN priorizado, why/fix/pattern por critério, EXECUTION ORDER e status de Intent Learning.

| # | Item | Arquivo | Status |
|---|------|---------|--------|
| AG1 | ~~Flag `--agent` + `generate_agent_output()` (Markdown)~~ | `agent_output.py`, `pipeline.py` | ✅ |

**Testes:** 297. **Nota:** a fundação JSON (ActionRecords) começou na sequência como v7.0 — ver `sprint_atual.md`.

---

## ✅ v6.2.0 — UX Overhaul (Concluída — 2026-05-23)

> **Problema:** profundidade técnica de sobra, comunicação pobre. Esta versão entregou a camada de UX que faltava.

| # | Item | Arquivo | Status |
|---|------|---------|--------|
| UX1 | ~~Welcome na primeira execução~~ | `terminal_ui.py` | ✅ |
| UX2 | ~~Bloco "O que fazer agora" contextual ao final de toda análise~~ | `terminal_ui.py` | ✅ |
| UX3 | ~~HTML gerado automaticamente (sem flag `--html`) e aberto no browser~~ | `pipeline.py` | ✅ |
| UX4 | ~~i18n pt/en (`code-analyze config lang`)~~ | `i18n.py`, `config_cli.py` | ✅ |
| UX5 | ~~`--force` agora zera também o criteria_cache~~ | `pipeline.py` | ✅ |

**Testes:** 297.

---

## ✅ v6.1.0 — Intent Learning (Concluída — 2026-05-24)

> **Entregue (IL1-IL9):** `IntentStore` (`.analyzer_intent.json`), `run_intent_session()` (loop Q&A), `INTENT.md` auto-gerado, inferência derivada, noisy detectors (penalty=0), `code-analyze intent` CLI (list/show/reset/export/import), `code-analyze health`. Calibração de confiança (Cohesion/DIP/ISP/OrmInLoop → 0.60). FP fixes (DictGet, InconsistentReturns, UnusedVariable, NoneComparison). 297 testes. A especificação original de design segue abaixo como registro histórico.

> **Mudança de visão (2026-05-24):** A v6.1 era "Suppression Learning" — silenciar findings por hash. Foi reformulada para **Intent Learning** após o insight de que o tool não precisa adivinhar a intenção do código: ele pode **perguntar**.
>
> **Problema central:** A maior parte dos FPs vem da ferramenta não saber a intenção por trás de uma decisão. Em vez de tentar reconstruir o "PRD do código" via LLM (caro, propenso a alucinação), o tool detecta ambiguidade, faz perguntas direcionadas ao usuário, e usa as respostas como ground truth nos próximos runs. Resposta humana é a única fonte de verdade que não apodrece.
>
> **Diferencial:** Nenhuma ferramenta hoje faz isso. Sonar/DeepSource despejam findings; Copilot/Cursor sugerem fixes sem perguntar contexto. Esta ferramenta assume que não sabe tudo, pergunta, persiste a resposta, vira mais inteligente a cada run. O subproduto é um `INTENT.md` ancorado em linhas reais — o design doc que ninguém escreveu.

### Princípios de UX

| Princípio | O que muda na prática |
|-----------|---------------------|
| **Conversacional, não transacional** | Diálogo com senior reviewer, não formulário pra preencher |
| **Progressive disclosure** | 3 perguntas por run, escolhidas pelo maior impacto/incerteza. Nunca dump de 30 |
| **Contexto na pergunta** | Mostra o código, o gatilho, o que peers fazem em situação similar, o que cada resposta implica |
| **Aprendizado visível** | Resumo no final: "aprendi X, score subiu Y porque Z FPs viraram silenciados-com-razão" |
| **Resposta como contrato** | "Você disse que view X é pública. Agora Y parece similar mas é autenticada — inconsistência?" |
| **Conversa vira documentação** | `INTENT.md` gerado automaticamente — design doc incremental, ancorado em linhas reais |

### Walkthrough de uma sessão

```
$ code-analyze .

Analisando 47 arquivos... ✓

📊 Score 8.2/10 (era 7.4 ontem, +0.8 após suas respostas anteriores)
   • 12 findings com confidence alta
   • 11 findings com confidence baixa — preciso de você

🤔 Posso te fazer 3 perguntas? São as que mais movem o score.

[s/n/depois] > s

╭─ Pergunta 1 de 3 ──────────────────────────────────────╮
│ 📍 apps/brain/views.py:42                              │
│                                                         │
│     @api_view(['POST'])                                │
│     def planner_create_course(request):                │
│         data = request.data                            │
│                                                         │
│ 💭 Sem @login_required.                                │
│    85% das outras views deste módulo têm.              │
│                                                         │
│ ❓ É público por design?                               │
│                                                         │
│   [s] Sim, intencionalmente público                    │
│   [n] Não — é bug, falta autenticação                  │
│   [c] Tem outro mecanismo (token, API key...)          │
│   [?] Não sei agora — pular                            │
╰─────────────────────────────────────────────────────────╯

> n

✓ Registrado. Esse finding agora é HIGH com confidence 1.0.
  Vou flagar novos endpoints sem auth neste módulo automaticamente.

[... pergunta 2, pergunta 3 ...]

╭─ Resumo da sessão ─────────────────────────────────────╮
│ Aprendi 3 coisas novas sobre seu projeto:              │
│   • planner_create_course precisa de auth (bug real)   │
│   • AgentOrchestrator usa side-effect no __init__      │
│   • _internal_helper tem prefixo obsoleto              │
│                                                         │
│ 📁 .analyzer_intent.json (3 decisões adicionadas)      │
│ 📄 INTENT.md atualizado                                │
│                                                         │
│ Score final: 8.4/10                                    │
╰─────────────────────────────────────────────────────────╯
```

### Confidence bands no relatório

| Símbolo | Estado | Significado |
|---|---|---|
| 🔴 | Certo | Confidence ≥ 0.85 — finding direto |
| 🟣 | Pergunta | Confidence < 0.7 — pendente de resposta |
| 🟢 | Confirmado | Você já respondeu — usa sua verdade |
| ⚪ | Silenciado | Você disse "tá ok" — não emite mais |

### Sub-features

| # | Item | Esforço | Notas |
|---|------|---------|-------|
| IL1 | **`confidence: float` em cada `Finding`** — cada detector emite 0.0-1.0 baseado em regras de contexto (ex: DictGet em payload externo = 0.9, em literal local = 0.2) | 1 sprint | Pré-requisito de todo o resto |
| IL2 | **Fila de perguntas** — `detection_runner` separa findings em `certain` (≥0.85), `ask` (<0.7) e `silenced` (resposta prévia). Ordena `ask` por impacto no score | 0.5 sprint | Top-N por run, N configurável |
| IL3 | **UI conversacional** — prompts com contexto, opções, suporte a `c` (resposta livre com nota), `?` (pular), Ctrl+C (sair sem perder progresso) | 1 sprint | Reusa `interactive.py` da v4.4 |
| IL4 | **`.analyzer_intent.json` persistido** — substitui o antigo `.analyzer_silenced.json`. Formato rico: `{ "<hash>": { "answer": "...", "note": "...", "asked_at": "...", "answered_by": "git-user", "applies_to_pattern": "..." } }`. Hash determinístico via `sha256(arquivo + critério + snippet normalizado)` (absorve SL1/SL2) | 1 sprint | Versionar formato pra migração futura |
| IL5 | **`INTENT.md` auto-gerado** — após cada sessão, agrega respostas em markdown legível, agrupado por categoria (Segurança, Padrões intencionais, Naming, etc). Linkando linhas reais | 0.5 sprint | Default commitado (decisão de produto) |
| IL6 | **Inferência derivada** — resposta a finding X gera regra para findings Y similares: mesmo padrão de código, mesmo módulo. "Você disse fire-and-forget aqui — silenciar 4 findings similares neste arquivo?" | 1-2 sprints | Core do "aprendizado" da ferramenta |
| IL7 | **`code-analyze intent` CLI** — `intent list`, `intent show <id>`, `intent reset <id>`, `intent export` (markdown), `intent import` (reusar de outro projeto). Substitui SL3 | 1 sprint | Comando subordinado, não top-level |
| IL8 | **Auto-detection de detectores ruidosos** — se >70% dos findings de um critério foram respondidos como "não é bug" em 10+ runs → emite em modo informacional, não pune score. Legado SL4 | 1 sprint | Telemetria local, sem callback externo |
| IL9 | **`code-analyze health` — relatório de saúde** — mostra "DictGet: 78% respondido como FP nos últimos 30 dias — considere ajuste de regras", "InconsistentReturns: 92% confirmado como bug — detector saudável". Legado SL5 | 0.5 sprint | Útil pra evoluir os detectores baseado em uso real |

### Decisões de produto pendentes

- **INTENT.md vai pro git ou fica gitignored?** Default proposto: **commitado**. Razão: o valor maior é como design doc compartilhado, não como cache pessoal.
- **`.analyzer_intent.json` vai pro git?** Default proposto: **commitado**. Razão: as decisões são do projeto, não do dev. Suprime FPs pra todos no time.
- **Gatilho das perguntas: sempre ou só com `--ask`?** Default proposto: **interativo quando TTY, silencioso em CI**. Em CI, findings com `confidence < 0.7` ficam pendentes e relatório lista "12 perguntas aguardando resposta — rode `code-analyze` localmente".
- **Limite de perguntas por run:** default **3**, configurável via `--ask-limit N`.

### Critério de pronto (status real na entrega)

- [~] `confidence: float` implementado em todos os 50 detectores (IL1) — **PARCIAL: apenas ~9/50 emitem confidence calibrada.** Completar é o item AR2 da v7.0 (ver `sprint_atual.md`).
- [x] Sessão completa funciona em projeto real: pergunta → resposta → persistência → próximo run usa resposta
- [x] `INTENT.md` gerado é legível como design doc
- [x] `code-analyze health` mostra detectores classificados (saudável / ruidoso / em revisão)
- [x] Migração: `.analyzer_silenced.json` (se existir) é convertido pra `.analyzer_intent.json` automaticamente
- [x] Todos os testes existentes continuam passando (297) + testes novos cobrindo IL1-IL9

---

## ✅ v6.0.1 — FP Fixes nos 4 Detectores Ruidosos (Concluída — 2026-05-23)

> **Problema:** Auto-teste em `analyzer/core.py` mostrou 32 findings, dos quais ~50% eram FPs. `InconsistentReturns` derrubava `context.py` para score 1 (CRÍTICO) ignorando type hints declarados. `DictGet` gerava 13 findings num único arquivo, todos em dicts internos com chaves controladas pelo próprio código.

### Fixes implementados

| # | Detector | Mudança | Impacto |
|---|---|---|---|
| FP1 | **`DictGet`** | Lógica invertida. Só emite quando origem do dict é provavelmente externa: `json.loads/load`, `.json()` method, `request.data/POST/GET/FILES/COOKIES/body/form/args/headers`, `os.environ`. Dicts internos (literais, parâmetros, loop vars, `dict()` constructor) não disparam. | 13 → 0 findings em core.py |
| FP2 | **`InconsistentReturns`** | Se função tem return annotation (`-> X`), descarta retornos "unknown" do conflito. O programador já declarou o tipo — retornos onde análise estática não consegue inferir são tratados como compatíveis. | context.py: score 1 CRÍTICO → 7. 1 finding restante (`get_nodes_by_type` sem hint). |
| FP3 | **`UnusedVariable`** | Ignora variáveis em tuple unpacking de `for k, v in ...:`. Nomes descritivos para elementos não usados servem como documentação (`for name, crit in criteria.items()` — name documenta o que está sendo iterado). | 2 → 0 findings em core.py |
| FP4 | **`NoneComparison`** | Ignora `Compare` que estão dentro de um `Assert` ancestral (via `ctx.parents`). `assert x == None` é assertiva explícita. | (preventivo — não havia FP no auto-teste) |

### Extra (mesmo commit)

| # | Item |
|---|---|
| SK1 | `_SKIP_DIRS` em `semantic.py` e `project_context.py` expandido: `+.venv, +env, +virtualenv` (Poetry, uv, pyenv) — antes só `"venv"` era pulado |

### Métricas finais

| Arquivo | Findings antes | Findings depois | Redução |
|---------|---------------|-----------------|---------|
| `analyzer/core.py` | 32 | 15 | **-53%** |
| `analyzer/context.py` | 7 (incl. score 1 CRÍTICO) | 5 (incl. score 7) | qualidade subiu, não só quantidade |

### Pendências derivadas (próxima sprint)

- `get_nodes_by_type` em `context.py` ainda gera 1 finding `InconsistentReturns` — adicionar `-> List[ast.AST]` resolve. **Não é bug do detector, é falta de hint no código.**
- Detectores não-tocados que apareceram no auto-teste (não eram FP): SRP (3), DeepNesting (4), FeatureEnvy (2), GodClass, MissingSuperInit, Coupling, Cohesion, UnusedIterationVar — são **arquiteturais reais** em core.py (911 linhas).
- Avaliar se `env` é genérico demais no skip list (projetos com pasta `env/` legítima perdem análise silenciosa).

**Commits:** `fbd3754` (FP fixes) + `215eb03` (release). Push para origin/main. npm publicado manualmente pelo usuário.

**Testes:** 206/206 (203 base + 3 novos: dict_get_ignores_internal_dict_literals, none_comparison_ignores_assert, unused_variable_ignores_tuple_unpack_in_for).

---

## ✅ v6.0.0 — Performance Overhaul + Pylint Removal (Concluída — 2026-05-22)

> **Problema:** Feedback de uso real (2026-05-22) apontou performance como bloqueador #1 — "2-5 min por arquivo é inaceitável pra pre-commit". Investigação mostrou que (a) 28 detectores re-parseavam `ctx.code` em vez de usar `ctx.tree`; (b) 43 detectores faziam `ast.walk` próprio em vez de cache compartilhado; (c) pylint subprocess custava ~2s/arquivo só em startup, sem detectar nada que ruff não detecte.

### Mudanças

| # | Item | Arquivo |
|---|------|---------|
| P1 | **`AnalysisContext` estendido** — `get_nodes_by_type()` memoizado por tipo, `parents` lazy property | `analyzer/context.py` |
| P2 | **43 detectores migrados** — sem mais `ast.parse(ctx.code)` ou `ast.walk(tree)`. Reuso de `ctx._walk_cache` | `analyzer/detectors/*.py` |
| P3 | **Cache de criteria por hash** — `hashlib.sha256(code + config + version)` em `~/.code-analyzer/criteria_cache/` | `analyzer/criteria_cache.py` (novo) |
| P4 | **Timing por detector** — `time.perf_counter` em `detect_all`, exposto em `result["performance"]["detector_timings"]` | `analyzer/detection_runner.py` |
| P5 | **Pylint removido** — `run_pylint()` excluído. `run_ruff()` agora usa `--select=E,F,W,B,SIM,UP,PL,RUF` (ruleset PL replica todos os checks de pylint em Rust nativo) | `analyzer/core.py` + `analyzer/__init__.py` |
| P6 | **`ThreadPoolExecutor` removido** — não precisa paralelizar duas ferramentas, só ruff | `analyzer/__init__.py` |
| P7 | **Flag `--no-cache` + env `CODE_ANALYZER_NO_CACHE`** — bypass do cache de criteria | `orchestrator.py` + `pipeline.py` |

### Resultados medidos

| Métrica | Antes | Depois | Ganho |
|---|---|---|---|
| Suite de testes (203 testes) | 117s | **14s** | **8.4×** |
| Análise por arquivo (cold) | ~3.0s | **~0.6s** | **5×** |
| Análise por arquivo (warm cache) | — | **~0.5s** | **6×** |

Auto-teste no próprio código (2026-05-22) confirmou ganho real em produção.

---

## ✅ v4.4.0 — Refatoração de Arquitetura (Concluída — 2026-05-22)

> **Problema:** `orchestrator.py` era uma God Function de 907 linhas com 3 responsabilidades misturadas (UI, menu interativo, pipeline). O score agregado recalculava a mesma fórmula em 3 lugares diferentes (UI, gate, relatório).

### Extração de módulos

| # | Item | Arquivo |
|---|------|---------|
| M1 | **`terminal_ui.py`** — 9 funções de UI + `ScoreBundle` dataclass. `_compute_score_bundle()` centraliza o cálculo que era duplicado | Novo |
| M2 | **`interactive.py`** — `interactive_menu` + `_ask_choice`, `_ask_user`, `_get_snippet` | Novo |
| M3 | **`gate.py`** — `check_min_score` isolado | Novo |
| M4 | **`pipeline.py`** — `PipelineContext` dataclass + `_setup`, `_phase1_identification`, `_phase2_proposition`, `_phase3_implementation`, `_finalize` | Novo |
| M5 | **`orchestrator.py`** — reduzido a `build_parser` + `main` (45 linhas) | Modificado |

### Resultados do auto-teste

| Módulo | Score | Linhas | MI |
|--------|-------|--------|-----|
| orchestrator.py | 9.3 A | 45 | 78.2 B |
| gate.py | 9.6 A | 30 | 90.4 A |
| terminal_ui.py | 7.6 B | 210 | 28.0 D |
| pipeline.py | 7.8 B | 390 | 46.7 C |
| interactive.py | 6.8 C | 280 | 9.8 D |

---

## ✅ v4.4.1 — Falsos Positivos (Concluída — 2026-05-22)

> **Problema (auto-teste):** a própria ferramenta penalizava seus módulos de UI com PrintLeak (prints são o propósito deles) e InconsistentReturns em funções com `None` implícito.

| # | Item | Detector | Arquivo |
|---|------|----------|---------|
| FP1 | **PrintLeak ignora módulos de UI** — `terminal_ui`, `interactive`, `cli`, `console`, `tui`, `prompt` no nome do arquivo → skip | PrintLeak | `detectors/print_leak.py` |
| FP2 | **InconsistentReturns não pune None implícito** — função sem return + return explícito é padrão Python normal | InconsistentReturns | `detectors/inconsistent_returns.py` |
| FP3 | **interactive.py: do_refactor extraído** — `_select_rules()` + `_apply_refactor()` reduziram `do_refactor` de 100+ para 30 linhas | — | `interactive.py` |
| FP4 | **DictGet e UnusedVariable** — severidade BAIXA, mantidos como informativos | — | — |

---

## ✅ v5.0.0 — Test Pain Core (Concluída — 2026-05-22)

> **Visão:** todo sinal de análise do backlog anterior foi gerado por máquina — AST, métricas, heurísticas. Este é o único sinal gerado por humano que a ferramenta pode ler: o custo que o dev pagou para testar o código. Arquitetura ruim torna testes difíceis de escrever. Medir essa dificuldade é medir acoplamento e coesão com uma precisão que análise estática nunca alcança sozinha.

### Métricas implementadas

| # | Item | O que faz | Score |
|---|------|-----------|-------|
| TP1 | **Cobertura real** | Conta funções/métodos testados vs total no source file | 0-100 |
| TP2 | **Mock density** | `patch`/`MagicMock` por função de teste — revela acoplamento oculto | 0-100 |
| TP3 | **Complexidade dos testes** | Complexidade ciclomática média das funções de teste | 0-100 |
| TP4 | **Isolamento** | Detecta imports de DB/network nos testes (django, requests, etc.) | 30/60/100 |

**Aggregate:** `TP1*0.30 + TP2*0.30 + TP3*0.20 + TP4*0.20`

### Integração no production_risk_score

| Componente | Antes | Depois |
|-----------|-------|--------|
| Cobertura | 25pts | **20pts** |
| Complexidade | 25pts | **20pts** |
| Coupling | 25pts | **20pts** |
| ALTA criteria | 25pts | **20pts** |
| **Test Pain** | — | **20pts** |

### Arquivos

| Arquivo | O que mudou |
|---------|-------------|
| `analyzer/test_pain.py` | **Novo** — TP1-TP4 + aggregate |
| `pipeline.py` | Chama `analyze_test_pain()` após `production_risk_score()` |
| `analyzer/scoring.py` | 5º componente em `production_risk_score()` |
| `report_generator.py` | Nova seção `_section_test_pain()` com tabela de sub-scores |
| `terminal_ui.py` | `ScoreBundle` ganha `test_pain_aggregate` |
| `tests/test_skill_core.py` | +10 testes (`TestTestPainMetrics`) |

### Pendente (v5.1)

| # | Item | Esforço |
|---|------|---------|
| TP5 | Correlação mock ↔ acoplamento real | G |
| TP6 | Módulos impossíveis de testar | M |
| TP7 | Grafo de dependências via testes | G |
| TP8 | Sugestão de refatoração por dor | G |
| TP9 | Priorização combinada | M |
| TP10 | Evolução do test pain no histórico | M |

**Testes:** 203 (193 base + 10 novos).

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

## ✅ v4.3.1 — P0 Fixes (Concluída — 2026-05-22)

> **Problema:** relatório externo (AAB-2026) identificou dois bugs P0 na v4.3.0: (1) LSP muito agressivo — `raise NotImplementedError` é o padrão Python para interfaces/ABCs, não violação LSP; (2) DesignPatterns reduzindo score — findings de padrões reconhecidos são informativos (elogios ao dev), não penalidades.

| # | Item | Arquivo | Status |
|---|------|---------|--------|
| P0-1 | ~~**LSP: remover check NotImplementedError** — manter apenas heurística `set_X` side-effect~~ | `detectors/lsp.py` | ✅ |
| P0-2 | ~~**DesignPatterns: `penalty_per_finding = 0`** — findings informativos não reduzem score de qualidade~~ | `detectors/design_patterns.py` | ✅ |

**Resultado:** AAB-2026 subiu de 96/100 → **100/100**. A5 (código limpo) passou de penalizado → 10.0/10.

---

## ✅ v4.3.0 — AAB-2026 (Concluída — 2026-05-22)

> **Problema:** benchmark AAB-2026 identificou gaps em detecção de FeatureEnvy, ShotgunSurgery e LSP; falsos positivos em UnusedVariable e InconsistentReturns; ausência de gate de qualidade (pre-commit) e configuração inteligente de projeto.

### Novos detectores

| # | Item | Esforço | Arquivo-alvo |
|---|------|---------|--------------|
| FE1 | ~~**FeatureEnvy** — método acessa `self.X.Y` (cadeia estrangeira) mais que `self.X` direto~~ | M | `detectors/feature_envy.py` |
| SS1 | ~~**ShotgunSurgery** — `ClassName.CONSTANTE` referenciada em 3+ classes distintas~~ | M | `detectors/shotgun_surgery.py` |
| LSP1 | ~~**LSP** — `set_X` atribui atributos extras além de `self.X` (Square/Rectangle pattern)~~ | M | `detectors/lsp.py` |

### Fixes de falsos positivos

| # | Item | Arquivo |
|---|------|---------|
| UV1 | ~~**UnusedVariable**: excluir atributos de classe + constantes ALL_CAPS~~ | `detectors/unused_variable.py` |
| IR1 | ~~**InconsistentReturns**: ignorar `return None` dentro de ExceptHandler~~ | `detectors/inconsistent_returns.py` |
| MA1 | ~~**MassAssignment**: detectar `fields='__all__'` em qualquer Meta class~~ | `detectors/mass_assignment.py` |
| SD2 | ~~**StringDispatch**: extensão para dispatch via `param.attr == "literal"`~~ | `detectors/string_dispatch.py` |

### Infraestrutura

| # | Item | Arquivo |
|---|------|---------|
| PC1 | ~~**Pre-commit gate** `--min-score N` + `.pre-commit-hooks.yaml`~~ | `orchestrator.py`, `.pre-commit-hooks.yaml` |
| IN1 | ~~**`code-analyze init`** com detecção Django/FastAPI/Flask + `.pre-commit-config.yaml`~~ | `cli.py` |

**Testes:** 193 (166 base + 27 novos). Score AAB-2026: 96/100 → 100/100 após v4.3.1.

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

## ✅ v5.0.0 — Test Pain como Sinal de Arquitetura (Concluída — 2026-05-22)

> **Visão:** todo sinal de análise do backlog anterior foi gerado por máquina — AST, métricas, heurísticas. Este é o único sinal gerado por humano que a ferramenta pode ler: o custo que o dev pagou para testar o código. Arquitetura ruim torna testes difíceis de escrever. Medir essa dificuldade é medir acoplamento e coesão com uma precisão que análise estática nunca alcança sozinha.

---

### 5.1 — Métricas de Dor de Teste (✅ Concluído)

| # | Item | Esforço | Arquivo-alvo | Status |
|---|------|---------|--------------|--------|
| TP1 | ~~**Mock density** — contar `patch`/`MagicMock` por função de teste~~ | M | `analyzer/test_pain.py` | ✅ |
| TP2 | ~~**Cobertura real** — funções testadas vs total no source file~~ | M | `analyzer/test_pain.py` | ✅ |
| TP3 | ~~**Complexidade dos testes** — complexidade ciclomática média das funções de teste~~ | M | `analyzer/test_pain.py` | ✅ |
| TP4 | ~~**Isolamento** — detectar imports de DB/network nos testes~~ | M | `analyzer/test_pain.py` | ✅ |

### 5.2 — Cruzamento com Análise Estrutural (⏳ Pendente — v5.1)

| # | Item | Esforço | Status |
|---|------|---------|--------|
| TP5 | Correlação mock ↔ acoplamento real | G | ⏳ |
| TP6 | Módulos impossíveis de testar | M | ⏳ |
| TP7 | Grafo de dependências via testes | G | ⏳ |

### 5.3 — Sugestões Orientadas por Dor (⏳ Pendente — v5.1)

| # | Item | Esforço | Status |
|---|------|---------|--------|
| TP8 | "Refatore para tornar testável" | G | ⏳ |
| TP9 | Priorização por dor humana | M | ⏳ |
| TP10 | Evolução do test pain no histórico | M | ⏳ |

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
| N23 | Test pain como sinal de arquitetura — o único sinal gerado por humano que a ferramenta pode ler | v5.0 ✅ — TP1/TP4 |
| N24 | Dependências implícitas reveladas pelos testes — grafo real vs. grafo AST | v5.1 — TP7 |
| N25 | Priorização por dor humana — score estrutural + test pain + fan-in | v5.1 — TP9 |
| N26 | PR pronto completo — patch + teste de equivalência + commit message em uma operação | v4.5 — EQ4/PL6 |
| N27 | Feature Envy detectado via AST — método que inveja mais o vizinho do que si mesmo | v4.3 ✅ — FeatureEnvy |
| N28 | Shotgun Surgery detectado — constante que ripocheta por 3+ classes | v4.3 ✅ — ShotgunSurgery |
| N29 | LSP detectado estaticamente — `set_X` com efeito colateral quebra contrato do pai | v4.3 ✅ — LSP |
| N30 | Pre-commit gate — `--min-score N` bloqueia commit abaixo do mínimo | v4.3 ✅ — `--min-score` |
| N31 | Smart init — detecta tipo de projeto e gera config + pre-commit em uma tacada | v4.3 ✅ — `code-analyze init` |
| N32 | AAB-2026 100/100 — benchmark independente, todas as 7 categorias aprovadas | v4.3.1 ✅ |
| N33 | Arquitetura interna limpa — orquestrador 907→45 linhas, 5 módulos com SRP | v4.4 ✅ |
| N34 | Test Pain — mock density, cobertura real, complexidade de teste, isolamento | v5.0 ✅ |

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
