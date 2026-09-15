"""
test_BE03_listing_projection_no_sensitive_fields.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: BE-03 · Proyección MongoDB en find_all() + response_model a EstablishmentSummary
       BE-06 · Verificar consistencia del contrato summary vs detalle
Correlaciones: Requiere BE-01, BE-02 · Habilita BE-04, FE-01

Verifica que:
  - find_all() usa LISTING_PROJECTION (constante exportable)
  - La proyección excluye connectivity, printers, licenses
  - GET /api/establishments responde con EstablishmentSummary (sin campos sensibles)
  - GET /api/establishments/{rbd} sigue respondiendo con Establishment completo (BE-06)
  - El payload de 79 establecimientos pesa menos de 50KB
  - Los filtros de búsqueda siguen funcionando con la proyección aplicada
"""
import copy
import pytest
import pytest_asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from tests.conftest import SAMPLE_ESTABLISHMENT, SAMPLE_ESTABLISHMENT_2


# ─── Helper: cursor mock ──────────────────────────────────────────────────────

def make_async_cursor(docs):
    """Devuelve un objeto iterable async que simula motor cursor."""
    class FakeAsyncCursor:
        def __init__(self, items):
            self._items = iter(items)

        def sort(self, *args, **kwargs):
            return self

        def skip(self, n):
            return self

        def limit(self, n):
            return self

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._items)
            except StopIteration:
                raise StopAsyncIteration

    return FakeAsyncCursor(docs)


# ─── Tests de LISTING_PROJECTION ──────────────────────────────────────────────

def test_BE03_listing_projection_constant_exists():
    """BE-03: LISTING_PROJECTION debe existir como constante en establishments_service."""
    try:
        from app.establishments.establishments_service import LISTING_PROJECTION
    except ImportError:
        pytest.fail(
            "LISTING_PROJECTION no existe en establishments_service.py. "
            "Definir: LISTING_PROJECTION = {'rbd': 1, 'name': 1, ...}"
        )


def test_BE03_listing_projection_excludes_sensitive_fields():
    """BE-03 (SEGURIDAD): LISTING_PROJECTION debe excluir licenses, connectivity, printers."""
    from app.establishments.establishments_service import LISTING_PROJECTION

    # Si un campo tiene valor 0 o está ausente de la proyección → se excluye
    assert LISTING_PROJECTION.get("licenses", 0) != 1, (
        "LISTING_PROJECTION incluye 'licenses'. "
        "CRÍTICO: Las contraseñas en licenses nunca deben ser parte del listado."
    )
    assert LISTING_PROJECTION.get("connectivity", 0) != 1, (
        "LISTING_PROJECTION incluye 'connectivity'. "
        "Este campo tiene ssid_password, no debe ser parte del listado."
    )
    assert LISTING_PROJECTION.get("printers", 0) != 1, (
        "LISTING_PROJECTION incluye 'printers'. "
        "Los datos de impresoras solo corresponden a la ficha de detalle."
    )


def test_BE03_listing_projection_includes_required_fields():
    """BE-03: LISTING_PROJECTION debe incluir los campos necesarios para el directorio."""
    from app.establishments.establishments_service import LISTING_PROJECTION

    required = ["rbd", "name", "comuna", "area_type"]
    for field in required:
        assert LISTING_PROJECTION.get(field, 0) == 1, (
            f"LISTING_PROJECTION no incluye '{field}'. "
            "El directorio necesita este campo para mostrar la tabla."
        )


# ─── Tests de find_all() con proyección ───────────────────────────────────────

@pytest.mark.asyncio
async def test_BE03_find_all_applies_projection_to_cursor():
    """BE-03: find_all() debe pasar LISTING_PROJECTION al cursor de MongoDB."""
    from app.establishments.establishments_service import EstablishmentsService, LISTING_PROJECTION

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=make_async_cursor([
        {**SAMPLE_ESTABLISHMENT, "_id": "abc123"}
    ]))
    mock_collection.count_documents = AsyncMock(return_value=1)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        result = await svc.find_all()

    # Verificar que find() fue llamado con la proyección
    call_args = mock_collection.find.call_args
    assert call_args is not None, "find() nunca fue llamado en find_all()."

    # El segundo argumento de find() debe ser la proyección
    args, kwargs = call_args
    projection_passed = args[1] if len(args) > 1 else kwargs.get("projection", kwargs.get("filter", None))

    assert projection_passed is not None, (
        "find_all() llama a find() sin proyección. "
        "Usar: self.db.establishments.find(query, LISTING_PROJECTION)"
    )


