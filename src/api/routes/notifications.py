"""/v1/notifications — A6: delivery channels, event×severity rules, quiet hours.

Everything sits behind ``edit_settings`` (admin) — the screen holds channel
secrets, so it is hidden from demo/visualizador/operador. Secrets are stored
Fernet-encrypted (AUTH_SECRET_KEY) and every read returns them MASKED; sending
the mask back unchanged on PATCH keeps the stored value (the contract A5 will
reuse). Channel/rule mutations land in the ledger as ``config_changed`` scope
``notifications`` (A4 trail) with masked payloads only.
"""
from __future__ import annotations

from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, HTTPException, Path

from src.api.authn import Principal, require_perm
from src.api.deps import get_ledger, get_notification_store
from src.api.schemas import (
    APIResponse, ChannelCreateIn, ChannelOut, ChannelPatchIn,
    NotificationSettingsOut, NotificationSettingsPatch, RuleIn, RuleOut,
    RulePatchIn,
)
from src.core.ledger import TradingLedger
from src.notifications.senders import send_via_channel
from src.notifications.store import (
    NotificationStore, masked_config, masked_destination,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])

_REQUIRED_FIELDS = {
    "email": ("to_email",),
    "telegram": ("bot_token", "chat_id"),
    "slack": ("webhook_url",),
    "webhook": ("url",),
}


def _channel_out(store: NotificationStore, row: Dict[str, Any]) -> ChannelOut:
    config = store.channel_config(row)
    return ChannelOut(
        id=row["id"], kind=row["kind"], label=row["label"],
        enabled=bool(row["enabled"]),
        config_masked=masked_config(row["kind"], config),
        destination_masked=masked_destination(row["kind"], config),
        created_at=row.get("created_at"), last_test_at=row.get("last_test_at"),
        last_test_ok=None if row.get("last_test_ok") is None else bool(row["last_test_ok"]),
        last_error=row.get("last_error"),
    )


def _log_change(ledger: TradingLedger, principal: Principal, detail: str,
                before: Dict[str, Any], after: Dict[str, Any]) -> None:
    changed = sorted(set(before) | set(after))
    ledger.log_decision("config_changed", {
        "actor": principal.actor, "scope": "notifications", "detail": detail,
        "before": {k: before.get(k) for k in changed},
        "after": {k: after.get(k) for k in changed},
    })


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail={
        "error": f"{what}_not_found", "message": f"{what.capitalize()} não encontrado.",
        "docs": "/v1/docs",
    })


# -------------------------------------------------------------------- channels
@router.get("/channels", response_model=APIResponse[List[ChannelOut]],
            summary="Canais conectados (configs mascaradas) + status de teste")
