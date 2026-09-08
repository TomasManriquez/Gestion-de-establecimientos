import math
from typing import List, Optional
from app.database.database_service import db_service
from app.establishments.establishments_entity import EstablishmentUpdate

LISTING_PROJECTION = {
    "_id": 1,
    "rbd": 1,
    "rbd_full": 1,
    "name": 1,
    "comuna": 1,
    "area_type": 1,
    "address": 1,
    "general_info.category": 1,
    "general_info.adp": 1,
    "general_info.covertura": 1,
}

class EstablishmentsService:
    async def find_all(
        self,
        search: Optional[str] = None,
        comuna: Optional[str] = None,
        area_type: Optional[str] = None,
        category: Optional[str] = None,
        coverage: Optional[str] = None,
        adp: Optional[str] = None,
        page: int = 1,
        page_size: int = 100
    ) -> dict:
        query = {}
        
        # Search by name or RBD (starts with/contains, case-insensitive)
        if search:
            # Check if search is numeric (could be RBD)
            if search.isdigit():
                query["rbd"] = {"$regex": f"^{search}", "$options": "i"}
            else:
                query["$or"] = [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"rbd": {"$regex": search, "$options": "i"}},
                    {"comuna": {"$regex": search, "$options": "i"}}
                ]

        if comuna:
            query["comuna"] = {"$regex": f"^{comuna}$", "$options": "i"}
        
        if area_type:
            query["area_type"] = {"$regex": f"^{area_type}$", "$options": "i"}
        # el dato de category tiene conflictos con () de establecimiento (curso combinado) por lo que se hace comparacion directa, sin regex.
        if category:
            query["general_info.category"] = category

        if coverage:
            query["general_info.covertura"] = {"$regex": f"^{coverage}", "$options": "i"}
            
        if adp:
            query["general_info.adp"] = {"$regex": f"^{adp}$", "$options": "i"}

        total = await db_service.db.establishments.count_documents(query)
        skip = (page - 1) * page_size

        cursor = db_service.db.establishments.find(query, LISTING_PROJECTION) \
                                              .sort("name", 1) \
                                              .skip(skip) \
                                              .limit(page_size)
        items = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            gi = doc.pop("general_info", {}) or {}
            doc["category"] = gi.get("category", "")
            doc["adp"] = gi.get("adp", "")
            doc["covertura"] = gi.get("covertura", "")
            items.append(doc)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total > 0 else 1,
        }

    async def find_by_rbd(self, rbd: str, include_sensitive: bool = False) -> Optional[dict]:
        doc = await db_service.db.establishments.find_one({"rbd": rbd})
        if doc:
            doc["_id"] = str(doc["_id"])
            if not include_sensitive:
                for lic in doc.get("licenses", []):
                    if lic.get("password"):
                        lic["password"] = "[REDACTED]"
                if doc.get("connectivity", {}).get("ssid_password"):
                    doc["connectivity"]["ssid_password"] = "[REDACTED]"
            return doc
        return None

    async def update_by_rbd(self, rbd: str, update_data: EstablishmentUpdate) -> Optional[dict]:
        # Filter out None values
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        
        # Flatten nested structures to avoid overwriting the whole object if we only edit a part
        # However, to be simple and safe, we can just replace the top-level objects that were provided.
        # Let's check what fields we have: general_info, connectivity, printers, licenses.
        set_data = {}
        for field in ["name", "comuna", "area_type", "address", "general_info", "connectivity", "printers", "licenses"]:
            if field in update_dict:
                set_data[field] = update_dict[field]

        if not set_data:
            return await self.find_by_rbd(rbd, include_sensitive=True)

        result = await db_service.db.establishments.update_one(
            {"rbd": rbd},
            {"$set": set_data}
        )
        
        if result.modified_count > 0 or result.matched_count > 0:
            return await self.find_by_rbd(rbd, include_sensitive=True)
        return None

establishments_service = EstablishmentsService()
