"""Conversión de `connectivity` del modelo antiguo al modelo en tres bloques (2030, BAM, otro).

Funciones puras, sin acceso a la base: las usan el seeding (`seed_service`) y el script de
migración (`scripts/migrate_connectivity.py`). Vive en `database` porque es base común: el modelo
de la API está en `establishments_entity.Connectivity`.

Modelo antiguo (carga inicial): `internet_provider` mezclaba Telsur con el proveedor de «otro
tipo»; `internet_status` era el estado del 2030 escrito a mano; `download_speed_2030` la velocidad
del 2030; `starlink.installed` una marca sin distinguir si el Starlink era del 2030 o independiente.

La hoja «Internet» de la planilla (opcional) completa lo que la carga inicial perdió: si el
establecimiento está en 2030 y los datos de «otro tipo de conexión» (tipo, vencimiento, velocidad, OC).
"""
import math
import re
import unicodedata
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

STATUS_2030 = ("fibra_optica", "microondas", "starlink", "satelital", "pendiente_instalacion", "sin_internet")
OTHER_TYPES = ("fibra_optica", "starlink", "microondas", "satelital", "movil", "otro")

# Proveedores conocidos con su grafía canónica (clave normalizada → nombre a mostrar)
PROVIDERS = {
    "telsur": "Telsur",
    "patagonia ip": "Patagonia IP",
    "ensena chile": "Enseña Chile",
    "camanchaca": "Camanchaca",
    "movistar": "Movistar",
    "entel": "Entel",
    "vtr": "VTR",
}


