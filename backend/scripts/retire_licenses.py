"""Retira el campo `licenses` de `establishments` (N15, F6).

El campo guardaba usuario y contraseña de plataformas externas en claro. La aplicación ya no lo lee
ni lo escribe; este script lo borra de los documentos que aún lo tengan.

    python scripts/retire_licenses.py            # solo cuenta (no modifica nada)
    python scripts/retire_licenses.py --apply    # ejecuta el $unset

Es idempotente. Usa MONGODB_URL y DATABASE_NAME del entorno (mismos nombres que la app). NO imprime
ningún valor de las credenciales. Hacer un respaldo antes (`scripts/backup-mongo.sh`) y, si algún
documento tenía credenciales reales, ROTARLAS en cada plataforma: borrarlas de Mongo no las invalida,
y siguen en los respaldos anteriores.
"""
import asyncio
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient


async def main(apply: bool) -> int:
    client = AsyncIOMotorClient(os.environ.get("MONGODB_URL", "mongodb://localhost:27017"))
    col = client[os.environ.get("DATABASE_NAME", "slep_llanquihue")].establishments
    with_field = await col.count_documents({"licenses": {"$exists": True}})
    with_entries = await col.count_documents({"licenses.0": {"$exists": True}})
    print(f"Documentos con `licenses`: {with_field} (con al menos una credencial: {with_entries})")
    if not apply:
        print("Modo simulación: no se modificó nada. Use --apply para borrar el campo.")
        return 0
    result = await col.update_many({"licenses": {"$exists": True}}, {"$unset": {"licenses": ""}})
    print(f"Documentos modificados: {result.modified_count}")
    if with_entries:
        print("ATENCIÓN: había credenciales guardadas. Rótelas en cada plataforma externa.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--apply" in sys.argv[1:])))
