"""
test_BE13_redacted_marker_protection.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-06 · Sobrescritura de secretos redactados (C5, C20, T4)

Antes: un cliente que recibía el detalle con "[REDACTED]" y lo reenviaba completo en el PUT
guardaba el literal "[REDACTED]" encima de la contraseña real (EditFicha.jsx:35 y :173-175).
Ahora el marcador conserva el valor almacenado o se rechaza; nunca se persiste.
"""
import copy
import pytest
from app.establishments.establishments_entity import EstablishmentUpdate, RedactedPlaceholderError
from app.establishments.establishments_service import establishments_service
from tests.conftest import SAMPLE_ESTABLISHMENT

MARK = "[REDACTED]"


def lic(name="Plataforma SIGE", password=MARK, **kw):
    return {"name": name, "email": "admin@liceo.cl", "password": password, "url": "", "obs": "", "is_new": False, **kw}


@pytest.fixture
def est(fake_db):
    fake_db.establishments.seed(copy.deepcopy(SAMPLE_ESTABLISHMENT))
    return fake_db.establishments


@pytest.mark.asyncio
async def test_BE13_redacted_marker_preserves_stored_license_password(est):
    await establishments_service.update_by_rbd("7722", EstablishmentUpdate(licenses=[lic()]))
    assert est.docs[0]["licenses"][0]["password"] == "clave-secreta-sige"


@pytest.mark.asyncio
async def test_BE13_redacted_marker_preserves_stored_ssid_password(est):
    conn = copy.deepcopy(SAMPLE_ESTABLISHMENT["connectivity"]); conn["ssid_password"] = MARK
    await establishments_service.update_by_rbd("7722", EstablishmentUpdate(connectivity=conn))
    assert est.docs[0]["connectivity"]["ssid_password"] == "password-secreta-wifi"


@pytest.mark.asyncio
async def test_BE13_redacted_marker_without_stored_value_rejected(est):
    est.docs[0]["licenses"] = []
    with pytest.raises(RedactedPlaceholderError):
        await establishments_service.update_by_rbd("7722", EstablishmentUpdate(licenses=[lic()]))
    assert est.docs[0]["licenses"] == [] and "update_one" not in est.calls          # no se escribió nada


@pytest.mark.asyncio
async def test_BE13_marker_without_stored_ssid_rejected(est):
    est.docs[0]["connectivity"]["ssid_password"] = ""
    conn = copy.deepcopy(SAMPLE_ESTABLISHMENT["connectivity"]); conn["ssid_password"] = MARK
    with pytest.raises(RedactedPlaceholderError):
        await establishments_service.update_by_rbd("7722", EstablishmentUpdate(connectivity=conn))


@pytest.mark.asyncio
async def test_BE13_marker_with_mismatched_entry_rejected(est):
    """Lista reordenada: en esa posición hay otra licencia. El backend no adivina."""
    with pytest.raises(RedactedPlaceholderError):
        await establishments_service.update_by_rbd("7722", EstablishmentUpdate(licenses=[lic(name="Otra plataforma")]))
    assert est.docs[0]["licenses"][0]["password"] == "clave-secreta-sige"


@pytest.mark.asyncio
async def test_BE13_new_password_overwrites(est):
    await establishments_service.update_by_rbd("7722", EstablishmentUpdate(licenses=[lic(password="NUEVA-clave-1")]))
    assert est.docs[0]["licenses"][0]["password"] == "NUEVA-clave-1"


@pytest.mark.asyncio
async def test_BE13_marker_is_never_persisted(est):
    conn = copy.deepcopy(SAMPLE_ESTABLISHMENT["connectivity"]); conn["ssid_password"] = MARK
    await establishments_service.update_by_rbd("7722", EstablishmentUpdate(licenses=[lic()], connectivity=conn))
    assert MARK not in str(est.docs[0])


@pytest.mark.asyncio
async def test_BE13_put_response_is_redacted_when_caller_is_not_sensitive(est):
    """D4: la respuesta del PUT ya no devuelve credenciales a quien no corresponde."""
    redacted = await establishments_service.update_by_rbd("7722", EstablishmentUpdate(name="X"), include_sensitive=False)
    clear = await establishments_service.update_by_rbd("7722", EstablishmentUpdate(name="Y"), include_sensitive=True)
    assert redacted["licenses"][0]["password"] == MARK and redacted["connectivity"]["ssid_password"] == MARK
    assert clear["licenses"][0]["password"] == "clave-secreta-sige"
    assert est.docs[0]["licenses"][0]["password"] == "clave-secreta-sige"            # la base no se contaminó
