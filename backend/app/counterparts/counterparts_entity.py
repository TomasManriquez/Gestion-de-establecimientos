from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

class CounterpartOrigin(str, Enum):
    ESTABLECIMIENTO = "ESTABLECIMIENTO"
    SLEP = "SLEP"

class CounterpartRole(str, Enum):
    DIRECTOR = "DIRECTOR"
    UTP_JEFE = "UTP_JEFE"
    PIE_ENCARGADO = "PIE_ENCARGADO"
    CONVIVENCIA_ESCOLAR = "CONVIVENCIA_ESCOLAR"
    INSPECTOR_GENERAL = "INSPECTOR_GENERAL"
    SIGE_ENCARGADO = "SIGE_ENCARGADO"
    TERRITORIAL = "TERRITORIAL"
    RRHH = "RRHH"
    INFRAESTRUCTURA = "INFRAESTRUCTURA"
    COMPRAS = "COMPRAS"
    TI = "TI"
    PAME = "PAME"
    PROFESIONAL_INCLUSION = "PROFESIONAL_INCLUSION"
    PROFESIONAL_AME_NT = "PROFESIONAL_AME_NT"
    PERSONAL_PROCESOS_ADM = "PERSONAL_PROCESOS_ADM"
    GESTOR_INFRAESTRUCTURA = "GESTOR_INFRAESTRUCTURA"
    COMPRADOR = "COMPRADOR"

class CounterpartBase(BaseModel):
    rbd: str
    role: CounterpartRole
    origin: CounterpartOrigin
    name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""

class CounterpartCreate(CounterpartBase):
    pass

class CounterpartUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[CounterpartRole] = None
    origin: Optional[CounterpartOrigin] = None

class Counterpart(CounterpartBase):
    id: str = Field(..., alias="_id")

    class Config:
        populate_by_name = True
