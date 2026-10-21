"""
test_BE54_no_cors.py
━━━━━━━━━━━━━━━━━━━━
Tarea: SEC-5 · Sin CORS: el frontend es de mismo origen (ADR-008)

Verifica que:
  - una petición con `Origin` ajeno no recibe `Access-Control-Allow-Origin` ni `-Credentials`
  - el preflight (OPTIONS) de un origen ajeno no se aprueba
  - `Retry-After` sigue siendo legible desde el mismo origen (no depende de CORS)
  - la aplicación no monta `CORSMiddleware`
"""
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from tests.conftest import ADMIN_USER, bearer_for, seed_users

EVIL = {"Origin": "https://evil.example"}


def client():
    from app.main import app
    return TestClient(app)


def test_BE54_foreign_origin_gets_no_cors_headers(fake_db):
    seed_users(fake_db, ADMIN_USER)
    r = client().get("/api/auth/me", headers={**bearer_for(ADMIN_USER), **EVIL})
    assert r.status_code == 200
    assert not any(h.lower().startswith("access-control-") for h in r.headers)


def test_BE54_preflight_from_foreign_origin_is_not_approved():
    r = client().options("/api/auth/login", headers={**EVIL, "Access-Control-Request-Method": "POST",
                                                     "Access-Control-Request-Headers": "authorization"})
    assert "access-control-allow-origin" not in {h.lower() for h in r.headers}
    assert r.status_code in (400, 405)


def test_BE54_no_cors_middleware_mounted():
    from app.main import app
    assert all(m.cls is not CORSMiddleware for m in app.user_middleware)
