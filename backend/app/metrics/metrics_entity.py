from pydantic import BaseModel, Field
from typing import Optional

class MetricBase(BaseModel):
    rbd: str
    year: int
    enrollment: int
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

class MetricUpdate(BaseModel):
    enrollment: Optional[int] = None
    attendance_avg: Optional[str] = None
    ive_basica: Optional[float] = None
    ive_media: Optional[float] = None
    num_teachers: Optional[int] = None
    num_assistants: Optional[int] = None
    grade_avg: Optional[float] = None
    promoted: Optional[int] = None
    failed: Optional[int] = None
    transferred: Optional[int] = None
    dropouts: Optional[int] = None
    desempeno_basica: Optional[str] = None
    desempeno_media: Optional[str] = None
    ptje_nem: Optional[float] = None
    ptje_ranking: Optional[float] = None
    score_lectura: Optional[float] = None
    score_matematica1: Optional[float] = None
    score_matematica2: Optional[float] = None
    score_historia: Optional[float] = None
    score_ciencia: Optional[float] = None
    total_rendidores: Optional[int] = None
    tasa_promocion: Optional[float] = None
    tasa_reprobacion: Optional[float] = None
    tasa_desercion: Optional[float] = None
    tasa_retencion: Optional[float] = None

class Metric(MetricBase):
    id: str = Field(..., alias="_id")

    class Config:
        populate_by_name = True
