"""
test_INT10_establishments_filter_injection.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: SEC-4 · D5 cerrada: los filtros de texto del directorio escapan el input

Verifica, por HTTP y con una base en memoria, que:
  - metacaracteres de regex (`.*`, `(a+)+$`, `.`, `^`, `[`) se tratan como texto literal en
    `search`, `comuna`, `area_type`, `coverage` y `adp`: no coinciden con todo y no rompen
  - sintaxis de regex inválida (`(`, `[`, `\\`) no produce 500
  - inyección de operadores por query string (`comuna[$ne]=x`) no altera el filtro
  - una búsqueda legítima (control positivo) sigue funcionando
"""
import copy
import time
import pytest
from fastapi.testclient import TestClient
from tests.conftest import SAMPLE_ESTABLISHMENT, VIEWER_USER, bearer_for, seed_users

ATTACKS = [".*", "(a+)+$", ".", "^", "[", "(", "\\", "a|b", ".+"]
FILTERS = ["search", "comuna", "area_type", "coverage", "adp"]


@pytest.fixture
def api(fake_db):
    seed_users(fake_db, VIEWER_USER)
    fake_db.establishments.seed(copy.deepcopy(SAMPLE_ESTABLISHMENT))
    from app.main import app
    return TestClient(app), bearer_for(VIEWER_USER)


def listing(api, **params):
    c, h = api
    return c.get("/api/establishments", params=params, headers=h)


def test_INT10_positive_control(api):
    assert listing(api, search="LICEO POLIT").json()["total"] == 1
    assert listing(api, comuna="puerto varas").json()["total"] == 1
    assert listing(api, area_type="urbano").json()["total"] == 1
    assert listing(api, coverage="MED").json()["total"] == 1
    assert listing(api, adp="si").json()["total"] == 1


@pytest.mark.parametrize("field", FILTERS)
@pytest.mark.parametrize("attack", ATTACKS)
def test_INT10_regex_metacharacters_are_literal_text(api, field, attack):
    r = listing(api, **{field: attack})
    assert r.status_code == 200, f"{field}={attack!r} -> {r.status_code}"
    assert r.json()["total"] == 0, f"{field}={attack!r} coincidió como regex"


def test_INT10_catastrophic_pattern_returns_fast(api):
    started = time.monotonic()
    assert listing(api, search="(a+)+$" + "a" * 5000).status_code == 200
    assert time.monotonic() - started < 2


def test_INT10_operator_injection_through_query_string_is_ignored(api):
    c, h = api
    r = c.get("/api/establishments?comuna[$ne]=x&search[$regex]=.*", headers=h)
    assert r.status_code == 200 and r.json()["total"] == 1       # parámetros desconocidos: sin filtro
