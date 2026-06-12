# Integração: Process Mining via `/v1/process/events`

`GET /v1/process/events` expõe o event log XES das transições de ordens. Cada evento
representa uma mudança de estado de uma ordem (`pending → approved → filled`, etc.),
seguindo a semântica do padrão XES (Extensible Event Stream) compatível com PM4Py.

## Autenticação

Se `API_KEYS` estiver configurado no ambiente, incluir o header em toda requisição:

```
X-API-Key: <sua-chave>
```

Se `API_KEYS` estiver vazio (default em dev), a API é aberta.

## Parâmetros

| Parâmetro | Tipo    | Padrão | Descrição                              |
|-----------|---------|--------|----------------------------------------|
| `case_id` | string  | —      | Filtra por uma ordem específica (order ID) |
| `limit`   | integer | 200    | Máximo de eventos retornados (1–1000)  |

## Schema do evento

```json
{
  "case_id":   "ord_abc123",
  "activity":  "order:filled",
  "actor":     "execution_agent",
  "timestamp": "2026-06-12T14:30:00Z",
  "attributes": {
    "pair":   "BTC/USDT",
    "side":   "buy",
    "price":  50000.0,
    "pnl":    null
  }
}
```

### Semântica `case_id`

`case_id` = order ID gerado pelo sistema (ex: `ord_<uuid8>`). Todos os eventos de uma
mesma ordem compartilham o mesmo `case_id`, equivalente ao `case:concept:name` no
padrão XES. Um "caso" corresponde ao lifecycle completo de uma ordem.

### Atividades (`activity`) comuns

| `activity`          | Descrição                                           |
|---------------------|-----------------------------------------------------|
| `order:submitted`   | Ordem enviada para aprovação HITL                   |
| `order:approved`    | Operador aprovou manualmente                        |
| `order:auto_filled` | Auto-aprovada dentro do threshold de autonomia      |
| `order:filled`      | Executada pelo loop de orquestração                 |
| `order:rejected`    | Bloqueada pelos guardrails de risco                 |
| `order:cancelled`   | Timeout de decisão expirou (`decision_timeout`)     |

## Exemplo: importar no PM4Py

```python
import requests
import pandas as pd
import pm4py

# 1. Buscar todos os eventos
events = requests.get(
    "http://localhost:8000/v1/process/events",
    headers={"X-API-Key": "sua-chave"},
    params={"limit": 1000},
).json()["data"]

# 2. Montar DataFrame compatível com PM4Py
df = pd.DataFrame([{
    "case:concept:name": e["case_id"],
    "concept:name":      e["activity"],
    "org:resource":      e["actor"],
    "time:timestamp":    pd.Timestamp(e["timestamp"]),
} for e in events])
df["time:timestamp"] = df["time:timestamp"].dt.tz_localize("UTC")

# 3. Converter e descobrir processo (Inductive Miner)
log = pm4py.convert_to_event_log(df)
net, im, fm = pm4py.discover_petri_net_inductive(log)
pm4py.view_petri_net(net, im, fm)
```

Para filtrar por uma única ordem: `?case_id=ord_abc123`.

## Referências

- [ADR-003: Estratégia de Persistência](../adr/003-persistence-sqlite-wal.md)
- Especificação XES: [xes-standard.org](http://www.xes-standard.org/)
- [PM4Py documentação](https://pm4py.fit.fraunhofer.de/)