async def list_channels(
    store: NotificationStore = Depends(get_notification_store),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[List[ChannelOut]]:
    return APIResponse(data=[_channel_out(store, r) for r in store.list_channels()])


@router.post("/channels", response_model=APIResponse[ChannelOut], status_code=201,
             summary="Conecta um canal (secrets cifrados em repouso)")
async def create_channel(
    body: ChannelCreateIn = Body(...),
    store: NotificationStore = Depends(get_notification_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[ChannelOut]:
    missing = [f for f in _REQUIRED_FIELDS[body.kind] if not body.config.get(f)]
    if missing:
        raise HTTPException(status_code=422, detail={
            "error": "validation_error",
            "message": f"Config do canal {body.kind} incompleta: falta {', '.join(missing)}.",
            "field": missing[0], "docs": "/v1/docs",
        })
    row = store.create_channel(body.kind, body.label, body.config)
    out = _channel_out(store, row)
    _log_change(ledger, principal, f"channel_created:{body.kind}",
                {}, {"label": body.label, "config": out.config_masked})
    return APIResponse(data=out)


@router.patch("/channels/{channel_id}", response_model=APIResponse[ChannelOut],
              summary="Edita um canal (mask inalterada = mantém o secret)")
async def patch_channel(
    channel_id: str = Path(...),
    body: ChannelPatchIn = Body(...),
    store: NotificationStore = Depends(get_notification_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[ChannelOut]:
    before_row = store.get_channel(channel_id)
    if before_row is None:
        raise _not_found("channel")
    before = _channel_out(store, before_row)
    row = store.update_channel(
        channel_id, label=body.label, enabled=body.enabled, config=body.config,
    )
    out = _channel_out(store, row)
    _log_change(ledger, principal, f"channel_updated:{row['kind']}",
                {"label": before.label, "enabled": before.enabled,
                 "config": before.config_masked},
                {"label": out.label, "enabled": out.enabled,
                 "config": out.config_masked})
    return APIResponse(data=out)


@router.delete("/channels/{channel_id}", response_model=APIResponse[dict],
               summary="Remove um canal")
async def delete_channel(
    channel_id: str = Path(...),
    store: NotificationStore = Depends(get_notification_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[dict]:
    row = store.get_channel(channel_id)
    if row is None or not store.delete_channel(channel_id):
        raise _not_found("channel")
    _log_change(ledger, principal, f"channel_deleted:{row['kind']}",
                {"label": row["label"]}, {})
    return APIResponse(data={"deleted": True})


@router.post("/channels/{channel_id}/test", response_model=APIResponse[dict],
             summary="Envia uma notificação de teste REAL pelo canal")
async def test_channel(
    channel_id: str = Path(...),
    store: NotificationStore = Depends(get_notification_store),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[dict]:
    row = store.get_channel(channel_id)
    if row is None:
        raise _not_found("channel")
    config = store.channel_config(row)
    try:
        send_via_channel(
            row["kind"], config,
            "Criptotrade — teste de notificação",
            f"✅ Canal “{row['label']}” conectado. Esta é uma mensagem de teste.",
        )
        store.record_test(channel_id, True, None)
        return APIResponse(data={
            "ok": True, "destination": masked_destination(row["kind"], config),
        })
    except Exception as exc:  # noqa: BLE001 - the operator needs the reason
        store.record_test(channel_id, False, str(exc)[:300])
        return APIResponse(data={
            "ok": False, "error": str(exc)[:300],
            "destination": masked_destination(row["kind"], config),
        })


# ----------------------------------------------------------------------- rules
@router.get("/rules", response_model=APIResponse[List[RuleOut]],
            summary="Regras evento × severidade → canais")
async def list_rules(
    store: NotificationStore = Depends(get_notification_store),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[List[RuleOut]]:
    return APIResponse(data=[RuleOut(**{**r, "enabled": bool(r["enabled"])})
                             for r in store.list_rules()])


@router.post("/rules", response_model=APIResponse[RuleOut], status_code=201,
             summary="Cria uma regra de entrega")
async def create_rule(
    body: RuleIn = Body(...),
    store: NotificationStore = Depends(get_notification_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[RuleOut]:
    rule = store.create_rule(body.alert_type, body.min_severity, body.channel_ids,
                             pairs=body.pairs)
    if not body.enabled:
        rule = store.update_rule(rule["id"], enabled=False)
    _log_change(ledger, principal, "rule_created", {}, {
        "alert_type": rule["alert_type"], "min_severity": rule["min_severity"],
        "channel_ids": rule["channel_ids"], "pairs": rule["pairs"],
    })
    return APIResponse(data=RuleOut(**{**rule, "enabled": bool(rule["enabled"])}))


@router.patch("/rules/{rule_id}", response_model=APIResponse[RuleOut],
              summary="Edita uma regra")
async def patch_rule(
    rule_id: str = Path(...),
    body: RulePatchIn = Body(...),
    store: NotificationStore = Depends(get_notification_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[RuleOut]:
    before = store.get_rule(rule_id)
    if before is None:
        raise _not_found("rule")
    rule = store.update_rule(
        rule_id, alert_type=body.alert_type, min_severity=body.min_severity,
        channel_ids=body.channel_ids, pairs=body.pairs, enabled=body.enabled,
    )
    _diff_keys = ("alert_type", "min_severity", "channel_ids", "pairs", "enabled")
    _log_change(ledger, principal, "rule_updated",
                {k: before[k] for k in _diff_keys},
                {k: rule[k] for k in _diff_keys})
    return APIResponse(data=RuleOut(**{**rule, "enabled": bool(rule["enabled"])}))


@router.delete("/rules/{rule_id}", response_model=APIResponse[dict],
               summary="Remove uma regra")
async def delete_rule(
    rule_id: str = Path(...),
    store: NotificationStore = Depends(get_notification_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[dict]:
    rule = store.get_rule(rule_id)
    if rule is None or not store.delete_rule(rule_id):
        raise _not_found("rule")
    _log_change(ledger, principal, "rule_deleted",
                {"alert_type": rule["alert_type"]}, {})
    return APIResponse(data={"deleted": True})


# -------------------------------------------------------------------- settings
@router.get("/settings", response_model=APIResponse[NotificationSettingsOut],
            summary="Quiet hours + janela de agrupamento anti-flood")
async def get_settings(
    store: NotificationStore = Depends(get_notification_store),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[NotificationSettingsOut]:
    return APIResponse(data=NotificationSettingsOut(**store.get_settings()))


@router.patch("/settings", response_model=APIResponse[NotificationSettingsOut],
              summary="Atualiza quiet hours/agrupamento")
async def patch_settings(
    body: NotificationSettingsPatch = Body(...),
    store: NotificationStore = Depends(get_notification_store),
    ledger: TradingLedger = Depends(get_ledger),
    principal: Principal = Depends(require_perm("edit_settings")),
) -> APIResponse[NotificationSettingsOut]:
    if body.quiet_tz:
        try:
            ZoneInfo(body.quiet_tz)
        except Exception:
            raise HTTPException(status_code=422, detail={
                "error": "validation_error",
                "message": "Fuso inválido — use um identificador IANA.",
                "field": "quiet_tz", "docs": "/v1/docs",
            })
    before = store.get_settings()
    updates: Dict[str, Any] = body.model_dump(exclude_none=True)
    updates.pop("clear_quiet_hours", None)
    if body.clear_quiet_hours:
        updates["quiet_start"] = None
        updates["quiet_end"] = None
    merged = store.set_settings(**updates) if updates else before
    if merged != before:
        _log_change(ledger, principal, "settings_updated", before, merged)
    return APIResponse(data=NotificationSettingsOut(**merged))


__all__ = ["router"]
