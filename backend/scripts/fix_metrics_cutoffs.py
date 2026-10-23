"""Corrige dos herencias de la carga inicial en `metrics` (2026-10-23).

1. La asistencia de 2025 se copió también en el registro 2026. Se vacía en 2026 cuando es idéntica
   a la de 2025 del mismo establecimiento (si difiere, alguien la cargó a mano y no se toca).
2. La matrícula 2026 es un corte de marzo («MATRÍCULA MARZO 2026»). Se marca `enrollment_as_of`
   = "2026-03" donde esté vacío.
3. Los establecimientos sin `status` quedan como "active".

    python scripts/fix_metrics_cutoffs.py            # vista previa (no modifica nada)
    python scripts/fix_metrics_cutoffs.py --apply    # escribe

Idempotente. Usa MONGODB_URL y DATABASE_NAME del entorno. Respaldo antes (`scripts/backup-mongo.sh`).
"""
import asyncio
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient


async def main(apply: bool) -> int:
    client = AsyncIOMotorClient(os.environ.get("MONGODB_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DATABASE_NAME", "slep_llanquihue")]

    att_2025 = {d["rbd"]: d.get("attendance_avg") async for d in db.metrics.find({"year": 2025}, {"rbd": 1, "attendance_avg": 1})}
    copied, kept = [], []
    async for d in db.metrics.find({"year": 2026}, {"rbd": 1, "attendance_avg": 1}):
        value = d.get("attendance_avg")
        if not value:
            continue
        (copied if att_2025.get(d["rbd"]) == value else kept).append(d["rbd"])
    # `None` en `$in` también encuentra los documentos que no tienen el campo
    no_cutoff = await db.metrics.count_documents({"year": 2026, "enrollment_as_of": {"$in": ["", None]}})
    no_status = await db.establishments.count_documents({"status": {"$exists": False}})

    print(f"Registros 2026 con la asistencia de 2025 copiada: {len(copied)} (se vacían)")
    if kept:
        print(f"Registros 2026 con asistencia distinta a la de 2025 (no se tocan): {', '.join(sorted(kept))}")
    print(f"Registros 2026 sin corte de matrícula: {no_cutoff} (se marcan 2026-03)")
    print(f"Establecimientos sin estado: {no_status} (quedan activos)")
    if not apply:
        print("Modo vista previa: no se modificó nada. Use --apply para escribir.")
        return 0

    r1 = await db.metrics.update_many({"year": 2026, "rbd": {"$in": copied}}, {"$set": {"attendance_avg": "", "attendance_as_of": ""}})
    r2 = await db.metrics.update_many({"year": 2026, "enrollment_as_of": {"$in": ["", None]}},
                                      {"$set": {"enrollment_as_of": "2026-03"}})
    r3 = await db.establishments.update_many({"status": {"$exists": False}}, {"$set": {"status": "active", "closed_year": None}})
    print(f"Modificados: asistencia {r1.modified_count} · corte {r2.modified_count} · estado {r3.modified_count}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--apply" in sys.argv[1:])))
