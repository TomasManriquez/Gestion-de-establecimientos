"""
test_BE60_metrics_edit_validation.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: edición de estadísticas desde la ficha · `PUT /api/metrics/establishment/{rbd}/{year}`

Verifica que la escritura de métricas valida rangos y campos, que no crea métricas para un
establecimiento inexistente y que un año nuevo queda legible aunque solo traiga algunos campos.
"""
import copy
import pytest
from fastapi.testclient import TestClient
from tests.conftest import EDITOR_USER, VIEWER_USER, SAMPLE_ESTABLISHMENT, seed_users, bearer_for

URL = "/api/metrics/establishment/7722"


def setup(fake_db):
    seed_users(fake_db, EDITOR_USER, VIEWER_USER)
    fake_db.establishments.seed(copy.deepcopy(SAMPLE_ESTABLISHMENT))
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_BE60_editor_creates_a_new_year_with_partial_fields(fake_db):
    c = setup(fake_db)
    r = c.put(f"{URL}/2027", json={"attendance_avg": "0.91", "num_teachers": 40}, headers=bearer_for(EDITOR_USER))
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == 2027 and body["num_teachers"] == 40 and body["enrollment"] == 0   # legible sin matrícula


def test_BE60_only_sent_fields_change(fake_db):
    c = setup(fake_db)
    h = bearer_for(EDITOR_USER)
    c.put(f"{URL}/2026", json={"enrollment": 500, "num_teachers": 40}, headers=h)
    body = c.put(f"{URL}/2026", json={"enrollment": 510}, headers=h).json()
    assert body["enrollment"] == 510 and body["num_teachers"] == 40


@pytest.mark.parametrize("payload", [
    {"enrollment": -1},
    {"num_teachers": 1.5},
    {"tasa_retencion": 100.3},
    {"ive_basica": 1.2},
    {"grade_avg": 7.5},
    {"attendance_avg": "1.4"},
    {"attendance_avg": "noventa"},
    {"campo_inventado": 1},
])
def test_BE60_out_of_range_or_unknown_fields_are_rejected(fake_db, payload):
    c = setup(fake_db)
    assert c.put(f"{URL}/2026", json=payload, headers=bearer_for(EDITOR_USER)).status_code == 422
    assert fake_db.metrics.docs == []                                                          # nada se escribió


@pytest.mark.parametrize("year", [1999, 2101])
def test_BE60_year_outside_range_is_rejected(fake_db, year):
    c = setup(fake_db)
    assert c.put(f"{URL}/{year}", json={"enrollment": 1}, headers=bearer_for(EDITOR_USER)).status_code == 422


def test_BE60_unknown_establishment_is_404_and_writes_nothing(fake_db):
    c = setup(fake_db)
    r = c.put("/api/metrics/establishment/99999/2026", json={"enrollment": 1}, headers=bearer_for(EDITOR_USER))
    assert r.status_code == 404 and fake_db.metrics.docs == []


def test_BE60_viewer_cannot_write_metrics(fake_db):
    c = setup(fake_db)
    assert c.put(f"{URL}/2026", json={"enrollment": 1}, headers=bearer_for(VIEWER_USER)).status_code == 403
    assert fake_db.metrics.docs == []
