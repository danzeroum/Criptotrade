"""/v1/exchanges + /v1/api-keys — A5: exchange connections & platform keys.

Everything sits behind ``manage_keys`` (admin). Hard guardrail: the exchange
SECRET never appears in any response, log line or ledger payload — the API key
shows masked, test errors pass through :func:`redact`, and the suite carries a
negative leak test. Trade scope requires the literal typed confirmation
("TRADE") validated HERE, not just in the UI.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException, Path

from src.api.authn import Principal, require_perm
from src.api.deps import get_connection_store, get_ledger, get_platform_key_store
from src.api.schemas import (
    APIResponse, ConnectionCreateIn, ConnectionOut, ConnectionRotateIn,
    PlatformKeyCreatedOut, PlatformKeyCreateIn, PlatformKeyOut,
)
from src.core.ledger import TradingLedger
from src.exchanges.store import ConnectionStore, PlatformKeyStore, mask_value
from src.exchanges.tester import test_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exchanges", tags=["exchanges"])
keys_router = APIRouter(prefix="/api-keys", tags=["exchanges"])

_TRADE_CONFIRMATION = "TRADE"


def _known_exchange(exchange_id: str) -> bool:
    try:
        import ccxt  # lazy — optional in the lean CI

        return exchange_id in ccxt.exchanges
    except ImportError:  # pragma: no cover - lean CI has no ccxt
        return True


def _conn_out(store: ConnectionStore, row: Dict[str, Any]) -> ConnectionOut:
    config = store.config(row)
    detail = None
    if row.get("last_test_detail"):
        import json

        try:
            detail = json.loads(row["last_test_detail"])
        except ValueError:
            detail = None
    return ConnectionOut(
        id=row["id"], exchange_id=row["exchange_id"], label=row["label"],
        scope=row["scope"], testnet=bool(row["testnet"]),
        is_active=bool(row["is_active"]),
        api_key_masked=mask_value(str(config.get("api_key") or "")) or "—",
        created_at=row.get("created_at"), last_test_at=row.get("last_test_at"),
        last_test_ok=None if row.get("last_test_ok") is None else bool(row["last_test_ok"]),
        last_test_detail=detail, revoked=row.get("revoked_at") is not None,
    )


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail={
        "error": f"{what}_not_found", "message": "Recurso não encontrado.",
        "docs": "/v1/docs",
    })


def _audit(ledger: TradingLedger, event: str, principal: Principal,
           data: Dict[str, Any]) -> None:
    # Payloads are ALWAYS masked before they reach the ledger.
    ledger.log_decision(event, {"actor": principal.actor, **data})


# ------------------------------------------------------------------ connections
@router.get("/connections", response_model=APIResponse[List[ConnectionOut]],
            summary="Conexões de exchange (key mascarada; secret nunca retorna)")
async def list_connections(
    store: ConnectionStore = Depends(get_connection_store),
    principal: Principal = Depends(require_perm("manage_keys")),
) -> APIResponse[List[ConnectionOut]]:
    return APIResponse(data=[_conn_out(store, r) for r in store.list()])


@router.post("/connect", response_model=APIResponse[ConnectionOut], status_code=201,
             summary="Adiciona credencial de exchange (trade exige confirmação digitada)")
async def create_connection(
    body: ConnectionCreateIn = Body(...),
    store: ConnectionStore = Depends(get_connection_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("manage_keys")),
) -> APIResponse[ConnectionOut]:
    if not _known_exchange(body.exchange_id):
        raise HTTPException(status_code=422, detail={
            "error": "validation_error",
            "message": f"Exchange '{body.exchange_id}' não é um id ccxt conhecido.",
            "field": "exchange_id", "docs": "/v1/docs",
        })
    if body.scope == "trade" and body.confirm != _TRADE_CONFIRMATION:
        raise HTTPException(status_code=422, detail={
            "error": "confirmation_required",
            "message": "Escopo 'trade' permite ENVIAR ORDENS REAIS com seu dinheiro. "
                       f"Digite \"{_TRADE_CONFIRMATION}\" no campo confirm para prosseguir.",
            "field": "confirm", "docs": "/v1/docs",
        })
    row = store.create(body.exchange_id, body.label, body.api_key, body.api_secret,
                       scope=body.scope, testnet=body.testnet)
    _audit(ledger, "connection_added", principal, {
        "label": body.label, "exchange": body.exchange_id,
        "connection_scope": body.scope, "testnet": body.testnet,
        "api_key": mask_value(body.api_key),
    })
    return APIResponse(data=_conn_out(store, row))


@router.post("/{conn_id}/test", response_model=APIResponse[dict],
             summary="Testa a conexão (read-only real — NUNCA envia ordem)")
async def test_connection_route(
    conn_id: str = Path(...),
    store: ConnectionStore = Depends(get_connection_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("manage_keys")),
) -> APIResponse[dict]:
    row = store.get(conn_id)
    if row is None or row["revoked_at"]:
        raise _not_found("connection")
    result = await test_connection(row["exchange_id"], store.config(row),
                                   bool(row["testnet"]))
    detail = {k: v for k, v in result.items() if k != "ok"}
    store.record_test(conn_id, result["ok"], detail)
    _audit(ledger, "connection_tested", principal, {
        "label": row["label"], "exchange": row["exchange_id"],
        "success": result["ok"], **detail,
    })
    return APIResponse(data=result)


@router.post("/{conn_id}/rotate", response_model=APIResponse[ConnectionOut],
             summary="Rotaciona o secret (zera o teste — live não sobe até re-testar)")
async def rotate_connection(
    conn_id: str = Path(...),
    body: ConnectionRotateIn = Body(...),
    store: ConnectionStore = Depends(get_connection_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("manage_keys")),
) -> APIResponse[ConnectionOut]:
    row = store.rotate(conn_id, api_secret=body.api_secret, api_key=body.api_key)
    if row is None:
        raise _not_found("connection")
    _audit(ledger, "connection_rotated", principal, {
        "label": row["label"], "exchange": row["exchange_id"],
        "api_key": mask_value(str(store.config(row).get("api_key") or "")),
    })
    return APIResponse(data=_conn_out(store, row))


@router.patch("/{conn_id}/activate", response_model=APIResponse[ConnectionOut],
              summary="Torna esta a conexão ativa (única)")
async def activate_connection(
    conn_id: str = Path(...),
    store: ConnectionStore = Depends(get_connection_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("manage_keys")),
) -> APIResponse[ConnectionOut]:
    if not store.activate(conn_id):
        raise _not_found("connection")
    row = store.get(conn_id)
    _audit(ledger, "connection_activated", principal, {
        "label": row["label"], "exchange": row["exchange_id"],
        "connection_scope": row["scope"], "testnet": bool(row["testnet"]),
    })
    return APIResponse(data=_conn_out(store, row))


@router.delete("/{conn_id}", response_model=APIResponse[dict],
               summary="Revoga uma conexão")
async def revoke_connection(
    conn_id: str = Path(...),
    store: ConnectionStore = Depends(get_connection_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("manage_keys")),
) -> APIResponse[dict]:
    row = store.get(conn_id)
    if row is None or not store.revoke(conn_id):
        raise _not_found("connection")
    _audit(ledger, "connection_revoked", principal, {
        "label": row["label"], "exchange": row["exchange_id"],
    })
    return APIResponse(data={"revoked": True})


# Egress IP (nota 4 do plano): shown so the owner locks the exchange key to it.
_egress_cache: Dict[str, Any] = {"ip": None, "at": 0.0}
_EGRESS_TTL_S = 3600.0


@router.get("/egress-ip", response_model=APIResponse[dict],
            summary="IP de egresso da VPS (trave a chave neste IP na exchange)")
async def egress_ip(
    principal: Principal = Depends(require_perm("manage_keys")),
) -> APIResponse[dict]:
    now = time.monotonic()
    if _egress_cache["ip"] and now - _egress_cache["at"] < _EGRESS_TTL_S:
        return APIResponse(data={"ip": _egress_cache["ip"], "cached": True})
    try:
        import httpx

        r = httpx.get("https://api.ipify.org?format=json", timeout=5.0)
        r.raise_for_status()
        ip = r.json().get("ip")
        _egress_cache.update(ip=ip, at=now)
        return APIResponse(data={"ip": ip, "cached": False})
    except Exception as exc:  # noqa: BLE001 - offline VPS still gets guidance
        return APIResponse(data={
            "ip": None,
            "error": f"Não foi possível detectar ({str(exc)[:120]}). "
                     "Descubra com: curl https://api.ipify.org na VPS.",
        })


# ------------------------------------------------------------- platform keys
def _key_out(row: Dict[str, Any]) -> PlatformKeyOut:
    return PlatformKeyOut(
        id=row["id"], label=row["label"], key_prefix=row["key_prefix"],
        scope=row["scope"], created_by=row.get("created_by"),
        created_at=row.get("created_at"), last_used_at=row.get("last_used_at"),
        revoked=row.get("revoked_at") is not None,
    )


@keys_router.get("", response_model=APIResponse[List[PlatformKeyOut]],
                 summary="Chaves da plataforma (prefixo p/ identificação + último uso)")
async def list_platform_keys(
    store: PlatformKeyStore = Depends(get_platform_key_store),
    principal: Principal = Depends(require_perm("manage_keys")),
) -> APIResponse[List[PlatformKeyOut]]:
    return APIResponse(data=[_key_out(r) for r in store.list()])


@keys_router.post("", response_model=APIResponse[PlatformKeyCreatedOut],
                  status_code=201,
                  summary="Cria chave escopada (exibida COMPLETA uma única vez)")
async def create_platform_key(
    body: PlatformKeyCreateIn = Body(...),
    store: PlatformKeyStore = Depends(get_platform_key_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("manage_keys")),
) -> APIResponse[PlatformKeyCreatedOut]:
    row, token = store.create(body.label, body.scope, principal.actor)
    _audit(ledger, "apikey_created", principal, {
        "label": body.label, "key_scope": body.scope,
        "key_prefix": row["key_prefix"],
    })
    return APIResponse(data=PlatformKeyCreatedOut(**_key_out(row).model_dump(),
                                                  key=token))


@keys_router.delete("/{key_id}", response_model=APIResponse[dict],
                    summary="Revoga uma chave da plataforma")
async def revoke_platform_key(
    key_id: str = Path(...),
    store: PlatformKeyStore = Depends(get_platform_key_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("manage_keys")),
) -> APIResponse[dict]:
    row = store.get(key_id)
    if row is None or not store.revoke(key_id):
        raise _not_found("apikey")
    _audit(ledger, "apikey_revoked", principal, {
        "label": row["label"], "key_prefix": row["key_prefix"],
    })
    return APIResponse(data={"revoked": True})


__all__ = ["router", "keys_router"]
