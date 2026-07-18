"""Per-channel delivery (A6). Every sender raises on failure — the dispatcher
owns retry/backoff and the ledger events; the /test route reports the error.

No new dependencies: e-mail rides the 4a SMTP infra, Telegram/Slack/webhook go
through httpx (already pinned).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict

import httpx

_TIMEOUT = 10.0


def _send_email(config: Dict[str, Any], subject: str, text: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        raise RuntimeError("SMTP não configurado (SMTP_HOST ausente no ambiente).")
    to_email = config.get("to_email")
    if not to_email:
        raise RuntimeError("Canal de e-mail sem destinatário (to_email).")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("SMTP_FROM", "no-reply@criptotrade.local")
    msg["To"] = to_email
    msg.set_content(text)
    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=_TIMEOUT) as smtp:
        smtp.starttls()
        user = os.getenv("SMTP_USER", "")
        if user:
            smtp.login(user, os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(msg)


def _send_telegram(config: Dict[str, Any], subject: str, text: str) -> None:
    token, chat_id = config.get("bot_token"), config.get("chat_id")
    if not token or not chat_id:
        raise RuntimeError("Canal Telegram sem bot_token/chat_id.")
    r = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": f"{subject}\n{text}"},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("ok"):
        raise RuntimeError(f"Telegram recusou: {body.get('description', 'erro desconhecido')}")


def _send_slack(config: Dict[str, Any], subject: str, text: str) -> None:
    url = config.get("webhook_url")
    if not url:
        raise RuntimeError("Canal Slack sem webhook_url.")
    r = httpx.post(url, json={"text": f"*{subject}*\n{text}"}, timeout=_TIMEOUT)
    r.raise_for_status()


def _send_webhook(config: Dict[str, Any], subject: str, text: str,
                  payload: Dict[str, Any] | None = None) -> None:
    url = config.get("url")
    if not url:
        raise RuntimeError("Canal webhook sem url.")
    body = json.dumps(
        payload or {"subject": subject, "text": text}, ensure_ascii=False
    ).encode()
    headers = {"Content-Type": "application/json"}
    secret = config.get("secret")
    if secret:
        headers["X-Criptotrade-Signature"] = hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
    r = httpx.post(url, content=body, headers=headers, timeout=_TIMEOUT)
    r.raise_for_status()


def send_via_channel(kind: str, config: Dict[str, Any], subject: str, text: str,
                     payload: Dict[str, Any] | None = None) -> None:
    """Deliver one message through a channel config. Raises on any failure."""
    if kind == "email":
        _send_email(config, subject, text)
    elif kind == "telegram":
        _send_telegram(config, subject, text)
    elif kind == "slack":
        _send_slack(config, subject, text)
    elif kind == "webhook":
        _send_webhook(config, subject, text, payload)
    else:
        raise RuntimeError(f"Tipo de canal desconhecido: {kind}")


__all__ = ["send_via_channel"]
