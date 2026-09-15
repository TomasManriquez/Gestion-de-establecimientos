"""
test_BE05_licenses_access_control.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: BE-05 · Controlar acceso a campos sensibles según rol del usuario
Correlaciones: Independiente · Complementa BE-03

Verifica que:
  - Un usuario admin recibe licenses[].password visible
  - Un usuario no-admin recibe licenses[].password como "[REDACTED]"
  - ssid_password también se redacta para no-admin
  - find_by_rbd() acepta parámetro include_sensitive
  - El controller pasa include_sensitive según el rol del usuario autenticado
"""
import copy
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tests.conftest import SAMPLE_ESTABLISHMENT, ADMIN_USER, VIEWER_USER


# ─── Tests de firma del método ────────────────────────────────────────────────

def test_BE05_find_by_rbd_accepts_include_sensitive_param():
    """BE-05: find_by_rbd() debe aceptar parámetro include_sensitive."""
    import inspect
    from app.establishments.establishments_service import EstablishmentsService

    sig = inspect.signature(EstablishmentsService.find_by_rbd)
    params = sig.parameters

    assert "include_sensitive" in params, (
        "find_by_rbd() no tiene el parámetro 'include_sensitive'. "
        "Añadir: async def find_by_rbd(self, rbd: str, include_sensitive: bool = False)"
    )

    default = params["include_sensitive"].default
    assert default == False, (
        f"El default de include_sensitive es {default}, se esperaba False. "
        "Por defecto debe redactar datos sensibles (principio de mínimo privilegio)."
    )


# ─── Tests de redacción de licenses ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_BE05_non_admin_receives_redacted_license_password():
    """BE-05: Usuario no-admin recibe licenses[].password == '[REDACTED]'."""
    from app.establishments.establishments_service import EstablishmentsService

    doc = copy.deepcopy(SAMPLE_ESTABLISHMENT)
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=doc)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        result = await svc.find_by_rbd("7722", include_sensitive=False)

    assert result is not None
    licenses = result.get("licenses", [])

    for lic in licenses:
        password = lic.get("password", "")
        assert password == "[REDACTED]", (
            f"licenses[].password es '{password}' para usuario no-admin. "
            "Debe ser '[REDACTED]' cuando include_sensitive=False."
        )


@pytest.mark.asyncio
async def test_BE05_admin_receives_real_license_password():
    """BE-05: Usuario admin recibe licenses[].password real."""
    from app.establishments.establishments_service import EstablishmentsService

    doc = copy.deepcopy(SAMPLE_ESTABLISHMENT)
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=doc)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        result = await svc.find_by_rbd("7722", include_sensitive=True)

    assert result is not None
    licenses = result.get("licenses", [])

    for lic in licenses:
        password = lic.get("password", "")
        assert password != "[REDACTED]", (
            "licenses[].password está redactado para usuario admin con include_sensitive=True. "
            "El admin debe ver las contraseñas reales."
        )
        assert password != "", "El admin recibió password vacío, se esperaba la clave real."


# ─── Tests de redacción de ssid_password ──────────────────────────────────────

@pytest.mark.asyncio
async def test_BE05_non_admin_receives_redacted_ssid_password():
    """BE-05: Usuario no-admin recibe connectivity.ssid_password == '[REDACTED]'."""
    from app.establishments.establishments_service import EstablishmentsService

    doc = copy.deepcopy(SAMPLE_ESTABLISHMENT)
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=doc)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        result = await svc.find_by_rbd("7722", include_sensitive=False)

    assert result is not None
    connectivity = result.get("connectivity", {})
    ssid_pw = connectivity.get("ssid_password", "")

    assert ssid_pw == "[REDACTED]", (
        f"connectivity.ssid_password es '{ssid_pw}' para usuario no-admin. "
        "Debe ser '[REDACTED]' cuando include_sensitive=False."
    )


@pytest.mark.asyncio
async def test_BE05_admin_receives_real_ssid_password():
    """BE-05: Usuario admin recibe connectivity.ssid_password real."""
    from app.establishments.establishments_service import EstablishmentsService

    doc = copy.deepcopy(SAMPLE_ESTABLISHMENT)
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=doc)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        result = await svc.find_by_rbd("7722", include_sensitive=True)

    connectivity = result.get("connectivity", {})
    ssid_pw = connectivity.get("ssid_password", "")

    assert ssid_pw not in ("", "[REDACTED]"), (
        f"connectivity.ssid_password está redactado/vacío para admin. "
        "El admin debe recibir la clave WiFi real."
    )


# ─── Tests del controller: include_sensitive según rol ───────────────────────

@pytest.mark.asyncio
async def test_BE05_controller_passes_include_sensitive_true_for_admin():
    """BE-05: El controller debe llamar find_by_rbd con include_sensitive=True para admin."""
    from app.establishments.establishments_service import EstablishmentsService

    with patch.object(EstablishmentsService, "find_by_rbd", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = {**SAMPLE_ESTABLISHMENT}

        with patch("app.establishments.establishments_controller.establishments_service") as mock_svc, \
             patch("app.establishments.establishments_controller.auth_service.get_current_user",
                   new_callable=AsyncMock) as mock_auth:

            mock_auth.return_value = ADMIN_USER
            mock_svc.find_by_rbd = mock_find

            # Importar y llamar al controller manualmente
            from app.establishments.establishments_controller import get_establishment_detail
            result = await get_establishment_detail(rbd="7722", current_user=ADMIN_USER)

    # Verificar que find_by_rbd fue llamado con include_sensitive=True
    call_kwargs = mock_find.call_args
    if call_kwargs:
        args, kwargs = call_kwargs
        include_sensitive = kwargs.get("include_sensitive", args[1] if len(args) > 1 else None)
        assert include_sensitive is True, (
            f"Controller llamó find_by_rbd con include_sensitive={include_sensitive} para admin. "
            "Debe ser True para usuarios con role='admin'."
        )


@pytest.mark.asyncio
async def test_BE05_controller_passes_include_sensitive_false_for_viewer():
    """BE-05: El controller debe llamar find_by_rbd con include_sensitive=False para no-admin."""
    with patch("app.establishments.establishments_service.EstablishmentsService.find_by_rbd",
               new_callable=AsyncMock) as mock_find:

        mock_find.return_value = {**SAMPLE_ESTABLISHMENT}

        with patch("app.establishments.establishments_controller.establishments_service") as mock_svc:
            mock_svc.find_by_rbd = mock_find

            from app.establishments.establishments_controller import get_establishment_detail
            await get_establishment_detail(rbd="7722", current_user=VIEWER_USER)

    if mock_find.call_args:
        args, kwargs = mock_find.call_args
        include_sensitive = kwargs.get("include_sensitive", False)
        assert include_sensitive is False, (
            f"Controller llamó find_by_rbd con include_sensitive={include_sensitive} para viewer. "
            "Debe ser False para usuarios sin rol admin."
        )
