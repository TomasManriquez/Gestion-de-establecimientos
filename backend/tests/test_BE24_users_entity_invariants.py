"""
test_BE24_users_entity_invariants.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-17 · Modelo `users` con invariantes (R1, R8, R9, T1, T2)

Verifica que el estado inválido es imposible de construir:
  - funcionario SLEP  <=> unit_id, sin rbd, sin positions
  - usuario de establecimiento <=> rbd y al menos un cargo, sin unit_id
  - positions es un enum cerrado de 10 valores (sin ENCARGADO_CONVIVENCIA)
  - el correo se normaliza y su dominio está en ALLOWED_EMAIL_DOMAINS
  - formatos de teléfono y anexo, longitudes máximas y extra='forbid'
"""
import pytest
from pydantic import ValidationError
from app.users.users_entity import (
    UserCreate, UserAdminUpdate, UserSelfUpdate, EstablishmentPosition, User, UserSummary, UserMe,
)
from app.counterparts.counterparts_entity import CounterpartRole

UNIT = "6600000000000000000000a1"


def slep(**kw):
    base = dict(email="ana.perez@slepllanquihue.cl", first_name="Ana", last_name="Pérez",
                is_slep_staff=True, unit_id=UNIT)
    base.update(kw)
    return UserCreate(**base)


def school(**kw):
    base = dict(email="luis.soto@slepllanquihue.cl", first_name="Luis", last_name="Soto",
                is_slep_staff=False, rbd="7722", positions=["DOCENTE"])
    base.update(kw)
    return UserCreate(**base)


# ─── Modo funcionario SLEP / establecimiento ─────────────────────────────────

def test_BE24_slep_staff_requires_unit_and_nothing_else():
    assert slep().unit_id == UNIT
    with pytest.raises(ValidationError, match="unit_id"):
        slep(unit_id=None)
    with pytest.raises(ValidationError, match="rbd"):
        slep(rbd="7722")
    with pytest.raises(ValidationError, match="positions"):
        slep(positions=["DOCENTE"])


def test_BE24_establishment_user_requires_rbd_and_positions():
    assert school().rbd == "7722"
    with pytest.raises(ValidationError, match="rbd"):
        school(rbd=None)
    with pytest.raises(ValidationError, match="al menos un cargo"):
        school(positions=[])
    with pytest.raises(ValidationError, match="unit_id"):
        school(unit_id=UNIT)


def test_BE24_neither_unit_nor_rbd_is_invalid_in_both_modes():
    with pytest.raises(ValidationError):
        UserCreate(email="x.y@slepllanquihue.cl", first_name="X", last_name="Y", is_slep_staff=True)
    with pytest.raises(ValidationError):
        UserCreate(email="x.y@slepllanquihue.cl", first_name="X", last_name="Y", is_slep_staff=False)


# ─── Cargos ──────────────────────────────────────────────────────────────────

def test_BE24_positions_enum_is_closed():
    assert len(EstablishmentPosition) == 10
    assert school(positions=["DOCENTE", "PIE_ENCARGADO"]).positions == [
        EstablishmentPosition.DOCENTE, EstablishmentPosition.PIE_ENCARGADO]
    assert school(positions=["ASISTENTE_EDUCACION"]).positions == [EstablishmentPosition.ASISTENTE_EDUCACION]
    assert "ENCARGADO_CONVIVENCIA" not in EstablishmentPosition.__members__
    with pytest.raises(ValidationError):
        school(positions=["ENCARGADO_CONVIVENCIA"])
    with pytest.raises(ValidationError):
        school(positions=["JEFE_DE_NADA"])
    with pytest.raises(ValidationError, match="repetidos"):
        school(positions=["DOCENTE", "DOCENTE"])


def test_BE24_position_values_match_counterpart_role():
    common = {"DIRECTOR", "UTP_JEFE", "PIE_ENCARGADO", "CONVIVENCIA_ESCOLAR", "INSPECTOR_GENERAL", "SIGE_ENCARGADO"}
    for name in common:
        assert EstablishmentPosition[name].value == CounterpartRole[name].value
    assert {p.name for p in EstablishmentPosition} - common == {"SECRETARIO", "ADMINISTRADOR", "DOCENTE", "ASISTENTE_EDUCACION"}


# ─── Correo ──────────────────────────────────────────────────────────────────

def test_BE24_email_normalized_and_domain_checked():
    assert slep(email="  Ana.Perez@SLEPllanquihue.CL ").email == "ana.perez@slepllanquihue.cl"
    for bad in ("ana@gmail.com", "ana@slepllanquihue.gob.cl", "ana@sub.slepllanquihue.cl", "sin-arroba", "a@b"):
        with pytest.raises(ValidationError):
            slep(email=bad)


# ─── Formatos y longitudes ───────────────────────────────────────────────────

def test_BE24_phone_and_extension_formats():
    assert slep(personal_phone="+56912345678", work_extension="4521").work_extension == "4521"
    for bad in ("912345678", "+5691234567", "+56 9 1234 5678", "+569123456789", "+56912345678; DROP"):
        with pytest.raises(ValidationError):
            slep(personal_phone=bad)
    for bad in ("4", "1234567", "45a1", "45 21", "٤٥٢١"):
        with pytest.raises(ValidationError):
            slep(work_extension=bad)


def test_BE24_surrounding_whitespace_is_stripped_not_rejected():
    assert slep(work_extension=" 4521\n").work_extension == "4521"


def test_BE24_max_lengths_and_extra_forbid():
    with pytest.raises(ValidationError):
        slep(first_name="a" * 81)
    with pytest.raises(ValidationError):
        slep(last_name="")
    with pytest.raises(ValidationError):
        slep(email="a" * 250 + "@slepllanquihue.cl")
    for extra in ("status", "access", "hashed_password", "created_by", "_id", "role"):
        with pytest.raises(ValidationError, match="Extra inputs"):
            slep(**{extra: "x"})


def test_BE24_operator_objects_are_rejected_where_scalars_are_expected():
    for field in ("email", "first_name", "unit_id", "rbd", "personal_phone"):
        with pytest.raises(ValidationError):
            slep(**{field: {"$ne": None}})


def test_BE24_unit_id_and_rbd_formats():
    with pytest.raises(ValidationError):
        slep(unit_id="no-es-un-objectid")
    with pytest.raises(ValidationError):
        school(rbd="77x2")
    with pytest.raises(ValidationError):
        school(rbd="1" * 9)


# ─── Modelos por audiencia ───────────────────────────────────────────────────

def test_BE24_self_update_only_accepts_phone_and_extension():
    assert UserSelfUpdate(personal_phone="+56912345678", work_extension="123").work_extension == "123"
    for forbidden in ("access", "status", "unit_id", "email", "first_name", "rbd", "positions", "is_slep_staff"):
        with pytest.raises(ValidationError, match="Extra inputs"):
            UserSelfUpdate(**{forbidden: "x"})


def test_BE24_admin_update_forbids_access_status_and_providers():
    UserAdminUpdate(first_name="Nueva")
    for forbidden in ("access", "status", "auth_providers", "hashed_password", "created_by"):
        with pytest.raises(ValidationError, match="Extra inputs"):
            UserAdminUpdate(**{forbidden: "x"})


def test_BE24_response_models_never_declare_hashes():
    for model in (User, UserSummary, UserMe):
        assert "hashed_password" not in model.model_fields
        assert "token_hash" not in model.model_fields
    assert "personal_phone" not in UserSummary.model_fields          # el listado no lo proyecta
    assert "auth_providers" not in UserSummary.model_fields
    assert "personal_phone" in User.model_fields and "personal_phone" in UserMe.model_fields
