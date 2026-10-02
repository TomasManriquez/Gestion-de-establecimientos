from dataclasses import dataclass, field
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ─── Plataformas y roles (ADR-009) ───────────────────────────────────────────
PLATFORM_IAM = "iam"
PLATFORM_DATOS = "datos"
PLATFORM_SELLOVERDE = "selloverde"

ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"

# Combinaciones que declaran los controllers de `datos` (matriz de 04 §9.3)
DATOS_READ = (ROLE_ADMIN, ROLE_EDITOR, ROLE_VIEWER)
DATOS_WRITE = (ROLE_ADMIN, ROLE_EDITOR)
DATOS_DELETE = (ROLE_ADMIN,)
IAM_ADMIN = (ROLE_ADMIN,)
# Roles que ven las credenciales en claro (C20): solo `viewer` las recibe redactadas.
SENSITIVE_ROLES = frozenset({ROLE_ADMIN, ROLE_EDITOR})


@dataclass
class AccessContext:
    """Resultado de `require_access`: quién es y qué rol tiene en la plataforma pedida.

    `user` es para el controller (por ejemplo `/me`). El service nunca recibe el usuario (L3):
    recibe `user_id` o booleanos como `include_sensitive`.
    """
    user_id: str
    role: Optional[str]
    user: dict = field(default_factory=dict, repr=False)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(..., min_length=1, max_length=254)   # correo, o username legado
    password: str = Field(..., min_length=1, max_length=1024)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class AccessSummary(BaseModel):
    platform_id: str
    role: str


class UserResponse(BaseModel):
    """Contrato de GET /api/auth/me. Los tres primeros campos son el contrato original;
    id, email y access son aditivos (no rompen a ningún cliente, 03 §8.2)."""
    username: str
    full_name: str
    role: str
    id: Optional[str] = None
    email: Optional[str] = None
    access: List[AccessSummary] = []
