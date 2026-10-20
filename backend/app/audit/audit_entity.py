"""audit_entity.py — modelos y reglas de saneamiento de `audit_log` (ADR-014)."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditAction(str, Enum):
    """Acciones registradas. Cada valor es `<objeto>.<verbo>`; el filtro de la API las valida."""
    USER_CREATE = "user.create"
    USER_AUTOPROVISION = "user.autoprovision"        # alta automática al entrar con Google (C24)
    USER_UPDATE = "user.update"
    USER_DISABLE = "user.disable"
    USER_ENABLE = "user.enable"
    USER_INVITE = "user.invite"                      # invitación enviada o reenviada
    USER_PASSWORD_RESET = "user.password_reset"      # el admin pidió restablecer
    USER_PASSWORD_SET = "user.password_set"          # la persona canjeó el enlace
    ACCESS_GRANT = "access.grant"
    ACCESS_REVOKE = "access.revoke"
    UNIT_CREATE = "unit.create"
    UNIT_UPDATE = "unit.update"
    UNIT_MOVE = "unit.move"
    UNIT_DEACTIVATE = "unit.deactivate"
    UNIT_ACTIVATE = "unit.activate"
    UNIT_HEAD = "unit.head"
    PLATFORM_UPDATE = "platform.update"
    SUBROGATION_CREATE = "subrogation.create"
    SUBROGATION_CANCEL = "subrogation.cancel"


class AuditTarget(str, Enum):
    USER = "user"
    UNIT = "unit"
    PLATFORM = "platform"
    SUBROGATION = "subrogation"


# `changes` jamás lleva credenciales (ADR-014). Se descartan por nombre, en cualquier nivel.
FORBIDDEN_KEYS = frozenset({
    "hashed_password", "password", "new_password", "current_password", "token", "token_hash",
    "access_token", "refresh_token", "secret", "client_secret", "jwt_secret", "authorization",
})
# Datos personales: se registra que cambiaron, no su valor.
MASKED_KEYS = frozenset({"personal_phone"})
MASK = "[REDACTED]"


class AuditEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id")
    at: datetime
    actor_id: Optional[str] = None            # None: acción del sistema (arranque, seed)
    action: str
    target_type: str
    target_id: str
    changes: Dict[str, Any] = {}
    bulk_id: Optional[str] = None


class AuditListResponse(BaseModel):
    items: List[AuditEntry]
    total: int
    page: int
    page_size: int
    total_pages: int