def _key(text: Any) -> str:
    """Minúsculas, sin tildes ni espacios repetidos. '' para vacíos y NaN de pandas."""
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return ""
    s = unicodedata.normalize("NFD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def normalize_status(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """Estado 2030 escrito a mano → (valor canónico, nota si no se reconoció)."""
    k = _key(raw)
    if not k:
        return None, None
    if "fibra" in k:
        return "fibra_optica", None
    if "microonda" in k:
        return "microondas", None
    if "starlink" in k:
        return "starlink", None
    if "satelit" in k:
        return "satelital", None
    if "instal" in k or "instl" in k or "tiene q" in k:      # «SE TIENE Q INSTLAR» también
        return "pendiente_instalacion", None
    if "sin internet" in k or "sin servicio" in k:
        return "sin_internet", None
    return None, f"estado 2030 no reconocido: «{raw}»"


def normalize_other_type(raw: Any) -> Optional[str]:
    k = _key(raw)
    if not k:
        return None
    for needle, value in (("fibra", "fibra_optica"), ("starlink", "starlink"), ("microonda", "microondas"),
                          ("satelit", "satelital"), ("bam", "movil"), ("movil", "movil")):
        if needle in k:
            return value
    return "otro"


def normalize_provider(raw: Any) -> str:
    k = _key(raw)
    return PROVIDERS.get(k, str(raw).strip() if k else "")


def normalize_speed(raw: Any) -> str:
    """'300 mbps', 300, 60.0 → '300' / '60' (Mbps). Texto no numérico se conserva."""
    k = _key(raw)
    if not k:
        return ""
    m = re.match(r"^(\d+(?:[.,]\d+)?)\s*(mbps)?$", k)
    if not m:
        return str(raw).strip()
    n = float(m.group(1).replace(",", "."))
    return str(int(n)) if n.is_integer() else str(n)


def normalize_date(raw: Any) -> Tuple[str, Optional[str]]:
    """Fecha de la planilla → ('AAAA-MM-DD', None); texto como 'sin servicio' → ('', nota)."""
    if isinstance(raw, (datetime, date)):
        return raw.strftime("%Y-%m-%d"), None
    k = _key(raw)
    if not k:
        return "", None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", k)
    if m:
        return m.group(1), None
    return "", f"vencimiento no es una fecha: «{raw}»"


def _text(raw: Any) -> str:
    return "" if not _key(raw) else str(raw).strip()


def empty_connectivity() -> Dict[str, Any]:
    return {
        "program_2030": {"enabled": False, "status": None, "download_speed": "", "test_date": ""},
        "ssid": "",
        "ssid_password": "",
        "bam": [],
        "other": {"provider": "", "type": None, "download_speed": "", "oc": "", "expiry_date": "",
                  "support_whatsapp": ""},
        "internal_network": {"installed_year": "", "points_count": "", "status": "", "obs": ""},
        "phone_extensions": [],
    }


def is_migrated(conn: Optional[dict]) -> bool:
    return isinstance(conn, dict) and isinstance(conn.get("program_2030"), dict)


def has_other(other: Optional[dict]) -> bool:
    return bool(other) and any(other.get(k) for k in ("provider", "type", "download_speed", "oc", "expiry_date",
                                                      "support_whatsapp"))


def without_internet(conn: dict) -> bool:
    """«Sin internet»: en 2030 con estado sin internet, o sin ningún bloque con conexión."""
    p = conn.get("program_2030") or {}
    if p.get("enabled") and p.get("status") == "sin_internet":
        return True
    return not p.get("enabled") and not conn.get("bam") and not has_other(conn.get("other"))


def migrate_connectivity(old: Optional[dict], sheet: Optional[dict] = None) -> Tuple[Dict[str, Any], List[str]]:
    """Convierte un `connectivity` antiguo. `sheet` es la fila de la hoja «Internet» del
    establecimiento, con las claves de `read_internet_sheet`, o None. Devuelve (nuevo, notas)."""
    old = old or {}
    if is_migrated(old):
        return old, ["ya migrado: sin cambios"]
    new = empty_connectivity()
    notes: List[str] = []

    # Se conservan tal cual
    new["ssid"] = old.get("ssid") or ""
    new["ssid_password"] = old.get("ssid_password") or ""
    new["bam"] = list(old.get("bam") or [])
    new["internal_network"] = {**new["internal_network"], **(old.get("internal_network") or {})}
    new["phone_extensions"] = list(old.get("phone_extensions") or [])

    # ── Bloque 2030 ────────────────────────────────────────────────────────────────────────
    status, note = normalize_status((sheet or {}).get("status_2030") or old.get("internet_status"))
    if note:
        notes.append(note)
    speed = normalize_speed((sheet or {}).get("speed_2030") or old.get("download_speed_2030"))
    if sheet is not None:
        enabled = _key(sheet.get("in_2030")) == "si"
    else:
        enabled = bool(status or speed or old.get("ssid") or _key(old.get("internet_provider")) == "telsur")
    new["program_2030"] = {"enabled": enabled, "status": status if enabled else None,
                           "download_speed": speed if enabled else "", "test_date": _text(old.get("test_date"))}
    if not enabled and (status or speed):
        notes.append("tenía estado o velocidad 2030 pero la planilla dice que no está en 2030: se descartan")

    # ── Bloque «otro tipo de conexión» ────────────────────────────────────────────────────
    if sheet is not None:
        provider = normalize_provider(sheet.get("other_provider"))
        other_type = normalize_other_type(sheet.get("other_type"))
        starlink_2030 = (other_type == "starlink" and not provider and enabled
                         and new["program_2030"]["status"] in (None, "starlink"))
        if _key(sheet.get("other_provider")) == "telsur" or starlink_2030:
            # Starlink financiado por el 2030: queda en el bloque 2030, no como conexión aparte
            if other_type == "starlink" and enabled and new["program_2030"]["status"] is None:
                new["program_2030"]["status"] = "starlink"
            if not new["program_2030"]["download_speed"]:
                new["program_2030"]["download_speed"] = normalize_speed(sheet.get("other_speed"))
            notes.append("«otro tipo» Starlink sin proveedor propio o de Telsur: se trató como Starlink del 2030")
        elif provider or other_type:
            expiry, note = normalize_date(sheet.get("other_expiry"))
            if note:
                notes.append(note)
            new["other"].update({"provider": provider, "type": other_type,
                                 "download_speed": normalize_speed(sheet.get("other_speed")),
                                 "oc": _text(sheet.get("other_oc")), "expiry_date": expiry})
    else:
        provider = normalize_provider(old.get("internet_provider"))
        if provider and _key(provider) != "telsur":
            new["other"]["provider"] = provider
            notes.append("proveedor de «otro tipo» sin tipo ni vencimiento (falta la planilla)")

    # ── Bloque BAM: contrato de la planilla cuando no hay equipos detallados ──────────────
    if sheet is not None:
        bam_fields = {k: sheet.get(k) for k in ("bam_carrier", "bam_qty", "bam_oc", "bam_term", "bam_end")}
        if any(_key(v) for v in bam_fields.values()):
            if new["bam"]:
                notes.append("la planilla trae un contrato BAM además de los equipos detallados: se conservan los equipos")
            else:
                end, note = normalize_date(bam_fields["bam_end"])
                if note:
                    notes.append(note)
                qty = _key(bam_fields["bam_qty"])
                new["bam"].append({"number": "", "oc": _text(bam_fields["bam_oc"]), "imei": "", "device": "", "holder": "",
                                   "carrier": normalize_provider(bam_fields["bam_carrier"]),
                                   "qty": int(float(qty)) if re.match(r"^\d+(\.0)?$", qty) else None,
                                   "start": "", "term": _text(bam_fields["bam_term"]), "end": end})

    # ── Lo que se deja de guardar ─────────────────────────────────────────────────────────
    starlink = (old.get("starlink") or {}).get("installed")
    if starlink and new["program_2030"]["status"] != "starlink" and new["other"]["type"] != "starlink":
        notes.append("tenía «Antena Starlink instalada» sin Starlink en 2030 ni en otro tipo: revisar")
    if without_internet(new):
        notes.append("queda como SIN INTERNET")
    return new, notes


# Columnas de la hoja «Internet» (fila 2 de encabezados): 2030 (6–11), BAM (13–17) y otro tipo
# (19–24). La clave del wifi de «otro tipo»
# (columna 20) y la observación (25, que tiene claves escritas a mano) NO se leen.
SHEET_COLUMNS = {1: "rbd", 4: "name", 6: "in_2030", 7: "status_2030", 11: "speed_2030",
                 13: "bam_carrier", 14: "bam_qty", 15: "bam_oc", 16: "bam_term", 17: "bam_end",
                 19: "other_provider", 21: "other_expiry", 22: "other_type", 23: "other_speed", 24: "other_oc"}


def rbd_from_sheet(raw: Any) -> str:
    """'7945-6' → '7945'; 35132 → '35132'."""
    k = _key(raw)
    if not k:
        return ""
    k = k.split("-")[0].strip()
    return k[:-2] if k.endswith(".0") else k


def rows_from_sheet(raw_rows: List[List[Any]]) -> Dict[str, dict]:
    """Filas crudas de la hoja (incluidos los dos encabezados) → {rbd: fila con claves de SHEET_COLUMNS}."""
    out: Dict[str, dict] = {}
    for row in raw_rows[2:]:
        rec = {key: (row[i] if i < len(row) else None) for i, key in SHEET_COLUMNS.items()}
        rbd = rbd_from_sheet(rec["rbd"])
        if rbd:
            out[rbd] = rec
    return out
