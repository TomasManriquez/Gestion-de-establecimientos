"""
test_INT02_no_sensitive_data_leak.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: INT-02 · Test de seguridad: ningún endpoint expone campos sensibles a no-admin
Correlaciones: Requiere BE-03, BE-05

Verifica a nivel de integración (usando TestClient) que:
  - GET /api/establishments nunca incluye password, ssid_password ni licenses
  - GET /api/establishments/{rbd} con token no-admin → passwords redactadas
  - GET /api/establishments/{rbd} con token admin → passwords visibles
  - El campo 'licenses' no aparece en ningún item del listado paginado
"""
import copy
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from tests.conftest import (
    SAMPLE_ESTABLISHMENT, SAMPLE_ESTABLISHMENT_2,
    ADMIN_USER, VIEWER_USER, authenticated_as
)


def make_async_cursor(docs):
    class FakeAsyncCursor:
        def __init__(self, items):
            self._items = iter(items)

        def sort(self, *a, **kw): return self
        def skip(self, n): return self
        def limit(self, n): return self
        def __aiter__(self): return self

        async def __anext__(self):
            try:
                return next(self._items)
            except StopIteration:
                raise StopAsyncIteration

    return FakeAsyncCursor(docs)


def get_test_client_with_mocks(current_user, db_docs, detail_doc=None):
    """Helper: crea TestClient con DB mockeada y usuario autenticado."""
    from app.main import app

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=make_async_cursor(db_docs))
    mock_collection.count_documents = AsyncMock(return_value=len(db_docs))
    mock_collection.find_one = AsyncMock(return_value=detail_doc or db_docs[0] if db_docs else None)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc, \
         patch("app.auth.auth_service.db_service") as mock_auth_db:

        mock_db_svc.db.establishments = mock_collection
        mock_auth_db.db.users.find_one = AsyncMock(return_value=current_user)

        client = TestClient(app)
        return client, mock_collection


# ─── Tests del listado (GET /api/establishments) ──────────────────────────────

def test_INT02_listing_response_never_contains_licenses_field():
    """INT-02 (CRÍTICO): GET /api/establishments no debe incluir 'licenses' en ningún item."""
    from app.main import app

    projected_docs = [
        {
            "_id": "id1", "rbd": "7722", "rbd_full": "7722-3",
            "name": "LICEO POLITÉCNICO PUERTO VARAS", "comuna": "PUERTO VARAS",
            "area_type": "URBANO", "address": "Calle 123",
            "general_info": {"category": "7. LICEO POLITÉCNICO", "adp": "Si", "covertura": "MEDIA"},
            # licenses, connectivity, printers AUSENTES por proyección
        },
        {
            "_id": "id2", "rbd": "7801", "rbd_full": "7801-5",
            "name": "ESCUELA BÁSICA FRUTILLAR", "comuna": "FRUTILLAR",
            "area_type": "RURAL", "address": "Av. Rural 456",
            "general_info": {"category": "6. RURAL MULTIGRADO", "adp": "No", "covertura": "BASICA"},
        }
    ]

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=make_async_cursor(projected_docs))
    mock_collection.count_documents = AsyncMock(return_value=2)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc, \
         authenticated_as(ADMIN_USER) as auth_headers:

        mock_db_svc.db.establishments = mock_collection

        with TestClient(app) as client:
            response = client.get(
                "/api/establishments",
                headers=auth_headers
            )

    assert response.status_code == 200, (
        f"La ruta respondió {response.status_code}: el test no verificaría nada. "
        f"Cuerpo: {response.text}"
    )
    data = response.json()
    items = data.get("items", data) if isinstance(data, dict) else data

    for item in items:
        assert "licenses" not in item, (
            f"El establecimiento '{item.get('name')}' incluye 'licenses' en el listado. "
            "La proyección MongoDB debe excluir este campo."
        )
        assert "connectivity" not in item, (
            f"El establecimiento '{item.get('name')}' incluye 'connectivity' en el listado. "
            "Este campo contiene ssid_password."
        )
        assert "printers" not in item, (
            f"El establecimiento '{item.get('name')}' incluye 'printers' en el listado."
        )


