from typing import List, Optional
from app.database.database_service import db_service
from app.metrics.metrics_entity import MetricCreate, MetricUpdate

class MetricsService:
    async def find_by_rbd(self, rbd: str) -> List[dict]:
        # Return historical metrics, sorted by year ascending
        cursor = db_service.db.metrics.find({"rbd": rbd}).sort("year", 1)
        metrics = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            metrics.append(doc)
        return metrics

    async def find_by_rbd_and_year(self, rbd: str, year: int) -> Optional[dict]:
        doc = await db_service.db.metrics.find_one({"rbd": rbd, "year": year})
        if doc:
            doc["_id"] = str(doc["_id"])
            return doc
        return None

    async def find_by_year(self, year: int) -> List[dict]:
        cursor = db_service.db.metrics.find({"year": year})
        metrics = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            metrics.append(doc)
        return metrics

    async def upsert(self, rbd: str, year: int, data: MetricUpdate) -> Optional[dict]:
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        
        result = await db_service.db.metrics.update_one(
            {"rbd": rbd, "year": year},
            {"$set": update_dict},
            upsert=True
        )
        return await self.find_by_rbd_and_year(rbd, year)

metrics_service = MetricsService()
