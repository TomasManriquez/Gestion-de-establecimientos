"""
test_BE61_connectivity_model.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: conectividad en tres bloques (2030, BAM, otro tipo) y su migración

Verifica la conversión del modelo antiguo (con y sin la hoja «Internet» de la planilla), el cálculo
de «sin internet», que la API valida los estados y tipos, que la clave wifi sigue redactada para
`viewer` y que el gráfico de conectividad cuenta por bloque.
"""
import copy
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.database.connectivity_migration import (has_other, migrate_connectivity, normalize_status,
                                                 rbd_from_sheet, rows_from_sheet, without_internet)
from tests.conftest import EDITOR_USER, VIEWER_USER, SAMPLE_ESTABLISHMENT, seed_users, bearer_for

OLD_TELSUR = {"internet_provider": "TELSUR", "internet_status": "Fibra óptica", "ssid": "Red",
              "ssid_password": "secreta", "download_speed_2030": "60", "bam": [],
              "starlink": {"installed": False, "date": ""}, "phone_extensions": ["5665"]}


def sheet(**kw):
    base = {"in_2030": "si", "status_2030": None, "speed_2030": None, "other_provider": None, "other_type": None,
            "other_speed": None, "other_oc": None, "other_expiry": None, "bam_carrier": None, "bam_qty": None,
            "bam_oc": None, "bam_term": None, "bam_end": None}
    return {**base, **kw}


def test_BE61_old_model_without_sheet_keeps_2030_and_secrets():
    new, notes = migrate_connectivity(OLD_TELSUR)
    assert new["program_2030"] == {"enabled": True, "status": "fibra_optica", "download_speed": "60", "test_date": ""}
    assert new["ssid"] == "Red" and new["ssid_password"] == "secreta" and new["phone_extensions"] == ["5665"]
    assert not has_other(new["other"]) and not without_internet(new)
    assert "internet_provider" not in new and "starlink" not in new                       # campos retirados


def test_BE61_other_connection_comes_from_the_sheet():
    old = {**OLD_TELSUR, "internet_provider": "Enseña Chile"}
    row = sheet(status_2030="Microondas", speed_2030=8, other_provider="Enseña Chile", other_type="starlink",
                other_expiry=datetime(2026, 12, 1), other_oc="434-ag24")
    new, _ = migrate_connectivity(old, row)
    assert new["program_2030"]["status"] == "microondas" and new["program_2030"]["download_speed"] == "8"
    assert new["other"] == {"provider": "Enseña Chile", "type": "starlink", "download_speed": "", "oc": "434-ag24",
                            "expiry_date": "2026-12-01", "support_whatsapp": ""}


@pytest.mark.parametrize("provider", ["telsur", None])
def test_BE61_starlink_of_the_2030_program_stays_in_the_2030_block(provider):
    row = sheet(status_2030="starlink", other_provider=provider, other_type="starlink", other_speed="300 mbps")
    new, notes = migrate_connectivity({**OLD_TELSUR, "download_speed_2030": ""}, row)
    assert new["program_2030"]["status"] == "starlink" and new["program_2030"]["download_speed"] == "300"
    assert not has_other(new["other"])
    assert any("Starlink del 2030" in n for n in notes)


def test_BE61_provider_names_are_unified():
    a, _ = migrate_connectivity({}, sheet(in_2030=None, other_provider="PATAGONIA IP", other_type="Fibra Optica"))
    b, _ = migrate_connectivity({}, sheet(in_2030=None, other_provider="Patagonia IP", other_type="fibra óptica"))
    assert a["other"]["provider"] == b["other"]["provider"] == "Patagonia IP"
    assert a["other"]["type"] == b["other"]["type"] == "fibra_optica"


@pytest.mark.parametrize("raw, expected", [
    ("SE TIENE Q INSTLAR", "pendiente_instalacion"), ("SE TIENE Q INSTALAR DE NUEVO", "pendiente_instalacion"),
    ("starlink (vtr)", "starlink"), ("Fibra óptica", "fibra_optica"), ("sin internet", "sin_internet"),
    ("Satelital", "satelital"), ("", None),
])
def test_BE61_status_normalization(raw, expected):
    assert normalize_status(raw)[0] == expected


