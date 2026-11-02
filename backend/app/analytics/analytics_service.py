from app.establishments.establishments_service import establishments_service
from app.metrics.metrics_service import metrics_service


class AnalyticsService:
    async def get_enrollment_dataset(self) -> dict:
        """Datos del tablero de matrícula por establecimiento y año (ADR-018). Sin año fijo: los años
        salen de los registros de `metrics`. En la carga inicial un 0 en docentes, asistentes o
        asistencia significa «sin dato»; en matrícula el 0 es real (establecimiento sin alumnos).
        Lee solo a través de los servicios de `establishments` y `metrics` (ADR-019)."""
        establishments = await establishments_service.list_for_enrollment()
        known = {e["rbd"] for e in establishments}

        def positive(v, cast):
            try:
                n = cast(v)
            except (TypeError, ValueError):
                return None
            return n if n > 0 else None

        points = []
        for m in await metrics_service.find_all():
            if m.get("rbd") not in known:
                continue
            enrollment = m.get("enrollment")
            points.append({
                "rbd": m["rbd"], "year": int(m["year"]),
                "enrollment": int(enrollment) if isinstance(enrollment, (int, float)) else None,
                "enrollment_as_of": m.get("enrollment_as_of") or "",
                "attendance": positive(m.get("attendance_avg"), float),
                "attendance_as_of": m.get("attendance_as_of") or "",
                "teachers": positive(m.get("num_teachers"), int),
                "assistants": positive(m.get("num_assistants"), int),
            })
        points.sort(key=lambda p: (p["year"], p["rbd"]))

        def years_with(key, test=lambda v: v is not None):
            return sorted({p["year"] for p in points if test(p[key])})

        return {
            "establishments": establishments,
            "points": points,
            "years": sorted({p["year"] for p in points}),
            "indicators": {
                "enrollment": {"label": "Matrícula", "years": years_with("enrollment", lambda v: bool(v))},
                "attendance": {"label": "Asistencia", "years": years_with("attendance")},
                "teachers": {"label": "Docentes", "years": years_with("teachers")},
                "assistants": {"label": "Asistentes de la educación", "years": years_with("assistants")},
            },
        }


analytics_service = AnalyticsService()
