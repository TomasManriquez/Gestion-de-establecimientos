from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Tipos de recurso que admiten concesión (ADR-021). Se amplía con cada vista nueva.
ResourceType = Literal["portal_resource", "vault"]
ALL_RESOURCES = "*"                 # concesión sobre todos los recursos de ese tipo
SUBJECT_USER = "user"
SUBJECT_UNIT = "unit"               # fase 4: cubre a quien tenga `unit_id` = esa unidad (y, con include_subunits, sus descendientes)


class GrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    resource_type: ResourceType
    resource_id: str = Field(..., pattern=r"^(\*|[A-Za-z0-9_-]{1,64})$")
    user_id: Optional[str] = Field(None, pattern=r"^[0-9a-f]{24}$")
    unit_id: Optional[str] = Field(None, pattern=r"^[0-9a-f]{24}$")
    include_subunits: bool = False

    @model_validator(mode="after")
    def _one_subject(self):
        if (self.user_id is None) == (self.unit_id is None):
            raise ValueError("Indica una persona (user_id) o una unidad (unit_id), no ambas")
        if self.user_id is not None and self.include_subunits:
            raise ValueError("include_subunits solo aplica a una unidad")
        return self


class Grant(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(..., alias="_id")
    resource_type: str
    resource_id: str
    subject_type: str
    subject_id: str
    include_subunits: bool = False
    granted_by: str
    granted_at: datetime
