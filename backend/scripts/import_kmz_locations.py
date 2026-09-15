"""
Importa coordenadas (lat/lng) de establecimientos desde un KMZ exportado de Google Earth.

Empareja cada Placemark del KMZ contra backend/establishments.json por comuna +
similitud de nombre, y para cada coincidencia de alta confianza:
  1. Escribe el campo "location" en backend/establishments.json (fuente del seed).
  2. Actualiza directamente el documento en MongoDB (si la base ya está poblada).

Los Placemarks/establecimientos que no logran una coincidencia confiable quedan
listados al final para carga manual desde la ficha (Editar > Latitud/Longitud).

Uso:
    cd backend
    python scripts/import_kmz_locations.py
"""
import asyncio
import difflib
import json
import os
import re
import sys
import unicodedata
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

KMZ_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "SLEP_EE.kmz")
ESTABLISHMENTS_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "establishments.json")

MATCH_THRESHOLD = 0.80

STOPWORDS = {
    "ESCUELA", "LICEO", "COLEGIO", "VTF", "JARDIN", "INFANTIL", "SALA", "CUNA",
    "RURAL", "BASICA", "ESPECIAL", "DIFERENCIAL", "POLITECNICO", "BICENTENARIO",
    "EXCELENCIA", "DE", "Y", "DIFUSION", "ARTISTICA",
}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def norm_full(text: str) -> str:
    text = strip_accents(text).upper()
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_core_tokens(text: str) -> set:
    return {t for t in norm_full(text).split() if t not in STOPWORDS}


def score_pair(name_a: str, name_b: str) -> float:
    seq_score = difflib.SequenceMatcher(None, norm_full(name_a), norm_full(name_b)).ratio()
    tokens_a, tokens_b = norm_core_tokens(name_a), norm_core_tokens(name_b)
    if tokens_a and tokens_b:
        overlap = len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))
    else:
        overlap = 0.0
    return max(seq_score, overlap)


def parse_kmz_placemarks(kmz_path: str) -> list[dict]:
    with zipfile.ZipFile(kmz_path) as z:
        kml_content = z.read("doc.kml").decode("utf-8")

    placemarks = re.findall(r"<Placemark>.*?</Placemark>", kml_content, re.S)
    entries = []
    for placemark in placemarks:
        desc_match = re.search(r"<description>(.*?)</description>", placemark, re.S)
        coords_match = re.search(r"<coordinates>(.*?)</coordinates>", placemark)
        if not desc_match or not coords_match:
            continue
        description = desc_match.group(1)
        if "Establecimiento:" not in description:
            continue  # skip non-school placemarks (SLEP offices, telecom towers, etc.)

        comuna_match = re.search(r"Comuna:\s*([^<|]+)", description)
        name_match = re.search(r"Establecimiento:\s*([^<|]+)", description)
        if not comuna_match or not name_match:
            continue

        lon, lat, *_ = coords_match.group(1).strip().split(",")
        entries.append({
            "comuna": comuna_match.group(1).strip(),
            "name": name_match.group(1).strip(),
            "lat": float(lat),
            "lng": float(lon),
        })
    return entries


def match_locations(kml_entries: list[dict], establishments: list[dict]):
    candidates_by_kml = []
    for kml_entry in kml_entries:
        kml_comuna = norm_full(kml_entry["comuna"])
        scored = [
            (score_pair(kml_entry["name"], est["name"]), est)
            for est in establishments
            if norm_full(est["comuna"]) == kml_comuna
        ]
        scored.sort(key=lambda pair: -pair[0])
        candidates_by_kml.append((kml_entry, scored))

    flat = [
        (score, kml_entry, est)
        for kml_entry, scored in candidates_by_kml
        for score, est in scored
    ]
    flat.sort(key=lambda triple: -triple[0])

    used_rbds, used_kml_ids, assignments = set(), set(), {}
    for score, kml_entry, est in flat:
        if score < MATCH_THRESHOLD:
            break
        kml_id = id(kml_entry)
        if kml_id in used_kml_ids or est["rbd"] in used_rbds:
            continue
        used_kml_ids.add(kml_id)
        used_rbds.add(est["rbd"])
        assignments[kml_id] = (kml_entry, est, score)

    return candidates_by_kml, assignments


async def main():
    if not os.path.exists(KMZ_PATH):
        print(f"No se encontró el KMZ en {KMZ_PATH}")
        return

    with open(ESTABLISHMENTS_JSON_PATH, encoding="utf-8") as f:
        establishments = json.load(f)

    kml_entries = parse_kmz_placemarks(KMZ_PATH)
    candidates_by_kml, assignments = match_locations(kml_entries, establishments)

    by_rbd = {est["rbd"]: est for est in establishments}
    matched_locations = {}
    for kml_entry, est, score in assignments.values():
        location = {"lat": kml_entry["lat"], "lng": kml_entry["lng"]}
        matched_locations[est["rbd"]] = location
        by_rbd[est["rbd"]]["location"] = location

    with open(ESTABLISHMENTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(establishments, f, ensure_ascii=False, indent=2)
        f.write("\n")

    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    updated_in_db = 0
    for rbd, location in matched_locations.items():
        result = await db.establishments.update_one({"rbd": rbd}, {"$set": {"location": location}})
        if result.matched_count:
            updated_in_db += 1
    client.close()

    print(f"Placemarks de establecimientos en el KMZ: {len(kml_entries)}")
    print(f"Coincidencias aplicadas (score >= {MATCH_THRESHOLD}): {len(assignments)}")
    print(f"Documentos actualizados en MongoDB: {updated_in_db}\n")

    print("Coincidencias aplicadas:")
    for kml_entry, scored in candidates_by_kml:
        if id(kml_entry) in assignments:
            _, est, score = assignments[id(kml_entry)]
            print(f"  [{score:.2f}] {kml_entry['name']!r} -> {est['name']} (rbd {est['rbd']})")

    print("\nSin coincidencia confiable — requieren carga manual de lat/lng en la ficha:")
    for kml_entry, scored in candidates_by_kml:
        if id(kml_entry) not in assignments:
            best = scored[0] if scored else None
            best_desc = f"{best[1]['name']} (score {best[0]:.2f})" if best else "sin candidato en la misma comuna"
            print(f"  KML: {kml_entry['name']!r} ({kml_entry['comuna']}) — mejor candidato: {best_desc}")

    matched_rbds = {est["rbd"] for _, est, _ in assignments.values()}
    unmatched_establishments = [est for est in establishments if est["rbd"] not in matched_rbds]
    if unmatched_establishments:
        print("\nEstablecimientos sin ubicación (ningún placemark del KMZ los alcanzó):")
        for est in unmatched_establishments:
            print(f"  rbd {est['rbd']} — {est['name']} ({est['comuna']})")


if __name__ == "__main__":
    asyncio.run(main())
