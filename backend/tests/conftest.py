"""
conftest.py — Fixtures compartidas para todos los tests del backend.

Estrategia: MongoDB se simula con `unittest.mock` (AsyncMock/MagicMock) sobre `db_service.db`
o con `tests/fake_mongo.py` (colecciones en memoria). Ningún test usa una base real.
"""
import os

# T9: la app no arranca sin estas variables. Se fijan ANTES de importar `app` (la
# configuración se lee al importar). Valores solo para pruebas; nunca son los de un despliegue.
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-deployments"
os.environ["ADMIN_PASSWORD"] = "test-only-admin-password"
os.environ["ALLOWED_EMAIL_DOMAINS"] = "slepllanquihue.cl"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@slepllanquihue.cl"
for _name in ("PASSWORD_MIN_LENGTH", "PASSWORD_MAX_LENGTH", "PASSWORD_REQUIRE_CHAR_CLASSES"):
    os.environ.pop(_name, None)

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

# ─── Datos de seed para tests ────────────────────────────────────────────────

SAMPLE_ESTABLISHMENT = {
    "_id": "6600000000000000000000a1",
    "rbd": "7722",
    "rbd_dv": "3",
    "rbd_full": "7722-3",
    "name": "LICEO POLITÉCNICO PUERTO VARAS",
    "comuna": "PUERTO VARAS",
    "area_type": "URBANO",
    "address": "Calle Ejemplo 123",
    "general_info": {
        "director": "Juan Pérez",
        "director_email": "director@liceo.cl",
        "director_phone": "+56912345678",
        "category": "7. LICEO POLITÉCNICO",
        "covertura": "MEDIA",
        "adp": "Si",
        "pame": "",
        "uni_bi_tridocente": "",
        "microcentro": "",
        "coordinador_microcentro": "",
        "detalle_niveles_combinados": "",
        "nivel_transicion_nt": "",
        "priorizado_asistencia": "",
        "distancia_cafra": "",
    },
    "connectivity": {
        "internet_provider": "TELSUR",
        "internet_status": "ACTIVO",
        "ssid": "LiceoRed",
        "ssid_password": "password-secreta-wifi",  # Campo sensible
        "test_date": "2026-01-15",
        "download_speed_2030": "100",
        "bam": [],
        "starlink": {"installed": False, "date": ""},
        "internal_network": {"installed_year": "2020", "points_count": "30", "status": "OK", "obs": ""},
        "phone_extensions": [],
    },
    "printers": {"owned": [], "leased": []},
    "licenses": [
        {
            "name": "Plataforma SIGE",
            "email": "admin@liceo.cl",
            "password": "clave-secreta-sige",  # Campo sensible
            "url": "https://sige.mineduc.cl",
            "obs": "",
            "is_new": False,
        }
    ],
}

SAMPLE_ESTABLISHMENT_2 = {
    "_id": "6600000000000000000000a2",
    "rbd": "7801",
    "rbd_dv": "5",
    "rbd_full": "7801-5",
    "name": "ESCUELA BÁSICA FRUTILLAR",
    "comuna": "FRUTILLAR",
    "area_type": "RURAL",
    "address": "Av. Rural 456",
    "general_info": {
        "director": "María López",
        "director_email": "directora@escuela.cl",
        "director_phone": "",
        "category": "6. RURAL MULTIGRADO",
        "covertura": "BASICA",
        "adp": "No",
        "pame": "",
        "uni_bi_tridocente": "UNI",
        "microcentro": "Si",
        "coordinador_microcentro": "",
        "detalle_niveles_combinados": "",
        "nivel_transicion_nt": "",
        "priorizado_asistencia": "Si",
        "distancia_cafra": "45 km",
    },
    "connectivity": {
        "internet_provider": "WOM",
        "internet_status": "ACTIVO",
        "ssid": "EscuelaWifi",
        "ssid_password": "otra-clave-secreta",
        "test_date": "",
        "download_speed_2030": "20",
        "bam": [],
        "starlink": {"installed": True, "date": "2025-03-01"},
        "internal_network": {},
        "phone_extensions": [],
    },
    "printers": {"owned": [], "leased": []},
    "licenses": [],
}

