from typing import Dict, List, Optional

from pydantic import BaseModel


class EnrollmentEstablishment(BaseModel):
    rbd: str
    name: str
    comuna: str
    area_type: str
    category: str = ""                 # con su prefijo numérico («7. LICEO POLITÉCNICO»)
    status: str = "active"
    closed_year: Optional[int] = None


class EnrollmentPoint(BaseModel):
    """Un establecimiento en un año. `None` = sin dato (distinto de 0, que es un valor real)."""
    rbd: str
    year: int
    enrollment: Optional[int] = None
    enrollment_as_of: str = ""          # AAAA-MM si es un corte parcial; "" = año completo
    attendance: Optional[float] = None  # proporción 0–1
    attendance_as_of: str = ""
    teachers: Optional[int] = None
    assistants: Optional[int] = None


class IndicatorInfo(BaseModel):
    label: str
    years: List[int]                    # años con al menos un dato


class EnrollmentDataset(BaseModel):
    """Contrato de GET /api/analytics/enrollment (ADR-018): datos por establecimiento y año; el
    tablero calcula filtros, totales y comparaciones en el navegador."""
    establishments: List[EnrollmentEstablishment]
    points: List[EnrollmentPoint]
    years: List[int]                    # años con algún registro, ascendente
    indicators: Dict[str, IndicatorInfo]
