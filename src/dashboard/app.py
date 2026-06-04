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
