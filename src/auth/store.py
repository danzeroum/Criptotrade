"""User and session persistence for authentication (A1).

Same style as the other stores: short-lived ``connection()`` per operation on
the main ``criptotrade.db`` (schema from ``migrations/005_auth.sql``). Sessions
are server-side rows addressed by SHA-256 token hashes — revocation is a row
update, effective immediately. Refresh rotation carries a ``family_id`` so a
rotated-then-reused refresh token (theft signal) revokes the whole family.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from src.auth import security
from src.core.db import connection, get_db_path

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _row(r: Any) -> Dict[str, Any]:
    return {k: r[k] for k in r.keys()}


class UserStore:
    """Accounts: creation, credential verification, 2FA state, resets."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db = db_path

    def _path(self):
        return self._db or get_db_path()

    # ----------------------------------------------------------------- lookup
    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with connection(self._path()) as conn:
            r = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
            ).fetchone()
        return _row(r) if r else None

    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        with connection(self._path()) as conn:
            r = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row(r) if r else None

    def count(self) -> int:
        with connection(self._path()) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    # ----------------------------------------------------------------- create
    def create(
        self,
        email: str,
        password: Optional[str],
        *,
        name: Optional[str] = None,
        role: str = "admin",
        status: str = "active",
    ) -> Dict[str, Any]:
        user = {
            "id": str(uuid.uuid4()),
            "email": email.strip().lower(),
            "name": name,
            "password_hash": security.hash_password(password) if password else None,
            "role": role,
            "status": status,
            "created_at": _iso(_now()),
        }
        with connection(self._path()) as conn:
            conn.execute(
                "INSERT INTO users (id, email, name, password_hash, role, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user["id"], user["email"], user["name"], user["password_hash"],
                 user["role"], user["status"], user["created_at"]),
            )
        return user

    # ------------------------------------------------------------ credentials
    def verify_login(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Constant-work check; None for wrong password, unknown email OR
        non-active account — indistinguishable to the caller (anti-enumeration)."""
        user = self.get_by_email(email)
        ok = security.verify_password(user["password_hash"] if user else None, password)
        if not ok or user is None or user["status"] != "active":
            return None
        return user

    def set_password(self, user_id: str, password: str) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (security.hash_password(password), user_id),
            )

    def touch_login(self, user_id: str) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?", (_iso(_now()), user_id)
            )

    # ------------------------------------------------------------------- 2FA
    def set_totp(self, user_id: str, secret_enc: Optional[str], enabled: bool,
                 backup_hashes: Optional[list] = None) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE users SET totp_secret_enc = ?, totp_enabled = ?, backup_codes = ?"
                " WHERE id = ?",
                (secret_enc, 1 if enabled else 0,
                 json.dumps(backup_hashes) if backup_hashes is not None else None, user_id),
            )

    def update_backup_codes(self, user_id: str, backup_hashes: list) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE users SET backup_codes = ? WHERE id = ?",
                (json.dumps(backup_hashes), user_id),
            )

    # ---------------------------------------------------------------- admin (A3)
    def list_users(self) -> list:
        with connection(self._path()) as conn:
            rows = conn.execute(
                "SELECT id, email, name, role, status, totp_enabled, created_at,"
                " last_login_at FROM users ORDER BY created_at"
            ).fetchall()
        return [_row(r) for r in rows]

    def set_role(self, user_id: str, role: str) -> None:
        with connection(self._path()) as conn:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))

    def set_status(self, user_id: str, status: str) -> None:
        with connection(self._path()) as conn:
            conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))

    def delete(self, user_id: str) -> None:
        with connection(self._path()) as conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def count_active_admins(self) -> int:
        with connection(self._path()) as conn:
            return int(conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND status = 'active'"
            ).fetchone()[0])

    # ---------------------------------------------------------------- invites
    def create_invite(self, email: str, role: str, invited_by: str,
                      ttl_days: int = 7) -> str:
        token = security.new_token()
        with connection(self._path()) as conn:
            conn.execute(
                "INSERT INTO invites (id, email, role, token_hash, invited_by,"
                " created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), email.strip().lower(), role,
                 security.hash_token(token), invited_by, _iso(_now()),
                 _iso(_now() + timedelta(days=ttl_days))),
            )
        return token

    def list_invites(self, pending_only: bool = True) -> list:
        with connection(self._path()) as conn:
            rows = conn.execute("SELECT * FROM invites ORDER BY created_at").fetchall()
        out = [_row(r) for r in rows]
        if pending_only:
            now = _now()
            out = [i for i in out
                   if i["accepted_at"] is None and i["revoked_at"] is None
                   and datetime.fromisoformat(i["expires_at"]) >= now]
        return out

    def get_invite(self, invite_id: str) -> Optional[Dict[str, Any]]:
        with connection(self._path()) as conn:
            r = conn.execute("SELECT * FROM invites WHERE id = ?", (invite_id,)).fetchone()
        return _row(r) if r else None

    def refresh_invite(self, invite_id: str, ttl_days: int = 7) -> Optional[str]:
        """Resend: rotate the token and extend the expiry. None if not pending."""
        invite = self.get_invite(invite_id)
        if invite is None or invite["accepted_at"] or invite["revoked_at"]:
            return None
        token = security.new_token()
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE invites SET token_hash = ?, expires_at = ? WHERE id = ?",
                (security.hash_token(token), _iso(_now() + timedelta(days=ttl_days)),
                 invite_id),
            )
        return token

    def revoke_invite(self, invite_id: str) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE invites SET revoked_at = ? WHERE id = ? AND accepted_at IS NULL",
                (_iso(_now()), invite_id),
            )

    def accept_invite(self, token: str, name: str, password: str) -> Optional[Dict[str, Any]]:
        """Single-use: creates the active user with the invited role, or None."""
        th = security.hash_token(token)
        with connection(self._path()) as conn:
            r = conn.execute("SELECT * FROM invites WHERE token_hash = ?", (th,)).fetchone()
            if (r is None or r["accepted_at"] is not None or r["revoked_at"] is not None
                    or datetime.fromisoformat(r["expires_at"]) < _now()):
                return None
            conn.execute(
                "UPDATE invites SET accepted_at = ? WHERE id = ?", (_iso(_now()), r["id"])
            )
            invite = _row(r)
        if self.get_by_email(invite["email"]) is not None:
            return None  # account already exists — invite cannot overwrite it
        return self.create(invite["email"], password, name=name,
                           role=invite["role"], status="active")

    # ---------------------------------------------------------- password reset
    def create_reset(self, user_id: str, ttl_minutes: int = 30) -> str:
        token = security.new_token()
        with connection(self._path()) as conn:
            conn.execute(
                "INSERT INTO password_resets (id, user_id, token_hash, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, security.hash_token(token),
                 _iso(_now() + timedelta(minutes=ttl_minutes))),
            )
        return token

    def consume_reset(self, token: str) -> Optional[str]:
        """Single-use: returns the user_id and burns the token, or None."""
        th = security.hash_token(token)
        with connection(self._path()) as conn:
            r = conn.execute(
                "SELECT * FROM password_resets WHERE token_hash = ?", (th,)
            ).fetchone()
            if r is None or r["used_at"] is not None:
                return None
            if datetime.fromisoformat(r["expires_at"]) < _now():
                return None
            conn.execute(
                "UPDATE password_resets SET used_at = ? WHERE id = ?",
                (_iso(_now()), r["id"]),
            )
            return r["user_id"]


class SessionStore:
    """Server-side sessions with sliding idle TTL and refresh rotation."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db = db_path

    def _path(self):
        return self._db or get_db_path()

    @staticmethod
    def _ttls(remember: bool) -> Dict[str, timedelta]:
        return {
            "idle": timedelta(minutes=int(os.getenv("SESSION_IDLE_TTL_MIN", "30"))),
            "absolute": timedelta(hours=int(os.getenv("SESSION_ABS_TTL_H", "12"))),
            "refresh": timedelta(days=int(
                os.getenv("REMEMBER_TTL_D", "30") if remember else os.getenv("REFRESH_TTL_D", "7")
            )),
        }

    def create(self, user_id: str, *, remember: bool = False,
               ip: Optional[str] = None, user_agent: Optional[str] = None,
               family_id: Optional[str] = None) -> Dict[str, str]:
        """Create a session row; returns the PLAINTEXT tokens (only time they exist)."""
        token, refresh = security.new_token(), security.new_token()
        ttl = self._ttls(remember)
        now = _now()
        with connection(self._path()) as conn:
            conn.execute(
                "INSERT INTO sessions (id, user_id, token_hash, refresh_hash, family_id,"
                " remember, ip, user_agent, created_at, last_seen_at, idle_expires_at,"
                " absolute_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, security.hash_token(token),
                 security.hash_token(refresh), family_id or str(uuid.uuid4()),
                 1 if remember else 0, ip, user_agent, _iso(now), _iso(now),
                 _iso(now + ttl["idle"]), _iso(now + ttl["absolute"])),
            )
        return {"token": token, "refresh": refresh}

    def resolve(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate + slide the idle window. None when missing/expired/revoked."""
        th = security.hash_token(token)
        now = _now()
        with connection(self._path()) as conn:
            r = conn.execute("SELECT * FROM sessions WHERE token_hash = ?", (th,)).fetchone()
            if r is None or r["revoked_at"] is not None:
                return None
            if (datetime.fromisoformat(r["idle_expires_at"]) < now
                    or datetime.fromisoformat(r["absolute_expires_at"]) < now):
                return None
            ttl = self._ttls(bool(r["remember"]))
            conn.execute(
                "UPDATE sessions SET last_seen_at = ?, idle_expires_at = ? WHERE id = ?",
                (_iso(now), _iso(now + ttl["idle"]), r["id"]),
            )
            return _row(r)

    def rotate(self, refresh: str, *, ip: Optional[str] = None,
               user_agent: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Refresh-token rotation. Reuse of an already-rotated token revokes the
        whole family (theft signal) and returns None."""
        th = security.hash_token(refresh)
        with connection(self._path()) as conn:
            r = conn.execute("SELECT * FROM sessions WHERE refresh_hash = ?", (th,)).fetchone()
        if r is None:
            return None
        if r["revoked_at"] is not None:
            # Rotated-then-reused: kill every session in the family.
            self.revoke_family(r["family_id"])
            return {"__reuse__": r["family_id"]}  # sentinel for the route to log
        if datetime.fromisoformat(r["absolute_expires_at"]) < _now():
            return None
        self.revoke(r["id"])
        tokens = self.create(
            r["user_id"], remember=bool(r["remember"]), ip=ip,
            user_agent=user_agent, family_id=r["family_id"],
        )
        tokens["user_id"] = r["user_id"]
        return tokens

    def revoke(self, session_id: str) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE id = ?", (_iso(_now()), session_id)
            )

    def revoke_by_token(self, token: str) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE token_hash = ?",
                (_iso(_now()), security.hash_token(token)),
            )

    def revoke_family(self, family_id: str) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE family_id = ? AND revoked_at IS NULL",
                (_iso(_now()), family_id),
            )

    def revoke_all_for_user(self, user_id: str) -> None:
        with connection(self._path()) as conn:
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (_iso(_now()), user_id),
            )


def bootstrap_admin(store: Optional[UserStore] = None) -> Optional[Dict[str, Any]]:
    """One-shot first-admin seed (D3): only when the users table is EMPTY and
    ADMIN_EMAIL + ADMIN_PASSWORD are set. Rotating the env later is inert."""
    email = os.getenv("ADMIN_EMAIL", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password:
        return None
    store = store or UserStore()
    try:
        if store.count() > 0:
            return None
        user = store.create(email, password, name="Admin", role="admin")
        logger.info("Bootstrapped first admin user %s", email)
        return user
    except Exception:  # pragma: no cover - bootstrap must never block startup
        logger.warning("Admin bootstrap failed", exc_info=True)
        return None


__all__ = ["UserStore", "SessionStore", "bootstrap_admin"]
