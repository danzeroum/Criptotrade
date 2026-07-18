"""Outbound auth e-mails (password reset) with a no-SMTP fallback.

When SMTP_* env vars are configured, sends real mail. When absent (dev, or the
VPS before a provider exists), the reset link is logged at INFO so an operator
with log access can complete the flow — and the HTTP response stays the same
generic 200 either way (anti-enumeration).
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class EmailSender:
    def send_password_reset(self, to_email: str, reset_link: str) -> None:
        host = os.getenv("SMTP_HOST", "").strip()
        if not host:
            logger.info("SMTP not configured — password reset link for %s: %s",
                        to_email, reset_link)
            return
        msg = EmailMessage()
        msg["Subject"] = "Criptotrade — redefinição de senha"
        msg["From"] = os.getenv("SMTP_FROM", "no-reply@criptotrade.local")
        msg["To"] = to_email
        msg.set_content(
            "Recebemos um pedido para redefinir sua senha no Criptotrade.\n\n"
            f"Redefina em: {reset_link}\n\n"
            "O link expira em 30 minutos. Se você não pediu, ignore este e-mail."
        )
        try:
            port = int(os.getenv("SMTP_PORT", "587"))
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                smtp.starttls()
                user = os.getenv("SMTP_USER", "")
                if user:
                    smtp.login(user, os.getenv("SMTP_PASSWORD", ""))
                smtp.send_message(msg)
        except Exception:  # pragma: no cover - mail failure must not leak to client
            logger.warning("Failed to send password-reset email", exc_info=True)


__all__ = ["EmailSender"]
