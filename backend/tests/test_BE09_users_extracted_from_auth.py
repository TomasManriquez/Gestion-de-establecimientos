"""
test_BE09_users_extracted_from_auth.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-02 · Extraer `users` de `auth` sin cambiar el comportamiento (C2, T3)

Verifica que:
  - el módulo `users` tiene exactamente los tres archivos de ADR-007
  - `auth` ya no toca la colección `users` ni la base
  - el contrato de login y de /api/auth/me no cambió (solo creció)
  - `users_service` no importa fastapi ni `auth` (dirección de dependencias, ADR-013)
"""
import ast
from pathlib import Path
from fastapi.testclient import TestClient
from tests.conftest import ADMIN_USER, seed_users, user_with_password, bearer_for

APP = Path(__file__).resolve().parents[1] / "app"


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def test_BE09_users_module_has_exactly_three_files():
    files = {p.name for p in (APP / "users").iterdir() if p.suffix == ".py"}
    assert files == {"__init__.py", "users_entity.py", "users_service.py", "users_controller.py"}


def test_BE09_auth_does_not_access_users_collection():
    for name in ("auth_service.py", "auth_controller.py", "auth_entity.py"):
        path = APP / "auth" / name
        assert "app.database.database_service" not in _imports(path), f"{name} importa db_service"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        collections = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert "users" not in collections, f"{name} referencia una colección .users"


def test_BE09_users_service_import_direction():
    mods = _imports(APP / "users" / "users_service.py") | _imports(APP / "users" / "users_entity.py")
    assert not any(m == "fastapi" or m.startswith("fastapi.") for m in mods)          # L2
    assert not any(m.startswith("app.auth") for m in mods)                            # ADR-013: auth -> users


def test_BE09_login_and_me_contract_unchanged(fake_db):
    from app.main import app
    seed_users(fake_db, user_with_password(ADMIN_USER, "una-clave-larga-de-prueba"))
    client = TestClient(app)

    r = client.post("/api/auth/login", json={"username": "admin@slepllanquihue.cl", "password": "una-clave-larga-de-prueba"})
    assert r.status_code == 200
    assert set(r.json()) == {"access_token", "token_type"} and r.json()["token_type"] == "bearer"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200
    body = me.json()
    assert {"username", "full_name", "role"} <= set(body)                   # contrato original
    assert all(isinstance(body[k], str) for k in ("username", "full_name", "role"))
    assert body["role"] == "admin" and body["full_name"] == "Administrador SLEP"
    assert {"id", "email", "access"} <= set(body)                            # aditivo

    anon = client.get("/api/auth/me")
    assert anon.status_code == 401 and anon.headers["www-authenticate"] == "Bearer"
