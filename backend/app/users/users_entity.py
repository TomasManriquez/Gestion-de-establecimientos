import re
from datetime import datetime
from enum import Enum
from typing import List, Optional

from bson import ObjectId
from pydantic import (BaseModel, ConfigDict, EmailStr, Field, computed_field,
                      field_validator, model_validator)

from app.config import settings


class EstablishmentPosition(str, Enum):
    """Cargo de un usuario de establecimiento (C22, C23).

    Los seis primeros coinciden con `CounterpartRole` (mismo string) para poder cruzar ambas
    colecciones. No existe ENCARGADO_CONVIVENCIA: duplicaría CONVIVENCIA_ESCOLAR.
    """
    DIRECTOR = "DIRECTOR"
    UTP_JEFE = "UTP_JEFE"
    PIE_ENCARGADO = "PIE_ENCARGADO"
    CONVIVENCIA_ESCOLAR = "CONVIVENCIA_ESCOLAR"
    INSPECTOR_GENERAL = "INSPECTOR_GENERAL"
    SIGE_ENCARGADO = "SIGE_ENCARGADO"
    SECRETARIO = "SECRETARIO"
    ADMINISTRADOR = "ADMINISTRADOR"
    DOCENTE = "DOCENTE"
    ASISTENTE_EDUCACION = "ASISTENTE_EDUCACION"


# ─── Errores de dominio (el service no importa fastapi, L2; el controller los traduce) ───

class UserNotFound(Exception):
    pass


