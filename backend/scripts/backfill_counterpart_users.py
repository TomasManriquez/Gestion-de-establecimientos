"""
Vincula contrapartes existentes con usuarios del sistema (ADR-011).

Empareja `counterparts.email` con `users.email` (normalizados: sin espacios y en minúsculas) y
escribe `counterparts.user_id`. El vínculo es opcional: lo que no empareja no se toca.

Por defecto es un ENSAYO (dry-run): solo informa. Para escribir hay que pasar --apply.
No pisa un `user_id` ya existente salvo con --overwrite. Un correo que coincide con más de un
usuario no puede ocurrir (el índice de `users.email` es único), pero se informa si lo hubiera.

Uso:
    cd backend
    python scripts/backfill_counterpart_users.py            # ensayo
    python scripts/backfill_counterpart_users.py --apply    # escribe
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.config import settings  # noqa: E402


def normalize(email) -> str:
    return (email or "").strip().lower()


async def plan(db, overwrite: bool = False) -> dict:
    """Calcula qué se vincularía. Es una función pura sobre la base: no escribe."""
    users = {}
    async for u in db.users.find({"email": {"$exists": True}}, {"email": 1}):
        users.setdefault(normalize(u["email"]), []).append(u["_id"])
    result = {"link": [], "already_linked": [], "no_email": [], "no_match": [], "ambiguous": []}
    async for cp in db.counterparts.find({}):
        email = normalize(cp.get("email"))
        if not email:
            result["no_email"].append(cp["_id"])
        elif cp.get("user_id") and not overwrite:
            result["already_linked"].append(cp["_id"])
        elif email not in users:
            result["no_match"].append(cp["_id"])
        elif len(users[email]) > 1:
            result["ambiguous"].append(cp["_id"])
        else:
            result["link"].append((cp["_id"], users[email][0]))
    return result


async def main(apply: bool, overwrite: bool) -> None:
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    result = await plan(db, overwrite)
    for key, rows in result.items():
        print(f"{key:15} {len(rows)}")
    if not apply:
        print("\nEnsayo: no se escribió nada. Usa --apply para vincular.")
    else:
        for cp_id, user_id in result["link"]:
            await db.counterparts.update_one({"_id": cp_id}, {"$set": {"user_id": user_id}})
        print(f"\nVinculadas {len(result['link'])} contrapartes.")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="escribe los vínculos (por defecto, ensayo)")
    parser.add_argument("--overwrite", action="store_true", help="reemplaza un user_id ya existente")
    args = parser.parse_args()
    asyncio.run(main(args.apply, args.overwrite))