SAMPLE_COUNTERPART = {
    "_id": "6600000000000000000000b1",
    "rbd": "7722",
    "role": "TI",
    "origin": "SLEP",
    "name": "Carlos Tecnología",
    "email": "ti@slep.cl",
    "phone": "+56911111111",
}

SAMPLE_METRIC_2026 = {
    "_id": "6600000000000000000000c1",
    "rbd": "7722",
    "year": 2026,
    "enrollment": 450,
    "attendance_avg": "92%",
    "ive_basica": 0.0,
    "ive_media": 68.5,
    "num_teachers": 32,
    "num_assistants": 8,
    "grade_avg": 5.4,
    "promoted": 410,
    "failed": 20,
    "transferred": 15,
    "dropouts": 5,
    "desempeno_basica": "",
    "desempeno_media": "MEDIO",
    "ptje_nem": 5.6,
    "ptje_ranking": 580.0,
    "score_lectura": 260.0,
    "score_matematica1": 255.0,
    "score_matematica2": 248.0,
    "score_historia": 252.0,
    "score_ciencia": 257.0,
    "total_rendidores": 68,
    "tasa_promocion": 91.1,
    "tasa_reprobacion": 4.4,
    "tasa_desercion": 1.1,
    "tasa_retencion": 94.5,
}

SAMPLE_METRIC_2025 = {
    "_id": "6600000000000000000000c2",
    "rbd": "7722",
    "year": 2025,
    "enrollment": 440,
    "attendance_avg": "91%",
    "ive_basica": 0.0,
    "ive_media": 67.0,
    "num_teachers": 31,
    "num_assistants": 8,
}

def _user(oid, email, first, last, access, **extra):
    """Usuario con el modelo nuevo (US-17). `access` es una lista [(plataforma, rol)]."""
    doc = {
        "_id": oid, "email": email, "first_name": first, "last_name": last,
        "personal_phone": "+56911112222", "work_extension": "1001",
        "is_slep_staff": True, "unit_id": "6600000000000000000000f1", "rbd": None, "positions": [],
        "status": "active",
        "auth_providers": [{"provider": "local", "hashed_password": "$2b$12$placeholder",
                            "password_changed_at": None, "must_change_password": False}],
        "access": [{"platform_id": p, "role": r, "granted_at": None, "granted_by": None} for p, r in access],
        "invitation": None, "last_login_at": None, "last_activity_at": None,
        "created_at": None, "created_by": None, "updated_at": None, "updated_by": None, "disabled_at": None,
    }
    doc.update(extra)
    return doc


# Admin global (iam/admin) que además es admin de `datos`
ADMIN_USER = _user("6600000000000000000000a0", "admin@slepllanquihue.cl", "Administrador", "SLEP",
                   [("iam", "admin"), ("datos", "admin")])
# Solo `datos`: rol de plataforma sin ser admin global
DATOS_ADMIN_USER = _user("6600000000000000000000a1", "datos.admin@slepllanquihue.cl", "Dora", "Admin", [("datos", "admin")])
EDITOR_USER = _user("6600000000000000000000a2", "editor@slepllanquihue.cl", "Edgar", "Editor", [("datos", "editor")])
VIEWER_USER = _user("6600000000000000000000a3", "viewer@slepllanquihue.cl", "Vera", "Lectura", [("datos", "viewer")])
# Autenticado pero sin acceso a `datos` (solo selloverde)
NO_DATOS_USER = _user("6600000000000000000000a4", "sello@slepllanquihue.cl", "Selo", "Verde", [("selloverde", "viewer")])


# ─── Aislamiento y autenticación para los tests ──────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_database_lifecycle():
    """Ningún test debe conectarse a la base real.

    `TestClient(app)` ejecuta el `lifespan` de `app.main`, que llama a
    `db_service.connect()` (seed + índices) contra `MONGODB_URL`. En un equipo con la
    MongoDB de desarrollo levantada (puerto 27017 publicado por docker-compose), eso
    escribe en la base real. Se reemplaza por un doble que no hace nada.
    """
    with patch("app.main.db_service") as mock_db, patch("app.main.run_bootstrap", new_callable=AsyncMock):
        mock_db.connect = AsyncMock()
        mock_db.close = AsyncMock()
        yield mock_db


