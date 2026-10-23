from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional

class MetricBase(BaseModel):
    rbd: str
    year: int
    enrollment: int = 0
    attendance_avg: Optional[str] = ""
    ive_basica: Optional[float] = 0.0
    ive_media: Optional[float] = 0.0
    num_teachers: Optional[int] = 0
    num_assistants: Optional[int] = 0
    grade_avg: Optional[float] = 0.0
    promoted: Optional[int] = 0
    failed: Optional[int] = 0
    transferred: Optional[int] = 0
    dropouts: Optional[int] = 0
    desempeno_basica: Optional[str] = ""
    desempeno_media: Optional[str] = ""
    ptje_nem: Optional[float] = 0.0
    ptje_ranking: Optional[float] = 0.0
    score_lectura: Optional[float] = 0.0
    score_matematica1: Optional[float] = 0.0
    score_matematica2: Optional[float] = 0.0
    score_historia: Optional[float] = 0.0
    score_ciencia: Optional[float] = 0.0
    total_rendidores: Optional[int] = 0
    tasa_promocion: Optional[float] = 0.0
    tasa_reprobacion: Optional[float] = 0.0
    tasa_desercion: Optional[float] = 0.0
    tasa_retencion: Optional[float] = 0.0

class MetricCreate(MetricBase):
    pass

# Rangos de lo que se puede escribir (la ficha edita estas métricas). Los valores ya cargados
# que estén fuera de rango (p. ej. una retención de 100,3) se pueden leer, pero un PUT que los
# reenvíe se rechaza con 422: el frontend manda solo los campos que la persona cambió.
_COUNT = dict(ge=0, le=100_000)
_RATE = dict(ge=0, le=100)          # porcentajes 0–100 (tasas)
_FRACTION = dict(ge=0, le=1)        # proporciones 0–1 (IVE)
_SCORE = dict(ge=0, le=1_000)       # puntajes PAES / NEM / ranking


class MetricUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enrollment: Optional[int] = Field(None, **_COUNT)
    attendance_avg: Optional[str] = Field(None, max_length=32)   # proporción 0–1 como texto, por la planilla
    ive_basica: Optional[float] = Field(None, **_FRACTION)
    ive_media: Optional[float] = Field(None, **_FRACTION)
    num_teachers: Optional[int] = Field(None, **_COUNT)
    num_assistants: Optional[int] = Field(None, **_COUNT)
    grade_avg: Optional[float] = Field(None, ge=0, le=7)
    promoted: Optional[int] = Field(None, **_COUNT)
    failed: Optional[int] = Field(None, **_COUNT)
    transferred: Optional[int] = Field(None, **_COUNT)
    dropouts: Optional[int] = Field(None, **_COUNT)
    desempeno_basica: Optional[str] = Field(None, max_length=40)
    desempeno_media: Optional[str] = Field(None, max_length=40)
    ptje_nem: Optional[float] = Field(None, **_SCORE)
    ptje_ranking: Optional[float] = Field(None, **_SCORE)
    score_lectura: Optional[float] = Field(None, **_SCORE)
    score_matematica1: Optional[float] = Field(None, **_SCORE)
    score_matematica2: Optional[float] = Field(None, **_SCORE)
    score_historia: Optional[float] = Field(None, **_SCORE)
    score_ciencia: Optional[float] = Field(None, **_SCORE)
    total_rendidores: Optional[int] = Field(None, **_COUNT)
    tasa_promocion: Optional[float] = Field(None, **_RATE)
    tasa_reprobacion: Optional[float] = Field(None, **_RATE)
    tasa_desercion: Optional[float] = Field(None, **_RATE)
    tasa_retencion: Optional[float] = Field(None, **_RATE)

    @field_validator("attendance_avg")
    @classmethod
    def _attendance_is_a_fraction(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        try:
            value = float(v)
        except ValueError:
            raise ValueError("attendance_avg debe ser una proporción entre 0 y 1")
        if not 0 <= value <= 1:
            raise ValueError("attendance_avg debe ser una proporción entre 0 y 1")
        return v

class Metric(MetricBase):
    id: str = Field(..., alias="_id")

    class Config:
        populate_by_name = True
