"""Streamlit dashboard — connected to the Criptotrade API.

Replaces the static ``"--"`` placeholder. The three KPIs (Sharpe, Win Rate, Max
Drawdown) now come from ``GET /v1/metrics`` (computed from the ledger). Every
panel degrades honestly: it shows ``Carregando…``, ``Sem dados`` or
``API offline`` — never an ambiguous ``--`` (UX finding P0).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "")
REFRESH_SECONDS = int(os.getenv("REFRESH_INTERVAL", "5"))

st.set_page_config(page_title="Crypto AI Trading Platform", layout="wide")


def _headers() -> Dict[str, str]:
    return {"X-API-Key": API_KEY} if API_KEY else {}


def _get(path: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """GET ``path`` from the API. Returns ``(json, error)`` — never raises."""
    try:
        resp = httpx.get(f"{API_URL}{path}", headers=_headers(), timeout=5.0)
        resp.raise_for_status()
        return resp.json(), None
    except httpx.HTTPStatusError as exc:
        return None, f"HTTP {exc.response.status_code}"
    except httpx.RequestError:
        return None, "API offline"


def _send(method: str, path: str, json: Dict[str, Any]) -> tuple[bool, str]:
    """POST/PATCH helper. Returns ``(ok, message)`` — never raises."""
    try:
        resp = httpx.request(method, f"{API_URL}{path}", headers=_headers(), json=json, timeout=5.0)
        if resp.status_code < 300:
            return True, "ok"
        body = resp.json()
        return False, body.get("message", f"HTTP {resp.status_code}")
    except httpx.RequestError:
        return False, "API offline"


def _fmt_pct(value: Optional[float]) -> str:
    return f"{value * 100:.1f}%" if value is not None else "Sem dados"


def _fmt_ratio(value: Optional[float]) -> str:
    return f"{value:.2f}" if value is not None else "Sem dados"


# ── Auto-refresh (optional dependency; falls back to a manual button) ──────────
def _auto_refresh() -> None:
    try:
        from streamlit_autorefresh import st_autorefresh

        st_autorefresh(interval=REFRESH_SECONDS * 1000, key="auto")
    except Exception:
        if st.button("🔄 Atualizar"):
            st.rerun()


st.title("📊 Crypto AI Trading Platform")
_auto_refresh()

# ── System status bar ─────────────────────────────────────────────────────────
health, health_err = _get("/health")
hitl, _ = _get("/v1/hitl/config")
status_col, autonomy_col = st.columns([2, 3])
with status_col:
    if health_err:
        st.error(f"🔴 Sistema: {health_err}")
    else:
        st.success("🟢 Sistema online")
with autonomy_col:
    if hitl:
        cfg = hitl["data"]
        st.info(
            f"⚡ Autonomia: Nível {cfg['current_level']}/{cfg['max_level']} — "
            f"{cfg['level_description']}  |  Pendentes: {cfg['pending_orders_count']}"
        )
    else:
        st.info("⚡ Autonomia: Carregando…")

st.divider()

# ── KPIs ──────────────────────────────────────────────────────────────────────
metrics, metrics_err = _get("/v1/metrics?period=7d")
c1, c2, c3 = st.columns(3)
if metrics_err:
    for col, label in zip((c1, c2, c3), ("Sharpe Ratio", "Win Rate", "Max Drawdown")):
        col.metric(label=label, value="API offline")
elif metrics and not metrics["data"]["has_data"]:
    for col, label in zip((c1, c2, c3), ("Sharpe Ratio", "Win Rate", "Max Drawdown")):
        col.metric(label=label, value="Sem dados")
    st.caption("Nenhum trade fechado ainda — os KPIs aparecem quando houver histórico no ledger.")
elif metrics:
    d = metrics["data"]
    c1.metric("Sharpe Ratio", _fmt_ratio(d["sharpe_ratio"]))
    c2.metric("Win Rate", _fmt_pct(d["win_rate"]))
    c3.metric("Max Drawdown", _fmt_pct(d["max_drawdown"]))
    st.caption(
        f"Portfólio: ${d['portfolio_value_usdt']:,.2f}  ·  "
        f"P&L (7d): ${d['pnl_period_usdt']:,.2f}  ·  "
        f"Trades: {d['total_trades']}  ·  Posições abertas: {d['open_positions']}"
    )

st.divider()

# ── Autonomy control (sidebar) ────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Autonomia (HITL)")
    if hitl:
        cfg = hitl["data"]
        new_level = st.slider(
            "Nível de autonomia", min_value=cfg["min_level"], max_value=cfg["max_level"],
            value=cfg["current_level"],
        )
        st.caption(next(
            (lvl["description"] for lvl in cfg["levels"] if lvl["level"] == new_level), ""
        ))
        if new_level != cfg["current_level"]:
            reason = st.text_input("Motivo da mudança", value="Ajuste pelo operador")
            if st.button("Aplicar nível"):
                ok, msg = _send(
                    "PATCH", "/v1/hitl/config",
                    {"level": new_level, "reason": reason, "operator": "dashboard"},
                )
                (st.success if ok else st.error)(msg if not ok else "Nível atualizado")
                if ok:
                    st.rerun()
    else:
        st.caption("Config HITL indisponível.")

# ── HITL console — pending orders ─────────────────────────────────────────────
st.subheader("⚡ Console HITL — Ordens pendentes")
pending, pending_err = _get("/v1/orders?status=pending&limit=200")
if pending_err:
    st.warning(f"Não foi possível carregar ordens ({pending_err}).")
elif pending and pending["data"]:
    for o in pending["data"]:
        with st.container(border=True):
            st.markdown(
                f"**{o['side'].upper()} {o['pair']}** · Qtd {o['quantity']} · "
                f"Notional ${o['notional']:,.2f} · Confiança {o['confidence'] * 100:.0f}%"
            )
            st.caption(f"🧠 {o['reason']}")
            note = st.text_input("Nota (obrigatória ao rejeitar)", key=f"note_{o['id']}")
            ca, cr = st.columns(2)
            if ca.button("✅ Aprovar", key=f"ap_{o['id']}"):
                ok, msg = _send(
                    "PATCH", f"/v1/orders/{o['id']}/status",
                    {"decision": "approve", "operator": "dashboard"},
                )
                (st.error if not ok else st.success)(msg if not ok else "Aprovada")
                if ok:
                    st.rerun()
            if cr.button("❌ Rejeitar", key=f"rj_{o['id']}"):
                if not note.strip():
                    st.warning("Informe a nota antes de rejeitar.")
                else:
                    ok, msg = _send(
                        "PATCH", f"/v1/orders/{o['id']}/status",
                        {"decision": "reject", "operator_note": note, "operator": "dashboard"},
                    )
                    (st.error if not ok else st.success)(msg if not ok else "Rejeitada")
                    if ok:
                        st.rerun()
else:
    st.caption("Nenhuma ordem pendente de aprovação.")

st.divider()

# ── Agents panel (real cycles from the running loop) ──────────────────────────
st.subheader("🤖 Agentes")
agents, agents_err = _get("/v1/agents")
_AGENT_ICON = {"idle": "🟢", "active": "🟢", "error": "🔴", "not_implemented": "⚪"}
_DOMAIN_LABEL = {
    "trading": "💹 trading",
    "engineering": "🔧 engineering",
    "orchestration": "🎯 orchestration",
    "security": "🛡️ security",
}

if agents_err:
    st.warning(f"Não foi possível carregar agentes ({agents_err}).")
elif agents and agents["data"]:
    # Fetch full config (params) for each agent upfront to avoid N+1 inside expanders.
    configs: dict = {}
    for a in agents["data"]:
        cfg, _ = _get(f"/v1/agents/{a['id']}/config")
        if cfg and cfg.get("data"):
            configs[a["id"]] = cfg["data"]

    # Summary dataframe — one row per agent, all visible including stubs.
    st.dataframe(
        [
            {
                "Agente": a["id"],
                "Descrição": a["description"],
                "Domínio": _DOMAIN_LABEL.get(a["domain"], a["domain"]),
                "Status": f"{_AGENT_ICON.get(a['status'], '⬜')} {a['status']}",
                "Implementado": "✅" if a["implemented"] else "❌ stub",
                "Ciclos (hoje)": a["cycles"],
                "Última ação": a["last_action_at"] or "—",
            }
            for a in agents["data"]
        ],
        hide_index=True,
        use_container_width=True,
    )

    # Per-agent detail expanders.
    for a in agents["data"]:
        icon = _AGENT_ICON.get(a["status"], "⬜")
        stub_badge = " · [stub]" if not a["implemented"] else ""
        with st.expander(f"{icon} **{a['id']}**{stub_badge} — {a['description']}"):
            if not a["implemented"]:
                st.warning(
                    "Agente não implementado (stub). "
                    "Chamadas à API retornam HTTP 501."
                )

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Domínio**")
                st.write(_DOMAIN_LABEL.get(a["domain"], a["domain"]))
                st.markdown("**Status**")
                st.write(f"{icon} {a['status']}")
                st.markdown("**Ciclos hoje**")
                st.write(a["cycles"])
                if a["last_action_at"]:
                    st.markdown("**Última ação**")
                    st.write(a["last_action_at"])

            cfg_data = configs.get(a["id"], {})
            params = cfg_data.get("params", {})
            with col2:
                if params:
                    st.markdown("**Parâmetros configuráveis**")
                    for k, v in params.items():
                        label = k.replace("_", " ").title()
                        st.write(f"- **{label}:** `{v}`")
                else:
                    st.caption("Nenhum parâmetro exposto.")

            st.caption(
                "Ações: em breve — ativar/desativar, reiniciar, testar execução"
            )
            st.button(
                "Reiniciar",
                key=f"restart_{a['id']}",
                disabled=True,
                help="Em breve",
            )
            st.button(
                "Testar",
                key=f"test_{a['id']}",
                disabled=True,
                help="Em breve",
            )

    total_cycles = sum(a["cycles"] for a in agents["data"])
    st.caption(
        f"Ciclos hoje (total): {total_cycles} · "
        "0 em todos = o loop (orchestrator) não está rodando."
    )
else:
    st.caption("Sem dados de agentes.")

st.divider()

# ── Recent orders (full lifecycle) ────────────────────────────────────────────
st.subheader("📋 Ordens recentes")
orders, orders_err = _get("/v1/orders?limit=50")
_ORDER_ICON = {
    "pending": "⏳", "approved": "✅", "filled": "💰", "rejected": "❌", "cancelled": "🚫",
}
if orders_err:
    st.warning(f"Não foi possível carregar ordens ({orders_err}).")
elif orders and orders["data"]:
    st.dataframe(
        [
            {
                "ID": o["id"],
                "Par": o["pair"],
                "Lado": o["side"].upper(),
                "Qtd": o["quantity"],
                "Notional": f"${o['notional']:,.2f}",
                "Status": f"{_ORDER_ICON.get(o['status'], '⬜')} {o['status']}",
                "Operador": o["operator_id"] or "—",
                "Criada": o["created_at"],
            }
            for o in orders["data"][:20]
        ],
        hide_index=True,
        use_container_width=True,
    )
else:
    st.caption("Nenhuma ordem registrada ainda.")

st.divider()

# ── Recent alerts ─────────────────────────────────────────────────────────────
st.subheader("🛡️ Alertas recentes")
alerts, alerts_err = _get("/v1/alerts/history?limit=10")
_ICON = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
if alerts_err:
    st.warning(f"Não foi possível carregar alertas ({alerts_err}).")
elif alerts and alerts["data"]:
    for a in alerts["data"]:
        icon = _ICON.get(a["severity"], "⬜")
        st.write(f"{icon} `{a['occurred_at']}` — **{a['type']}** — {a['message']}")
else:
    st.caption("Sem alertas registrados.")