def test_BE61_bam_contract_from_the_sheet_when_no_devices():
    row = sheet(in_2030=None, bam_carrier="Movistar", bam_qty=15, bam_oc="1394-AG23", bam_end=datetime(2024, 5, 31))
    new, _ = migrate_connectivity({}, row)
    assert new["bam"] == [{"number": "", "oc": "1394-AG23", "imei": "", "device": "", "holder": "", "carrier": "Movistar",
                           "qty": 15, "start": "", "term": "", "end": "2024-05-31"}]
    assert not without_internet(new)


def test_BE61_without_internet_has_two_causes():
    in_2030_down, _ = migrate_connectivity({}, sheet(status_2030="sin internet"))
    nothing, notes = migrate_connectivity({}, sheet(in_2030=None))
    assert without_internet(in_2030_down) and without_internet(nothing)
    assert "queda como SIN INTERNET" in notes


def test_BE61_migration_is_idempotent():
    new, _ = migrate_connectivity(OLD_TELSUR)
    again, notes = migrate_connectivity(new)
    assert again == new and notes == ["ya migrado: sin cambios"]


def test_BE61_sheet_rows_are_keyed_by_rbd_without_dv():
    raw = [["h"], ["h"], [1, "7945-6", None, "Fresia", "PEUCHEN"], [2, 35132, None, "Fresia", "JARDÍN"]]
    assert set(rows_from_sheet(raw)) == {"7945", "35132"} and rbd_from_sheet("22105-8") == "22105"


# ── API ────────────────────────────────────────────────────────────────────────────────────────

def _client(fake_db, conn):
    seed_users(fake_db, EDITOR_USER, VIEWER_USER)
    fake_db.establishments.seed({**copy.deepcopy(SAMPLE_ESTABLISHMENT), "connectivity": conn})
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_BE61_put_rejects_unknown_status_and_type(fake_db):
    c = _client(fake_db, migrate_connectivity(OLD_TELSUR)[0])
    h = bearer_for(EDITOR_USER)
    assert c.put("/api/establishments/7722", json={"connectivity": {"program_2030": {"enabled": True, "status": "lento"}}},
                 headers=h).status_code == 422
    assert c.put("/api/establishments/7722", json={"connectivity": {"other": {"type": "palomas"}}},
                 headers=h).status_code == 422
    ok = c.put("/api/establishments/7722", json={"connectivity": {
        "program_2030": {"enabled": True, "status": "sin_internet"},
        "other": {"provider": "Patagonia IP", "type": "fibra_optica", "support_whatsapp": "+56911112222"}}}, headers=h)
    assert ok.status_code == 200 and ok.json()["connectivity"]["other"]["support_whatsapp"] == "+56911112222"


def test_BE61_viewer_still_gets_the_wifi_password_redacted(fake_db):
    c = _client(fake_db, migrate_connectivity(OLD_TELSUR)[0])
    body = c.get("/api/establishments/7722", headers=bearer_for(VIEWER_USER)).json()
    assert body["connectivity"]["ssid_password"] == "[REDACTED]" and "secreta" not in str(body)


def test_BE61_connectivity_chart_counts_by_block():
    from app.analytics.analytics_service import connectivity_breakdown
    other_only, _ = migrate_connectivity({}, sheet(in_2030=None, other_provider="Patagonia IP", other_type="fibra óptica"))
    data = connectivity_breakdown([migrate_connectivity(OLD_TELSUR)[0], other_only, {}, None])   # {} y None sin migrar
    assert {d["label"]: d["value"] for d in data} == {"Conectividad 2030": 1, "Banda ancha móvil": 0,
                                                      "Otro tipo de conexión": 1, "Sin internet": 2}


def test_BE61_unmigrated_document_is_served_in_the_new_shape(fake_db):
    c = _client(fake_db, copy.deepcopy(OLD_TELSUR))                                  # modelo antiguo en la base
    body = c.get("/api/establishments/7722", headers=bearer_for(VIEWER_USER)).json()["connectivity"]
    assert body["program_2030"]["status"] == "fibra_optica" and "internet_provider" not in body
    assert body["ssid_password"] == "[REDACTED]"                                      # se convierte y luego se redacta
