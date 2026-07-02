from app.database.database_service import db_service

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

        # 4. Connectivity providers count
        conn_pipeline = [
            {
                "$group": {
                    "_id": "$connectivity.internet_provider",
                    "value": {"$sum": 1}
                }
            },
            {"$project": {"label": "$_id", "value": 1, "_id": 0}}
        ]
        conn_cursor = db_service.db.establishments.aggregate(conn_pipeline)
        connectivity_data = []
        async for doc in conn_cursor:
            label = doc.get("label")
            if not label:
                label = "Sin Conexión"
            connectivity_data.append({"label": label, "value": doc["value"]})

        return {
            "enrollment_by_area": area_data,
            "enrollment_by_commune": commune_data,
            "establishments_by_category": category_data,
            "establishments_by_connectivity": connectivity_data
        }

analytics_service = AnalyticsService()
