from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Tipos de recurso que admiten concesión (ADR-021). Se amplía con cada vista nueva.
ResourceType = Literal["portal_resource", "vault"]
ALL_RESOURCES = "*"                 # concesión sobre todos los recursos de ese tipo
SUBJECT_USER = "user"               # shortcut: solo personas; sumar "unit" cuando exista el registro de unidades por persona (ADR-021)


class GrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    resource_type: ResourceType
    resource_id: str = Field(..., pattern=r"^(\*|[A-Za-z0-9_-]{1,64})$")
    user_id: str = Field(..., pattern=r"^[0-9a-f]{24}$")


class Grant(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(..., alias="_id")
    resource_type: str
    resource_id: str
    subject_type: str
    subject_id: str
    granted_by: str
    granted_at: datetime
