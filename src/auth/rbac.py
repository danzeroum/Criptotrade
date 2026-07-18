"""Role-based access control (A3): roles and the permission matrix.

Single source of truth for authorization. Roles are code-defined this phase
(custom roles + editing the matrix via PATCH /v1/roles are deferred — the
matrix is served read-only by ``GET /v1/roles``). The machine principal
(X-API-Key) gets every operational permission but NOT user management, so a
leaked integration key cannot mint accounts.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, List

from src.api.authn import Principal

ROLES: List[str] = ["visualizador", "operador", "admin"]

# permission -> roles that hold it (kind 'user'); see MACHINE_PERMS for api-key.
PERMISSIONS: Dict[str, FrozenSet[str]] = {
    "approve_order":   frozenset({"operador", "admin"}),
    "change_autonomy": frozenset({"operador", "admin"}),
    "change_risk":     frozenset({"admin"}),
    "edit_settings":   frozenset({"admin"}),
    "manage_keys":     frozenset({"admin"}),
    "view_audit":      frozenset({"operador", "admin"}),
    "manage_users":    frozenset({"admin"}),
}

MACHINE_PERMS: FrozenSet[str] = frozenset(PERMISSIONS) - {"manage_users"}

ROLE_LABELS: Dict[str, str] = {
    "visualizador": "Visualizador",
    "operador": "Operador",
    "admin": "Admin",
}


def permissions_for(principal: Principal) -> List[str]:
    """Permissions held by a principal (demo/anonymous hold none)."""
    if principal.kind == "machine":
        return sorted(MACHINE_PERMS)
    if principal.kind == "user":
        return sorted(p for p, roles in PERMISSIONS.items() if principal.role in roles)
    return []


def has_perm(principal: Principal, perm: str) -> bool:
    if principal.kind == "machine":
        return perm in MACHINE_PERMS
    if principal.kind == "user":
        return principal.role in PERMISSIONS.get(perm, frozenset())
    return False


def role_matrix() -> List[Dict[str, object]]:
    """Read-only matrix for GET /v1/roles (and the console's matrix card)."""
    return [
        {
            "id": role,
            "label": ROLE_LABELS[role],
            "permissions": sorted(p for p, roles in PERMISSIONS.items() if role in roles),
        }
        for role in ROLES
    ]


__all__ = ["ROLES", "PERMISSIONS", "MACHINE_PERMS", "ROLE_LABELS",
           "permissions_for", "has_perm", "role_matrix"]
