import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ─── Errores de dominio (el service no importa fastapi, L2; el controller los traduce) ───

class UnitNotFound(Exception):
    pass


class UnitConflict(Exception):
    """Violación de una regla de negocio (nivel, jerarquía, unicidad, estado). -> 409"""
    def __init__(self, message: str, code: str = "conflict"):
        super().__init__(message)
        self.message = message
        self.code = code


# ─── Estructura real del SLEP (R2) ───────────────────────────────────────────
# (code, nombre, nivel, code del padre, orden). El nivel es el invariante; el nombre es un
# dato. "Gestión Territorial" aparece dos veces (SD-GT nivel 3, GT-GT nivel 4): por eso el
# `code` es el identificador y el nombre solo es único entre hermanas.
UNITS_SEED = [
    ("DE", "Dirección Ejecutiva", 1, None, 1),
    ("GAB", "Gabinete", 2, "DE", 1),
    ("JUR", "Jurídica", 2, "DE", 2),
    ("COM", "Comunicaciones", 2, "DE", 3),
    ("AUD", "Auditoría", 2, "DE", 4),
    ("SD-GP", "Subdirección de Gestión de Personas", 3, "DE", 5),
    ("SD-AF", "Subdirección de Administración y Finanzas", 3, "DE", 6),
    ("SD-GT", "Subdirección de Gestión Territorial", 3, "DE", 7),
    ("UATP", "Unidad de Apoyo Técnico Pedagógico", 3, "DE", 8),
    ("SD-PC", "Subdirección de Planificación y Control", 3, "DE", 9),
    ("GP-REM", "Remuneraciones", 4, "SD-GP", 1),
    ("GP-PA", "Procesos Administrativos", 4, "SD-GP", 2),
    ("GP-FD", "Formación y Desarrollo", 4, "SD-GP", 3),
    ("AF-CL", "Compras y Logística", 4, "SD-AF", 1),
    ("AF-TI", "Tecnologías de la Información", 4, "SD-AF", 2),
    ("AF-FIN", "Finanzas", 4, "SD-AF", 3),
    ("GT-GT", "Gestión Territorial", 4, "SD-GT", 1),
    ("GT-CAC", "Coordinación de Atención Ciudadana", 4, "SD-GT", 2),
    ("AT-MC", "Mejora Continua", 4, "UATP", 1),
    ("AT-MS", "Monitoreo y Seguimiento", 4, "UATP", 2),
    ("PC-INF", "Infraestructura", 4, "SD-PC", 1),
    ("PC-MAN", "Mantenimiento", 4, "SD-PC", 2),
    ("PC-CG", "Control de Gestión", 4, "SD-PC", 3),
]

# Nivel que debe tener el padre de una unidad de cada nivel (None = es la raíz).
PARENT_LEVEL = {1: None, 2: 1, 3: 1, 4: 3, 5: 4}
# Los niveles 2 y 3 cuelgan del 1; una unidad de nivel 2 no puede tener hijas.
CANNOT_HAVE_CHILDREN = {2}

CODE_RE = re.compile(r"[A-Z0-9]+(-[A-Z0-9]+)*")


class UnitStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass
class HeadCandidate:
    """Lo que `units` necesita saber de un usuario para fijarlo como jefatura.

    Lo calcula el controller con `users_service` y se lo pasa al service como parámetro:
    así `units` no importa `users` (ADR-013, evita el ciclo users <-> units).
    """
    id: str
    active: bool
    is_slep_staff: bool
    unit_id: Optional[str]


class UnitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(..., min_length=2, max_length=12)
    name: str = Field(..., min_length=1, max_length=120)
    level: int = Field(..., ge=1, le=5)
    parent_id: Optional[str] = Field(None, max_length=24)
    order: int = Field(0, ge=0, le=1000)

    @field_validator("code")
    @classmethod
    def _code(cls, v):
        v = v.upper()
        if not CODE_RE.fullmatch(v):
            raise ValueError("code debe ser un slug en mayúsculas (letras, dígitos y guiones)")
        return v


class UnitUpdate(BaseModel):
    """Renombrar solo cambia `name` y `order`: code, level, parent_id y ancestors no se editan."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    order: Optional[int] = Field(None, ge=0, le=1000)


class UnitMove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_id: str = Field(..., min_length=24, max_length=24)


class UnitHead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: Optional[str] = Field(None, min_length=24, max_length=24)


class HeadRef(BaseModel):
    """Jefatura expandida: solo id y nombre a mostrar, sin correo ni teléfono."""
    id: str
    display_name: str


class Unit(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(..., alias="_id")
    code: str
    name: str
    level: int
    parent_id: Optional[str] = None
    ancestors: List[str] = []
    head_user_id: Optional[str] = None
    head: Optional[HeadRef] = None
    order: int = 0
    status: str


class UnitNode(Unit):
    children: List["UnitNode"] = []


UnitNode.model_rebuild()
