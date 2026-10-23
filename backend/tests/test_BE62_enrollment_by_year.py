"""
test_BE62_enrollment_by_year.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: datos por año para el tablero de matrícula · estado activo/cerrado · cortes parciales

Verifica que:
  - GET /api/analytics/enrollment entrega establecimientos y puntos por año, sin año fijo
  - un 0 en docentes / asistentes / asistencia es «sin dato», pero en matrícula es un valor real
  - cada indicador declara sus propios años y el corte parcial viaja con el dato
  - el estado del establecimiento se valida (cerrado necesita año; reabrir borra el año)
  - el corte (AAAA-MM) de la matrícula y la asistencia se valida al editar
"""
import copy
import pytest
from fastapi.testclient import TestClient
from tests.conftest import EDITOR_USER, VIEWER_USER, NO_DATOS_USER, SAMPLE_ESTABLISHMENT, seed_users, bearer_for


def _client(fake_db):
    seed_users(fake_db, EDITOR_USER, VIEWER_USER, NO_DATOS_USER)
    fake_db.establishments.seed(copy.deepcopy(SAMPLE_ESTABLISHMENT),
                                {**copy.deepcopy(SAMPLE_ESTABLISHMENT), "rbd": "9001", "name": "ESCUELA CERRADA",
                                 "status": "closed", "closed_year": 2026})
    fake_db.metrics.seed(
        {"rbd": "7722", "year": 2025, "enrollment": 470, "attendance_avg": "0.865", "num_teachers": 0, "num_assistants": 0},
        {"rbd": "7722", "year": 2026, "enrollment": 450, "enrollment_as_of": "2026-03", "attendance_avg": "",
         "num_teachers": 40, "num_assistants": 12},
        {"rbd": "9001", "year": 2025, "enrollment": 0, "attendance_avg": "", "num_teachers": 0},
        {"rbd": "huerfano", "year": 2026, "enrollment": 5},                          # sin establecimiento: se ignora
    )
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_BE62_dataset_by_year(fake_db):
    c = _client(fake_db)
    r = c.get("/api/analytics/enrollment", headers=bearer_for(VIEWER_USER))
    assert r.status_code == 200
    body = r.json()
    assert body["years"] == [2025, 2026]
    closed = next(e for e in body["establishments"] if e["rbd"] == "9001")
    assert closed["status"] == "closed" and closed["closed_year"] == 2026
    assert next(e for e in body["establishments"] if e["rbd"] == "7722")["status"] == "active"   # sin campo: activo
    p = {(x["rbd"], x["year"]): x for x in body["points"]}
    assert ("huerfano", 2026) not in p
    assert p[("7722", 2025)]["attendance"] == pytest.approx(0.865) and p[("7722", 2025)]["teachers"] is None
    assert p[("7722", 2026)]["attendance"] is None and p[("7722", 2026)]["enrollment_as_of"] == "2026-03"
    assert p[("9001", 2025)]["enrollment"] == 0                                         # el 0 de matrícula es real


def test_BE62_each_indicator_declares_its_years(fake_db):
    ind = _client(fake_db).get("/api/analytics/enrollment", headers=bearer_for(VIEWER_USER)).json()["indicators"]
    assert ind["enrollment"]["years"] == [2025, 2026]
    assert ind["attendance"]["years"] == [2025]
    assert ind["teachers"]["years"] == [2026] and ind["assistants"]["years"] == [2026]


def test_BE62_dataset_requires_datos_access(fake_db):
    c = _client(fake_db)
    assert c.get("/api/analytics/enrollment").status_code == 401
    assert c.get("/api/analytics/enrollment", headers=bearer_for(NO_DATOS_USER)).status_code == 403


@pytest.mark.parametrize("payload", [
    {"status": "closed"},                               # cerrado sin año
    {"status": "active", "closed_year": 2026},          # activo con año
    {"closed_year": 2026},                              # año sin estado
    {"status": "demolido", "closed_year": 2026},
    {"status": "closed", "closed_year": 1990},
])
def test_BE62_status_validation(fake_db, payload):
    c = _client(fake_db)
    assert c.put("/api/establishments/7722", json=payload, headers=bearer_for(EDITOR_USER)).status_code == 422


def test_BE62_close_and_reopen(fake_db):
    c = _client(fake_db)
    h = bearer_for(EDITOR_USER)
    closed = c.put("/api/establishments/7722", json={"status": "closed", "closed_year": 2027}, headers=h).json()
    assert closed["status"] == "closed" and closed["closed_year"] == 2027
    reopened = c.put("/api/establishments/7722", json={"status": "active"}, headers=h).json()
    assert reopened["status"] == "active" and reopened["closed_year"] is None
    assert c.put("/api/establishments/7722", json={"status": "closed", "closed_year": 2027},
                 headers=bearer_for(VIEWER_USER)).status_code == 403


@pytest.mark.parametrize("value, code", [("2026-06", 200), ("", 200), ("2026-13", 422), ("junio", 422), ("2026-6", 422)])
def test_BE62_partial_cutoff_format(fake_db, value, code):
    c = _client(fake_db)
    r = c.put("/api/metrics/establishment/7722/2026", json={"attendance_as_of": value}, headers=bearer_for(EDITOR_USER))
    assert r.status_code == code
