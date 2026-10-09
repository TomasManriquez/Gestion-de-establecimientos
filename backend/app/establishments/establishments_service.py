import math
from typing import List, Optional
from app.database.database_service import db_service
from app.establishments.establishments_entity import EstablishmentUpdate, RedactedPlaceholderError

REDACTED = "[REDACTED]"

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

    async def existing_rbds(self, rbds) -> set:
        """Subconjunto de `rbds` que existe en `establishments`, con una sola consulta.
        Lo usan `users` (alta y edición) y `counterparts` para validar referencias (L5)."""
        rbds = [r for r in set(rbds) if isinstance(r, str)]
        if not rbds:
            return set()
        cursor = db_service.db.establishments.find({"rbd": {"$in": rbds}}, {"rbd": 1})
        return {d["rbd"] async for d in cursor}

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

    async def _resolve_redacted_markers(self, rbd: str, set_data: dict) -> None:
        """Un cliente que recibió el detalle redactado y lo reenvía completo en el PUT no debe
        destruir las credenciales reales (EditFicha.jsx:35 y :173-175, ver 04 §3.2).

        Si un secreto llega como "[REDACTED]" se conserva el valor almacenado, siempre que haya
        uno equivalente: misma posición y mismo `name` en las licencias. Si no, se rechaza.
        """
        licenses = set_data.get("licenses") or []
        ssid_marker = (set_data.get("connectivity") or {}).get("ssid_password") == REDACTED
        if not ssid_marker and not any(lic.get("password") == REDACTED for lic in licenses):
            return
        stored = await db_service.db.establishments.find_one({"rbd": rbd}) or {}
        stored_licenses = stored.get("licenses") or []
        for i, lic in enumerate(licenses):
            if lic.get("password") != REDACTED:
                continue
            prev = stored_licenses[i] if i < len(stored_licenses) else None
            if prev is None or prev.get("name") != lic.get("name") or not prev.get("password"):
                raise RedactedPlaceholderError(f"licenses[{i}].password")
            lic["password"] = prev["password"]
        if ssid_marker:
            prev_ssid = (stored.get("connectivity") or {}).get("ssid_password")
            if not prev_ssid:
                raise RedactedPlaceholderError("connectivity.ssid_password")
            set_data["connectivity"]["ssid_password"] = prev_ssid

    async def update_by_rbd(self, rbd: str, update_data: EstablishmentUpdate,
                            include_sensitive: bool = True) -> Optional[dict]:
        """`include_sensitive` decide si la respuesta lleva las credenciales en claro. El controller
        lo fija según el rol (antes se devolvía siempre sin redactar: D4)."""
        # Filter out None values
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}

        # Flatten nested structures to avoid overwriting the whole object if we only edit a part
        # However, to be simple and safe, we can just replace the top-level objects that were provided.
        # Let's check what fields we have: general_info, connectivity, printers, licenses.
        set_data = {}
        for field in ["name", "comuna", "area_type", "address", "location", "general_info", "connectivity", "printers", "licenses"]:
            if field in update_dict:
                set_data[field] = update_dict[field]

        if not set_data:
            return await self.find_by_rbd(rbd, include_sensitive=include_sensitive)

        await self._resolve_redacted_markers(rbd, set_data)

        result = await db_service.db.establishments.update_one(
            {"rbd": rbd},
            {"$set": set_data}
        )

        if result.modified_count > 0 or result.matched_count > 0:
            return await self.find_by_rbd(rbd, include_sensitive=include_sensitive)
        return None

establishments_service = EstablishmentsService()
