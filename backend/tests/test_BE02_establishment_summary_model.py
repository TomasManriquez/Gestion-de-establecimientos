"""
test_BE02_establishment_summary_model.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: BE-02 · Crear modelo Pydantic EstablishmentSummary para el listado
Correlaciones: Requiere BE-01 · Bloquea BE-03, FE-01

Verifica que:
  - EstablishmentSummary existe en establishments_entity
  - Contiene solo los campos necesarios para el listado
  - NO contiene campos de connectivity, printers ni licenses
  - Los campos de general_info están aplanados (no anidados)
  - Valida correctamente con Pydantic v2
  - EstablishmentListResponse existe para la paginación (BE-04)
"""
import pytest
from pydantic import ValidationError


# ─── Tests de existencia del modelo ──────────────────────────────────────────

def test_BE02_establishment_summary_exists():
    """BE-02: EstablishmentSummary debe existir en establishments_entity."""
    try:
        from app.establishments.establishments_entity import EstablishmentSummary
    except ImportError:
        pytest.fail(
            "EstablishmentSummary no existe en establishments_entity.py. "
            "Crear clase EstablishmentSummary(BaseModel) con los campos del listado."
        )


def test_BE02_establishment_list_response_exists():
    """BE-02/BE-04: EstablishmentListResponse debe existir para la paginación."""
    try:
        from app.establishments.establishments_entity import EstablishmentListResponse
    except ImportError:
        pytest.fail(
            "EstablishmentListResponse no existe en establishments_entity.py. "
            "Crear clase EstablishmentListResponse(BaseModel) con {items, total, page, page_size, total_pages}."
        )


# ─── Tests de campos requeridos ───────────────────────────────────────────────

def test_BE02_summary_has_required_listing_fields():
    """BE-02: EstablishmentSummary debe tener los campos necesarios para el directorio."""
    from app.establishments.establishments_entity import EstablishmentSummary

    required_fields = {"rbd", "rbd_full", "name", "comuna", "area_type"}
    model_fields = set(EstablishmentSummary.model_fields.keys())

    missing = required_fields - model_fields
    assert not missing, (
        f"EstablishmentSummary le faltan campos obligatorios: {missing}. "
        "El directorio necesita al menos: rbd, rbd_full, name, comuna, area_type."
    )


def test_BE02_summary_has_flattened_general_info_fields():
    """BE-02: category, adp, covertura deben ser campos directos (no anidados en general_info)."""
    from app.establishments.establishments_entity import EstablishmentSummary

    model_fields = set(EstablishmentSummary.model_fields.keys())
    flattened_fields = {"category", "adp", "covertura"}

    missing_flat = flattened_fields - model_fields
    assert not missing_flat, (
        f"Los campos {missing_flat} deben ser aplanados directamente en EstablishmentSummary "
        "(no anidados bajo general_info). El directorio los muestra en columnas directas."
    )


# ─── Tests de campos PROHIBIDOS ──────────────────────────────────────────────

def test_BE02_summary_does_not_contain_licenses():
    """BE-02 (SEGURIDAD): EstablishmentSummary NO debe tener el campo licenses."""
    from app.establishments.establishments_entity import EstablishmentSummary

    model_fields = set(EstablishmentSummary.model_fields.keys())
    assert "licenses" not in model_fields, (
        "EstablishmentSummary contiene 'licenses'. "
        "CRÍTICO: Este campo contiene contraseñas en texto plano. "
        "No debe estar en el modelo del listado."
    )


def test_BE02_summary_does_not_contain_connectivity():
    """BE-02 (SEGURIDAD): EstablishmentSummary NO debe tener el campo connectivity."""
    from app.establishments.establishments_entity import EstablishmentSummary

    model_fields = set(EstablishmentSummary.model_fields.keys())
    assert "connectivity" not in model_fields, (
        "EstablishmentSummary contiene 'connectivity'. "
        "Este campo incluye ssid_password. No debe estar en el modelo del listado."
    )


def test_BE02_summary_does_not_contain_printers():
    """BE-02: EstablishmentSummary NO debe tener el campo printers."""
    from app.establishments.establishments_entity import EstablishmentSummary

    model_fields = set(EstablishmentSummary.model_fields.keys())
    assert "printers" not in model_fields, (
        "EstablishmentSummary contiene 'printers'. "
        "Las impresoras son datos de la ficha de detalle, no del listado."
    )


def test_BE02_summary_does_not_contain_general_info_nested():
    """BE-02: EstablishmentSummary NO debe tener general_info como objeto anidado."""
    from app.establishments.establishments_entity import EstablishmentSummary

    model_fields = set(EstablishmentSummary.model_fields.keys())
    assert "general_info" not in model_fields, (
        "EstablishmentSummary contiene 'general_info' como objeto anidado. "
        "Los campos deben estar aplanados directamente: category, adp, covertura."
    )


# ─── Tests de validación Pydantic ─────────────────────────────────────────────

def test_BE02_summary_validates_correctly_with_full_data():
    """BE-02: EstablishmentSummary debe validar con datos completos sin errores."""
    from app.establishments.establishments_entity import EstablishmentSummary

    valid_data = {
        "rbd": "7722",
        "rbd_full": "7722-3",
        "name": "LICEO POLITÉCNICO PUERTO VARAS",
        "comuna": "PUERTO VARAS",
        "area_type": "URBANO",
        "address": "Calle Ejemplo 123",
        "category": "7. LICEO POLITÉCNICO",
        "adp": "Si",
        "covertura": "MEDIA",
    }

    try:
        summary = EstablishmentSummary(**valid_data)
        assert summary.rbd == "7722"
        assert summary.name == "LICEO POLITÉCNICO PUERTO VARAS"
    except ValidationError as e:
        pytest.fail(f"EstablishmentSummary lanzó ValidationError con datos válidos: {e}")


def test_BE02_summary_validates_with_optional_fields_missing():
    """BE-02: EstablishmentSummary debe funcionar aunque falten campos opcionales."""
    from app.establishments.establishments_entity import EstablishmentSummary

    minimal_data = {
        "rbd": "7801",
        "rbd_full": "7801-5",
        "name": "ESCUELA RURAL",
        "comuna": "FRUTILLAR",
        "area_type": "RURAL",
        "address": "",
    }

    try:
        summary = EstablishmentSummary(**minimal_data)
        assert summary.rbd == "7801"
    except ValidationError as e:
        pytest.fail(
            f"EstablishmentSummary requiere campos que deberían ser opcionales: {e}. "
            "Añadir Optional[] y default='' a campos como category, adp, covertura."
        )


# ─── Test de consistencia con Establishment ──────────────────────────────────

def test_BE02_all_summary_fields_exist_in_establishment():
    """BE-02/BE-06: Todo campo de EstablishmentSummary debe existir en Establishment."""
    from app.establishments.establishments_entity import EstablishmentSummary, Establishment

    summary_fields = set(EstablishmentSummary.model_fields.keys())
    establishment_fields = set(Establishment.model_fields.keys())

    # Los campos aplanados (category, adp, covertura) están en general_info
    # del Establishment, no directamente — esta verificación valida el resto
    direct_fields = summary_fields - {"category", "adp", "covertura"}
    missing_in_full = direct_fields - establishment_fields

    assert not missing_in_full, (
        f"Los campos {missing_in_full} de EstablishmentSummary no existen en Establishment. "
        "Inconsistencia en el contrato de datos."
    )