def test_INT02_listing_response_does_not_contain_password_string_anywhere():
    """INT-02 (CRÍTICO): El JSON del listado no debe contener la cadena 'password' como clave."""
    from app.main import app

    projected_docs = [
        {
            "_id": "id1", "rbd": "7722", "rbd_full": "7722-3",
            "name": "LICEO POLITÉCNICO", "comuna": "PUERTO VARAS",
            "area_type": "URBANO", "address": "",
            "general_info": {"category": "", "adp": "", "covertura": ""},
        }
    ]

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=make_async_cursor(projected_docs))
    mock_collection.count_documents = AsyncMock(return_value=1)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc, \
         authenticated_as(ADMIN_USER) as auth_headers:

        mock_db_svc.db.establishments = mock_collection

        with TestClient(app) as client:
            response = client.get(
                "/api/establishments",
                headers=auth_headers
            )

    assert response.status_code == 200, (
        f"La ruta respondió {response.status_code}: el test no verificaría nada. "
        f"Cuerpo: {response.text}"
    )
    raw_json = response.text
    # Buscar 'password' como clave JSON (entre comillas seguida de :)
    import re
    password_keys = re.findall(r'"password"\s*:', raw_json)
    assert len(password_keys) == 0, (
        f"El JSON del listado contiene {len(password_keys)} ocurrencia(s) de '\"password\":'. "
        "CRÍTICO: Ningún campo password debe estar en la respuesta del directorio."
    )


# ─── Tests del detalle (GET /api/establishments/{rbd}) ────────────────────────

def test_INT02_detail_with_non_admin_token_returns_redacted_passwords():
    """INT-02: GET /api/establishments/{rbd} con token no-admin retorna passwords redactadas."""
    from app.main import app

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc, \
         authenticated_as(VIEWER_USER) as auth_headers:

        mock_db_svc.db.establishments.find_one = AsyncMock(return_value=copy.deepcopy(SAMPLE_ESTABLISHMENT))

        with TestClient(app) as client:
            response = client.get(
                "/api/establishments/7722",
                headers=auth_headers
            )

    assert response.status_code == 200, (
        f"La ruta respondió {response.status_code}: el test no verificaría nada. "
        f"Cuerpo: {response.text}"
    )
    data = response.json()

    # Verificar licenses
    for lic in data.get("licenses", []):
        pw = lic.get("password", "")
        assert pw == "[REDACTED]", (
            f"Usuario viewer recibió password='{pw}'. "
            "Debe ser '[REDACTED]' para usuarios sin rol admin."
        )

    # Verificar ssid_password
    ssid_pw = data.get("connectivity", {}).get("ssid_password", "")
    assert ssid_pw == "[REDACTED]", (
        f"Usuario viewer recibió ssid_password='{ssid_pw}'. "
        "Debe ser '[REDACTED]' para usuarios sin rol admin."
    )


def test_INT02_detail_with_admin_token_returns_real_passwords():
    """INT-02: GET /api/establishments/{rbd} con token admin retorna passwords reales."""
    from app.main import app

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc, \
         authenticated_as(ADMIN_USER) as auth_headers:

        mock_db_svc.db.establishments.find_one = AsyncMock(return_value=copy.deepcopy(SAMPLE_ESTABLISHMENT))

        with TestClient(app) as client:
            response = client.get(
                "/api/establishments/7722",
                headers=auth_headers
            )

    assert response.status_code == 200, (
        f"La ruta respondió {response.status_code}: el test no verificaría nada. "
        f"Cuerpo: {response.text}"
    )
    data = response.json()

    for lic in data.get("licenses", []):
        pw = lic.get("password", "")
        assert pw != "[REDACTED]", (
            "Admin recibió '[REDACTED]' en un password. "
            "El admin debe ver las contraseñas reales."
        )

    ssid_pw = data.get("connectivity", {}).get("ssid_password", "")
    assert ssid_pw != "[REDACTED]", (
        "Admin recibió '[REDACTED]' en ssid_password."
    )
