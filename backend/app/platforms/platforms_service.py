from typing import List, Optional

from app.database.database_service import db_service
from app.platforms.platforms_entity import PLATFORMS_SEED, PlatformUpdate


class PlatformsService:
    async def ensure_bootstrap_platforms(self) -> None:
        """Siembra iam, datos y selloverde solo si la colección está vacía."""
        if await db_service.db.platforms.count_documents({}) == 0:
            await db_service.db.platforms.insert_many([dict(p) for p in PLATFORMS_SEED])

    async def find_all(self) -> List[dict]:
        return [d async for d in db_service.db.platforms.find({}).sort("_id", 1)]

    async def find_by_id(self, platform_id: str) -> Optional[dict]:
        if not isinstance(platform_id, str):
            return None
        return await db_service.db.platforms.find_one({"_id": platform_id})

    async def update(self, platform_id: str, data: PlatformUpdate) -> Optional[dict]:
        changes = {k: (v.value if hasattr(v, "value") else v) for k, v in data.model_dump().items() if v is not None}
        if changes:
            result = await db_service.db.platforms.update_one({"_id": platform_id}, {"$set": changes})
            if result.matched_count == 0:
                return None
        return await self.find_by_id(platform_id)

    async def allowed_roles(self, platform_id: str) -> Optional[List[str]]:
        """Roles válidos de la plataforma, o None si no existe. Lo usa `users` para validar accesos."""
        doc = await self.find_by_id(platform_id)
        return None if doc is None else list(doc.get("roles", []))


platforms_service = PlatformsService()
