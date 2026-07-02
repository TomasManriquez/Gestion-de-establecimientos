from bson import ObjectId
from typing import List, Optional
from app.database.database_service import db_service
from app.counterparts.counterparts_entity import CounterpartCreate, CounterpartUpdate

class CounterpartsService:
    async def find_by_rbd(self, rbd: str) -> List[dict]:
        cursor = db_service.db.counterparts.find({"rbd": rbd})
        counterparts = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            counterparts.append(doc)
        return counterparts

    async def create(self, data: CounterpartCreate) -> dict:
        doc = data.model_dump()
        result = await db_service.db.counterparts.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return doc

    async def update(self, cp_id: str, data: CounterpartUpdate) -> Optional[dict]:
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        if not update_dict:
            return await self.find_by_id(cp_id)

        result = await db_service.db.counterparts.update_one(
            {"_id": ObjectId(cp_id)},
            {"$set": update_dict}
        )
        if result.matched_count > 0:
            return await self.find_by_id(cp_id)
        return None

    async def delete(self, cp_id: str) -> bool:
        result = await db_service.db.counterparts.delete_one({"_id": ObjectId(cp_id)})
        return result.deleted_count > 0

    async def find_by_id(self, cp_id: str) -> Optional[dict]:
        doc = await db_service.db.counterparts.find_one({"_id": ObjectId(cp_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
            return doc
        return None

counterparts_service = CounterpartsService()