class UserConflict(Exception):
    """Violación de una regla de negocio o de unicidad. -> 409"""
    def __init__(self, message: str, code: str = "conflict", field: str = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.field = field


class UserInvalid(Exception):
    """Referencia o combinación inválida detectada por el service (por ejemplo, unit_id inexistente). -> 422"""
    def __init__(self, errors):
        super().__init__("; ".join(e["message"] for e in errors))
        self.errors = errors


class UserStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    DISABLED = "disabled"


PHONE_RE = re.compile(r"^\+56[0-9]{9}$")        # E.164 chileno
EXTENSION_RE = re.compile(r"^[0-9]{2,6}$")      # supuesto A3 del plan
RBD_RE = re.compile(r"^[0-9]{1,8}$")
NAME_MAX = 80


def normalize_email(value: str) -> str:
    return value.strip().lower()


def is_object_id(value: str) -> bool:
    return isinstance(value, str) and len(value) == 24 and ObjectId.is_valid(value)


def check_mode(is_slep_staff: bool, unit_id, rbd, positions) -> None:
    """Invariante central de R1: funcionario SLEP XOR usuario de establecimiento.

    Una sola función para el modelo de alta y para la edición (el service la aplica sobre el
    documento ya fusionado), de modo que no haya dos versiones de la regla.
    """
    if is_slep_staff:
        if not unit_id:
            raise ValueError("Un funcionario SLEP debe tener unit_id")
        if rbd:
            raise ValueError("Un funcionario SLEP no puede tener rbd")
        if positions:
            raise ValueError("Un funcionario SLEP no tiene cargos de establecimiento (positions debe estar vacío)")
    else:
        if not rbd:
            raise ValueError("Un usuario de establecimiento debe tener rbd")
        if unit_id:
            raise ValueError("Un usuario de establecimiento no puede tener unit_id")
        if not positions:
            raise ValueError("Un usuario de establecimiento debe tener al menos un cargo (positions)")


# ─── Validadores compartidos ─────────────────────────────────────────────────

def _email_in_allowed_domain(value: str) -> str:
    domain = value.rpartition("@")[2]
    if domain not in settings.ALLOWED_EMAIL_DOMAINS:
        raise ValueError(f"El correo debe pertenecer a: {', '.join('@' + d for d in settings.ALLOWED_EMAIL_DOMAINS)}")
    return value


def _check_phone(v: Optional[str]) -> Optional[str]:
    if v is not None and not PHONE_RE.fullmatch(v):
        raise ValueError("personal_phone debe tener formato +56 y 9 dígitos (E.164 chileno)")
    return v


def _check_extension(v: Optional[str]) -> Optional[str]:
    if v is not None and not EXTENSION_RE.fullmatch(v):
        raise ValueError("work_extension debe tener entre 2 y 6 dígitos")
    return v


def _check_object_id(v: Optional[str]) -> Optional[str]:
    if v is not None and not is_object_id(v):
        raise ValueError("Identificador inválido")
    return v


def _check_rbd(v: Optional[str]) -> Optional[str]:
    if v is not None and not RBD_RE.fullmatch(v):
        raise ValueError("rbd debe ser numérico (hasta 8 dígitos)")
    return v


def _check_positions(v: Optional[List[EstablishmentPosition]]):
    if v is not None and len(set(v)) != len(v):
        raise ValueError("positions no admite valores repetidos")
    return v


STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _Fields(BaseModel):
    """Campos comunes de entrada. `extra='forbid'`: asignación masiva imposible (T1)."""
    model_config = STRICT

    @field_validator("email", mode="before", check_fields=False)
    @classmethod
    def _email_before(cls, v):
        return normalize_email(v) if isinstance(v, str) else v

    @field_validator("email", check_fields=False)
    @classmethod
    def _email_after(cls, v):
        return _email_in_allowed_domain(v) if v is not None else v

    _phone = field_validator("personal_phone", check_fields=False)(_check_phone)
    _ext = field_validator("work_extension", check_fields=False)(_check_extension)
    _uid = field_validator("unit_id", check_fields=False)(_check_object_id)
    _rbd = field_validator("rbd", check_fields=False)(_check_rbd)
    _pos = field_validator("positions", check_fields=False)(_check_positions)


class UserCreate(_Fields):
    """Body del alta. No admite status, access ni credenciales: se asignan en el servidor."""
    email: EmailStr = Field(..., max_length=254)
    first_name: str = Field(..., min_length=1, max_length=NAME_MAX)
    last_name: str = Field(..., min_length=1, max_length=NAME_MAX)
    personal_phone: Optional[str] = Field(None, max_length=16)
    work_extension: Optional[str] = Field(None, max_length=6)
    is_slep_staff: bool
    unit_id: Optional[str] = Field(None, max_length=24)
    rbd: Optional[str] = Field(None, max_length=8)
    positions: List[EstablishmentPosition] = Field(default_factory=list, max_length=len(EstablishmentPosition))

    @model_validator(mode="after")
    def _mode(self):
        check_mode(self.is_slep_staff, self.unit_id, self.rbd, self.positions)
        return self


class UserAdminUpdate(_Fields):
    """PATCH del admin global. Sin access/status/auth_providers: tienen endpoints propios."""
    email: Optional[EmailStr] = Field(None, max_length=254)
    first_name: Optional[str] = Field(None, min_length=1, max_length=NAME_MAX)
    last_name: Optional[str] = Field(None, min_length=1, max_length=NAME_MAX)
    personal_phone: Optional[str] = Field(None, max_length=16)
    work_extension: Optional[str] = Field(None, max_length=6)
    is_slep_staff: Optional[bool] = None
    unit_id: Optional[str] = Field(None, max_length=24)
    rbd: Optional[str] = Field(None, max_length=8)
    positions: Optional[List[EstablishmentPosition]] = Field(None, max_length=len(EstablishmentPosition))


class UserSelfUpdate(_Fields):
    """PATCH /api/users/me (C19): el usuario solo cambia teléfono y anexo. La protección
    está en el tipo: cualquier otro campo da 422, no depende de un `if`."""
    personal_phone: Optional[str] = Field(None, max_length=16)
    work_extension: Optional[str] = Field(None, max_length=6)


class AccessGrant(BaseModel):
    model_config = STRICT
    role: str = Field(..., min_length=1, max_length=20)


# ─── Respuestas (response_model: lo que no se declara no sale) ───────────────

class _Out(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AccessEntry(_Out):
    platform_id: str
    role: str
    granted_at: Optional[datetime] = None
    granted_by: Optional[str] = None


class AuthProviderPublic(_Out):
    """Nunca declara hashed_password: el response_model descarta el campo."""
    provider: str
    linked_at: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    must_change_password: Optional[bool] = None


class InvitationState(_Out):
    sent_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    last_error: Optional[str] = None

    @computed_field
    @property
    def sent(self) -> bool:
        return self.sent_at is not None and self.last_error is None


class UserSummary(_Out):
    """Ítem del listado: sin personal_phone ni auth_providers (T4)."""
    id: str = Field(..., alias="_id")
    email: Optional[str] = None
    first_name: str = ""
    last_name: str = ""
    work_extension: Optional[str] = None
    is_slep_staff: bool = False
    unit_id: Optional[str] = None
    rbd: Optional[str] = None
    positions: List[str] = []
    status: str
    access: List[AccessEntry] = []
    invitation: Optional[InvitationState] = None
    last_login_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None


class User(UserSummary):
    """Detalle para el admin global: agrega personal_phone y trazabilidad."""
    personal_phone: Optional[str] = None
    auth_providers: List[AuthProviderPublic] = []
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    disabled_at: Optional[datetime] = None


class UserMe(_Out):
    """Lo que un usuario ve de sí mismo (incluye su propio personal_phone)."""
    id: str = Field(..., alias="_id")
    email: Optional[str] = None
    first_name: str = ""
    last_name: str = ""
    personal_phone: Optional[str] = None
    work_extension: Optional[str] = None
    is_slep_staff: bool = False
    unit_id: Optional[str] = None
    rbd: Optional[str] = None
    positions: List[str] = []
    status: str
    access: List[AccessEntry] = []
    last_login_at: Optional[datetime] = None


class UserListResponse(BaseModel):
    items: List[UserSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class FieldError(BaseModel):
    field: str
    code: str
    message: str


class BulkItemResult(BaseModel):
    index: int
    status: str
    id: Optional[str] = None
    errors: List[FieldError] = []


class BulkResult(BaseModel):
    bulk_id: str
    dry_run: bool
    total: int
    created: int
    failed: int
    items: List[BulkItemResult]
