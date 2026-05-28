# Sprint Atual — v7.0 Agent-Ready Output (Em andamento — 2026-05-24)

## Nome

Caminho das Pedras — output que agente de codificação consome

## Meta

Transformar findings em ActionRecords estruturados (JSON) com confidence, provenance, verify steps — output primário para `--agent`.

## Escopo

| # | Item | Status |
|---|------|--------|
| AR1 | ActionRecord dataclass + build_action_records() | ✅ 2026-05-24 |
| AR3 | --agent-mode produz JSON com ActionRecords | ✅ 2026-05-24 |
| AR5 | Diff generation para 4 padrões mecânicos | ⬜ próximo |
| AR2 | Confidence por detector (8 detectores) | ⬜ |

## Critério de pronto parcial

- 297/297 testes passando
- `code-analyze check core.py --agent` produz JSON com action records

## ⚠️ Decisão aberta — contrato da flag `--agent` (Trilha 2)

A v6.3.0 lançou `--agent` = **Markdown** (`generate_agent_output()`). O trabalho WIP (commit `56d52a1`) trocou `--agent` para **JSON** (`generate_agent_json()`) — quebrando o contrato recém-lançado, e **sem teste guardando** nenhum dos dois formatos.

**Recomendação:** preservar `--agent` = Markdown e expor o JSON novo por flag separada (`--agent-json` ou `--format json`); adicionar um teste para cada formato. Resolver no início da Trilha 2, junto com AR2 (confidence real).

## ⚠️ Fundação oca — AR2 (confidence real)

`action_plan.py` lê `finding.get("confidence", 1.0)`, mas só ~9/50 detectores emitem confidence calibrada. Logo `confidence`, `risk_level` e `safe_auto_apply` no JSON são ficção para ~80% dos findings. AR4 (enrichment) também está stubbed: `blast_radius` sempre `[]`, `_find_callers` lê chave inexistente. **AR2 é pré-requisito real de AR1/AR3/AR4 — fazer antes de avançar a v7.0.**

## Próximo (Trilha 2): AR2 (confidence) → contrato `--agent` → AR5 (Diff 4 padrões)

1. `dict[k]` → `dict.get(k)`
2. `== None` → `is None`  
3. `range(len())` → `enumerate()`
4. `except:` → `except Exception:`
