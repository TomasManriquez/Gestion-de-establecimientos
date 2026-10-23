from app.database.database_service import db_service
from app.database.connectivity_migration import has_other, is_migrated, migrate_connectivity, without_internet

def connectivity_breakdown(conns) -> list:
    """Cuenta establecimientos por bloque de conectividad. Uno puede contar en varios bloques."""
    counts = {"Conectividad 2030": 0, "Banda ancha móvil": 0, "Otro tipo de conexión": 0, "Sin internet": 0}
    for conn in conns:
        conn = conn or {}
        if not is_migrated(conn):
            conn = migrate_connectivity(conn)[0]
        counts["Conectividad 2030"] += bool((conn.get("program_2030") or {}).get("enabled"))
        counts["Banda ancha móvil"] += bool(conn.get("bam"))
        counts["Otro tipo de conexión"] += has_other(conn.get("other"))
        counts["Sin internet"] += without_internet(conn)
    return [{"label": k, "value": v} for k, v in counts.items()]


class AnalyticsService:
    async def get_kpis(self) -> dict:
        # 1. Total Establishments
        total_est = await db_service.db.establishments.count_documents({})
        
        # 2. Total enrollment and teachers (year 2026)
        enrollment_teachers_pipeline = [
            {"$match": {"year": 2026}},
            {"$group": {
                "_id": None,
                "total_enrollment": {"$sum": "$enrollment"},
                "total_teachers": {"$sum": "$num_teachers"}
            }}
        ]
        et_cursor = db_service.db.metrics.aggregate(enrollment_teachers_pipeline)
        et_data = {"total_enrollment": 0, "total_teachers": 0}
        async for doc in et_cursor:
            et_data["total_enrollment"] = doc.get("total_enrollment", 0)
            et_data["total_teachers"] = doc.get("total_teachers", 0)

        # 3. Total enrollment 2025 (for comparison)
        enrollment_25_pipeline = [
            {"$match": {"year": 2025}},
            {"$group": {"_id": None, "total_enrollment": {"$sum": "$enrollment"}}}
        ]
        e25_cursor = db_service.db.metrics.aggregate(enrollment_25_pipeline)
        enrollment_2025 = 0
        async for doc in e25_cursor:
            enrollment_2025 = doc.get("total_enrollment", 0)

        # 4. Total unique communes
        communes = await db_service.db.establishments.distinct("comuna")
        total_communes = len(communes)

        return {
            "total_establishments": total_est,
            "total_enrollment_2026": et_data["total_enrollment"],
            "total_enrollment_2025": enrollment_2025,
            "total_teachers_2026": et_data["total_teachers"],
            "total_communes": total_communes
        }

    async def get_charts_data(self) -> dict:
        # 1. Enrollment by Area Type (Urban vs Rural) for Year 2026
        area_pipeline = [
            {"$match": {"year": 2026}},
            {
                "$lookup": {
                    "from": "establishments",
                    "localField": "rbd",
                    "foreignField": "rbd",
                    "as": "est"
                }
            },
            {"$unwind": "$est"},
            {
                "$group": {
                    "_id": "$est.area_type",
                    "value": {"$sum": "$enrollment"}
                }
            },
            {"$project": {"label": "$_id", "value": 1, "_id": 0}}
        ]
        area_cursor = db_service.db.metrics.aggregate(area_pipeline)
        area_data = []
        async for doc in area_cursor:
            if doc.get("label"):
                area_data.append(doc)

        # 2. Enrollment by Commune for Year 2026
        commune_pipeline = [
            {"$match": {"year": 2026}},
            {
                "$lookup": {
                    "from": "establishments",
                    "localField": "rbd",
                    "foreignField": "rbd",
                    "as": "est"
                }
            },
            {"$unwind": "$est"},
            {
                "$group": {
                    "_id": "$est.comuna",
                    "value": {"$sum": "$enrollment"}
                }
            },
            {"$project": {"label": "$_id", "value": 1, "_id": 0}}
        ]
        commune_cursor = db_service.db.metrics.aggregate(commune_pipeline)
        commune_data = []
        async for doc in commune_cursor:
            if doc.get("label"):
                commune_data.append(doc)

        # 3. Category count
        category_pipeline = [
            {
                "$group": {
                    "_id": "$general_info.category",
                    "value": {"$sum": 1}
                }
            },
            {"$project": {"label": "$_id", "value": 1, "_id": 0}}
        ]
        cat_cursor = db_service.db.establishments.aggregate(category_pipeline)
        category_data = []
        async for doc in cat_cursor:
            # Clean category label (remove numbers like '7. LICEO' -> 'LICEO')
            label = doc.get("label") or "Sin Categoría"
            if "." in label:
                label = label.split(".", 1)[1].strip()
            category_data.append({"label": label, "value": doc["value"]})

        # 4. Conectividad por bloque. Un establecimiento cuenta en cada bloque que tenga (2030, BAM,
        #    otro tipo); «Sin internet» se calcula. Un documento aún sin migrar se convierte al vuelo.
        conns = [doc.get("connectivity") async for doc in db_service.db.establishments.find({}, {"connectivity": 1})]
        connectivity_data = connectivity_breakdown(conns)

        return {
            "enrollment_by_area": area_data,
            "enrollment_by_commune": commune_data,
            "establishments_by_category": category_data,
            "establishments_by_connectivity": connectivity_data
        }

    async def get_enrollment_dataset(self) -> dict:
        """Datos del tablero de matrícula por establecimiento y año (ADR-018). Sin año fijo: los años
        salen de los registros de `metrics`. En la carga inicial un 0 en docentes, asistentes o
        asistencia significa «sin dato»; en matrícula el 0 es real (establecimiento sin alumnos)."""
        projection = {"rbd": 1, "name": 1, "comuna": 1, "area_type": 1, "general_info.category": 1,
                      "status": 1, "closed_year": 1}
        establishments = []
        async for d in db_service.db.establishments.find({}, projection):
            establishments.append({
                "rbd": d["rbd"], "name": d.get("name", ""), "comuna": d.get("comuna", ""),
                "area_type": d.get("area_type", ""), "category": (d.get("general_info") or {}).get("category", "") or "",
                "status": d.get("status") or "active", "closed_year": d.get("closed_year"),
            })
        known = {e["rbd"] for e in establishments}

        def positive(v, cast):
            try:
                n = cast(v)
            except (TypeError, ValueError):
                return None
            return n if n > 0 else None

        points = []
        async for m in db_service.db.metrics.find({}):
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
