"""Cryptographic primitives for authentication (A1).

Passwords use argon2id (memory-hard, no bcrypt 72-byte truncation). Session and
reset tokens are opaque 32-byte urlsafe values; only their SHA-256 lands in the
database, so a leaked DB cannot be replayed as a cookie. TOTP secrets are
encrypted at rest with Fernet keyed from ``AUTH_SECRET_KEY`` — losing that key
makes 2FA secrets unrecoverable (users fall back to backup codes / CLI reset).
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
from typing import List, Optional, Tuple

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

_hasher = PasswordHasher()  # argon2id defaults (t=3, m=64MiB, p=4)

# Fixed hash verified for unknown emails so login runs constant work whether or
# not the account exists (anti-enumeration; A1 acceptance).
DUMMY_HASH = PasswordHasher().hash("dummy-password-for-timing-equalization")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: Optional[str], password: str) -> bool:
    try:
        _hasher.verify(password_hash or DUMMY_HASH, password)
        return password_hash is not None
    except VerifyMismatchError:
        return False
    except Exception:  # malformed hash: treat as mismatch, never raise
        return False


def new_token() -> str:
    """Opaque credential handed to the client (cookie value)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """What we store: SHA-256 of the opaque token (constant-time comparable)."""
    return hashlib.sha256(token.encode()).hexdigest()


# ------------------------------------------------- secrets at rest (Fernet)
def encrypt_secret(plaintext: str) -> str:
    """Encrypt an arbitrary secret at rest (A6 channel configs; A5 will reuse).
    Same Fernet keyed from AUTH_SECRET_KEY as the TOTP secrets."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> Optional[str]:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, RuntimeError):
        return None


# ------------------------------------------------------------------ TOTP (2FA)
def _fernet() -> Fernet:
    raw = os.getenv("AUTH_SECRET_KEY", "").strip()
    if not raw:
        raise RuntimeError(
            "AUTH_SECRET_KEY must be set to use 2FA (it encrypts TOTP secrets at rest)."
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(key)


def new_totp_secret() -> str:
    return pyotp.random_base32()


def encrypt_totp_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_totp_secret(secret_enc: str) -> Optional[str]:
    try:
        return _fernet().decrypt(secret_enc.encode()).decode()
    except (InvalidToken, RuntimeError):
        return None


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="Criptotrade")


def verify_totp(secret: str, code: str) -> bool:
    try:
        return pyotp.TOTP(secret).verify(code.strip().replace(" ", ""), valid_window=1)
    except Exception:
        return False


# ------------------------------------------------------------ backup codes
def generate_backup_codes(count: int = 10) -> Tuple[List[str], List[str]]:
    """Return (plaintext codes shown once, argon2 hashes stored)."""
    codes = [secrets.token_hex(4) for _ in range(count)]  # 8 hex chars each
    return codes, [_hasher.hash(c) for c in codes]


def consume_backup_code(hashes: List[str], code: str) -> Optional[List[str]]:
    """If ``code`` matches one stored hash, return the list WITHOUT it; else None."""
    normalized = code.strip().lower().replace("-", "").replace(" ", "")
    for i, h in enumerate(hashes):
        try:
            _hasher.verify(h, normalized)
            return hashes[:i] + hashes[i + 1:]
        except Exception:
            continue
    return None


__all__ = [
    "DUMMY_HASH", "hash_password", "verify_password", "new_token", "hash_token",
    "new_totp_secret", "encrypt_totp_secret", "decrypt_totp_secret", "totp_uri",
    "verify_totp", "generate_backup_codes", "consume_backup_code",
]