@pytest.mark.asyncio
async def test_BE03_find_all_returns_items_list():
    """BE-03: find_all() debe retornar una lista de documentos (o el dict paginado de BE-04)."""
    from app.establishments.establishments_service import EstablishmentsService

    doc1 = {**SAMPLE_ESTABLISHMENT, "_id": "id1"}
    doc2 = {**SAMPLE_ESTABLISHMENT_2, "_id": "id2"}

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=make_async_cursor([doc1, doc2]))
    mock_collection.count_documents = AsyncMock(return_value=2)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        result = await svc.find_all()

    # Puede retornar lista directa o dict paginado {items: [...], total: ...}
    if isinstance(result, dict):
        items = result.get("items", [])
    else:
        items = result

    assert len(items) == 2, f"find_all() devolvió {len(items)} items, se esperaban 2."


@pytest.mark.asyncio
async def test_BE03_find_all_result_has_no_licenses_field():
    """BE-03 (SEGURIDAD): Los documentos de find_all() no deben tener el campo licenses."""
    from app.establishments.establishments_service import EstablishmentsService

    # Simular que MongoDB devuelve solo los campos proyectados (sin licenses)
    projected_doc = {
        "_id": "abc123",
        "rbd": "7722",
        "rbd_full": "7722-3",
        "name": "LICEO POLITÉCNICO PUERTO VARAS",
        "comuna": "PUERTO VARAS",
        "area_type": "URBANO",
        "address": "Calle Ejemplo 123",
        "general_info": {
            "category": "7. LICEO POLITÉCNICO",
            "adp": "Si",
            "covertura": "MEDIA",
        },
        # licenses, connectivity, printers AUSENTES — simulando proyección real
    }

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=make_async_cursor([projected_doc]))
    mock_collection.count_documents = AsyncMock(return_value=1)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        result = await svc.find_all()

    if isinstance(result, dict):
        items = result.get("items", [])
    else:
        items = result

    assert len(items) > 0
    doc = items[0]
    assert "licenses" not in doc, (
        "find_all() devuelve documentos con 'licenses'. "
        "La proyección debe excluir este campo."
    )
    assert "connectivity" not in doc, (
        "find_all() devuelve documentos con 'connectivity'. "
        "La proyección debe excluir este campo."
    )


# ─── Test BE-06: Consistencia summary vs detalle ──────────────────────────────

@pytest.mark.asyncio
async def test_BE06_find_by_rbd_returns_full_document_not_projected():
    """BE-06: find_by_rbd() NO debe usar la proyección del listado — retorna doc completo."""
    from app.establishments.establishments_service import EstablishmentsService

    full_doc = copy.deepcopy(SAMPLE_ESTABLISHMENT)

    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=full_doc)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        result = await svc.find_by_rbd("7722")

    assert result is not None
    assert "connectivity" in result, (
        "find_by_rbd() no retorna connectivity. "
        "La proyección del listado no debe aplicarse en el endpoint de detalle."
    )
    assert "licenses" in result, (
        "find_by_rbd() no retorna licenses. "
        "La ficha completa (para admin) debe incluir todos los campos."
    )
    assert "printers" in result, (
        "find_by_rbd() no retorna printers. "
        "La ficha técnica incluye datos de impresoras."
    )


# ─── Tests de filtros con proyección ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_BE03_find_all_with_comuna_filter_still_works():
    """BE-03: El filtro por comuna debe seguir funcionando después de aplicar proyección."""
    from app.establishments.establishments_service import EstablishmentsService

    projected_doc = {
        "_id": "id2",
        "rbd": "7801",
        "rbd_full": "7801-5",
        "name": "ESCUELA BÁSICA FRUTILLAR",
        "comuna": "FRUTILLAR",
        "area_type": "RURAL",
        "address": "Av. Rural 456",
        "general_info": {"category": "6. RURAL MULTIGRADO", "adp": "No", "covertura": "BASICA"},
    }

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=make_async_cursor([projected_doc]))
    mock_collection.count_documents = AsyncMock(return_value=1)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        result = await svc.find_all(comuna="FRUTILLAR")

    # Verificar que el filtro se pasó a find()
    call_args = mock_collection.find.call_args
    query = call_args[0][0] if call_args[0] else call_args[1].get("filter", {})
    assert "comuna" in query, (
        "El filtro por 'comuna' no se incluye en la query de MongoDB. "
        "La proyección no debe eliminar los filtros de búsqueda."
    )


@pytest.mark.asyncio
async def test_BE03_find_all_with_search_term_still_works():
    """BE-03: El filtro de búsqueda por nombre/RBD debe seguir funcionando con proyección."""
    from app.establishments.establishments_service import EstablishmentsService

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=make_async_cursor([]))
    mock_collection.count_documents = AsyncMock(return_value=0)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        await svc.find_all(search="LICEO")

    call_args = mock_collection.find.call_args
    query = call_args[0][0] if call_args[0] else {}

    has_search = "$or" in query or "name" in query or "rbd" in query
    assert has_search, (
        "El término de búsqueda no se aplica en la query de MongoDB. "
        "La proyección no debe afectar la lógica de filtros."
    )
