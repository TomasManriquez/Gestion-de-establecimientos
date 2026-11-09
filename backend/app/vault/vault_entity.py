"""vault_entity.py — credenciales de un establecimiento (ADR-021).

Ningún modelo de salida lleva la contraseña: solo `has_password`. La única forma de leerla es `Reveal`.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

# Solo http(s): una URL `javascript:` guardada aquí se ejecutaría al hacer clic en el enlace.
_URL = r"^https?://\S+$"


class CredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=80)
    username: Optional[str] = Field(None, max_length=120)
    password: str = Field(..., min_length=1, max_length=256)
    url: Optional[str] = Field(None, max_length=500, pattern=_URL)


class CredentialUpdate(BaseModel):
    """Cada campo es opcional; `password` ausente deja la contraseña como está."""
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=80)
    username: Optional[str] = Field(None, max_length=120)
    password: Optional[str] = Field(None, min_length=1, max_length=256)
    url: Optional[str] = Field(None, max_length=500, pattern=_URL)


class Credential(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id")
    rbd: str
    name: str
    username: Optional[str] = None
    url: Optional[str] = None
    has_password: bool = True
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime


class Reveal(BaseModel):
    password: str


# Límite de revelaciones (ADR-021): por persona, ventana fija. Frena y deja huella; no impide.
REVEAL_LIMIT = 100
REVEAL_WINDOW_SECONDS = 60 * 60
