"""portal_entity.py — temas y recursos del portal (ADR-021)."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Solo http(s): una URL `javascript:` guardada aquí se ejecutaría al hacer clic en el enlace.
_URL = r"^https?://\S+$"
_ID = r"^[0-9a-f]{24}$"

Visibility = Literal["org", "restricted"]
COVER_MAX_BYTES = 512 * 1024       # carátula: el frontend la reduce antes de subir; el servidor igual lo exige
CATASTRO_RESTRICTED = 2            # política B.4: nivel 2 nace restringido; 0 y 1, abierto a la organización


class TopicCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=80)
    parent_id: Optional[str] = Field(None, pattern=_ID)      # máximo dos niveles: el padre no puede tener padre


class TopicUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=80)


class Topic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(..., alias="_id")
    name: str
    parent_id: Optional[str] = None


class ResourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(..., min_length=1, max_length=120)
    url: str = Field(..., max_length=500, pattern=_URL)
    description: Optional[str] = Field(None, max_length=500)
    topic_id: str = Field(..., pattern=_ID)
    unit_id: Optional[str] = Field(None, pattern=_ID)         # unidad dueña (la responsable); no da permisos
    catastro_level: int = Field(..., ge=0, le=2)


class ResourceUpdate(BaseModel):
    """Todo opcional. `visibility` solo la cambia `iam/admin` (el controller lo exige)."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: Optional[str] = Field(None, min_length=1, max_length=120)
    url: Optional[str] = Field(None, max_length=500, pattern=_URL)
    description: Optional[str] = Field(None, max_length=500)
    topic_id: Optional[str] = Field(None, pattern=_ID)
    unit_id: Optional[str] = Field(None, pattern=_ID)
    catastro_level: Optional[int] = Field(None, ge=0, le=2)
    visibility: Optional[Visibility] = None


class Resource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(..., alias="_id")
    title: str
    url: str
    description: Optional[str] = None
    platform: str
    topic_id: str
    unit_id: Optional[str] = None
    catastro_level: int
    visibility: Visibility
    has_cover: bool = False
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