from contextlib import contextmanager


@contextmanager
def authenticated_as(user):
    """Autentica de verdad: emite un JWT firmado y simula solo la lectura del usuario.

    A diferencia de parchear `get_current_user` (la dependencia ya quedó capturada al
    importar el controller, así que el parche no surte efecto y la ruta responde 401),
    esto ejercita el camino completo de verificación del token. Cede las cabeceras.
    """
    from app.auth.auth_service import auth_service
    token = auth_service.create_access_token({"sub": str(user["_id"])})
    with patch("app.auth.auth_service.users_service") as mock_users:
        mock_users.find_for_session = AsyncMock(return_value=user)
        mock_users.touch_activity = AsyncMock(return_value=False)
        yield {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _fast_bcrypt():
    """bcrypt con costo mínimo en los tests (el costo real es ~0.25 s por hash)."""
    import app.auth.auth_service as auth_module
    previous = auth_module.BCRYPT_ROUNDS
    auth_module.BCRYPT_ROUNDS = 4
    yield
    auth_module.BCRYPT_ROUNDS = previous


@pytest.fixture
def fake_db():
    """MongoDB en memoria (tests/fake_mongo.py) montada sobre el singleton `db_service`.
    Todos los services comparten ese singleton, así que basta con reemplazar `.db`."""
    from app.database.database_service import db_service
    from tests.fake_mongo import FakeDatabase
    db = FakeDatabase()
    with patch.object(db_service, "db", db):
        yield db


# ─── Helpers para tests con MongoDB en memoria ───────────────────────────────

def as_stored(user: dict) -> dict:
    """Convierte un usuario de los fixtures (ids como string) al formato almacenado en Mongo."""
    import copy
    from bson import ObjectId
    doc = copy.deepcopy(user)
    doc["_id"] = ObjectId(doc["_id"])
    if doc.get("unit_id"):
        doc["unit_id"] = ObjectId(doc["unit_id"])
    for a in doc.get("access", []):
        if a.get("granted_by"):
            a["granted_by"] = ObjectId(a["granted_by"])
    return doc


def seed_users(db, *users):
    """Inserta usuarios de los fixtures en la base en memoria y devuelve sus documentos."""
    docs = [as_stored(u) for u in users]
    db.users.seed(*docs)
    return docs


def bearer_for(user: dict, **claims):
    """Cabecera Authorization con un JWT real para ese usuario (sub = str(_id))."""
    from app.auth.auth_service import auth_service
    token = auth_service.create_access_token({"sub": str(user["_id"]), **claims})
    return {"Authorization": f"Bearer {token}"}


def hashed(password: str) -> str:
    from app.auth.auth_service import auth_service
    return auth_service.get_password_hash(password)


def user_with_password(user: dict, password: str, **overrides) -> dict:
    """Copia del fixture con una contraseña local real (bcrypt de costo mínimo)."""
    import copy
    doc = copy.deepcopy(user)
    doc["auth_providers"] = [{"provider": "local", "hashed_password": hashed(password),
                              "password_changed_at": None, "must_change_password": False}]
    doc.update(overrides)
    return doc


def run(coro):
    """Ejecuta una corrutina desde un test síncrono (preparación de datos con la base en memoria)."""
    import asyncio
    return asyncio.run(coro)


def prepare_org(fake_db, *users):
    """Índices + organigrama + plataformas + usuarios de prueba. Devuelve {code: id(str)} de las unidades."""
    from app.database.database_service import DatabaseService
    from app.platforms.platforms_service import platforms_service
    from app.units.units_service import units_service
    svc = DatabaseService()
    svc.db = fake_db
    run(svc.ensure_indexes())
    run(units_service.ensure_bootstrap_units())
    run(platforms_service.ensure_bootstrap_platforms())
    if users:
        seed_users(fake_db, *users)
    return {d["code"]: str(d["_id"]) for d in fake_db.units.docs}
