from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

# Se siembra solo con la colección vacía (ADR-009). `iam` es una plataforma lógica.
PLATFORMS_SEED = [
    {"_id": "iam", "name": "Administración de usuarios", "base_url": "https://datos.slepllanquihue.gob.cl",
     "roles": ["admin"], "status": "active"},
    {"_id": "datos", "name": "Gestión de Establecimientos", "base_url": "https://datos.slepllanquihue.gob.cl",
     "roles": ["admin", "editor", "viewer"], "status": "active"},
    {"_id": "selloverde", "name": "Sello Verde", "base_url": "https://selloverde.slepllanquihue.gob.cl",
     "roles": ["admin", "editor", "viewer"], "status": "active"},
]


class PlatformStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class PlatformUpdate(BaseModel):
    """Solo nombre y estado. `roles` y `_id` no se editan por API."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    status: Optional[PlatformStatus] = None


class Platform(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(..., alias="_id")
    name: str
    base_url: str
    roles: List[str]
    status: str
